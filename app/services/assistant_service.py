from __future__ import annotations

import logging
import re
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.models.patent import Patent
from app.schemas.assistant import (
    AssistantRequest,
    AssistantResponse,
    ClaimStructure,
    DependentCandidate,
    EvidenceCard,
    IndependentCandidate,
)
from app.generation import llm_router
from app.generation.llm_client import LLMConnectionError, LLMParseError, LLMResponseError
from app.services import faithfulness

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ask(db: Session, patent_id: int, req: AssistantRequest) -> AssistantResponse:
    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    if not patent:
        return _insufficient("P1", "Patent not found.", "Patent not found.")

    idf = patent.invention_disclosure
    rr = patent.research_report

    if req.pattern_id == "P1":
        return _run_p1(patent_id, idf, rr)
    if req.pattern_id == "P2":
        return _run_p2(patent_id, idf, rr)
    if req.pattern_id == "P3":
        return _run_p3(patent_id, rr, req.term)

    return _insufficient(req.pattern_id, "Unknown pattern.", "Unknown pattern.")


# ---------------------------------------------------------------------------
# P1 — Core Problem (single-pass)
# ---------------------------------------------------------------------------

_P1_SYSTEM = "You are a patent drafting assistant. Output valid JSON only. No markdown, no explanation."

_P1_USER = """In a patent, the core technical problem is the specific limitation or shortcoming in existing solutions (prior art) that the invention is designed to fix. The proposed solution is the technical mechanism or approach the invention introduces to overcome that problem.

Your task: read the source text below and identify these two things.

[TEXT]
{docs}
[/TEXT]

Look for sentences that describe:
- What is wrong with or missing from existing systems (this is the core problem).
- What the invention does differently, or what it introduces, to fix that (this is the proposed solution).

Then output this JSON:
{{
  "support_level": "explicit" or "insufficient",
  "answer": "2-3 sentences stating the core problem and the proposed solution. Empty string if insufficient.",
  "insufficient_message": "explain what is missing — problem, solution, or both. Empty string if support_level is explicit.",
  "evidence": [
    {{
      "field": "prior_art_and_problems" or "executive_summary",
      "excerpt": "copy one sentence exactly as it appears in the text — character by character, no changes, no paraphrase"
    }}
  ]
}}

Important:
- Use ONLY the text between [TEXT] and [/TEXT]. Do not use outside knowledge.
- Set support_level to "explicit" only if both the problem AND the solution are directly stated in the text.
- Set support_level to "insufficient" if either is missing, vague, or only implied.
- field must be exactly "prior_art_and_problems" or "executive_summary" — use the section label shown in the text.
- excerpt must be an exact copy of a sentence from the text. Do not summarize or paraphrase."""


