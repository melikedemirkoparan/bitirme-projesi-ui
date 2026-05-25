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
        return _run_p2(patent_id, rr, req.elements)
    if req.pattern_id == "P3":
        return _run_p3(patent_id, rr, req.term)

    return _insufficient(req.pattern_id, "Unknown pattern.", "Unknown pattern.")


# ---------------------------------------------------------------------------
# P1 — Core Problem (single-pass)
# ---------------------------------------------------------------------------

_P1_SYSTEM = (
    "You are a patent drafting assistant helping a patent engineer review source documents. "
    "Think carefully before answering, but output valid JSON only. No markdown, no explanation."
)

_P1_USER = """Your task: read the patent source documents below and present the core technical problem and the proposed solution to a patent engineer.

[TEXT]
{docs}
[/TEXT]

Work through the text in three steps:

STEP 1 — FIND THE TECHNICAL PROBLEM.
Search for sentences that describe a failure, drawback, limitation, or safety risk in existing designs. Identify: which component is involved, what goes wrong, and what the consequence is (e.g. weight penalty, oil accumulation, chip contamination risk, catastrophic failure). If this information is directly stated in one or more sentences → it is explicit. If the facts are all present in the text but require connecting separately stated sentences to form the complete picture → it is inferred. If it is not described at all → the source is insufficient.

STEP 2 — FIND THE PROPOSED SOLUTION.
Search for sentences that describe what the invention introduces: a specific mechanism, component, or arrangement that fixes the problem from Step 1. Identify: what is introduced, how it works, and what result it achieves. If the solution is directly stated → it is explicit. If the facts are all in the text but require connecting → it is inferred. If it is absent → insufficient.

STEP 3 — WRITE THE ANSWER.
Combine the two findings into a professional summary for the patent engineer. Use the document's own component names and technical terminology throughout. Do not use vague phrases like "addresses the issue" or "improves performance" — be specific. Format:
  First sentence(s): the technical problem — what fails, in what component, with what consequence.
  Last sentence: the invention's approach — what is introduced and what it achieves.

Then output this JSON:
{{
  "support_level": "explicit" or "inferred" or "insufficient",
  "answer": "Professional technical summary written for a patent engineer — specific component names, specific failure mode, specific proposed mechanism. Empty string only if insufficient.",
  "insufficient_message": "State exactly what is missing or unclear: the technical problem, the proposed solution, or both. Empty string if support_level is explicit or inferred.",
  "evidence": [
    {{
      "field": "prior_art_and_problems" or "executive_summary",
      "excerpt": "Exact verbatim copy of one sentence from the text that you used to construct the answer — character by character, no changes, no paraphrase, no shortening"
    }}
  ]
}}

IMPORTANT — evidence list:
Include ALL sentences from the source text that you directly used to write the answer. Each sentence goes in a separate evidence entry. Do not summarize or merge sentences — copy each one exactly as it appears in the text.

support_level decision rules:
- "explicit": both the specific technical problem AND the specific proposed solution are directly and clearly stated in the text in technical terms.
- "inferred": the answer requires connecting separately stated facts, but those facts are all directly present in the text.
- "insufficient": the text does not provide enough information to identify either the specific technical problem or the specific proposed solution.

Additional rules:
- Use ONLY the text between [TEXT] and [/TEXT]. Do not use outside knowledge.
- Name specific components from the document — do not replace them with generic terms.
- field must be exactly "prior_art_and_problems" or "executive_summary" — use the section label shown in the text.
- Each excerpt must be verbatim — copy one sentence exactly as it appears, no changes."""


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

    # ---------------------------------------------------------------------------
    # Normalize support_level.
    # The LLM now returns "explicit", "inferred", or "insufficient".
    # "inferred" means all facts are in the text but require connecting.
    # Any unrecognized value → "insufficient" so Pydantic validation never fails.
    # ---------------------------------------------------------------------------
    support_raw = raw.get("support_level", "insufficient")
    support: str = support_raw if support_raw in {"explicit", "inferred", "insufficient"} else "insufficient"

    answer = (raw.get("answer") or "").strip()
    insuf_msg = (raw.get("insufficient_message") or "").strip()
    evidence_raw = raw.get("evidence", [])

    # If the LLM itself says insufficient (or gave no answer), return immediately.
    if support == "insufficient" or not answer:
        return AssistantResponse(
            pattern_id="P1",
            title="Core Problem",
            support_level="insufficient",
            answer="",
            insufficient_message=insuf_msg or (
                "The source documents do not provide enough information to identify "
                "both the core problem and the proposed solution."
            ),
            claim_structure=None,
            evidence=[],
        )

    evidence = _build_evidence_cards("P1", evidence_raw, idf, rr)

    # ---------------------------------------------------------------------------
    # Faithfulness + Coverage guard (second LLM call).
    # Every answer MUST pass this gate — no answer is returned without it.
    #
    #  check_failed=True  → faithfulness judge itself failed (LLM error /
    #                        timeout / bad JSON) → block the answer.
    #  faithfulness="unsupported" → genuine hallucination → block.
    #  faithfulness="inferred"    → downgrade support level if needed, pass.
    #  faithfulness="explicit"    → pass as-is.
    #  coverage gaps              → surface as notes, never block.
    # ---------------------------------------------------------------------------
    result = faithfulness.check(
        source=docs_text,
        answer=answer,
        question_context="core technical problem and proposed solution",
    )

    if result.check_failed:
        return _insufficient(
            "P1", "Core Problem",
            "The answer could not be verified — the faithfulness check failed "
            "(model unavailable or did not return valid JSON). Please try again.",
        )

    if result.faithfulness == "unsupported":
        return _insufficient(
            "P1", "Core Problem",
            f"The answer is not supported by the source documents: {result.faithfulness_reasoning}".strip(": "),
        )

    # Faithfulness judge says "inferred" but LLM had claimed "explicit" →
    # downgrade.  If the LLM already said "inferred", leave it as-is.
    if result.faithfulness == "inferred" and support == "explicit":
        support = "inferred"
        if result.faithfulness_reasoning:
            insuf_msg = f"Note: {result.faithfulness_reasoning}"

    # Faithful but possibly incomplete: surface missing facts as a note,
    # never as a failure.
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

    # Evidence gate: if we claim explicit/inferred but have no verifiable
    # verbatim excerpt, degrade to insufficient rather than show an unsupported answer.
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
#   1. Parse the user-supplied numbered element list (deterministic regex).
#   2. Send element list + element_patent_analysis to the LLM.
#      The prompt validates each element in three sub-steps:
#        1a. Gibberish check — meaningless names → verdict "unclear".
#        1b. Name-to-analysis match — element name must share at least one
#            technical keyword with the corresponding numbered header in the
#            analysis; mismatch → verdict "unclear".
#        1c. Passage lookup by element number for valid elements.
#      Then for each valid element the model assigns:
#        - verdict: novelty_and_inventive | novelty_only | no_novelty | unclear
#        - novelty_reasoning + inventive_step_reasoning
#        - prior_art_comparison (Case A: specific patents named;
#                                Case B: no prior-art document found;
#                                Case C: empty)
#        - support_excerpts: verbatim sentences from the analysis
#   3. Per-element faithfulness guards (no extra LLM calls for excerpt check):
#        a. Excerpt verification — each support_excerpt is substring-matched
#           against the analysis; unverified excerpts are dropped.
#           Zero verified excerpts → support_level "inferred" (not "explicit").
#        b. PAC grounding check (one faithfulness.check() call per element
#           that has a Case A pac) — verifies that the patent numbers and
#           feature descriptions in prior_art_comparison are supported by the
#           analysis. "unsupported" → pac removed. "inferred" → card
#           support_level downgraded to "inferred".
#   4. All-unclear gate — if every element is "unclear", return insufficient.
#   5. Overall faithfulness guard (one faithfulness.check() call) — verifies
#      the verdict summary sentence against the analysis.
#   6. Build claim_structure from the verdicts:
#        novelty_and_inventive → independent_candidate
#        novelty_only          → dependent_candidate
#        no_novelty            → caution (with pac note)
#        unclear               → caution
# ---------------------------------------------------------------------------

