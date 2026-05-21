"""
Patent Draft Composer service.

Spec: docs/patent_draft_composer.md

Assembles a patent specification from a project's claims plus supporting
context (element definitions, invention disclosure).

A real patent file has three parts, and that is exactly what this composer
produces, in this order:

  1. Description -- LLM-written full specification text (technical field,
                    background, summary, detailed description)
  2. Claims      -- deterministic; copied verbatim from the saved claims,
                    their wording is never altered
  3. Abstract    -- LLM-written concise summary of the invention

Output language is ENGLISH. The saved claims are in English, so a
consistent specification must be in English too.

The Abstract is generated AFTER the Description and is given the
Description text as its input, so it genuinely summarises what the
Description says instead of being written independently from the claims.

LLM calls go through ``llm_router.generate_json``. Each prompt asks for a
single JSON field ``content``; this reuses the router's JSON parsing/retry
and tolerates reasoning-model ``<think>`` blocks.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.generation import llm_router
from app.generation.llm_client import (
    LLMConnectionError,
    LLMParseError,
    LLMResponseError,
)
from app.models.patent import Patent
from app.services import (
    claim_service,
    element_service,
    invention_disclosure_service,
)

logger = logging.getLogger(__name__)


# Per-input char caps — keep prompts within a small/reasoning model's
# context window.
_CLAIMS_CAP = 4000
_CONTEXT_CAP = 2500
# The generated description fed back into the abstract prompt is capped so
# a very long description cannot blow the context window.
_DESCRIPTION_FEED_CAP = 10000

# Token budgets: the description is long-form prose, the abstract is short
# (a patent abstract is conventionally ~150 words or fewer).
_DESCRIPTION_MAX_TOKENS = 3500
_ABSTRACT_MAX_TOKENS = 600
_TEMPERATURE = 0.3

_PLACEHOLDER = (
    "[This section could not be generated — check the LLM connection and try again.]"
)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class _DraftContext:
    patent_name: str
    patent_owner: str
    domain: str
    invention_context: str
    claims_text: str       # substance fed to the LLM (textarea or saved claims)
    extra_context: str     # element definitions + disclosure, capped
    db_claims: list        # ORM Claim rows, for the deterministic Claims section


def _trim(value: str | None, cap: int) -> str:
    if not value:
        return ""
    return str(value).strip()[:cap]


def _format_claims(db_claims: list) -> str:
    """Render the saved claims as 'Claim N: ...' blocks, verbatim."""
    lines = []
    for c in db_claims:
        txt = (c.claim_text or "").strip()
        lines.append(
            f"Claim {c.claim_number}: {txt}" if txt
            else f"Claim {c.claim_number}: (no text entered)"
        )
    return "\n\n".join(lines)


def _build_context(
    db: Session,
    patent_id: int,
    claims_text_override: str | None,
) -> _DraftContext | None:
    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    if patent is None:
        return None

    db_claims = claim_service.list_claims(db, patent_id)

    # Primary substance: the textarea content the user reviewed in the
    # composer, or — when empty — the saved claim texts.
    claims_text = (claims_text_override or "").strip()
    if not claims_text:
        claims_text = _format_claims(db_claims)
    claims_text = _trim(claims_text, _CLAIMS_CAP)

    # Supporting context: element definitions + invention disclosure.
    context_parts: list[str] = []

    elements = element_service.list_elements(db, patent_id)
    defs = []
    for e in elements:
        ref = f" ({e.reference_number})" if getattr(e, "reference_number", None) else ""
        definition = getattr(e, "definition_text", None)
        defs.append(
            f"- {e.element_name}{ref}"
            + (f": {definition.strip()}" if definition and definition.strip() else "")
        )
    if defs:
        context_parts.append("Elements and their definitions:\n" + "\n".join(defs))

    idf = invention_disclosure_service.get_invention_disclosure(db, patent_id)
    if idf is not None:
        for label, val in (
            ("Known prior art and problems", getattr(idf, "prior_art_and_problems", "")),
            ("Closest prior patents", getattr(idf, "closest_prior_patents", "")),
            ("Novel features", getattr(idf, "novel_features", "")),
        ):
            if val and val.strip():
                context_parts.append(f"{label}: {val.strip()}")

    return _DraftContext(
        patent_name=patent.patent_name or "",
        patent_owner=patent.patent_owner or "",
        domain=patent.domain or "",
        invention_context=patent.invention_context or "",
        claims_text=claims_text,
        extra_context=_trim("\n\n".join(context_parts), _CONTEXT_CAP),
        db_claims=db_claims,
    )


# ---------------------------------------------------------------------------
# Reasoning-model output cleanup
# ---------------------------------------------------------------------------

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    """Drop reasoning-model <think> blocks if any leaked into the field.

    DeepSeek-R1 / other reasoning models emit a <think>...</think> block
    before the answer. The router's JSON parser usually isolates the answer
    object, but this is a cheap belt-and-braces pass in case reasoning text
    ended up inside the JSON value.
    """
    if not text:
        return ""
    low = text.lower()
    if "</think>" in low:
        text = text[low.rfind("</think>") + len("</think>"):]
    text = _THINK_BLOCK_RE.sub("", text)
    return re.sub(r"</?think>", "", text, flags=re.IGNORECASE).strip()


# ---------------------------------------------------------------------------
# Prompts (English output)
# ---------------------------------------------------------------------------

_DESCRIPTION_SYSTEM = (
    "You are an experienced patent attorney drafting the DESCRIPTION part "
    "of a patent specification in formal, technical English.\n\n"
    "You are given the invention's claims and supporting context. Write a "
    "complete, well-structured patent description that covers, in order:\n"
    "  - the technical field of the invention;\n"
    "  - the background art and the problems/limitations of existing "
    "solutions;\n"
    "  - a summary of the invention, its objective and the advantages it "
    "provides;\n"
    "  - a detailed description of the invention: every element, how the "
    "elements relate to one another, and how the invention works.\n\n"
    "RULES:\n"
    "- Rely ONLY on the information provided; do not invent facts, numbers "
    "or features.\n"
    "- Write in formal, objective, technical patent English. Output ENGLISH "
    "ONLY — no other language or alphabet.\n"
    "- Preserve every reference numeral exactly as given (e.g. \"rotating "
    "rod (4)\").\n"
    "- Use flowing paragraphs separated by blank lines. No bullet points, "
    "no markdown, no headings.\n"
    "- Do NOT reproduce the claim text verbatim; the claims are a separate "
    "part of the document.\n"
    '- Output ONLY this JSON object: {"content": "<the description text>"}\n'
    "- No explanation, markdown or code fences outside the JSON."
)

_ABSTRACT_SYSTEM = (
    "You are an experienced patent attorney writing the ABSTRACT of a "
    "patent specification in formal, technical English.\n\n"
    "You are given the full DESCRIPTION of the invention. Write a single "
    "concise paragraph that summarises the invention described.\n\n"
    "RULES:\n"
    "- The abstract MUST be consistent with the description and only "
    "summarise it; introduce nothing new.\n"
    "- One paragraph, about 100-150 words.\n"
    "- Formal, objective, technical patent English. Output ENGLISH ONLY.\n"
    "- No bullet points, no markdown, no headings.\n"
    '- Output ONLY this JSON object: {"content": "<the abstract text>"}\n'
    "- No explanation, markdown or code fences outside the JSON."
)


def _description_user_prompt(ctx: _DraftContext) -> str:
    parts = [f"INVENTION TITLE: {ctx.patent_name or '(not specified)'}"]
    if ctx.domain:
        parts.append(f"TECHNICAL DOMAIN: {ctx.domain}")
    if ctx.invention_context:
        parts.append(f"INVENTION CONTEXT: {ctx.invention_context}")
    parts.append(
        "\nCLAIMS AND ELEMENTS:\n" + (ctx.claims_text or "(no claims entered)")
    )
    if ctx.extra_context:
        parts.append("\nADDITIONAL CONTEXT:\n" + ctx.extra_context)
    return "\n".join(parts)


def _abstract_user_prompt(ctx: _DraftContext, description_body: str) -> str:
    return (
        f"INVENTION TITLE: {ctx.patent_name or '(not specified)'}\n\n"
        "FULL DESCRIPTION OF THE INVENTION:\n"
        + _trim(description_body, _DESCRIPTION_FEED_CAP)
    )


# ---------------------------------------------------------------------------
# LLM section call
# ---------------------------------------------------------------------------

def _call_section(
    system_prompt: str,
    user_prompt: str,
    max_new_tokens: int,
    attempts: int = 1,
) -> str:
    """Run one LLM call and return the 'content' string, with up to
    ``attempts`` tries. Raises the last error if every attempt fails."""
    last_exc: Exception = LLMResponseError("LLM call could not be made.")
    for i in range(attempts):
        try:
            parsed = llm_router.generate_json(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=_TEMPERATURE,
                max_new_tokens=max_new_tokens,
            )
            body = (
                parsed.get("content")
                or parsed.get("icerik")
                or parsed.get("text")
                or ""
            )
            if not isinstance(body, str):
                body = str(body)
            body = _strip_reasoning(body)
            if body:
                return body
            last_exc = LLMResponseError("LLM returned empty content.")
        except (LLMConnectionError, LLMResponseError, LLMParseError) as exc:
            last_exc = exc
            logger.warning(
                "[COMPOSER] section attempt %d/%d failed: %s",
                i + 1, attempts, exc,
            )
    raise last_exc


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_html(sections: list[dict]) -> str:
    """Build the draft HTML: <h4> per section title, <p> per paragraph."""
    out: list[str] = []
    for s in sections:
        out.append(f"<h4>{s['number']}. {html.escape(s['title'])}</h4>")
        body = s["body"] or ""
        if s["key"] == "claims":
            # One paragraph per claim line.
            paras = [ln.strip() for ln in body.splitlines() if ln.strip()]
        else:
            paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            if not paras and body.strip():
                paras = [body.strip()]
        for p in paras:
            out.append(f"<p>{html.escape(p)}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_draft(
    db: Session,
    patent_id: int,
    claims_text: str | None = None,
) -> dict | None:
    """Generate the 3-part patent draft (Description, Claims, Abstract).

    Returns:
        None                     -> patent not found
        {"error": "no_claims"}   -> nothing to draft from
        {patent_id, backend, sections, draft_html, warnings} -> success

    Raises:
        LLMConnectionError -> the LLM backend was unreachable while writing
                              the Description (fast feedback; nothing usable).
    """
    ctx = _build_context(db, patent_id, claims_text)
    if ctx is None:
        return None

    has_claims = bool(ctx.claims_text.strip()) or any(
        (c.claim_text or "").strip() for c in ctx.db_claims
    )
    if not has_claims:
        return {"error": "no_claims"}

    backend = llm_router.active_backend()
    logger.info(
        "[COMPOSER] patent=%s backend=%s — generating 3-part draft",
        patent_id, backend,
    )

    sections: list[dict] = []
    warnings: list[str] = []

    # --- 1. Description (LLM) ---------------------------------------------
    # Generated first; the Abstract is derived from it. An unreachable
    # backend here aborts fast — without a description there is nothing
    # usable to build the rest of the draft from.
    try:
        description_body = _call_section(
            _DESCRIPTION_SYSTEM,
            _description_user_prompt(ctx),
            _DESCRIPTION_MAX_TOKENS,
            attempts=1,
        )
    except LLMConnectionError:
        raise
    except (LLMResponseError, LLMParseError) as exc:
        logger.warning("[COMPOSER] description failed: %s", exc)
        description_body = ""
        warnings.append(
            f"Description: could not be generated ({type(exc).__name__})."
        )
    sections.append({
        "number": 1,
        "key": "description",
        "title": "Description",
        "body": description_body.strip() or _PLACEHOLDER,
        "generated": bool(description_body.strip()),
    })

    # --- 2. Claims (deterministic) ----------------------------------------
    # Copied verbatim from the saved claims — the wording is never altered.
    claims_body = _format_claims(ctx.db_claims)
    if not claims_body.strip() or "(no text entered)" in claims_body:
        # Saved claims have no text -> fall back to the composer textarea.
        if ctx.claims_text.strip():
            claims_body = ctx.claims_text
    sections.append({
        "number": 2,
        "key": "claims",
        "title": "Claims",
        "body": claims_body.strip() or "(no claims entered)",
        "generated": True,
    })

    # --- 3. Abstract (LLM, summarising the Description) -------------------
    abstract_body = ""
    if description_body.strip():
        try:
            abstract_body = _call_section(
                _ABSTRACT_SYSTEM,
                _abstract_user_prompt(ctx, description_body),
                _ABSTRACT_MAX_TOKENS,
                attempts=2,
            )
        except (LLMConnectionError, LLMResponseError, LLMParseError) as exc:
            logger.warning("[COMPOSER] abstract failed: %s", exc)
            warnings.append(
                f"Abstract: could not be generated ({type(exc).__name__})."
            )
    else:
        warnings.append(
            "Abstract: skipped because the Description was not generated."
        )
    sections.append({
        "number": 3,
        "key": "abstract",
        "title": "Abstract",
        "body": abstract_body.strip() or _PLACEHOLDER,
        "generated": bool(abstract_body.strip()),
    })

    draft_html = _render_html(sections)

    # Persist so the draft survives reload/restart (same field the editor uses).
    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    if patent is not None:
        patent.patent_draft = draft_html
        db.commit()

    return {
        "patent_id": patent_id,
        "backend": backend,
        "sections": sections,
        "draft_html": draft_html,
        "warnings": warnings,
    }