def _run_p1(patent_id: int, idf, rr) -> AssistantResponse:
    parts = []

    if idf and idf.prior_art_and_problems:
        parts.append(f"--- prior_art_and_problems ---\n{idf.prior_art_and_problems}")

    if rr and rr.executive_summary:
        parts.append(f"--- executive_summary ---\n{rr.executive_summary}")

    if not parts:
        return _insufficient("P1", "Core Problem",
                             "No relevant documents are available. "
                             "Please add an Invention Disclosure or Research Report in Project Inputs.")

    docs_text = "\n\n".join(parts)
    raw, err = _call_model(_P1_SYSTEM, _P1_USER.format(docs=docs_text))
    if raw is None:
        return _insufficient("P1", "Core Problem", err)

    support = raw.get("support_level", "insufficient")
    answer = raw.get("answer", "")
    insuf_msg = raw.get("insufficient_message", "")
    evidence_raw = raw.get("evidence", [])

    evidence = _build_evidence_cards("P1", evidence_raw, idf, rr)

    # Faithfulness + Coverage: shared LLM judge layer.
    # Faithfulness catches hallucinations (claims not in source).
    # Coverage catches incompleteness (facts in source missing from answer).
    if support == "explicit" and answer:
        result = faithfulness.check(
            source=docs_text,
            answer=answer,
            question_context="core technical problem and proposed solution",
        )
        if result.faithfulness == "unsupported":
            return _insufficient(
                "P1", "Core Problem",
                f"The answer is not supported by the source documents: {result.faithfulness_reasoning}".strip(": "),
            )
        # "inferred" is accepted with a downgraded support level — the answer
        # is faithful but combines facts that aren't a single direct quote.
        if result.faithfulness == "inferred":
            support = "inferred"
            if result.faithfulness_reasoning:
                insuf_msg = f"Note: {result.faithfulness_reasoning}"
        # Faithful but possibly incomplete: surface missing facts as a note
        # rather than failing the response.
        def _format_missing(facts: list[str], limit: int) -> str:
            cleaned = [f.strip().rstrip(".;,") for f in facts[:limit] if f.strip()]
            return "; ".join(cleaned)

        if result.coverage == "missing_critical" and result.missing_facts:
            answer = (
                f"{answer}\n\nNote (coverage gap): The source also mentions: "
                f"{_format_missing(result.missing_facts, 3)}."
            )
        elif result.coverage == "partial" and result.missing_facts:
            answer = (
                f"{answer}\n\nNote: minor details in the source not covered: "
                f"{_format_missing(result.missing_facts, 2)}."
            )

    if support in {"explicit", "inferred"} and not evidence:
        support = "insufficient"
        insuf_msg = "The answer could not be verified against a verbatim source excerpt."
        answer = ""

    return AssistantResponse(
        pattern_id="P1",
        title="Core Problem",
        support_level=support if answer else "insufficient",
        answer=answer,
        insufficient_message=insuf_msg,
        claim_structure=None,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# P2 — Patentability Assessment (LLM-judged)
#
# Pipeline:
#   1. Pull the numbered element list from the executive summary (deterministic
#      regex — robust enough and avoids spending an LLM call on parsing).
#   2. Send the element list + element_patent_analysis to the local LLM and
#      ask for a per-element verdict, drafting reason, and a verbatim
#      supporting excerpt copied from the analysis.
#   3. Verify each excerpt is an exact substring of element_patent_analysis.
#      Excerpts that don't verify drop the element to a caution — this is the
#      faithfulness guard for hallucinated quotes.
#   4. Build claim_structure from the verdicts:
#        novelty + inventive step       → independent_candidate
#        novelty but no inventive step  → dependent_candidate
#        no novelty                     → caution
#        unclear / unverifiable         → caution
# ---------------------------------------------------------------------------

_P2_TITLE = "Patentability Assessment"

# "1. Title", "\t1.\tTitle", "  1. Title" — capture number and title.
_ELEMENT_HEADER_RE = re.compile(
    r"(?:^|\n)\s*(\d+)\.\s*(?:\t)?\s*(.+?)(?=\n\s*\d+\.|\n\n|\Z)",
    re.DOTALL,
)


def _extract_element_titles(executive_summary: str | None) -> list[dict]:
    """Pull numbered elements (number + title) from the executive summary list."""
    if not executive_summary:
        return []
    titles = []
    for m in _ELEMENT_HEADER_RE.finditer(executive_summary):
        num = int(m.group(1))
        title = re.sub(r"\s+", " ", m.group(2).strip())
        if title:
            titles.append({"number": num, "name": title})
    return titles


_P2_SYSTEM = (
    "You are a patent drafting assistant. You read an element-patent analysis "
    "and assign a patentability verdict to each numbered element. "
    "Output valid JSON only. No markdown, no explanation."
)

_P2_USER = """You are given a list of invention elements and the element-patent analysis written by a patent searcher.

[ELEMENTS]
{elements}
[/ELEMENTS]

[ELEMENT_PATENT_ANALYSIS]
{analysis}
[/ELEMENT_PATENT_ANALYSIS]

For EACH element above, decide one of these verdicts based ONLY on what the analysis says:
- "novelty_and_inventive": the analysis concludes the element has BOTH novelty AND an inventive step over the cited prior art.
- "novelty_only": the analysis concludes the element is novel but does NOT have an inventive step (or the inventive step is rejected).
- "no_novelty": the analysis concludes the element lacks novelty (it is already disclosed in the prior art).
- "unclear": the analysis does not state a clear verdict for this element.

For every element, also copy ONE supporting sentence from the analysis verbatim — character by character, no paraphrase, no summary. If the analysis does not mention the element by number or by name, set verdict to "unclear" and leave support_excerpt as an empty string.

Return this JSON exactly:
{{
  "elements": [
    {{
      "number": 1,
      "verdict": "novelty_and_inventive" | "novelty_only" | "no_novelty" | "unclear",
      "reason": "one short sentence explaining the verdict in drafting terms",
      "support_excerpt": "exact verbatim sentence from the analysis, or empty string"
    }}
  ]
}}

Rules:
- Use ONLY the text inside [ELEMENT_PATENT_ANALYSIS]. Do not use outside knowledge.
- support_excerpt MUST be an exact copy of a sentence (or contiguous text span) from the analysis. Do not edit punctuation or whitespace.
- Return one entry per element, in the same order as the input list.
- Use cautious drafting language in "reason" (e.g. "appears", "is concluded", "is rejected by the analysis")."""


def _format_element_list_for_prompt(titles: list[dict]) -> str:
    return "\n".join(f"{el['number']}. {el['name']}" for el in titles)


def _normalize_for_match(text: str) -> str:
    """Collapse whitespace so substring checks survive line wraps and tabs."""
    return re.sub(r"\s+", " ", text).strip()


def _verdict_summary(verdicts: list[str]) -> str:
    counts = {
        "novelty_and_inventive": 0,
        "novelty_only": 0,
        "no_novelty": 0,
        "unclear": 0,
    }
    for v in verdicts:
        counts[v] = counts.get(v, 0) + 1

    parts = []
    if counts["novelty_and_inventive"]:
        parts.append(
            f"{counts['novelty_and_inventive']} element(s) with novelty and inventive step "
            "(independent claim candidates)"
        )
    if counts["novelty_only"]:
        parts.append(
            f"{counts['novelty_only']} element(s) novel but lacking inventive step "
            "(dependent or weak)"
        )
    if counts["no_novelty"]:
        parts.append(
            f"{counts['no_novelty']} element(s) without novelty (cannot be claimed)"
        )
    if counts["unclear"]:
        parts.append(f"{counts['unclear']} element(s) with no clear verdict in the analysis")

    if not parts:
        return ""
    return "Patentability assessment: " + "; ".join(parts) + "."


def _run_p2(patent_id: int, idf, rr) -> AssistantResponse:
    if not rr or not rr.element_patent_analysis:
        return _insufficient(
            "P2", _P2_TITLE,
            "No Element-Patent Analysis is available. "
            "Please add the Research Report element-patent analysis in Project Inputs.",
        )

    analysis_text = rr.element_patent_analysis
    titles = _extract_element_titles(rr.executive_summary)
    if not titles:
        return _insufficient(
            "P2", _P2_TITLE,
            "Could not find a numbered element list in the executive summary. "
            "Please ensure the executive summary lists each element of the invention.",
        )

    raw, err = _call_model(
        _P2_SYSTEM,
        _P2_USER.format(
            elements=_format_element_list_for_prompt(titles),
            analysis=analysis_text,
        ),
    )
    if raw is None:
        return _insufficient("P2", _P2_TITLE, err)

    items = raw.get("elements", [])
    if not isinstance(items, list) or not items:
        return _insufficient(
            "P2", _P2_TITLE,
            "The local model did not return a per-element assessment. Please try again.",
        )

    by_number: dict[int, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            num = int(item.get("number"))
        except (TypeError, ValueError):
            continue
        by_number[num] = item

    independent: list[IndependentCandidate] = []
    dependent: list[DependentCandidate] = []
    cautions: list[str] = []
    evidence_cards: list[EvidenceCard] = []
    verdicts: list[str] = []

    normalized_analysis = _normalize_for_match(analysis_text)

    for i, el in enumerate(titles):
        num = el["number"]
        name = el["name"]
        item = by_number.get(num, {})

        verdict = item.get("verdict", "unclear")
        if verdict not in {"novelty_and_inventive", "novelty_only", "no_novelty", "unclear"}:
            verdict = "unclear"

        excerpt = (item.get("support_excerpt") or "").strip()
        reason = (item.get("reason") or "").strip()

        # Faithfulness guard: the excerpt must be a substring of the analysis.
        # Models occasionally fabricate quotes, so verify before trusting them.
        excerpt_verified = False
        if excerpt:
            normalized_excerpt = _normalize_for_match(excerpt)
            if normalized_excerpt and normalized_excerpt in normalized_analysis:
                excerpt_verified = True

        if not excerpt_verified and verdict != "unclear":
            # Verdict claimed without a verifiable supporting quote — drop to
            # caution rather than show an unsupported assertion.
            cautions.append(
                f"Element {num} ({name}): the model gave a verdict but no verifiable "
                "supporting quote was found in the analysis — needs review."
            )
            verdicts.append("unclear")
            continue

        verdicts.append(verdict)

        if verdict == "novelty_and_inventive":
            independent.append(IndependentCandidate(
                label=f"Element {num}",
                features=[name],
                reason=reason or "Novelty and inventive step established by the analysis.",
                support_level="explicit",
                support_note=excerpt,
            ))
        elif verdict == "novelty_only":
            dependent.append(DependentCandidate(
                label=f"Element {num}",
                depends_on="Independent Claim",
                features=[name],
                reason=reason or "Novel but lacking inventive step — better placed as a dependent feature.",
                support_level="explicit",
                support_note=excerpt,
            ))
        elif verdict == "no_novelty":
            cautions.append(
                f"Element {num} ({name}): no novelty established — cannot be claimed. "
                f"{reason}".strip()
            )
        else:  # unclear
            cautions.append(
                f"Element {num} ({name}): no clear verdict in the analysis — needs review."
            )

        if excerpt_verified:
            evidence_cards.append(EvidenceCard(
                evidence_id=f"E{i+1}",
                document_type="research_report",
                field="element_patent_analysis",
                excerpt=excerpt,
            ))

    claim_structure = ClaimStructure(
        independent_candidates=independent,
        dependent_candidates=dependent,
        cautions=cautions,
    )

    answer = _verdict_summary(verdicts)
    if not answer:
        return _insufficient(
            "P2", _P2_TITLE,
            "The local model did not produce a usable assessment for any element. "
            "The element-patent analysis may not yet contain novelty/inventive-step conclusions.",
        )

    return AssistantResponse(
        pattern_id="P2",
        title=_P2_TITLE,
        support_level="explicit",
        answer=answer,
        insufficient_message="",
        claim_structure=claim_structure,
        evidence=evidence_cards,
    )


# ---------------------------------------------------------------------------
# P3 — Element Lookup (deterministic match + optional LLM ranking)
# ---------------------------------------------------------------------------

_P3_RANK_SYSTEM = """You rank source excerpts for a patent drafting assistant.
Output valid JSON only. No markdown, no explanation.

Ranking criteria, most useful (rank 1) to least useful (rank N):
1. Blocks containing a verdict sentence — directly state whether the element has novelty, inventive step, both, or neither.
2. Blocks comparing the searched term against a specific cited prior-art document — describe how the element differs from that document.
3. Blocks explaining the technical role or mechanism of the element in the invention.
4. Blocks giving general background or context about the term.

Rules:
- Use ONLY the provided matched evidence blocks.
- Do not add new technical facts. Do not summarize beyond a short usefulness note.
- usefulness_note must explicitly state which criterion (1, 2, 3, or 4) the block matches and why.
- Return only evidence IDs that were provided."""

_P3_RANK_USER = """---SEARCH TERM---
{term}

---MATCHED EVIDENCE BLOCKS---
{blocks}

---TASK---
Rank the blocks from most useful (rank 1) to least useful using the criteria in the system message. Every block must receive a usefulness_note that names the matching criterion and the specific reason.

Return this JSON:
{{
  "ranked_evidence": [
    {{"evidence_id": "E1", "usefulness_note": "Criterion N — short specific reason this block is useful"}}
  ]
}}"""

def _run_p3(patent_id: int, rr, term: str | None) -> AssistantResponse:
    if not term or not term.strip():
        return _insufficient("P3", "Element Lookup",
                             "Please enter a technical term to search for.")

    term = term.strip()

    if not rr or not rr.element_patent_analysis:
        return _insufficient("P3", "Element Lookup",
                             "No Research Report with Element–Patent Analysis is available. "
                             "Please upload a Research Report first.")

    text = rr.element_patent_analysis
    blocks = _split_paragraphs(text)
    matches = [b for b in blocks if term.lower() in b.lower()]

    if not matches:
        return AssistantResponse(
            pattern_id="P3",
            title="Element Lookup",
            support_level="insufficient",
            answer="",
            insufficient_message=(
                f"'{term}' was not found in the element patent analysis. "
                "Note: terminology in the research report may differ from the invention disclosure. "
                "Try an alternative or more general term."
            ),
            claim_structure=None,
            evidence=[],
        )

    evidence = [
        EvidenceCard(
            evidence_id=f"E{i+1}",
            document_type="research_report",
            field="element_patent_analysis",
            excerpt=block.strip(),
            match_term=term,
        )
        for i, block in enumerate(matches)
    ]

    evidence = _rank_p3_evidence(term, evidence)

    count = len(matches)
    summary = (
        f"'{term}' was found in {count} {'place' if count == 1 else 'places'} "
        "in the element patent analysis. Matches are ordered by drafting usefulness: "
        "(1) verdict sentences, (2) prior-art comparisons, (3) technical role explanations, "
        "(4) general context. Each card's note states the matching criterion."
    )

    return AssistantResponse(
        pattern_id="P3",
        title="Element Lookup",
        support_level="explicit",
        answer=summary,
        insufficient_message="",
        claim_structure=None,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_paragraphs(text: str) -> list[str]:
    """Split by blank lines; fall back to ~400-char windows if blocks are huge."""
    raw_blocks = re.split(r"\n{2,}", text.strip())
    result = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) <= 1200:
            result.append(block)
        else:
            # chunk large blocks by sentence boundary
            sentences = re.split(r"(?<=[.!?])\s+", block)
            chunk = ""
            for s in sentences:
                if len(chunk) + len(s) < 1200:
                    chunk = (chunk + " " + s).strip()
                else:
                    if chunk:
                        result.append(chunk)
                    chunk = s
            if chunk:
                result.append(chunk)
    return result


def _rank_p3_evidence(term: str, evidence: list[EvidenceCard]) -> list[EvidenceCard]:
    if len(evidence) <= 1:
        return evidence

    max_blocks_for_ranking = 20
    rankable = evidence[:max_blocks_for_ranking]
    overflow = evidence[max_blocks_for_ranking:]

    blocks_text = "\n\n".join(
        f"[{card.evidence_id}]\n{card.excerpt}"
        for card in rankable
    )
    raw, _err = _call_model(
        _P3_RANK_SYSTEM,
        _P3_RANK_USER.format(term=term, blocks=blocks_text),
    )
    if raw is None:
        return evidence

    ranked_raw = raw.get("ranked_evidence", [])
    if not isinstance(ranked_raw, list):
        return evidence

    by_id = {card.evidence_id: card for card in rankable}
    ranked = []
    used_ids = set()

    for item in ranked_raw:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id", "")).strip()
        card = by_id.get(evidence_id)
        if not card or evidence_id in used_ids:
            continue
        note = item.get("usefulness_note")
        if isinstance(note, str) and note.strip():
            card.usefulness_note = note.strip()[:240]
        ranked.append(card)
        used_ids.add(evidence_id)

    if not ranked:
        return evidence

    remaining = [card for card in rankable if card.evidence_id not in used_ids]
    return ranked + remaining + overflow


def _build_evidence_cards(
    pattern_id: str,
    evidence_raw: list,
    idf,
    rr,
    fallback_field: str | None = None,
) -> list[EvidenceCard]:
    cards = []
    for i, e in enumerate(evidence_raw):
        if not isinstance(e, dict):
            continue
        field = _normalize_field(e.get("field", ""))
        if not field and fallback_field:
            field = fallback_field
        excerpt = e.get("excerpt", "").strip()
        if not field or not excerpt:
            continue
        source_text = _field_text(field, idf, rr)
        if not source_text or excerpt not in source_text:
            continue
        doc_type = _field_to_doc_type(field)
        cards.append(EvidenceCard(
            evidence_id=f"E{i+1}",
            document_type=doc_type,
            field=field,
            excerpt=excerpt,
        ))
    return cards


def _normalize_field(field: str) -> str:
    normalized = (field or "").strip().lower()
    normalized = normalized.replace("—", " ").replace("-", " ")
    normalized = re.sub(r"[^a-z0-9_& ]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    aliases = {
        "prior_art_and_problems": "prior_art_and_problems",
        "prior art problems": "prior_art_and_problems",
        "prior art & problems": "prior_art_and_problems",
        "invention disclosure prior art problems": "prior_art_and_problems",
        "invention disclosure prior art & problems": "prior_art_and_problems",
        "novel_features": "novel_features",
        "novel features": "novel_features",
        "closest_prior_patents": "closest_prior_patents",
        "closest prior patents": "closest_prior_patents",
        "executive_summary": "executive_summary",
        "executive summary": "executive_summary",
        "research report executive summary": "executive_summary",
        "element_patent_analysis": "element_patent_analysis",
        "element patent analysis": "element_patent_analysis",
        "element patent analysis": "element_patent_analysis",
    }
    return aliases.get(normalized, "")


def _parse_claim_structure(raw: dict) -> ClaimStructure:
    independent = []
    dependent = []

    for item in raw.get("independent_candidates", []):
        if not isinstance(item, dict):
            continue
        try:
            independent.append(IndependentCandidate(**item))
        except ValidationError:
            continue

    for item in raw.get("dependent_candidates", []):
        if not isinstance(item, dict):
            continue
        try:
            dependent.append(DependentCandidate(**item))
        except ValidationError:
            continue

    cautions = raw.get("cautions", [])
    if not isinstance(cautions, list):
        cautions = []

    return ClaimStructure(
        independent_candidates=independent,
        dependent_candidates=dependent,
        cautions=[str(c) for c in cautions if c],
    )


def _field_text(field: str, idf, rr) -> str:
    if field == "prior_art_and_problems" and idf:
        return idf.prior_art_and_problems or ""
    if field == "novel_features" and idf:
        return idf.novel_features or ""
    if field == "closest_prior_patents" and idf:
        return idf.closest_prior_patents or ""
    if field == "executive_summary" and rr:
        return rr.executive_summary or ""
    if field == "element_patent_analysis" and rr:
        return rr.element_patent_analysis or ""
    return ""


def _field_to_doc_type(field: str) -> str:
    rr_fields = {"executive_summary", "element_patent_analysis",
                 "search_strategy", "classification_and_keywords"}
    return "research_report" if field in rr_fields else "invention_disclosure"


def _call_model(system_prompt: str, user_prompt: str) -> tuple[dict | None, str]:
    """Call the local LLM and return (parsed_json, user_facing_error).

    On success: (dict, "").
    On failure: (None, short message describing what went wrong).
    The full exception is logged so the server console shows the real cause.
    """
    try:
        result = llm_router.generate_json(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.15,
        )
        return result, ""
    except LLMConnectionError as exc:
        logger.warning("Assistant LLM connection error: %s", exc)
        return None, (
            "The local model could not be reached or timed out. "
            "Ensure Ollama is running and the configured model is loaded."
        )
    except LLMResponseError as exc:
        logger.warning("Assistant LLM response error: %s", exc)
        return None, "The local model returned an error response."
    except LLMParseError as exc:
        logger.warning("Assistant LLM parse error: %s", exc)
        return None, (
            "The local model did not return valid JSON. "
            "Try again, or switch to a model that better follows JSON output instructions."
        )


def _insufficient(pattern_id: str, title: str, message: str) -> AssistantResponse:
    return AssistantResponse(
        pattern_id=pattern_id,
        title=title,
        support_level="insufficient",
        answer="",
        insufficient_message=message,
        claim_structure=None,
        evidence=[],
    )