_P2_TITLE = "Patentability Assessment"

# Match "1. Title", "  2. Title" — captures number and title on the same line only.
# No DOTALL: title is always a single line; multi-paragraph bleed is prevented.
_ELEMENT_HEADER_RE = re.compile(r"(?:^|\n)\s*(\d+)\.\s+([^\n]+)")

# Detects patent/document numbers in a prior_art_comparison string.
# Used to decide whether to run the faithfulness grounding check:
#   Case A pac (contains a patent number) → check both the number and
#     the feature description attributed to it via faithfulness.check().
#   Case B pac ("No specific prior-art document…") → skip the check;
#     running it against the full multi-element analysis would produce
#     false positives from other elements' patent numbers.
_PAC_PATENT_NUM_RE = re.compile(r"[A-Z]{2}\d{4,}")


def _extract_element_titles(elements_text: str | None) -> list[dict]:
    """Parse a user-provided numbered list into structured element dicts.

    Expected input format (one element per line):
        1. Element name
        2. Another element name
        ...

    Returns a list of {"number": int, "name": str} dicts in order.
    """
    if not elements_text:
        return []
    titles = []
    for m in _ELEMENT_HEADER_RE.finditer(elements_text):
        num = int(m.group(1))
        title = re.sub(r"\s+", " ", m.group(2).strip())
        if title:
            titles.append({"number": num, "name": title})
    return titles


