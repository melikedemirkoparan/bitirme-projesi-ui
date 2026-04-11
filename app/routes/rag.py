"""
RAG + LLM routes for AI-assisted definition generation.
Uses the rag_engine module from the original patent-drafting-tool.
"""

import os
import threading

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import rag_engine

router = APIRouter(prefix="/api/rag", tags=["rag"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

_loading = {"status": "idle", "error": None, "count": 0}


def _auto_load_on_startup():
    """Try to auto-load RAG data from cached Excel files on startup."""
    if rag_engine.is_data_loaded():
        return
    for fname in ["TUSAŞ_Tarifname_Translated.xlsx", "all_definitions_translated.xlsx"]:
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            try:
                count = rag_engine.load_data(fpath)
                _loading["status"] = "done"
                _loading["count"] = count
                print(f"[RAG] Auto-loaded {count} docs from {fname}")
                return
            except Exception as e:
                print(f"[RAG] Auto-load failed for {fname}: {e}")


# Auto-load in background thread so server starts fast
threading.Thread(target=_auto_load_on_startup, daemon=True).start()


class GenerateDefRequest(BaseModel):
    element_name: str
    context: str = ""
    bbf_text: str = ""
    top_k: int = 5


class RetrieveRequest(BaseModel):
    element_name: str
    context: str = ""
    top_k: int = 5


@router.get("/data-status")
def data_status():
    return {
        "loaded": rag_engine.is_data_loaded(),
        "status": _loading["status"],
        "error": _loading["error"],
        "count": _loading["count"],
    }


@router.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
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

    def bg_load():
        try:
            count = rag_engine.load_data(save_path)
            _loading["status"] = "done"
            _loading["count"] = count
        except Exception as e:
            _loading["status"] = "error"
            _loading["error"] = str(e)

    threading.Thread(target=bg_load, daemon=True).start()
    return {"ok": True, "filename": filename}


@router.post("/retrieve")
def retrieve(data: RetrieveRequest):
    if not rag_engine.is_data_loaded():
        raise HTTPException(status_code=400, detail="Data not loaded yet")
    results = rag_engine.retrieve(data.element_name, data.context, data.top_k)
    return {"results": results}


@router.post("/generate-definition")
def generate_definition(data: GenerateDefRequest):
    if not rag_engine.is_data_loaded():
        raise HTTPException(status_code=400, detail="Data not loaded yet")
    result = rag_engine.generate_definition(
        data.element_name, data.context, data.bbf_text, data.top_k
    )
    return result


@router.get("/elements")
def list_elements():
    return rag_engine.get_elements_list()


class LLMUrlRequest(BaseModel):
    url: str


@router.post("/set-llm-url")
def set_llm_url(data: LLMUrlRequest):
    rag_engine.set_remote_llm_url(data.url)
    return {"ok": True, "url": data.url}


@router.get("/llm-status")
def llm_status():
    url = rag_engine.get_remote_llm_url()
    return {"connected": bool(url), "url": url}
