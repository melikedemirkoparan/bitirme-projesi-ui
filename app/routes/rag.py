from __future__ import annotations
"""RAG + LLM routes for AI-assisted definition generation.

Frontend contract is preserved (same paths, same response shapes) so
the UI does not need changes here. Internally:

  - Excel upload -> app.ingestion.run_ingestion (ChromaDB)
  - Retrieval    -> app.retrieval.chroma_retrieval (2-stage)
  - LLM URL      -> app.generation.remote_llm_client (ngrok endpoint)

Set the remote LLM URL to use the ngrok/Colab backend; clear it
(empty string) to fall back to local Ollama via the router.
"""

import os
import threading

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.generation import llm_router, remote_llm_client
from app.ingestion.ingest_service import run_ingestion
from app.retrieval import chroma_retrieval

router = APIRouter(prefix="/api/rag", tags=["rag"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Tracks the most recent upload-driven ingestion so the UI can poll for
# progress and surface errors. Status is cleared on each new upload.
_loading: dict = {"status": "idle", "error": None, "count": 0}


class GenerateDefRequest(BaseModel):
    element_name: str
    context: str = ""
    bbf_text: str = ""
    top_k: int = 5
    domain: str | None = None


class RetrieveRequest(BaseModel):
    element_name: str
    context: str = ""
    top_k: int = 5
    domain: str | None = None


@router.get("/data-status")
def data_status():
    """Return whether Chroma collections exist and have data. The shape
    is unchanged from the FAISS version so the frontend's existing
    `ragStatus.loaded` check keeps working.

    `count` is the current Chroma collection size when no fresh upload
    is in progress, falling back to the in-flight upload's count while
    a load is running. This way the UI shows the persisted size after
    a server restart, not zero.
    """
    loaded = chroma_retrieval.is_data_loaded()
    in_progress = _loading["status"] == "loading"
    if in_progress:
        count = _loading["count"]
    else:
        count = chroma_retrieval.get_definition_count() if loaded else 0
    return {
        "loaded": loaded,
        "status": _loading["status"] if not loaded or _loading["status"] != "idle" else "done",
        "error": _loading["error"],
        "count": count,
    }


@router.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    """Accept an Excel file and rebuild Chroma collections from it.

    Validation matches the legacy flow: only .xlsx/.xls accepted, magic
    bytes checked. The actual ingestion runs in a background thread so
    the request returns immediately and the UI polls /data-status.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xls files accepted")

    file_bytes = await file.read()
    if len(file_bytes) < 4 or file_bytes[:2] != b"PK":
        raise HTTPException(status_code=400, detail="Invalid Excel file")

    save_path = os.path.join(DATA_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    _loading["status"] = "loading"
    _loading["error"] = None
    _loading["count"] = 0

    def bg_load():
        try:
            result = run_ingestion(file_bytes=file_bytes, filename=filename)
            if result.error:
                _loading["status"] = "error"
                _loading["error"] = result.error
                _loading["count"] = 0
                return
            # Sum up the docs across created collections so the UI shows
            # something meaningful. Definition collection is the primary.
            total = sum(
                r.doc_count for r in result.collections if r.status == "created"
            )
            _loading["status"] = "done"
            _loading["count"] = total
        except Exception as e:
            _loading["status"] = "error"
            _loading["error"] = str(e)

    threading.Thread(target=bg_load, daemon=True).start()
    return {"ok": True, "filename": filename}


@router.post("/retrieve")
def retrieve(data: RetrieveRequest):
    """Direct retrieval endpoint (used by debugging/inspection UIs).

    Accepts an optional `domain` to engage the 2-stage filter; without
    it, falls back to a single-stage element-name semantic search.
    """
    if not chroma_retrieval.is_data_loaded():
        raise HTTPException(status_code=400, detail="Data not loaded yet")
    results = chroma_retrieval.retrieve(
        element_name=data.element_name,
        domain=(data.domain or None),
        top_k=data.top_k,
    )
    return {"results": results}


@router.post("/generate-definition")
def generate_definition(data: GenerateDefRequest):
    """Standalone (no patent_id) definition generation entry point used
    by the legacy 'try a definition' UI. It does not run the 3-stage
    pipeline — that is the per-element /patents/.../generate-definition
    route. Here we just return the retrieval hits and a basic fragment
    pulled from the top hit, mirroring the legacy response shape.
    """
    if not chroma_retrieval.is_data_loaded():
        raise HTTPException(status_code=400, detail="Data not loaded yet")

    retrieved = chroma_retrieval.retrieve(
        element_name=data.element_name,
        domain=(data.domain or None),
        top_k=data.top_k,
    )

    rag_fragment = ""
    if retrieved:
        defn = (retrieved[0].get("definition_en") or "").strip()
        rag_fragment = defn[:300]

    return {
        "element": data.element_name,
        "rag_fragment": rag_fragment,
        "bbf_fragment": "",
        "final_definition": rag_fragment,
        "retrieved_examples": retrieved,
    }


@router.get("/elements")
def list_elements():
    """List distinct (en, tr) element names indexed in Chroma. Used by
    the 'pick an element to test retrieval' dropdown in the debug UI."""
    if not chroma_retrieval.is_data_loaded():
        return []

    from app.ingestion.chroma_client import get_chroma_client
    try:
        client = get_chroma_client()
        coll = client.get_collection("patent_definition_en")
        # Pull all metadata; the corpus is small enough that this is fine.
        # If the corpus grows past ~50k rows, switch to a paginated fetch.
        result = coll.get(include=["metadatas"])
        metadatas = result.get("metadatas") or []
        seen: set[tuple[str, str]] = set()
        out: list[dict] = []
        for m in metadatas:
            if not m:
                continue
            en = (m.get("element_name_en") or "").strip()
            tr = (m.get("element_name_tr") or "").strip()
            key = (en, tr)
            if not en or key in seen:
                continue
            seen.add(key)
            out.append({"element_name_en": en, "element_name_tr": tr})
        return out
    except Exception:
        return []


class LLMUrlRequest(BaseModel):
    url: str


@router.post("/set-llm-url")
def set_llm_url(data: LLMUrlRequest):
    """Set (or clear, by passing "") the remote LLM URL. With a URL,
    the router sends LLM calls to ngrok/Colab; without one, it falls
    back to local Ollama."""
    remote_llm_client.set_remote_llm_url(data.url)
    return {"ok": True, "url": data.url, "backend": llm_router.active_backend()}


@router.get("/llm-status")
def llm_status():
    """Report which LLM backend would handle the next call."""
    url = remote_llm_client.get_remote_llm_url()
    return {
        "connected": bool(url),
        "url": url,
        "backend": llm_router.active_backend(),
    }