_P2_SYSTEM = (
    "You are a patent claim analysis assistant. "
    "You read an element-patent analysis written by a patent searcher and assess "
    "the patentability of each numbered invention element. "
    "Output valid JSON only. No markdown, no explanation."
)

_P2_USER = """You are given a numbered list of invention elements and an element-patent analysis.

PATENT TERMINOLOGY:
- Novelty: an element is novel if it is NOT disclosed in any single cited prior-art document.
- Inventive step: an element has an inventive step if it would NOT have been obvious to a person skilled in the art from the combination of cited documents.

[ELEMENTS]
{elements}
[/ELEMENTS]

[ELEMENT_PATENT_ANALYSIS]
{analysis}
[/ELEMENT_PATENT_ANALYSIS]

For EACH numbered element, work through these steps:

Step 1 — Pre-validation: reject mismatched or gibberish element names BEFORE any analysis.
This step is applied PER ELEMENT. If one element fails validation, set its verdict to
"unclear" and move on to the next element — do NOT stop assessing the remaining elements.

Example: if 3 elements are provided and element 2 is gibberish or mismatched, elements
1 and 3 are still fully assessed; only element 2 gets verdict="unclear".

Sub-step 1a — Gibberish check.
Is the element name from [ELEMENTS] a coherent technical description? A valid name is a
meaningful phrase about a component, mechanism, feature, or engineering concept.
INVALID examples: "eren", "asdfjkl", "blabla", "test123", single personal names,
random characters, placeholder text, words with no engineering meaning.
→ If INVALID: set verdict="unclear", novelty_reasoning="Element description is not a
meaningful technical concept — assessment skipped."
Skip sub-steps 1b and 1c for this element; continue to the NEXT element.

Sub-step 1b — Name-to-analysis match check.
[ELEMENT_PATENT_ANALYSIS] contains numbered section headers such as:
  "1. CHANGING THE SWAY BRACE POSITIONS FOR DIFFERENT AMMUNITION DIAMETERS…"
  "2. MOVING THE SHOES ONLY IN THE VERTICAL PLANE…"
Find the header for element number N. Ask: does the provided element name share at least
one meaningful technical keyword (component, mechanism, action, or engineering term) with
that header?
→ If NO shared technical keyword: set verdict="unclear", novelty_reasoning="Provided
element name does not correspond to Element N in the analysis — check numbering."
Skip sub-step 1c for this element; continue to the NEXT element.
→ If YES: continue to sub-step 1c.

Sub-step 1c — Find passages.
Search [ELEMENT_PATENT_ANALYSIS] for all passages containing "Element N" where N is
this element's number. Use these passages for Steps 2–6.

Step 2 — Evidence: copy the KEY sentences from the matching passage for this element.
Select the sentences you will directly use to assign the verdict and write the
prior_art_comparison. Include:
  - The novelty verdict sentence.
  - The inventive step verdict sentence (if present).
  - The most important sentence describing the relevant prior-art document and what it discloses (if any).
  - The most important sentence comparing the invention against the prior art (if any).
Do NOT include sentences about other elements. Each excerpt must be verbatim — character by character, no paraphrase, no shortening.

Step 3 — Novelty: does the matching passage state whether this element is disclosed in a cited prior-art document?
- "involves novelty" or "no relevant document was found" → novel.
- "does not involve novelty" or cites a document that discloses it → not novel.

Step 4 — Inventive step: does the matching passage state whether this element would have been obvious?
- "involves an inventive step" → has inventive step.
- "does not involve an inventive step" or "considered obvious to a person skilled in the art" → no inventive step.

Step 5 — Assign verdict:
- "novelty_and_inventive": analysis concludes BOTH novelty AND inventive step → independent claim candidate.
- "novelty_only": analysis concludes novelty but NOT inventive step → dependent claim candidate.
- "no_novelty": analysis concludes the element lacks novelty → cannot be independently claimed.
- "unclear": the analysis does not contain sufficient information for this element.

Step 6 — Prior-art comparison note.
Write in your own words — do not copy verbatim. Do not invent details not in the analysis.
Base this note only on the matching passage for this element and the support_excerpts
you selected in Step 2.

  Case A — One or more prior-art documents ARE named for this element:
    For novel elements (novelty_and_inventive or novelty_only):
      Name ALL prior-art documents mentioned in the passage for this element, then state
      how the invention differs. If multiple documents are cited, list them all.
      Example: "Considering US4620680A (bevel gears), US4395003A (cam and gears), and
      US4122754A (rack-and-pinion), none of these disclose a four-bar mechanism — this
      element differs in using a four-bar linkage instead."
    For no_novelty elements:
      Name the document that covers this element and which feature matches.
      Example: "Considering US10518883B2, which discloses [matching feature], this element
      is already covered by that document."

  Case B — The analysis passage for this element contains the phrase "no relevant document
  has been found" (or equivalent) AND no patent number or document ID appears in that passage:
    Write exactly: "No specific prior-art document was identified. The novelty assessment
    relies on absence of direct prior-art disclosure rather than a concrete technical
    distinction."

  Case C — Only a final verdict sentence exists; no patent number or document ID is named,
  and no "no relevant document" phrase appears:
    Return empty string "".

  IMPORTANT: If any patent number (e.g. US4620680A) or document ID appears anywhere in the
  passage for this element — even if the element is ultimately found to be novel — use Case A,
  not Case B or C.

Return this JSON:
{{
  "elements": [
    {{
      "number": 1,
      "verdict": "novelty_and_inventive" | "novelty_only" | "no_novelty" | "unclear",
      "novelty_reasoning": "one sentence — why this element is or is not novel according to the analysis",
      "inventive_step_reasoning": "one sentence — why this element does or does not have an inventive step, or empty string if verdict is no_novelty or unclear",
      "prior_art_comparison": "1–2 sentence note per the rules above. Empty string only for Case C.",
      "support_excerpts": [
        "verbatim key sentence 1",
        "verbatim key sentence 2"
      ]
    }}
  ]
}}

Rules:
- Use ONLY [ELEMENT_PATENT_ANALYSIS]. Do not use outside knowledge.
- prior_art_comparison: write in your own words (synthesis), NOT verbatim from the source.
- support_excerpts: exact verbatim copies only — no paraphrase, no shortening, no punctuation changes.
- Return one entry per element, in the same order as the input list.
- Use cautious drafting language in reasoning (e.g. "the analysis concludes", "is stated to", "appears to establish").
- If an element is not mentioned in the analysis, set verdict to "unclear" and support_excerpts to []."""


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


