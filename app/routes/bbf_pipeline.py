"""
BBF/Report Pipeline route — automatic element extraction from BBF + Report documents.

Accepts either freshly uploaded files (multipart) or, when no files are sent,
falls back to the latest BBF and Research Report documents already stored on
the patent. This lets the Extract modal work after a close/reopen without
re-uploading.
"""

import shutil
import threading
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.services import (
    invention_disclosure_service,
    research_report_service,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

_pipeline_status = {
    "status": "idle",
    "error": None,
    "elements": [],
    "bbf_text": "",
    "patent_id": None,
    "stage": "",
}


# ── Element-name quality filter ─────────────────────────────────────────
# Heuristic upstream catches Turkish noun phrases well but, after we
# translate to English, lets through sentence fragments, leading
# articles, and form-template noise. These rules drop anything that
# does not look like a short technical noun phrase.

# Articles/prepositions/demonstratives — when they lead a phrase, the
# real noun is usually right after them, so we strip the article and
# re-validate ("the gear assembly" → "gear assembly").
_ELEMENT_LEADING_ARTICLES = {
    "a", "an", "the", "this", "that", "these", "those",
    "in", "on", "at", "of", "for", "with", "to", "from", "by", "as",
    "and", "or", "but", "if", "when", "where", "while", "during",
    "into", "onto", "upon", "about", "between", "through", "across",
}

# Imperative verbs / sentence-starting commands — when these lead a
# phrase, the entire phrase is a command from form template text, not
# an invention element. We drop instead of rescuing because the
# remainder is typically just an object noun without enough context
# ("Attach photographs" → just "photographs" carries no invention
# meaning).
_ELEMENT_LEADING_VERBS = {
    "attach", "provide", "include", "comprise", "comprises", "contain",
    "contains", "describe", "describes", "use", "uses", "ensure",
    "ensures", "specify", "specifies", "show", "shows", "list", "lists",
    "submit", "fill", "indicate", "explain", "enter", "input", "select",
    "complete", "sign", "review", "check", "ensure", "verify",
}

# Combined view used wherever we just need to ask "is this a stopword?"
_ELEMENT_LEADING_STOPWORDS = _ELEMENT_LEADING_ARTICLES | _ELEMENT_LEADING_VERBS

_ELEMENT_BLOCKED_PHRASES = {
    # Form / meta / boilerplate phrases pulled out of the BBF template
    # and patent process documents — never genuine invention elements.
    "invention disclosure", "invention disclosure form",
    "intellectual property", "intellectual property board",
    "patent application", "patent claim", "patent claims",
    "research report", "executive summary", "abstract", "drawing",
    "drawings", "figure", "figures", "claim", "claims",
    "technical field", "background", "summary",
    "embodiment", "embodiments", "preferred embodiment",
    "person skilled", "prior art", "novelty", "inventive step",
    # Abstract geometric / coordinate references — these describe a
    # frame of reference, not an invention component. Patents mention
    # them constantly in motion/orientation prose ("moves in the
    # vertical plane"), but they are never themselves elements.
    "single plane", "vertical plane", "horizontal plane",
    "this plane", "the plane", "a plane", "one plane",
    "vertical axis", "horizontal axis", "longitudinal axis",
    "central axis", "main axis", "this axis", "the axis",
    "first direction", "second direction", "same direction",
    "first position", "second position", "third position",
    "first side", "second side", "same side", "the side",
    "upper part", "lower part", "front part", "rear part",
    "first end", "second end", "same plane",
}

# Stopwords that, when found *between* content words, mean we are
# looking at a sentence fragment rather than a noun phrase. ("shaft of
# the system", "wing in the body", "rod for the assembly".)
# Distinct from leading articles — there we strip; here we drop.
_ELEMENT_INTERNAL_STOPWORDS = {
    "of", "the", "a", "an", "in", "on", "at", "for", "with", "to",
    "from", "by", "as", "this", "that", "these", "those",
    "and", "or", "but", "into", "onto", "between", "through",
}

# One-word terms that are too generic to be useful as a patent element
# on their own. Patents are full of "systems" and "devices" — without
# a modifier they carry no specificity.
_ELEMENT_GENERIC_SINGLES = {
    "system", "device", "apparatus", "mechanism", "assembly",
    "part", "piece", "element", "component", "section", "structure",
    "plane", "axis", "side", "area", "region", "zone",
    "direction", "position", "place", "location",
    "end", "edge", "surface", "face", "point",
    "thing", "item", "unit", "object",
}


_MAX_ELEMENT_WORDS = 4


def _clean_element_name(name: str) -> str | None:
    """Return a normalized element name, or None if it should be dropped.

    The aim is to keep real noun phrases of any length up to 4 words
    ("Sway Brace Shaft", "Release Rack Apparatus") while dropping
    sentence fragments. We use **structural** rules — not just word
    count — so legitimate technical compounds survive even when long.

    Rules (in order):
      1. Trim and collapse whitespace, strip outer punctuation.
      2. Reject if too short (<3 chars) or longer than the cap.
      3. Reject if the lower-cased phrase is in the blocked-phrase set
         (form/meta artefacts and abstract geometric references).
      4. If the first word is an imperative verb → drop entirely
         (it is a command, not an element name).
      5. If the first word is an article/preposition → strip it and
         re-run the cleaner on what remains.
      6. Reject if any *internal* word (positions 2..N) is a stopword
         (`of/the/in/this/...`). That signals a prose fragment like
         "shaft of the system", not a compound noun.
      7. Reject if the final phrase is a single generic word
         (`apparatus`, `plane`, `system`, ...). Single nouns must be
         specific to the invention to be useful.
    """
    if not name:
        return None
    cleaned = name.strip().strip(".,;:!?-—")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) < 3:
        return None

    words = cleaned.split()
    if len(words) > _MAX_ELEMENT_WORDS:
        # Genuine element names rarely need more than 4 words. Five-plus
        # word output is almost always a sentence fragment that slipped
        # through the upstream extractor — drop instead of trim, since
        # truncating prose tends to produce nonsense.
        return None

    lower = cleaned.lower()
    if lower in _ELEMENT_BLOCKED_PHRASES:
        return None

    first = words[0].lower().rstrip(".,;:")

    if first in _ELEMENT_LEADING_VERBS:
        # Imperative verb at the head — entire phrase is a command,
        # not an element. Do NOT rescue.
        return None

    if first in _ELEMENT_LEADING_ARTICLES:
        # Article/preposition — strip and re-validate the rest.
        if len(words) >= 2:
            return _clean_element_name(" ".join(words[1:]))
        return None

    # Internal stopword check — content noun phrases ("Sway Brace
    # Shaft") have no stopwords between their content words; sentence
    # fragments ("rod of the system", "wing in the assembly") do.
    for w in words[1:]:
        if w.lower().rstrip(".,;:") in _ELEMENT_INTERNAL_STOPWORDS:
            return None

    # Single-word generic-noun guard — patents are full of "systems",
    # "devices", "apparatuses". On their own they carry no specificity.
    if len(words) == 1 and lower in _ELEMENT_GENERIC_SINGLES:
        return None

    return cleaned


