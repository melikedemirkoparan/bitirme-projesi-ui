"""
4-stage definition generator pipeline.

Spec: docs/definition_generator_specification.md

Stage 0 (RAG Pre-filter) -> filter raw RAG hits based on project context + target role.
Stage 1 (Functional)     -> generic intrinsic characteristics (uses filtered RAG).
Stage 2 (Geometry)       -> case-specific placement (uses project inputs only).
Stage 3 (Synthesis)      -> assemble final candidate using [geom], [func], a [name] (ref#).
Post-process             -> deterministically inject related-element reference numbers.

All LLM calls go through `llm_router.generate_json`, which uses Ollama's
native `format=json` mode. Each prompt is split into a system message
(instructions, output schema) and a user message (input data). We never
manually include ChatML tags — Ollama applies the model's own chat template.

Modularity: each stage is a pure function over the PipelineContext.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.generation import llm_router
from app.generation.llm_client import (
    LLMConnectionError,
    LLMParseError,
    LLMResponseError,
)
from app.models.patent import Patent
from app.retrieval import chroma_retrieval
from app.services import (
    element_service,
    invention_disclosure_service,
    inventor_qa_service,
    research_report_service,
)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

_FIELD_CAP = 8000


@dataclass
class TargetElement:
    name: str
    reference_number: str


@dataclass
class RelatedElement:
    name: str
    reference_number: str


@dataclass
class StructuredInputs:
    idf_prior_art: str = ""
    idf_novel_features: str = ""
    rr_executive_summary: str = ""
    qa_text: str = ""


@dataclass
class PipelineContext:
    target_element: TargetElement
    related_elements: list[RelatedElement]
    inputs: StructuredInputs
    rag_hits: list[dict] = field(default_factory=list)


def _trim(value: str | None) -> str:
    if not value:
        return ""
    s = str(value).strip()
    return s[:_FIELD_CAP]


def _placeholder(value: str) -> str:
    """Replace empty inputs with literal '(none)' so the model never sees a blank label."""
    return value if value else "(none)"


def build_context(
    db: Session,
    patent_id: int,
    element_id: int,
    top_k: int = 15,
) -> PipelineContext | None:
    """Load target element, related elements, structured inputs and RAG hits from DB."""
    target = element_service.get_element_for_patent(db, patent_id, element_id)
    if not target:
        return None

    patent = db.query(Patent).filter(Patent.patent_id == patent_id).first()
    domain = (patent.domain or "").strip() if patent else ""

    all_elems = element_service.list_elements(db, patent_id)
    related = [
        RelatedElement(name=e.element_name, reference_number=e.reference_number)
        for e in all_elems
        if e.element_id != target.element_id
    ]

    idf = invention_disclosure_service.get_invention_disclosure(db, patent_id)
    rr = research_report_service.get_research_report(db, patent_id)
    qa = inventor_qa_service.get_inventor_qa(db, patent_id)

    inputs = StructuredInputs(
        idf_prior_art=_trim(getattr(idf, "prior_art_and_problems", "")),
        idf_novel_features=_trim(getattr(idf, "novel_features", "")),
        rr_executive_summary=_trim(getattr(rr, "executive_summary", "")),
        qa_text=_trim(getattr(qa, "questions_and_answers", "")),
    )

    rag_hits: list[dict] = []
    if chroma_retrieval.is_data_loaded():
        rag_hits = chroma_retrieval.retrieve(
            element_name=target.element_name,
            domain=domain or None,
            top_k=top_k,
            top_k_titles=5,
        )

    return PipelineContext(
        target_element=TargetElement(
            name=target.element_name,
            reference_number=target.reference_number,
        ),
        related_elements=related,
        inputs=inputs,
        rag_hits=rag_hits,
    )


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

# Strip DeepSeek-R1 / other reasoning model <think>…</think> blocks.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Balanced JSON object extractor (same logic as llm_client._extract_balanced_json_objects).
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def _parse_raw_for_json(raw: str) -> dict | None:
    """Strip <think> block then extract the first valid JSON object."""
    text = _THINK_RE.sub("", raw).strip()
    # Try direct parse first.
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    # Fall back to extracting the last balanced {...} block.
    blocks = _JSON_OBJECT_RE.findall(text)
    for block in reversed(blocks):
        try:
            result = json.loads(block)
            if isinstance(result, dict):
                return result
        except Exception:
            continue
    return None


def _call_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.35,
    stage: str = "?",
) -> dict | None:
    """Call the LLM in raw mode, strip <think> blocks, parse JSON.

    Uses `llm_router.generate_raw` (no response_format constraint) so that
    reasoning models (DeepSeek-R1, etc.) can emit <think>…</think> before
    their JSON answer. The think block is stripped and the JSON is parsed
    from whatever remains.
    """
    raw = llm_router.generate_raw(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
    )
    if not raw:
        print(f"[PIPE/{stage}] LLM returned empty text")
        return None
    parsed = _parse_raw_for_json(raw)
    if parsed is None:
        print(f"[PIPE/{stage}] No JSON found in response (len={len(raw)})")
    return parsed


def _format_related_elements(related: list[RelatedElement]) -> str:
    if not related:
        return "(none)"
    return "\n".join(f"- {r.name} ({r.reference_number})" for r in related)


def _format_filtered_rag_hits(hits: list[dict]) -> str:
    if not hits:
        return "(none)"
    return "\n".join(
        f"[{i}] {h.get('definition_en', h.get('definition_text', ''))}"
        for i, h in enumerate(hits, 1)
    )


# Inline ref-number guard for Stage 1 — the template reserves the ref-number
# slot for the deterministic post-process; the model must not emit them.
_INLINE_REF_RE = re.compile(r"\s*\(\s*[A-Za-z0-9'\-]{1,10}\s*\)")


def _scrub_inline_refs(text: str) -> str:
    if not text:
        return text
    cleaned = _INLINE_REF_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip().rstrip(",").rstrip(".")


def _fill_prompt(template: str, **placeholders: str) -> str:
    """Substitute {placeholder} tokens in a prompt without using str.format().

    The prompts contain JSON SCHEMA blocks with literal `{...}` braces that
    str.format() would mis-parse as placeholders. Using plain str.replace()
    keeps the SCHEMA braces intact and only substitutes the named keys.
    """
    out = template
    for key, value in placeholders.items():
        out = out.replace("{" + key + "}", value)
    return out


# ---------------------------------------------------------------------------
# Stage 0 — RAG pre-filter
# ---------------------------------------------------------------------------

_STAGE_0_SYSTEM = """You are Stage 0: Context-Aware RAG Pre-Filter for a patent element-definition generator pipeline.

