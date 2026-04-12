"""
BBF/Report Pipeline route — automatic element extraction from BBF + Report documents.
"""

import threading
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

_pipeline_status = {"status": "idle", "error": None, "elements": [], "bbf_text": ""}


def _bg_run_pipeline(bbf_path, report_path):
    global _pipeline_status
    try:
        _pipeline_status = {"status": "running", "error": None, "elements": [], "bbf_text": ""}

        from app.bbf_report_unsur_pipeline import build_pipeline, infer_project_id, ensure_dir, DocumentLoader

        # Extract BBF text for later use by AI Suggest Definition
        bbf_text = ""
        try:
            loader = DocumentLoader(disable_ocr=True)
            doc = loader.load(Path(bbf_path))
            if doc and doc.text:
                bbf_text = doc.text
                print(f"[BBF] Extracted {len(bbf_text)} chars from BBF document")
        except Exception as ex:
            print(f"[BBF] DocumentLoader failed, trying plain read: {ex}")
            try:
                bbf_text = Path(bbf_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass

        class _Args:
            bbf = str(bbf_path)
            report = str(report_path)
            out_dir = str(Path(bbf_path).parent)
            project_id = ""
            llm_base_url = ""
            llm_api_key = ""
            llm_model = ""
            local_model = "heuristic"
            temperature = 0.1
            max_chars_per_chunk = 12000
            disable_ocr = True
            relation_cue_xlsx = ""
            pdf_low_density_threshold = 300
            dedup_threshold = 0.75
            element_resolve_threshold = 0.65
            rule_unsur_confidence = 0.55
            rule_bullet_confidence = 0.45
            max_component_words = 4
            max_relation_candidates = 200
            heuristic_relation_confidence = 0.35
            llm_default_confidence = 0.78
            disable_heuristic_relation_fallback = False
            debug = False
            extra_docs = []
            input_dir = None

        args = _Args()
        pipeline, _ = build_pipeline(args)
        out_dir = Path(bbf_path).parent
        ensure_dir(out_dir)
        pid = infer_project_id(Path(bbf_path), Path(report_path))
        payload = pipeline.run_from_files(
            bbf_path=Path(bbf_path),
            report_path=Path(report_path),
            out_dir=out_dir,
            project_id=pid,
        )

        def _to_en(text):
            if not text or not text.strip():
                return ""
            try:
                from deep_translator import GoogleTranslator
                return GoogleTranslator(source="tr", target="en").translate(text)
            except Exception:
                return text

        elements = []
        for e in payload.get("elements", []):
            name_en = e.get("name_en", "").strip()
            if not name_en:
                name_en = _to_en(e.get("name_tr", ""))
            definition_en = e.get("definition_en", "").strip()
            if not definition_en:
                definition_en = _to_en(e.get("definition_tr", ""))
            elements.append({
                "name_en": name_en,
                "definition_en": definition_en,
            })
        _pipeline_status = {"status": "done", "error": None, "elements": elements, "bbf_text": bbf_text}

        # Save bbf_text to file for persistence across restarts
        try:
            bbf_cache = Path(__file__).parent.parent.parent / "data" / ".cache" / "bbf_text.txt"
            bbf_cache.parent.mkdir(parents=True, exist_ok=True)
            bbf_cache.write_text(bbf_text, encoding="utf-8")
            print(f"[BBF] Saved bbf_text to cache ({len(bbf_text)} chars)")
        except Exception:
            pass
    except Exception as e:
        _pipeline_status = {"status": "error", "error": str(e), "elements": [], "bbf_text": ""}


@router.post("/extract-elements")
async def extract_elements(bbf: UploadFile = File(...), report: UploadFile = File(...)):
    tmp_dir = Path(tempfile.mkdtemp())
    bbf_path = tmp_dir / (bbf.filename or "bbf.docx")
    report_path = tmp_dir / (report.filename or "report.docx")

    with open(bbf_path, "wb") as f:
        f.write(await bbf.read())
    with open(report_path, "wb") as f:
        f.write(await report.read())

    _pipeline_status["status"] = "running"
    _pipeline_status["error"] = None
    _pipeline_status["elements"] = []
    threading.Thread(target=_bg_run_pipeline, args=(bbf_path, report_path), daemon=True).start()
    return {"ok": True, "status": "running"}


@router.get("/extract-elements-status")
def extract_elements_status():
    # If bbf_text is empty but cache exists, load from cache
    if not _pipeline_status.get("bbf_text") and _pipeline_status["status"] != "running":
        try:
            bbf_cache = Path(__file__).parent.parent.parent / "data" / ".cache" / "bbf_text.txt"
            if bbf_cache.exists():
                _pipeline_status["bbf_text"] = bbf_cache.read_text(encoding="utf-8")
        except Exception:
            pass
    return _pipeline_status