def _set_stage(stage: str) -> None:
    """Update the human-readable progress label that the UI polls. The
    rest of the status fields are left intact."""
    _pipeline_status["stage"] = stage
    print(f"[BBF] {stage}")


def _bg_run_pipeline(bbf_path, report_path, patent_id: int | None = None):
    global _pipeline_status
    try:
        _pipeline_status = {
            "status": "running",
            "error": None,
            "elements": [],
            "bbf_text": "",
            "patent_id": patent_id,
            "stage": "Loading documents…",
        }

        from app.bbf_report_unsur_pipeline import (
            build_pipeline,
            infer_project_id,
            ensure_dir,
            DocumentLoader,
            _translate_tr_to_en_batch,
        )

        # Extract BBF text for later use by AI Suggest Definition
        _set_stage("Reading BBF document…")
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
        _set_stage("Building extraction pipeline…")
        pipeline, _ = build_pipeline(args)
        out_dir = Path(bbf_path).parent
        ensure_dir(out_dir)
        pid = infer_project_id(Path(bbf_path), Path(report_path))
        _set_stage("Extracting elements + translating…")
        payload = pipeline.run_from_files(
            bbf_path=Path(bbf_path),
            report_path=Path(report_path),
            out_dir=out_dir,
            project_id=pid,
        )

        # Most elements already come back fully translated by the
        # pipeline's batch step. Backfill anything still missing in one
        # additional batched HTTP request.
        raw = payload.get("elements", [])
        missing_names_idx: list[int] = []
        missing_defs_idx: list[int] = []
        names_tr: list[str] = []
        defs_tr: list[str] = []
        for i, e in enumerate(raw):
            if not (e.get("name_en", "") or "").strip():
                missing_names_idx.append(i)
                names_tr.append(e.get("name_tr", "") or "")
            if not (e.get("definition_en", "") or "").strip():
                missing_defs_idx.append(i)
                defs_tr.append(e.get("definition_tr", "") or "")

        if names_tr or defs_tr:
            _set_stage("Backfilling translations…")
            translated = _translate_tr_to_en_batch(names_tr + defs_tr)
            n_split = len(names_tr)
            translated_names = translated[:n_split]
            translated_defs = translated[n_split:]
            for idx, val in zip(missing_names_idx, translated_names):
                raw[idx]["name_en"] = val
            for idx, val in zip(missing_defs_idx, translated_defs):
                raw[idx]["definition_en"] = val

        # Quality filter on the English side — the heuristic upstream
        # uses Turkish-tuned regexes and lets through sentence fragments
        # ("the vertical plane", "Attach photographs", "contain"), form
        # template artefacts ("invention disclosure", "intellectual
        # property board"), and bare verbs. We want short nominal
        # element names, so we drop everything that smells like prose,
        # meta, or commands.
        elements = []
        for e in raw:
            name = (e.get("name_en", "") or "").strip()
            definition = (e.get("definition_en", "") or "").strip()
            cleaned = _clean_element_name(name)
            if cleaned is None:
                continue
            elements.append({"name_en": cleaned, "definition_en": definition})
        # Dedup on the cleaned name (case-insensitive) — extraction
        # often produces the same noun phrase twice.
        seen: set[str] = set()
        deduped = []
        for el in elements:
            key = el["name_en"].lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(el)
        elements = deduped
        _pipeline_status = {
            "status": "done",
            "error": None,
            "elements": elements,
            "bbf_text": bbf_text,
            "patent_id": patent_id,
            "stage": f"Done — {len(elements)} elements",
        }

        # Persist extracted bbf_text on the patent's invention_disclosure
        # so the Settings modal and AI Suggest Definition see it after a
        # restart. We require patent_id; without it (legacy multipart
        # call), there is no patent to write to and the value lives only
        # in the in-memory _pipeline_status until the next request.
        if patent_id is not None and bbf_text:
            try:
                from app.services import invention_disclosure_service
                invention_disclosure_service.set_bbf_text(
                    SessionLocal(), patent_id, bbf_text
                )
                print(f"[BBF] Persisted bbf_text on patent {patent_id} ({len(bbf_text)} chars)")
            except Exception as ex:
                print(f"[BBF] Could not persist bbf_text: {ex}")
    except Exception as e:
        _pipeline_status = {
            "status": "error",
            "error": str(e),
            "elements": [],
            "bbf_text": "",
            "patent_id": patent_id,
            "stage": f"Error: {e}",
        }