Your task is NOT to draft claims.
Your task is NOT to generate the final definition.
Your task is NOT to perform detailed geometry, relation, or claim-structure analysis.

Your only task is to select the RAG definitions that are useful for defining the TARGET ELEMENT in this specific invention.

You will receive:
1. target_element: The element whose definition will be generated in later stages.
2. invention_disclosure.novel_features: What the invention introduces and which elements are involved.
3. research_report.executive_summary: Problem, solution, and novelty features.
4. inventor_qa.questions_and_answers: Inventor explanations about components.
5. raw_rag_hits: Candidate definitions retrieved from other patents.

SOURCE RULES
Use the executive summary and inventor Q&A as the factual basis for understanding the current invention.
Use RAG hits only as external examples. A RAG hit is not factual evidence about the current invention.

INTERNAL PROCEDURE (do not output chain-of-thought)
Step 1 — Understand the invention context.
Step 2 — Understand the target element (role, subsystem, form).
Step 3 — Evaluate each RAG hit based on compatibility with the target element's role in this invention.

SELECTION RULES
Select a RAG hit if:
- the element name matches or is strongly related, AND
- the definition's general functional/form characteristic fits the target element in this invention.

You may also select a RAG hit with a different name if its function/form is clearly analogous to the target element's role.

Reject a RAG hit if:
- it only matches by name but has a different function.
- it describes a different subsystem.
- it is too generic or semantically incompatible.
- it carries no useful generic content — i.e. the definition is essentially just the element name and a reference number (e.g. "A body (B)", "at least one body (G)") with no form, motion, function, or intrinsic property. Such hits cannot contribute a pattern in Stage 1 and must be rejected even when the name matches.
- it consists only of case-specific placement (e.g. "the X attached to the Y on side Z") with no generic/intrinsic content. Pure geometry belongs to Stage 2, not the generic pattern Stage 1 needs.