def _run_p2(patent_id: int, rr, elements_text: str | None) -> AssistantResponse:
    if not rr or not rr.element_patent_analysis:
        return _insufficient(
            "P2", _P2_TITLE,
            "No Element-Patent Analysis is available. "
            "Please add the Research Report element-patent analysis in Project Inputs.",
        )

    if not elements_text or not elements_text.strip():
        return _insufficient(
            "P2", _P2_TITLE,
            "Please enter the invention elements in numbered list format (1. … 2. … 3. …).",
        )

    analysis_text = rr.element_patent_analysis

    # Parse the user-provided numbered list into structured titles.
    titles = _extract_element_titles(elements_text)
    if not titles:
        return _insufficient(
            "P2", _P2_TITLE,
            "Could not parse the element list. "
            "Please use a numbered format: 1. Element name\\n2. Element name …",
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
    evidence_counter = 0  # global counter for unique evidence IDs across all elements

    for el in titles:
        num = el["number"]
        name = el["name"]
        item = by_number.get(num, {})

        verdict = item.get("verdict", "unclear")
        if verdict not in {"novelty_and_inventive", "novelty_only", "no_novelty", "unclear"}:
            verdict = "unclear"

        novelty_reasoning = (item.get("novelty_reasoning") or "").strip()
        inv_step_reasoning = (item.get("inventive_step_reasoning") or "").strip()
        prior_art_comparison = (item.get("prior_art_comparison") or "").strip()

        # Compose the human-readable reason shown in the claim card.
        reason_parts = [p for p in (novelty_reasoning, inv_step_reasoning) if p]
        reason = " ".join(reason_parts)

        # ---------------------------------------------------------------------------
        # Faithfulness guard — verify each excerpt against the actual analysis text.
        # Models occasionally fabricate quotes; only verified excerpts are trusted.
        # An unverified excerpt is silently dropped (not shown, not counted).
        # A verdict with ZERO verified excerpts is demoted to "unclear" / caution.
        # ---------------------------------------------------------------------------
        raw_excerpts = item.get("support_excerpts")
        if not isinstance(raw_excerpts, list):
            # Handle models that still return a single string.
            raw_excerpts = [item.get("support_excerpt") or ""]

        verified_excerpts: list[str] = []
        for exc in raw_excerpts:
            exc = (exc or "").strip()
            if not exc:
                continue
            if _normalize_for_match(exc) in normalized_analysis:
                verified_excerpts.append(exc)

        # ---------------------------------------------------------------------------
        # Support level: "explicit" if at least one excerpt verified verbatim;
        # "inferred" if no excerpt verified but the verdict is still accepted
        # (model correctly identified the verdict, but transcription was imperfect).
        # Only "unclear" verdicts from the model itself are dropped to caution.
        # ---------------------------------------------------------------------------
        if verified_excerpts:
            inferred_only = False
            support_level_val = "explicit"
        else:
            inferred_only = True
            support_level_val = "inferred"

        # ---------------------------------------------------------------------------
        # PAC grounding check — faithfulness judge evaluates whether the
        # prior_art_comparison text is actually supported by the analysis.
        #
        # Only run when the pac contains a patent/document number (Case A).
        # Case B pacs ("No specific prior-art document was identified…") are
        # deterministic paraphrases of the "no relevant document found" phrase
        # in the analysis; running the faithfulness judge against the full
        # analysis would produce false positives because it sees patent numbers
        # from other elements and incorrectly flags the no-doc claim.
        #
        # "explicit"    → pac content is directly stated — keep as-is.
        # "inferred"    → pac is a reasonable synthesis — keep, note the grounding.
        # "unsupported" → pac is not grounded in the source — remove it entirely
        #                 to avoid showing hallucinated patent/feature claims.
        # ---------------------------------------------------------------------------
        pac_grounding_note = ""
        if prior_art_comparison and _PAC_PATENT_NUM_RE.search(prior_art_comparison):
            pac_faith = faithfulness.check(
                source=analysis_text,
                answer=prior_art_comparison,
                question_context=(
                    f"prior-art documents cited and the features attributed to "
                    f"them for Element {num} ({name}) in the element-patent analysis"
                ),
            )
            if not pac_faith.check_failed:
                if pac_faith.faithfulness == "unsupported":
                    prior_art_comparison = ""
                    pac_grounding_note = (
                        f"Prior-art comparison removed — not supported by source: "
                        f"{pac_faith.faithfulness_reasoning}"
                    )
                else:
                    # "explicit" or "inferred": keep the pac, carry the reasoning forward.
                    pac_grounding_note = (
                        f"Prior-art comparison ({pac_faith.faithfulness}): "
                        f"{pac_faith.faithfulness_reasoning}"
                    )
                    # If the PAC is only inferred (synthesized, not verbatim), downgrade
                    # the card's support_level too — showing "Explicitly Stated" while the
                    # prior-art comparison is interpretive would be misleading.
                    if pac_faith.faithfulness == "inferred":
                        support_level_val = "inferred"

        verdicts.append(verdict)

        # Build evidence cards from all verified excerpts for this element.
        element_evidence_ids: list[str] = []
        for exc in verified_excerpts:
            evidence_counter += 1
            eid = f"E{evidence_counter}"
            evidence_cards.append(EvidenceCard(
                evidence_id=eid,
                document_type="research_report",
                field="element_patent_analysis",
                excerpt=exc,
            ))
            element_evidence_ids.append(eid)

        # Support note: verbatim excerpt (or fallback) + pac grounding note.
        if verified_excerpts:
            support_note = verified_excerpts[0]
        elif inferred_only:
            support_note = "Verdict based on analysis; verbatim excerpt could not be pinpointed — review recommended."
        else:
            support_note = ""
        if pac_grounding_note:
            support_note = (
                (support_note + "\n" + pac_grounding_note).strip()
                if support_note else pac_grounding_note
            )

        if verdict == "novelty_and_inventive":
            independent.append(IndependentCandidate(
                label=f"Element {num}",
                features=[name],
                reason=reason or "Novelty and inventive step established by the analysis.",
                prior_art_comparison=prior_art_comparison,
                support_level=support_level_val,
                support_note=support_note,
                evidence_ids=element_evidence_ids,
            ))
        elif verdict == "novelty_only":
            dependent.append(DependentCandidate(
                label=f"Element {num}",
                depends_on="Independent Claim",
                features=[name],
                reason=reason or "Novel but lacking inventive step — suitable as a dependent feature.",
                prior_art_comparison=prior_art_comparison,
                support_level=support_level_val,
                support_note=support_note,
                evidence_ids=element_evidence_ids,
            ))
        elif verdict == "no_novelty":
            pac_note = f" {prior_art_comparison}" if prior_art_comparison else ""
            cautions.append(
                f"Element {num} ({name}): no novelty established — cannot be independently "
                f"claimed. {novelty_reasoning}{pac_note}".strip()
            )
        else:  # unclear
            cautions.append(
                f"Element {num} ({name}): no clear verdict found in the analysis — needs review."
            )

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

    # If every verdict is "unclear" — no candidates, no no_novelty findings —
    # the input elements were not found in the analysis (e.g. gibberish names,
    # wrong numbering, or the analysis does not address them at all).
    # Return insufficient rather than an uninformative all-unclear result.
    if verdicts and all(v == "unclear" for v in verdicts):
        return _insufficient(
            "P2", _P2_TITLE,
            "None of the provided elements could be matched to a verdict in the "
            "element-patent analysis. Check that the element descriptions correspond "
            "to the elements assessed in the research report and that the numbering matches.",
        )

    # ---------------------------------------------------------------------------
    # Faithfulness guard — same post-generation evaluator used by P1.
    # Verifies that the verdict summary is grounded in the analysis text.
    # P2 already has a per-element excerpt guard above, but this second layer
    # catches systematic errors where all excerpts verified but the overall
    # verdict summary contradicts the analysis.
    #
    # "inferred" is expected and accepted for P2 — the summary combines
    # per-element conclusions into one statistical sentence, so it will
    # rarely be "explicit" by the faithfulness evaluator's definition.
    # ---------------------------------------------------------------------------
    faith = faithfulness.check(
        source=analysis_text,
        answer=answer,
        question_context=(
            "patentability assessment — novelty and inventive step verdicts "
            "for each numbered invention element"
        ),
    )

    if faith.check_failed:
        return _insufficient(
            "P2", _P2_TITLE,
            "The verdict summary could not be verified — the faithfulness evaluator "
            "failed (model unavailable or did not return valid JSON). Please try again.",
        )

    if faith.faithfulness == "unsupported":
        return _insufficient(
            "P2", _P2_TITLE,
            f"The verdict summary is not supported by the element-patent analysis: "
            f"{faith.faithfulness_reasoning}".strip(": "),
        )

    # Top-level support_level comes from the faithfulness judge — same semantics as P1:
    #   "explicit"  → verdict summary is directly stated in the analysis text
    #   "inferred"  → verdict summary is grounded in the analysis but requires
    #                 connecting separately stated facts (normal for a multi-element summary)
    # "unsupported" is already handled above (returns insufficient).
    overall_support: str = faith.faithfulness if faith.faithfulness in {"explicit", "inferred"} else "inferred"

    return AssistantResponse(
        pattern_id="P2",
        title=_P2_TITLE,
        support_level=overall_support,
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