@router.post("/extract-elements")
async def extract_elements(
    bbf: UploadFile | None = File(default=None),
    report: UploadFile | None = File(default=None),
    patent_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Run the extraction pipeline.

    The BBF and Report files may be supplied either as fresh multipart
    uploads (legacy behavior) or implicitly from the patent's stored
    documents when only `patent_id` is given. When a fresh upload is
    provided alongside `patent_id`, that fresh file is used and the patent
    is left untouched here — auto-uploading is handled by the dedicated
    document routes.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    bbf_path: Path | None = None
    report_path: Path | None = None

    if bbf is not None:
        bbf_path = tmp_dir / (bbf.filename or "bbf.docx")
        with open(bbf_path, "wb") as f:
            f.write(await bbf.read())
    elif patent_id is not None:
        stored = invention_disclosure_service.get_latest_document(db, patent_id)
        if stored is None:
            raise HTTPException(
                status_code=400,
                detail="No BBF document available for this patent.",
            )
        _, src = stored
        bbf_path = tmp_dir / src.name
        shutil.copy(src, bbf_path)

    if report is not None:
        report_path = tmp_dir / (report.filename or "report.docx")
        with open(report_path, "wb") as f:
            f.write(await report.read())
    elif patent_id is not None:
        stored = research_report_service.get_latest_document(db, patent_id)
        if stored is None:
            raise HTTPException(
                status_code=400,
                detail="No Research Report document available for this patent.",
            )
        _, src = stored
        report_path = tmp_dir / src.name
        shutil.copy(src, report_path)

    if bbf_path is None or report_path is None:
        raise HTTPException(
            status_code=400,
            detail="BBF and Report files are required (or patent_id with stored documents).",
        )

    _pipeline_status["status"] = "running"
    _pipeline_status["error"] = None
    _pipeline_status["elements"] = []
    _pipeline_status["patent_id"] = patent_id
    threading.Thread(
        target=_bg_run_pipeline,
        args=(bbf_path, report_path, patent_id),
        daemon=True,
    ).start()
    return {"ok": True, "status": "running"}


@router.get("/extract-elements-status")
def extract_elements_status(
    patent_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Return the latest pipeline state.

    When `patent_id` is supplied and the in-memory `bbf_text` is empty
    (server restarted, modal reopened without re-extraction, etc.) we
    fall back to the bbf_text persisted on that patent's
    invention_disclosure row.
    """
    status = dict(_pipeline_status)
    if patent_id is not None and not status.get("bbf_text"):
        idf = invention_disclosure_service.get_invention_disclosure(db, patent_id)
        if idf and idf.bbf_text:
            status["bbf_text"] = idf.bbf_text
    return status