OUTPUT
Return strict JSON only. Return ONLY the selected RAG hits. Do not include markdown blocks like ```json.

SCHEMA
{
  "selected_rag_definitions": [
    {
      "rag_hit_id": 1,
      "original_element_name": "string",
      "definition_text": "string"
    }
  ]
}"""

_STAGE_0_PROMPT = _STAGE_0_SYSTEM + """

INPUT

target_element:
{target_element_name}

invention_disclosure.novel_features:
{idf_novel_features}

research_report.executive_summary:
{rr_executive_summary}

inventor_qa.questions_and_answers:
{qa_text}

raw_rag_hits:
{raw_rag_hits_block}"""


def _format_raw_rag_hits_for_stage0(hits: list[dict]) -> str:
    if not hits:
        return "(none)"
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(
            f"rag_hit_id: {i}\n"
            f"original_element_name: {h.get('element_name_en', '')}\n"
            f"patent_title: {h.get('title_en', '')}\n"
            f"definition_text: {h.get('definition_en', '')}\n"
            f"score: {h.get('score', 0)}\n"
            + ("-" * 20)
        )
    return "\n".join(blocks)


def run_stage_0_prefilter(ctx: PipelineContext) -> list[dict]:
    """Select RAG hits compatible with the target element in this invention.

    Returns a subset of `ctx.rag_hits` (original dicts preserved), filtered by
    the LLM's `selected_rag_definitions` list. On LLM failure, returns []
    (downstream Stage 1 will then operate under CASE C/D logic).
    """
    if not ctx.rag_hits:
        return []

    user_prompt = _fill_prompt(
        _STAGE_0_PROMPT,
        target_element_name=ctx.target_element.name,
        idf_novel_features=_placeholder(ctx.inputs.idf_novel_features),
        rr_executive_summary=_placeholder(ctx.inputs.rr_executive_summary),
        qa_text=_placeholder(ctx.inputs.qa_text),
        raw_rag_hits_block=_format_raw_rag_hits_for_stage0(ctx.rag_hits),
    )

    parsed = _call_json("", user_prompt, stage="0")
    if not parsed or not isinstance(parsed.get("selected_rag_definitions"), list):
        return []

    selected_ids: set[str] = set()
    for hit in parsed["selected_rag_definitions"]:
        rid = hit.get("rag_hit_id") if isinstance(hit, dict) else None
        if rid is not None:
            selected_ids.add(str(rid))

    if not selected_ids:
        return []

    filtered = [
        hit for i, hit in enumerate(ctx.rag_hits, 1)
        if str(i) in selected_ids
    ]
    print(f"[PIPE/0] Pre-filter kept {len(filtered)}/{len(ctx.rag_hits)} RAG hits")
    return filtered


# ---------------------------------------------------------------------------
# Stage 1 — Generic / intrinsic characteristics
# ---------------------------------------------------------------------------

_STAGE_1_SYSTEM = """Role: You are Stage 1 of a four-stage patent element-definition generator.

Final definition template: a [name] (ref#), [geometry/relation], [generic characteristics]

Your ONLY task is to produce the [generic characteristics] slot.

WHAT IS THE "GENERIC CHARACTERISTICS" SLOT?
This slot answers one question about the target element:
what is always true about it, regardless of which invention it appears in?

Look at what the sources actually say 
If they describe a physical shape, capture that.
If they describe what it does mechanically, capture that.
If they describe both, combine them into one short clause.
If they describe neither, return empty.

This information may come from RAG hits or from the invention texts —
both are valid sources. If the invention texts explicitly describe the
element's form or function, that takes priority.

Capture what the element fundamentally IS.

SOURCE RULES
RAG Hits — Historical Pattern & Specificity Baseline:
- True Purpose Extraction: Analyze the RAG hits to identify the
  recurring core characteristic that consistently defines this type
  of element across past definitions. Before weighting any hit,
  assess whether its element name matches or is semantically close
  to the target element name. If the hit is for the same part or a
  clear synonym/variant, treat it as high-relevance and prioritize
  its pattern. If the hit is for a clearly different type of part,
  treat it as lower-relevance context and adjust your confidence
  in that pattern accordingly.
- Company Style Benchmark: Treat these hits as the historical company
  standard. Use their level of technical narrowing and specificity as
  your benchmark — not broader, not narrower.
- Avoid Dictionary Phrasing: Do not write generic public-dictionary
  concepts. Match the professional, patent-specific depth found in
  the historical data.

Invention Texts — Validation & Narrowing Filter:
- Targeted Extraction: Scan the invention texts (IDF, RR, QA) for
  sentences that explicitly mention the target element. Do NOT focus on 
  the overall system-level characteristics. Focus strictly on the exact 
  text segments where the specific target element is mentioned, extracting 
  only its core physical form or operational function.
- Synthesis & Narrowing: If the invention texts reveal a specific core 
  characteristic of the element, commit strictly to that text-based 
  characteristic—do NOT attempt to blend, average, or merge it back into 
  a broader, generic RAG pattern. Translate this specific narrowed feature 
  into precise, formal patent terminology without over-generalizing it, 
  ensuring its unique engineering identity is fully preserved.
CRITICAL: When a mention is found in the text, isolate its unique core 
  characteristic and translate the context directly into formal patent 
  language, strictly avoiding informal wording, literal copying, or dilution 
  via broad generalizations.


- RAG Sufficiency: If the target element does not appear in any
  invention text, the RAG hits alone are sufficient. Two or more
  agreeing RAG hits produce a valid output with no invention-text
  confirmation needed.
- Fallback: If neither source provides any form or function
  information, return "" for generic_clause.

MOST CRITICAL PART : Generic Phrase Formulation Rule:
- The generic_clause is a segment within a larger template, not a
  standalone sentence. Write it so it flows naturally when read
  as part of the full definition.
- Start directly with a participle or adjective phrase — the first
  word must immediately convey the element's form or action.
- Do not open with a noun wrapper such as "a device", "a component",
  "a mechanism", "a system", or "means for".
- Avoid disjunctive or open-ended phrasing. Do NOT use "or" to list alternative characteristics. Select and commit to the single, most precise engineering state derived from the sources.

PROCEDURE
1. For each RAG hit, mentally remove placement phrases and neighbor
   names. What remains — the form or action description — is your
   building block.
2. Find the pattern that repeats across multiple hits. Extract the
   primary shared characteristic — the one that appears most
   consistently — at the same level of technical specificity seen
   in the hits. Do not flatten it into a broad generic description,
   and do not merge every unique detail from all hits into one clause.
   One dominant pattern, written at patent depth, is the target.
3. Check invention texts for sentences explicitly naming the target element. If a specific mention is found, trust and prioritize the text's core characteristic entirely, converting it directly into the required patent-style definition format. If no text mention exists, the RAG pattern alone is valid.
4. Write the generic_clause from your building blocks. 
   STYLING RULE: Treat this clause strictly as the fluid, integrated generic segment of a larger definition sentence. Do NOT start with standalone noun wrappers like "a device", "a mechanism", or "a component". It must seamlessly plug into the final template as the intrinsic technical core of the sentence.
   If filtered_rag_hits is non-empty, generic_clause must also be
   non-empty. The only valid reason to return "" is when both
   filtered_rag_hits is empty and invention texts contain no
   form or function data.
5. Copy the exact invention-text sentence into source_sentence if
   used. Leave source_sentence as "" if RAG only.

HARD CONSTRAINTS
- 4 to 10 words. No period at the end.
- No "wherein", "when", or subordinate clauses.
- Do not start with noun wrappers (e.g., "a device", "a component", "a mechanism", "means for").
- Do not include the element name, reference number, or quantity.
- Do not name neighboring components. If a RAG hit links the element
  to a specific neighbor, replace that neighbor with an abstract
  role description. The clause must still carry meaningful technical
  content — never return empty solely because abstraction is required.
OUTPUT
Return strict JSON only. No markdown, no backticks.

confidence:
- "rag+text_based" → Both RAG hits and invention texts provide clear, aligning evidence.
- "rag_based"      → Evidence is derived clearly from RAG hits only.
- "text_based"     → Evidence is derived clearly from invention texts only.
- "none"           → No valid evidence found in either source.

SCHEMA
{
  "target_element": "string",
  "generic_clause": "string",
  "source_sentence": "string",
  "style_source": "rag | text | rag_validated | none",
  "confidence": "rag_based | text_based | rag+text_based | none",
  "evidence_note": "string"
}"""

_STAGE_1_PROMPT = _STAGE_1_SYSTEM + """

INPUT

target_element:
{target_element_name}

filtered_rag_hits:
{rag_hits_block}

invention_disclosure.novel_features:
{idf_novel_features}

research_report.executive_summary:
{rr_executive_summary}

inventor_qa.questions_and_answers:
{qa_text}"""


def _stage_1_fallback(ctx: PipelineContext) -> dict:
    return {
        "target_element": ctx.target_element.name,
        "generic_clause": "",
        "style_source": "none",
        "confidence": "none",
        "evidence_note": "Fallback: LLM output unusable",
    }


def run_stage_1_functional(ctx: PipelineContext) -> dict:
    user_prompt = _fill_prompt(
        _STAGE_1_PROMPT,
        target_element_name=ctx.target_element.name,
        rag_hits_block=_format_filtered_rag_hits(ctx.rag_hits),
        idf_novel_features=_placeholder(ctx.inputs.idf_novel_features),
        rr_executive_summary=_placeholder(ctx.inputs.rr_executive_summary),
        qa_text=_placeholder(ctx.inputs.qa_text),
    )

    parsed = _call_json("", user_prompt, stage="1")
    if not parsed or not isinstance(parsed.get("generic_clause"), str):
        return _stage_1_fallback(ctx)

    clause = _scrub_inline_refs(parsed["generic_clause"].strip().rstrip("."))
    style = parsed.get("style_source", "none")
    conf = parsed.get("confidence", "none")

    if style not in {"rag", "text", "rag_validated", "none"}:
        style = "none" if not clause else "rag"
    if conf not in {"rag_based", "text_based", "rag+text_based", "none"}:
        conf = "rag_based" if clause else "none"

    if not clause:
        conf = "none"
        style = "none"

    return {
        "target_element": ctx.target_element.name,
        "generic_clause": clause,
        "source_sentence": parsed.get("source_sentence", ""),
        "style_source": style,
        "confidence": conf,
        "evidence_note": parsed.get("evidence_note", ""),
    }


# ---------------------------------------------------------------------------
# Stage 2 — Geometry / relation
# ---------------------------------------------------------------------------

_STAGE_2_SYSTEM = """You are Stage 2 of a four-stage patent element-definition generator.

The final definition will follow this template:
    a [name] (ref#), [placement_relation_clause], [generic characteristics]

Your only task is to produce the [placement_relation_clause] slot.

WHAT IS THE "placement_relation_clause" SLOT?
This slot is a short 3D spatial placement and orientation clause. It must describe exactly how the target element physically relates to a neighboring component in THIS specific invention, typically built upon standard relation templates such as:
- located on / positioned on
- spaced apart from / positioned with a clearance from
- rotatably arranged at/on / rotatably located at
- removably mounted to / removably attached to
- extending outwardly from
- arranged sequentially along / arranged in series
- positioned at equal intervals along / equidistantly spaced relative to
- at a predetermined [interval/angle/distance] relative to

THE BLANK CANVAS PRINCIPLE
Imagine a completely blank white canvas. Your clause must provide enough concrete spatial data—strictly leveraging or mirroring the standard relation templates listed above—so that someone who has never seen the drawing can mentally place, snap, or sketch this component directly relative to its neighboring part.

There are no RAG hits in this stage. Use only the provided invention texts.

Do NOT write:
- the target element name or its reference number,
- the element's function, purpose, or intended technical advantage,
- functional clauses expressing what the part actively does (keep it strictly placement-only),
- a full definition.

SOURCE RULES
1. Valid sources only: Use only explicit, declarative sentences where
   the target element itself is directly named. Never extract from
   questions, assumptions, or explanatory text.
   CRITICAL — Name check first: If the target element's exact name does
   not appear in the sentence, the sentence fails Rule 1 immediately —
   stop, do not evaluate further, discard it. Membership in a group
   or system does NOT substitute for the name appearing literally.
   CRITICAL — Subject check: After the name check, ask: is the target
   element the explicit grammatical subject of the sentence's main
   placement verb — not merely the owner of a feature mentioned in the
   sentence? Owning a feature (e.g., "the slots ON the tube") makes
   the tube a surface, not a subject. Discard it.

2. Placement test: A sentence is usable only if it directly answers
   where the target element is located, on which element it sits,
   or in what orientation its body is statically arranged.
   CRITICAL: The sentence must establish a fixed, frozen-in-time 3D
   spatial position. If it describes motion, range of travel, or
   adjustment paths rather than a static physical location, discard it.

3. CRITICAL : No Inference (Strict Interpretation): A sentence is valid ONLY if
   the spatial data is explicitly stated with zero logical deduction.
   If the relationship is implied, incomplete, or only functionally
   suggested, you MUST return "".
   - Signal words that mean Rule 3 is violated: "implies", "suggests",
     "since X is part of", "because X belongs to", "therefore X is".
     If any of these appear in your reasoning, stop and return "".
   - Mechanical Pathways Are Denied: Driving paths (e.g., "A drives B
     through C") express operational force transmission, NOT static
     physical placement. Do not convert functional connections into
     spatial attachments.
   - No Educated Guesses: Never force a clause using common-sense
     layout or typical machine design. The only valid output when
     there is any uncertainty is "".

4. No Transfer (Zero Assembly Inheritance): Spatial data declared for
   a larger assembly, mechanism, or group belongs ONLY to that group.
   - Prohibited Inheritance: Do NOT copy or infer the orientation,
     plane, or location of a system onto the target element just
     because the element is a component of it.
   - Hard check: If the sentence places an assembly or mechanism in
     space but the target element's name does not appear as the
     grammatical subject of that placement, the sentence fails Rule 4.
     The target element's name being absent from the sentence at all
     automatically fails Rules 1 and 4 together.

5. No Inversion (Direction Check): Do not reverse the direction of
   placement. If a sentence places a sub-feature (e.g., an opening,
   slot, channel, or sensor) onto the target element, it defines that
   sub-feature's location — NOT the target element's position.
   Discard it. Owning a feature ≠ being placed somewhere.

CRITICAL: Placement Relation Phrase Formulation Rule:
- The placement_relation_clause is a segment within the final definition, not a standalone sentence. Write it so it flows naturally after the element name and before the generic clause.
- Priority: if the source text contains a static placement that matches one of the standard templates ("located on", "spaced apart from", "rotatably arranged at", "removably mounted to", "extending outwardly from", "arranged sequentially along", "positioned at equal intervals", "installed in place of", "secured to", "attached to"), use that template form.
- If the source contains a clear, explicit, static placement relationship that does NOT map to one of the templates above, you MAY express it using the exact static spatial language from the source text — as long as it passes all SOURCE RULES.
- Do not force a template onto a relationship that does not clearly match it. Do not use the target element name or noun wrappers such as "a component", "a device", or "a mechanism".
- If the physical relation is not 100% clear from the source, you MUST return "".


RELATED ELEMENT REFERENCES
You will receive a related_elements list with names and reference numbers.
If your clause mentions a component from this list, append its reference number in parentheses immediately after its name.
If your clause mentions a component that does not appear in this list, write its name exactly as stated in the source text — do not add a reference number and do not omit it.
Do not add a reference number to the target element itself.
Do not invent or assume a spatial relationship just to produce a reference.
If no valid placement sentence survives the SOURCE RULES, you MUST return "".

HARD CONSTRAINTS
- 2 to 18 words. No period at the end. Be highly economical with word choice.
- No target element name, reference number, or quantity.
- Use ONLY the approved template vocabulary (located on/at, spaced apart from, rotatably arranged at, removably mounted to, extending outwardly from, arranged sequentially along, positioned at equal intervals) or exact static textual equivalents.
- Strictly FORBID any directional or functional tracking phrases (Do NOT use "pointing to", "aiming at", "aligned toward", or "configured to move").
- Zero Assembly Inheritance & Subject Veto: If the target element is not the explicit grammatical subject of a static position, or if the placement belongs to a larger assembly, you MUST return "".
- No active functional verbs, "when", "such that", or subordinate clauses.
- Your clause must come 100% from the runtime inputs — do not reuse terminology from these instructions.

OUTPUT
Return strict JSON only. Do not include markdown blocks like ```json.

