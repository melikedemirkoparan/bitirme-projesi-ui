"""
Patent Draft Composer service.

Spec: docs/patent_draft_composer.md

Assembles a full Turkish patent specification (tarifname) from a project's
claims plus supporting context (element definitions, invention disclosure).

The draft is produced section by section: each section is one LLM call with
a focused prompt. This keeps every request small enough for small offline /
reasoning models and lets a single weak section fail without losing the
whole draft.

Sections (TÜRKPATENT tarifname order):
  1. Özet
  2. Teknik Alan
  3. Tekniğin Bilinen Durumu
  4. Buluşun Amacı
  5. Buluşun Özeti
  6. Buluşun Detaylı Açıklaması
  7. İstemler            -- deterministic, copied from the saved claims

LLM calls go through ``llm_router.generate_json`` so the remote Colab LLM
or the local Ollama instance is chosen at call time. Each section prompt
asks for a single JSON field ``icerik``; this reuses the router's existing
JSON parsing/retry and tolerates reasoning-model ``<think>`` blocks.
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


# Per-input char caps — keep each section prompt small enough to fit a
# small offline model's context window (and leave a reasoning model room
# for its <think> block).
_CLAIMS_CAP = 3000
_CONTEXT_CAP = 1800

_SECTION_MAX_TOKENS = 2500
_SECTION_TEMPERATURE = 0.35

_PLACEHOLDER = "[Bu bölüm üretilemedi — LLM bağlantısını kontrol edip tekrar deneyin.]"


# ---------------------------------------------------------------------------
# Section catalogue
# ---------------------------------------------------------------------------

@dataclass
class _Section:
    key: str
    title: str
    instruction: str


# LLM-generated sections, in output order. İstemler is appended separately
# (deterministic — copied straight from the saved claims).
_LLM_SECTIONS: list[_Section] = [
    _Section(
        "ozet", "Özet",
        "Buluşun ne olduğunu, çözdüğü teknik problemi ve sağladığı temel "
        "faydayı tek bir paragrafta özetle. Yaklaşık 80-150 kelime.",
    ),
    _Section(
        "teknik_alan", "Teknik Alan",
        "Buluşun ilgili olduğu teknik/teknoloji alanını 2-4 cümleyle açıkla.",
    ),
    _Section(
        "teknigin_bilinen_durumu", "Tekniğin Bilinen Durumu",
        "Mevcut teknikte bilinen çözümleri, bunların eksiklik ve "
        "dezavantajlarını, ve buluşun gidermeyi hedeflediği problemleri "
        "açıkla. 1-2 paragraf.",
    ),
    _Section(
        "bulusun_amaci", "Buluşun Amacı",
        "Buluşun amaçlarını ve hedeflerini, tekniğin bilinen durumundaki "
        "problemleri nasıl çözmeyi amaçladığını belirterek açıkla. 1 paragraf.",
    ),
    _Section(
        "bulusun_ozeti", "Buluşun Özeti",
        "İstemlerde tanımlanan ana unsurlara dayanarak buluşun temel teknik "
        "özelliklerini özetle. 1-2 paragraf.",
    ),
    _Section(
        "bulusun_detayli_aciklamasi", "Buluşun Detaylı Açıklaması",
        "Buluşu; istemlerdeki tüm unsurları, bunların birbirleriyle "
        "ilişkisini ve çalışma şeklini ayrıntılı biçimde açıkla. İstemlerde "
        "geçen referans numaralarını koru. 2-4 paragraf.",
    ),
]


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
    db_claims: list        # ORM Claim rows, for the deterministic İstemler section


def _trim(value: str | None, cap: int) -> str:
    if not value:
        return ""
    return str(value).strip()[:cap]


def _format_claims(db_claims: list) -> str:
    """Render the saved claims as 'İstem N: ...' blocks."""
    lines = []
    for c in db_claims:
        txt = (c.claim_text or "").strip()
        lines.append(
            f"İstem {c.claim_number}: {txt}" if txt
            else f"İstem {c.claim_number}: (metin girilmemiş)"
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
        context_parts.append("Unsurlar ve tanımları:\n" + "\n".join(defs))

    idf = invention_disclosure_service.get_invention_disclosure(db, patent_id)
    if idf is not None:
        for label, val in (
            ("Bilinen teknik ve problemler", getattr(idf, "prior_art_and_problems", "")),
            ("En yakın önceki patentler", getattr(idf, "closest_prior_patents", "")),
            ("Yenilikçi özellikler", getattr(idf, "novel_features", "")),
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
# Prompting
# ---------------------------------------------------------------------------

_SYSTEM_BASE = (
    "Sen deneyimli bir Türk patent vekilisin. TÜRKPATENT (Türk Patent ve "
    "Marka Kurumu) formatında bir patent başvuru tarifnamesi hazırlıyorsun.\n\n"
    "Sana buluşa ait istemler ve destekleyici bağlam bilgisi verilecek. "
    'Görevin yalnızca tarifnamenin "{title}" bölümünü Türkçe yazmaktır.\n\n'
    "KURALLAR:\n"
    "- Yalnızca verilen bilgilere dayan; bilgi, sayı veya özellik uydurma.\n"
    "- Resmi, teknik ve nesnel bir patent dili kullan.\n"
    "- Metnin tamamını YALNIZCA Türkçe yaz; başka hiçbir dil veya alfabe kullanma.\n"
    "- Bölüm başlığını tekrar yazma; sadece bölümün metnini üret.\n"
    "- Madde imleri kullanma; akıcı paragraflar yaz.\n"
    '- Çıktıyı SADECE şu JSON nesnesi olarak ver: {{"icerik": "..."}}\n'
    "- JSON dışında açıklama, markdown veya kod bloğu yazma.\n\n"
    "BÖLÜM TALİMATI ({title}):\n{instruction}"
)


def _build_user_prompt(ctx: _DraftContext) -> str:
    parts = [f"BULUŞ BAŞLIĞI: {ctx.patent_name or '(belirtilmemiş)'}"]
    if ctx.domain:
        parts.append(f"TEKNİK ALAN: {ctx.domain}")
    if ctx.invention_context:
        parts.append(f"BULUŞ BAĞLAMI: {ctx.invention_context}")
    parts.append("\nİSTEMLER VE UNSURLAR:\n" + (ctx.claims_text or "(istem girilmemiş)"))
    if ctx.extra_context:
        parts.append("\nEK BAĞLAM:\n" + ctx.extra_context)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Reasoning-model output cleanup
# ---------------------------------------------------------------------------

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    """Drop reasoning-model <think> blocks if any leaked into the field.

    DeepSeek-R1 / other reasoning models emit a <think>...</think> block
    before the answer. The router's JSON parser usually isolates the answer
    object on its own, but this is a cheap belt-and-braces pass in case
    reasoning text ended up inside the JSON value.
    """
    if not text:
        return ""
    low = text.lower()
    if "</think>" in low:
        text = text[low.rfind("</think>") + len("</think>"):]
    text = _THINK_BLOCK_RE.sub("", text)
    return re.sub(r"</?think>", "", text, flags=re.IGNORECASE).strip()


def _generate_section(section: _Section, user_prompt: str, attempts: int = 1) -> str:
    """Run the LLM call for one section, with up to ``attempts`` tries.

    A draft is many sequential calls, so a transient backend blip (an
    ngrok hiccup, a momentary timeout) mid-run should not lose a whole
    section — non-first sections are given a retry. Raises the last error
    if every attempt fails.
    """
    system_prompt = _SYSTEM_BASE.format(
        title=section.title, instruction=section.instruction
    )
    last_exc: Exception = LLMResponseError("LLM çağrısı yapılamadı.")
    for i in range(attempts):
        try:
            parsed = llm_router.generate_json(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=_SECTION_TEMPERATURE,
                max_new_tokens=_SECTION_MAX_TOKENS,
            )
            body = parsed.get("icerik") or parsed.get("content") or parsed.get("text") or ""
            if not isinstance(body, str):
                body = str(body)
            body = _strip_reasoning(body)
            if body:
                return body
            last_exc = LLMResponseError("LLM boş içerik döndürdü.")
        except (LLMConnectionError, LLMResponseError, LLMParseError) as exc:
            last_exc = exc
            logger.warning(
                "[COMPOSER] section '%s' attempt %d/%d failed: %s",
                section.key, i + 1, attempts, exc,
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
        if s["key"] == "istemler":
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
    """Generate the full patent draft for a project.

    Returns:
        None                       -> patent not found
        {"error": "no_claims"}     -> nothing to draft from
        {patent_id, backend, sections, draft_html, warnings} -> success

    Raises:
        LLMConnectionError -> the LLM backend was unreachable for the very
                              first section (fast feedback; nothing usable).
    """
    ctx = _build_context(db, patent_id, claims_text)
    if ctx is None:
        return None

    has_claims = bool(ctx.claims_text.strip()) or any(
        (c.claim_text or "").strip() for c in ctx.db_claims
    )
    if not has_claims:
        return {"error": "no_claims"}

    user_prompt = _build_user_prompt(ctx)
    backend = llm_router.active_backend()
    logger.info("[COMPOSER] patent=%s backend=%s — generating draft", patent_id, backend)

    sections: list[dict] = []
    warnings: list[str] = []

    for idx, spec in enumerate(_LLM_SECTIONS):
        number = len(sections) + 1
        # First section: a single try so an unreachable backend fails fast.
        # Later sections: one retry to ride out transient mid-run blips.
        attempts = 1 if idx == 0 else 2
        try:
            body = _generate_section(spec, user_prompt, attempts=attempts)
        except LLMConnectionError:
            # Unreachable on the first section -> abort fast, nothing usable.
            if idx == 0:
                raise
            body = ""
            warnings.append(f"{spec.title}: LLM yanıt vermedi.")
        except (LLMResponseError, LLMParseError) as exc:
            logger.warning("[COMPOSER] section '%s' failed: %s", spec.key, exc)
            body = ""
            warnings.append(f"{spec.title}: üretilemedi ({type(exc).__name__}).")

        generated = bool(body.strip())
        sections.append({
            "number": number,
            "key": spec.key,
            "title": spec.title,
            "body": body.strip() if generated else _PLACEHOLDER,
            "generated": generated,
        })

    # İstemler — deterministic, straight from the saved claims.
    istemler_body = _format_claims(ctx.db_claims)
    if not istemler_body.strip() or "(metin girilmemiş)" in istemler_body:
        # Saved claims have no text -> fall back to the composer textarea.
        if ctx.claims_text.strip():
            istemler_body = ctx.claims_text
    sections.append({
        "number": len(sections) + 1,
        "key": "istemler",
        "title": "İstemler",
        "body": istemler_body.strip() or "(İstem girilmemiş)",
        "generated": True,
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