SCHEMA
{
  "target_element": "string",
  "geometry_clause": "string",
  "source_sentence": "string",
  "evidence_note": "string"
}"""

_STAGE_2_PROMPT = _STAGE_2_SYSTEM + """

INPUT

target_element:
{target_element_name}

related_elements:
{related_elements_block}

invention_disclosure.novel_features:
{idf_novel_features}

research_report.executive_summary:
{rr_executive_summary}

inventor_qa.questions_and_answers:
{qa_text}"""


def _stage_2_fallback(ctx: PipelineContext) -> dict:
    return {
        "target_element": ctx.target_element.name,
        "geometry_clause": "",
        "evidence_note": "Fallback: LLM output unusable",
    }


def run_stage_2_geometry(ctx: PipelineContext) -> dict:
    user_prompt = _fill_prompt(
        _STAGE_2_PROMPT,
        target_element_name=ctx.target_element.name,
        related_elements_block=_format_related_elements(ctx.related_elements),
        idf_novel_features=_placeholder(ctx.inputs.idf_novel_features),
        rr_executive_summary=_placeholder(ctx.inputs.rr_executive_summary),
        qa_text=_placeholder(ctx.inputs.qa_text),
    )

    parsed = _call_json("", user_prompt, stage="2")
    if not parsed or not isinstance(parsed.get("geometry_clause"), str):
        return _stage_2_fallback(ctx)

    return {
        "target_element": ctx.target_element.name,
        "geometry_clause": parsed["geometry_clause"].strip().rstrip("."),
        "source_sentence": parsed.get("source_sentence", ""),
        "evidence_note": parsed.get("evidence_note", ""),
    }


# ---------------------------------------------------------------------------
# Stage 3 — Deterministic synthesis / assembly
# ---------------------------------------------------------------------------
#
# Stage 3 is intentionally NOT an LLM call. The slot order, comma placement,
# and ref-number position are strict template rules — an LLM tends to drift
# (e.g. emit "a sensor capable of measuring X (6)" instead of
# "capable of measuring X, a sensor (6)"). The template is mechanical, so we
# resolve it mechanically.

_VOWEL_LETTERS = ("a", "e", "i", "o", "u")

# Words that *spell* vowels but *sound* like consonants — break the simple
# first-letter rule. Use longest-match-first.
_CONSONANT_SOUND_PREFIXES = (
    "uni",      # universal, unit, university
    "use",      # used, useful, user
    "user",
    "europe",   # european
    "one",      # one-piece, one-way
)

# Words that *spell* consonants but *sound* like vowels.
_VOWEL_SOUND_PREFIXES = (
    "hour",     # hour, hourly
    "honest",
    "honor",
    "honour",
    "heir",
    "x-",       # x-ray
)


def _select_quantity(element_name: str) -> str:
    """Pick "a" / "an" / "at least one" for the element name.

    Rules:
      - If the name is inherently plural (ends in -s but not -ss/-us/-is,
        or matches a known plural pattern), use "at least one".
      - Otherwise pick "a" or "an" based on initial sound, accounting for
        the common spelling-vs-sound exceptions above.
    """
    if not element_name:
        return "a"

    name = element_name.strip()
    lower = name.lower()

    # Plural detection — terse and rule-based, no NLTK needed.
    if _is_plural_form(lower):
        return "at least one"

    # Sound-based article selection.
    for pref in _VOWEL_SOUND_PREFIXES:
        if lower.startswith(pref):
            return "an"
    for pref in _CONSONANT_SOUND_PREFIXES:
        if lower.startswith(pref):
            return "a"

    return "an" if lower[0] in _VOWEL_LETTERS else "a"


def _is_plural_form(lower_name: str) -> bool:
    """Best-effort plural detection for English noun phrases.

    Triggers "at least one" rather than "a/an". Uses the LAST token because
    a noun phrase like "shoe rods" is plural on the head noun.
    """
    if not lower_name:
        return False
    tokens = lower_name.split()
    head = tokens[-1]

    # Singular endings that LOOK plural — exclude first.
    if head.endswith(("ss", "us", "is", "ous", "ics")):
        return False
    # Singular -ies / -es / -s exceptions that the simple rule below would mis-classify.
    if head in {"series", "species", "axis", "lens", "news"}:
        return False
    # Common irregular plurals.
    if head in {"children", "people", "men", "women", "feet", "teeth", "mice", "geese"}:
        return True
    # -ies plural (bodies, batteries).
    if head.endswith("ies") and len(head) > 4:
        return True
    # -es / -s plural — catches rods, shoes, brushes, etc.
    if head.endswith("es") and len(head) > 3:
        return True
    if head.endswith("s") and len(head) > 2:
        return True
    return False


def _strip_clause(clause: str) -> str:
    """Trim trailing/leading commas, periods and stray whitespace."""
    if not clause:
        return ""
    return clause.strip().strip(",").strip().rstrip(".").rstrip(",").strip()


def run_stage_3_synthesis(
    ctx: PipelineContext,
    generic_clause: str,
    geometry_clause: str,
    stage1_confidence: str = "none",
) -> dict:
    """Deterministically assemble the final candidate.

    Template:
        <quantity> <name> (<ref#>), [geometry], [generic]

    - Name+quantity comes first, then geometry, then generic.
    - Empty clauses are skipped (no trailing double commas).
    - Quantity is auto-selected: a / an / at least one.
    - Confidence is passed through from Stage 1, but downgraded to "none"
      if both clauses are empty.
    """
    geo = _strip_clause(geometry_clause)
    gen = _strip_clause(generic_clause)

    quantity = _select_quantity(ctx.target_element.name)
    name_phrase = f"{quantity} {ctx.target_element.name} ({ctx.target_element.reference_number})"

    parts: list[str] = [name_phrase]
    if geo:
        parts.append(geo)
    if gen:
        parts.append(gen)

    final_text = ", ".join(parts)

    final_conf = stage1_confidence
    if not geo and not gen:
        final_conf = "none"
    if final_conf not in {"high", "medium", "low", "none"}:
        final_conf = "none"

    return {
        "final_candidate": final_text,
        "confidence": final_conf,
        "quantity": quantity,
        "components_used": {
            "geometry_clause": geo,
            "generic_clause": gen,
        },
    }


# ---------------------------------------------------------------------------
# Reference-number injection (deterministic post-process)
# ---------------------------------------------------------------------------

def inject_reference_numbers(
    text: str,
    related_elements: list[RelatedElement],
    target_name: str,
) -> str:
    """Insert (refN) after each related-element name occurrence.

    Rules:
      1. Iterate by descending name length so multi-word names match first.
      2. Match name as a whole word, case-insensitive.
      3. Skip if already followed by ( ... ).
      4. Do NOT inject inside the trailing element phrase (after last comma) —
         that segment already contains the target's own ref number.
    """
    if not text or not related_elements:
        return text

    # New template: "<quantity> <name> (ref#), [geometry], [generic]"
    # The first comma separates the name phrase from the rest.
    # Inject ref numbers only in the segment AFTER the first comma
    # (geometry + generic), never in the leading name phrase.
    first_comma = text.find(",")
    if first_comma == -1:
        return text  # only name phrase, nothing to inject into
    head = text[: first_comma + 1]   # "<quantity> <name> (ref#),"
    tail = text[first_comma + 1:]    # " [geometry], [generic]"

    candidates = [
        r for r in related_elements
        if r.name and r.reference_number and r.name.lower() != target_name.lower()
    ]
    candidates.sort(key=lambda r: len(r.name), reverse=True)

    def _inject_in(segment: str) -> str:
        for r in candidates:
            pattern = re.compile(
                r"\b" + re.escape(r.name) + r"\b(\s*\([^)]*\))?",
                re.IGNORECASE,
            )

            def _sub(m: re.Match) -> str:
                if m.group(1):
                    return m.group(0)
                return f"{m.group(0)} ({r.reference_number})"

            segment = pattern.sub(_sub, segment)
        return segment

    return _inject_in(head) + tail


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_definition(
    db: Session,
    patent_id: int,
    element_id: int,
    top_k: int = 15,
) -> dict | None:
    """Run the full 4-stage pipeline for one element."""
    ctx = build_context(db, patent_id, element_id, top_k=top_k)
    if ctx is None:
        return None

    raw_rag_count = len(ctx.rag_hits)

    # Stage 0 — RAG pre-filter
    filtered_rag = run_stage_0_prefilter(ctx)
    ctx.rag_hits = filtered_rag

    # Stage 1 — Generic / functional
    stage1 = run_stage_1_functional(ctx)

    # Stage 2 — Geometry / relation
    stage2 = run_stage_2_geometry(ctx)

    # Stage 3 — Synthesis (LLM, with deterministic fallback)
    stage3 = run_stage_3_synthesis(
        ctx,
        generic_clause=stage1.get("generic_clause", ""),
        geometry_clause=stage2.get("geometry_clause", ""),
        stage1_confidence=stage1.get("confidence", "none"),
    )

    # Post-process — inject reference numbers for related elements
    final_text = stage3.get("final_candidate", "")
    if final_text:
        final_text = inject_reference_numbers(
            final_text,
            ctx.related_elements,
            target_name=ctx.target_element.name,
        )
        stage3["final_candidate"] = final_text

    return {
        "target_element": ctx.target_element.name,
        "reference_number": ctx.target_element.reference_number,
        "final_candidate": stage3.get("final_candidate", ""),
        "confidence": stage3.get("confidence", "none"),
        "components_used": stage3.get("components_used", {}),
        "stage_outputs": {
            "stage0_prefilter": {
                "raw_hits": raw_rag_count,
                "kept_hits": len(filtered_rag),
            },
            "stage1_functional": stage1,
            "stage2_geometry": stage2,
            "stage3_synthesis": {
                k: v for k, v in stage3.items()
                if k not in ("final_candidate", "components_used")
            },
        },
        "rag_hits": filtered_rag,
    }
