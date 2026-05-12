"""
3-stage definition generator pipeline.

Spec: docs/definition_generator_specification.md

Stage 1 (Functional)  -> uses RAG hits as stylistic reference
Stage 2 (Geometry)    -> uses structured project inputs only, no RAG
Stage 3 (Synthesis)   -> assembles a single candidate using the template
                          [geometry], [function], [quantity] [ref#] [name]

After Stage 3 the orchestrator deterministically injects related-element
reference numbers into the final candidate.

Modularity: each stage is a pure function over the PipelineContext.
  - LLM calls go through `llm_router.call_llm` (auto-selects between
    remote ngrok endpoint and local Ollama).
  - RAG retrieval goes through `chroma_retrieval.retrieve` (2-stage:
    domain -> title filter -> element-name semantic ranking).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.generation import llm_router
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

# Per-field char cap before insertion into prompts; per spec ~1500.
_FIELD_CAP = 1500


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
    # element_patent_analysis is intentionally excluded — it cites prior-art
    # patents (e.g. "US4620680A... bevel gear 20") and the LLM was attributing
    # those competitor mechanisms to the invention. Stick to invention-side
    # sources (BBF fields + executive_summary + Q&A).
    idf_prior_art: str = ""
    idf_closest_prior: str = ""
    idf_novel_features: str = ""
    rr_executive_summary: str = ""
    rr_search_strategy: str = ""
    rr_classification_keywords: str = ""
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


def _focus_sentences(text: str, target_name: str, related_names: list[str], max_sentences: int = 8) -> str:
    """Filter the source text down to the sentences that mention the target
    element (or, failing that, sentences that mention any related element).
    This keeps the model's attention on element-specific evidence rather than
    making it re-read the patent's whole high-level summary."""
    if not text:
        return ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    target_low = target_name.lower()
    target_hits = [s for s in sentences if target_low in s.lower()]
    if target_hits:
        return " ".join(target_hits[:max_sentences])
    # Fall back: keep sentences that mention any related element name.
    rel_low = [r.lower() for r in related_names if r]
    rel_hits = [s for s in sentences if any(r in s.lower() for r in rel_low)]
    if rel_hits:
        return " ".join(rel_hits[:max_sentences])
    # No element-specific signal — return a short head of the original text so
    # the model still has SOME context but isn't drowning in patent-wide text.
    return " ".join(sentences[:max_sentences])


def _placeholder(value: str) -> str:
    """Replace empty inputs with a literal '(none)' so the model never sees a blank label."""
    return value if value else "(none)"


def build_context(
    db: Session,
    patent_id: int,
    element_id: int,
    top_k: int = 5,
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
        idf_closest_prior=_trim(getattr(idf, "closest_prior_patents", "")),
        idf_novel_features=_trim(getattr(idf, "novel_features", "")),
        rr_executive_summary=_trim(getattr(rr, "executive_summary", "")),
        rr_search_strategy=_trim(getattr(rr, "search_strategy", "")),
        rr_classification_keywords=_trim(getattr(rr, "classification_and_keywords", "")),
        qa_text=_trim(getattr(qa, "questions_and_answers", "")),
    )

    # 2-stage retrieval: Stage A picks the top-5 most domain-relevant
    # description titles, Stage B does element-name semantic search
    # restricted to definitions whose title is in that filter set. If
    # the patent has no domain, Stage A is skipped (single-stage fallback).
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

# Match a balanced-looking { ... } block, non-greedy so we can iterate.
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
# Detect prompt-echo: many local-model HTTP wrappers return prompt + generation
# concatenated. We detect by matching the first ~120 chars of the prompt at the
# start of the response and stripping them.
_PROMPT_ECHO_PROBE = 120
# Placeholder text in our prompts that must NEVER appear in valid output.
_PLACEHOLDER_RE = re.compile(r"^<[^>]+>$")


def _strip_prompt_echo(raw: str, prompt: str) -> str:
    """If the response begins with the prompt itself, strip it."""
    if not raw or not prompt:
        return raw
    probe = prompt.strip()[:_PROMPT_ECHO_PROBE]
    if probe and raw.lstrip().startswith(probe):
        # Find the end of the echoed prompt and return everything after it.
        idx = raw.find(prompt.strip())
        if idx >= 0:
            return raw[idx + len(prompt.strip()):].lstrip()
        # Fallback: cut at the end of the OUTPUT marker line in our prompts.
        marker_idx = raw.rfind("OUTPUT (return strict JSON, nothing else)")
        if marker_idx >= 0:
            # Skip past the marker line and the closing brace of the example shape.
            after_marker = raw[marker_idx:]
            close_idx = after_marker.find("\n}")
            if close_idx >= 0:
                return after_marker[close_idx + 2:].lstrip()
    return raw


def _is_placeholder_dict(parsed: dict) -> bool:
    """True if every string value looks like a `<placeholder>` from the prompt."""
    str_values = [v for v in parsed.values() if isinstance(v, str)]
    if not str_values:
        return False
    return all(_PLACEHOLDER_RE.match(v.strip()) for v in str_values if v.strip())


def _try_parse_json(blob: str) -> dict | None:
    blob = blob.strip()
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


# Fallback for LLMs that ignore the JSON contract and emit "LABEL: value" lines.
_LABEL_VALUE_RE = re.compile(
    r'^\s*(?:"|")?(?P<key>[a-z_][a-z0-9_ ]+)(?:"|")?\s*[:=]\s*'
    r'(?:"(?P<qval>[^"]+)"|(?P<bval>.+?))\s*$',
    re.IGNORECASE | re.MULTILINE,
)
# Map free-form labels seen in the wild back to our canonical keys.
_KEY_ALIASES = {
    "functional clause": "functional_clause",
    "function": "functional_clause",
    "geometry clause": "geometry_clause",
    "geometry": "geometry_clause",
    "geometry/relation": "geometry_clause",
    "geometry / relation": "geometry_clause",
    "evidence note": "evidence_note",
    "style source": "style_source",
}


def _parse_label_value_fallback(text: str) -> dict | None:
    """Last-ditch parse for outputs like:
        FUNCTIONAL CLAUSE: "configured to ..."
        Style source: inferred
        Evidence note: ...
    Returns a dict with whatever keys we can recover, or None if nothing found.
    """
    found: dict = {}
    for m in _LABEL_VALUE_RE.finditer(text):
        raw_key = m.group("key").strip().lower()
        canon = _KEY_ALIASES.get(raw_key, raw_key.replace(" ", "_"))
        value = m.group("qval") or m.group("bval") or ""
        value = value.strip().strip('"').strip()
        if value and canon not in found:
            found[canon] = value
    return found or None


def _llm_json(prompt: str, max_tokens: int = 256) -> dict | None:
    """Call the LLM and return parsed JSON, or None on failure.

    Defenses:
      - strip prompt-echo if the response repeats the prompt
      - try strict parse first
      - then iterate every {...} block (last one usually wins for echoing models)
      - reject parsed objects whose values are still the prompt's <placeholders>
    """
    raw = llm_router.call_llm(prompt, max_new_tokens=max_tokens, temperature=0.1)
    if not raw:
        print("[PIPE] LLM returned empty text")
        return None

    stripped = _strip_prompt_echo(raw, prompt).strip()
    print(
        f"[PIPE] Raw LLM output (len={len(raw)}, post-strip={len(stripped)}):\n"
        f"--- BEGIN (post-strip) ---\n{stripped[:1500]}\n--- END ---"
    )
    if not stripped:
        return None

    # 1) Strict parse on the post-strip blob.
    parsed = _try_parse_json(stripped)
    if parsed and not _is_placeholder_dict(parsed):
        print("[PIPE] Strict JSON parse OK")
        return parsed

    # 2) Iterate every {...} block; prefer LATER blocks (real output usually
    #    comes after any echoed contract example) and skip placeholder-only ones.
    blocks = _JSON_OBJECT_RE.findall(stripped)
    for block in reversed(blocks):
        parsed = _try_parse_json(block)
        if parsed and not _is_placeholder_dict(parsed):
            print(f"[PIPE] Extracted-block JSON parse OK (block len={len(block)})")
            return parsed

    # 3) Free-form "LABEL: value" fallback for models that ignore JSON contract.
    parsed = _parse_label_value_fallback(stripped)
    if parsed:
        print(f"[PIPE] Label/value fallback parse OK (keys={list(parsed.keys())})")
        return parsed

    print("[PIPE] No usable output found in LLM response")
    return None


def _format_rag_hits(hits: list[dict]) -> str:
    if not hits:
        return "(none)"
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(
            f"[{i}] element={h.get('element_name_en', '')} | "
            f"score={h.get('score', 0)}\n"
            f"    definition: {h.get('definition_en', '')}\n"
            f"    title: {h.get('title_en', '')}"
        )
    return "\n".join(blocks)


def _format_related_elements(related: list[RelatedElement]) -> str:
    if not related:
        return "(none)"
    return "\n".join(f"- {r.name} ({r.reference_number})" for r in related)


# ---------------------------------------------------------------------------
# Stage 1 — Functional
# ---------------------------------------------------------------------------

_STAGE_1_PROMPT = """SYSTEM
You are a senior patent drafting assistant operating as Stage 1 of a three-stage
definition generator. Your sole responsibility is to produce the FUNCTIONAL
clause of a patent-style element definition. You do not handle geometry,
position, or reference numbering. You do not produce the final definition.

You are working with a small offline language model. Follow the procedure
exactly. Do not improvise. Do not produce content outside the requested JSON.

PROCEDURE
Step 1 — Read the invention source texts (BBF + executive summary + Q&A)
  and identify what the TARGET ELEMENT ITSELF does in THIS invention. Do NOT
  restate the invention's overall purpose. Focus narrowly on this one
  element's specific contribution.
Step 2 — Inspect the retrieved similar definitions as STYLISTIC reference
  only. They come from other patents in the same domain. Borrow the phrasing
  pattern only when the underlying function described by the invention source
  also fits. If a retrieved hit names a mechanism (e.g. "bevel gear",
  "worm drive") that the invention source does NOT mention, do NOT carry that
  mechanism into your output — it belongs to a different invention.
Step 3 — Write a single English functional clause obeying ALL constraints
  below. Then re-read your draft once and remove any violation before output.

HARD CONSTRAINTS (violation = invalid output)
  - LENGTH: maximum 14 words. Be terse, patent-style.
  - PATENT VERBS: start with one of "configured to", "adapted to",
    "operable to", "for ...ing", "providing", "having", "comprising".
  - NO REFERENCE NUMBERS: never write "(3)", "(5a)", "(11)", etc. The system
    will inject reference numbers automatically in a later stage.
  - DO NOT RESTATE THE INVENTION'S OVERALL PURPOSE. Do not echo the
    high-level goal of the patent. Focus narrowly on the TARGET ELEMENT's
    own contribution. If your draft begins to describe what the patent as a
    whole does, rewrite it.
  - NO POSITIONAL LANGUAGE: never use "on", "in", "between", "located",
    "mounted", "extending", "above", "below", "within", "along", "near".
  - NO TARGET NAME: do not repeat "{target_element_name}".
  - SINGLE CLAUSE: no commas, no "and" joining two ideas, no subordinate
    clauses ("when ...", "such that ...", "because ...").
  - NO PERIOD at the end.
  - COMPONENT NAMES: you MAY mention another component only if the name
    appears in (a) the related_elements list below OR (b) the invention
    source texts in the INPUT section. Names that appear only in the
    retrieved similar definitions or in general knowledge are forbidden —
    they are not parts of THIS invention. NEVER add reference numbers next
    to component names — the system injects references later.
  - TECHNICAL CONTENT: every multi-word technical phrase in your clause
    (e.g. mechanism names, action+object pairs, prepositional phrases
    naming a thing) must come from the invention source texts. Do NOT
    transplant such phrases from the retrieved similar definitions, even
    when they sound idiomatic. If the invention source does not describe
    the function in those words, rewrite using the invention's own
    vocabulary — or omit the detail entirely.

related_elements (existing project elements — these get reference numbers automatically):
{forbidden_names_block}

STYLE GUIDE (pattern only, no element-specific examples)
  - Form: <patent_verb> <action_phrase>
  - Patent verbs: "configured to", "adapted to", "operable to", "for ...ing",
    "providing", "having".
  - Action phrase: a short verb-object describing what the target does.
  - Total length: 4–14 words. Single clause, no commas.

ANTI-PATTERNS (must NOT appear in your output)
  ✗ Restating the invention's overall purpose instead of the element's role.
  ✗ Multiple clauses joined by "and" / commas.
  ✗ Mentioning the target name or any reference number.
  ✗ Borrowing a mechanism from a retrieved style example that is not
      described in the invention source texts (this is contamination from
      another patent).
  ✗ Using component names that appear neither in related_elements nor in
      the invention source texts.
  ✗ Subordinate clauses ("when ...", "such that ...", "enabling ...").

INPUT
target_element: {target_element_name}

invention_disclosure.prior_art_and_problems:
{idf_prior_art}

invention_disclosure.novel_features:
{idf_novel_features}

research_report.executive_summary:
{rr_executive_summary}

inventor_qa.questions_and_answers:
{qa_text}

retrieved_similar_definitions (style reference only):
{rag_hits_block}

OUTPUT (return strict JSON, nothing else)
{{
  "target_element": "{target_element_name}",
  "functional_clause": "<one short English clause obeying all hard constraints, or empty string>",
  "style_source": "rag" | "inferred" | "none",
  "evidence_note": "<one sentence>"
}}
"""


def _stage_1_fallback(ctx: PipelineContext) -> dict:
    """Deterministic fallback. Strict: only borrow phrasing from a RAG hit
    whose underlying element name matches the target (case-insensitive) AND
    whose definition reads as a function-only fragment. Otherwise return empty
    so we never fabricate a function for the target from an unrelated hit.
    """
    positional_starts = (
        "located", "disposed", "positioned", "mounted", "between",
        "on the", "in the", "at the", "above", "below", "extending",
    )
    target_name = ctx.target_element.name.strip().lower()
    for hit in ctx.rag_hits[:5]:
        hit_name = (hit.get("element_name_en") or "").strip().lower()
        if hit_name != target_name:
            continue
        defn = (hit.get("definition_en") or "").strip()
        if not defn or len(defn) < 15:
            continue
        if any(defn.lower().startswith(p) for p in positional_starts):
            continue
        cleaned = defn.rstrip(".")
        return {
            "target_element": ctx.target_element.name,
            "functional_clause": cleaned[:300],
            "style_source": "rag",
            "evidence_note": "Fallback: borrowed from same-name RAG hit",
        }
    return {
        "target_element": ctx.target_element.name,
        "functional_clause": "",
        "style_source": "none",
        "evidence_note": "Fallback: no aligned same-name RAG hit and no LLM output",
    }


_RELATED_NAME_PATTERNS_CACHE: dict[str, re.Pattern] = {}


# Strip parenthesized reference numbers from a clause: "(3)", "(5a)", "( 11 )"
_INLINE_REF_RE = re.compile(r"\s*\(\s*[A-Za-z0-9'\-]{1,10}\s*\)")
# Strip dangling preposition+article residue at clause end after ref strip
_TRAIL_PREP_RE = re.compile(
    r"\s*(via|with|by|through|using|by means of)\s+(the|a|an)?\s*$",
    re.IGNORECASE,
)


def _scrub_inline_refs(text: str) -> str:
    """Stage 1 guard: strip any (N) parenthesized reference number the model
    inserted, then trim a dangling 'via the' / 'with a' tail if the strip
    left one. Names of other elements are allowed to remain."""
    if not text:
        return text
    cleaned = _INLINE_REF_RE.sub("", text)
    cleaned = _TRAIL_PREP_RE.sub("", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip().rstrip(",").rstrip(".")


def _forbidden_names_block(related: list[RelatedElement]) -> str:
    if not related:
        return "(none)"
    return ", ".join(f'"{r.name}"' for r in related)


def _focused(ctx: PipelineContext, field: str) -> str:
    related_names = [r.name for r in ctx.related_elements]
    text = getattr(ctx.inputs, field, "")
    return _placeholder(_focus_sentences(text, ctx.target_element.name, related_names))


def _build_invention_corpus(ctx: PipelineContext) -> str:
    """Concatenate invention-side text whose component names are 'real parts
    of THIS invention' and may be referenced by the model.

    Intentionally excludes prior-art-heavy fields (prior_art_and_problems,
    closest_prior_patents) because those name competitor mechanisms we do
    not want attributed to the invention. element_patent_analysis is also
    excluded upstream for the same reason.

    Also includes the names of the project's elements (target + related).
    These names are typically the English translations from the extraction
    pipeline; including them lets the corpus check survive cross-language
    paraphrases (e.g. output says "rotating bar" while the BBF uses Turkish
    "döner çubuk" — the related-elements list still bridges the gap).

    A phrase that appears here is treated as legitimate. A phrase that does
    NOT appear here is treated as a likely hallucination from the retrieved
    style references and gets stripped.
    """
    text_parts = [
        ctx.inputs.idf_novel_features,
        ctx.inputs.rr_executive_summary,
        ctx.inputs.qa_text,
    ]
    name_parts = [ctx.target_element.name]
    name_parts.extend(r.name for r in ctx.related_elements if r.name)
    return " ".join(s for s in text_parts + name_parts if s)


# Words that frequently appear in patent definitions and are SAFE noun targets
# even when they don't match a project's related_elements. Used to whitelist
# common patent vocabulary so we don't false-flag generic terms.
_PATENT_NOUN_WHITELIST = {
    "system", "device", "apparatus", "assembly", "mechanism", "member",
    "component", "element", "structure", "surface", "axis", "force", "motion",
    "rotation", "position", "operation", "action", "movement", "alignment",
    "support", "load", "pressure", "fluid", "gas", "current", "voltage",
    "signal", "data", "shape", "form", "direction", "side", "end", "section",
    "portion", "region", "zone", "area", "interior", "exterior", "front",
    "rear", "top", "bottom", "side", "plane", "axis", "angle", "rotation",
    "linear", "vertical", "horizontal", "lateral", "axial", "radial",
    "diameter", "radius", "length", "width", "height", "thickness",
}

# Heuristic: nouns that look like "specific patent components" — capitalized
# multi-word phrases or hyphenated compounds. We extract these from a clause
# to compare against the allowed names.
_NOUN_CANDIDATE_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9]*(?:[\s\-][A-Z][A-Za-z0-9]*)+\b"  # "Sway Brace Shaft", "4-bar mechanism" partial
)


def _detect_unknown_components(
    text: str,
    allowed_names: list[str],
    invention_corpus: str = "",
) -> list[str]:
    """Find component-like phrases in `text` that are NOT in the allowed list
    and NOT mentioned in the invention's own source corpus.

    A phrase is considered "unknown" (likely hallucinated from style references
    or general knowledge) only if it fails BOTH checks: it isn't in the project's
    element list, and it doesn't appear in any invention-side source text.
    """
    if not text:
        return []
    allowed_low = {n.lower() for n in allowed_names if n}
    corpus_low = invention_corpus.lower() if invention_corpus else ""
    found = set()
    for m in _NOUN_CANDIDATE_RE.findall(text):
        if m.lower() in allowed_low:
            continue
        if corpus_low and m.lower() in corpus_low:
            continue
        found.add(m)
    return sorted(found)


def _strip_unknown_components(
    text: str,
    allowed_names: list[str],
    invention_corpus: str = "",
) -> str:
    """Remove any 'the X' or 'X' span where X is a capitalized multi-word
    phrase that is NOT in the allowed list AND NOT mentioned in the invention
    source corpus. A phrase that appears in the source corpus is treated as a
    real part of THIS invention even if it has not yet been added to the
    element list — its reference number can be injected later by the
    deterministic post-process pass."""
    if not text:
        return text
    allowed_low = {n.lower() for n in allowed_names if n}
    corpus_low = invention_corpus.lower() if invention_corpus else ""
    cleaned = text
    for m in set(_NOUN_CANDIDATE_RE.findall(text)):
        if m.lower() in allowed_low:
            continue
        if corpus_low and m.lower() in corpus_low:
            continue
        # Strip "the M" or "a M" or just "M" (with optional trailing ref).
        pattern = re.compile(
            r"\s*(the\s+|a\s+|an\s+)?" + re.escape(m) + r"(\s*\([^)]*\))?",
            re.IGNORECASE,
        )
        cleaned = pattern.sub("", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip().rstrip(",").rstrip(".")


# Tokens that are template glue in patent prose — articles, prepositions,
# conjunctions, standard patent verbs, generic geometry words. These are SAFE
# to write without source attestation; they're not facts about the invention.
# Anything outside this set is content that must be backed by the invention
# corpus. Set is intentionally domain-neutral so the same check applies to
# every patent.
_TEMPLATE_TOKENS = frozenset({
    # articles & determiners
    "a", "an", "the", "this", "that", "these", "those",
    # prepositions
    "of", "to", "in", "on", "at", "by", "for", "with", "from", "into",
    "onto", "upon", "via", "through", "between", "among", "against",
    "above", "below", "near", "along", "within", "around", "across",
    "over", "under", "about", "during",
    # conjunctions & relatives
    "and", "or", "but", "so", "as", "if", "while", "when", "where",
    "which", "that", "than", "such",
    # auxiliaries / copulas
    "is", "are", "be", "being", "been", "was", "were",
    # patent / drafting verbs
    "configured", "adapted", "operable", "providing", "having",
    "comprising", "including", "located", "disposed", "mounted",
    "positioned", "extending", "spaced", "rotatably", "pivotably",
    "removably", "surrounding", "arranged", "coupled", "connected",
    # comparators / quantifiers / ordinals
    "more", "less", "most", "least", "many", "few", "all", "any", "no",
    "one", "two", "three", "first", "second", "third",
    # generic shape / direction nouns kept as template glue
    "side", "end", "axis", "plane", "direction", "position", "shape",
    "form",
    # auxiliary phrasing
    "thereby", "thereof", "therein", "wherein", "respectively",
})


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


def _content_runs(text: str) -> list[tuple[int, int, str]]:
    """Yield (start, end, phrase) for maximal runs of >=2 consecutive content
    tokens.

    A 'content token' is any 3+-letter word that isn't in _TEMPLATE_TOKENS.
    Single content words are skipped — they're handled by other strips and
    stripping a lone noun usually destroys legitimate output. We target the
    multi-word compounds where contamination tends to live ("bevel gear",
    "aircraft flight", "mechanical clamp").
    """
    matches = list(_TOKEN_RE.finditer(text))
    runs: list[tuple[int, int, str]] = []
    cur_start: int | None = None
    cur_end: int | None = None
    cur_words: list[str] = []
    for m in matches:
        if m.group(0).lower() in _TEMPLATE_TOKENS:
            if cur_start is not None and len(cur_words) >= 2:
                runs.append((cur_start, cur_end, " ".join(cur_words)))
            cur_start = None
            cur_end = None
            cur_words = []
        else:
            if cur_start is None:
                cur_start = m.start()
            cur_end = m.end()
            cur_words.append(m.group(0))
    if cur_start is not None and len(cur_words) >= 2:
        runs.append((cur_start, cur_end, " ".join(cur_words)))
    return runs


def _phrase_supported_by_corpus(phrase: str, corpus_low: str) -> bool:
    """A phrase is supported if either:
      * the whole phrase appears in the corpus (case-insensitive substring),
        OR
      * any of its 2-grams appears in the corpus (handles minor paraphrase).

    Bigram fallback prevents over-stripping when the model rearranges words
    that ARE in the source ("rotation transmission" vs source's "transmission
    of rotation").
    """
    p = phrase.lower()
    if p in corpus_low:
        return True
    words = p.split()
    if len(words) < 2:
        return True  # single-word runs are filtered earlier; safety net
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if bigram in corpus_low:
            return True
    return False


def _strip_unsupported_phrases(text: str, corpus: str) -> tuple[str, list[str]]:
    """Strip multi-word content phrases that don't appear in the invention
    corpus. Catches content-level retrieval contamination that the
    capitalized-component strip misses ("bevel gear", "force aircraft flight",
    "mechanical clamp" when those tokens are individually in the corpus but
    the specific compound is not a real fact about THIS invention).

    Returns (cleaned_text, list_of_stripped_phrases).
    """
    if not text or not corpus:
        return text, []
    corpus_low = corpus.lower()
    runs = _content_runs(text)
    if not runs:
        return text, []
    stripped: list[str] = []
    cleaned = text
    # Walk in reverse so earlier offsets stay valid as we splice the string.
    for start, end, phrase in reversed(runs):
        if _phrase_supported_by_corpus(phrase, corpus_low):
            continue
        cleaned = cleaned[:start] + cleaned[end:]
        stripped.append(phrase)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip().rstrip(",").rstrip(".")
    # Collapse trailing dangling prepositions left behind by the splice.
    cleaned = _TRAIL_PREP_RE.sub("", cleaned).rstrip()
    return cleaned, stripped


def _strip_target_name(text: str, target_name: str) -> str:
    """Stage 1 guard: strip mentions of the target's own name so the LLM's
    leakage doesn't end up in the functional clause."""
    if not text or not target_name:
        return text
    pattern = re.compile(
        r"\s*(the\s+|a\s+|an\s+)?" + re.escape(target_name) + r"(\s*\([^)]*\))?",
        re.IGNORECASE,
    )
    cleaned = pattern.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip().rstrip(",").rstrip(".")


def run_stage_1_functional(ctx: PipelineContext) -> dict:
    prompt = _STAGE_1_PROMPT.format(
        target_element_name=ctx.target_element.name,
        idf_prior_art=_focused(ctx, "idf_prior_art"),
        idf_novel_features=_focused(ctx, "idf_novel_features"),
        rr_executive_summary=_focused(ctx, "rr_executive_summary"),
        qa_text=_focused(ctx, "qa_text"),
        rag_hits_block=_format_rag_hits(ctx.rag_hits),
        forbidden_names_block=_forbidden_names_block(ctx.related_elements),
    )
    parsed = _llm_json(prompt, max_tokens=350)
    if parsed and isinstance(parsed.get("functional_clause"), str):
        clause = parsed["functional_clause"].strip().rstrip(".")
        # Code-side guard: strip any (N) reference numbers the model inserted.
        # Element names are allowed; ref injection runs in Stage 3 post-process.
        scrubbed = _scrub_inline_refs(clause)
        # Strip target's own name (the prompt forbids it but models leak).
        scrubbed = _strip_target_name(scrubbed, ctx.target_element.name)
        # Strip hallucinated component names (e.g. "bevel gear" leaking from
        # a retrieved style example, or names from the model's own knowledge).
        # A name survives the strip if it's either in the project's element
        # list OR it appears in the invention's own source text — the latter
        # lets the LLM legitimately reference parts that the inventor described
        # but haven't been added as elements yet.
        allowed = [r.name for r in ctx.related_elements] + [ctx.target_element.name]
        invention_corpus = _build_invention_corpus(ctx)
        unknown = _detect_unknown_components(scrubbed, allowed, invention_corpus)
        if unknown:
            print(f"[PIPE] Stage 1 stripped hallucinated components: {unknown}")
            scrubbed = _strip_unknown_components(scrubbed, allowed, invention_corpus)
        # Phrase-level contamination guard: catches content compounds (verb
        # objects, multi-noun mechanism names) that the component strip misses
        # because they're lowercase or aren't proper-noun-shaped. This is what
        # blocks "force for aircraft flight" or "mechanical clamp" from
        # leaking out of a retrieved style example into the final clause.
        scrubbed, stripped_phrases = _strip_unsupported_phrases(scrubbed, invention_corpus)
        if stripped_phrases:
            print(f"[PIPE] Stage 1 stripped unsupported content phrases: {stripped_phrases}")
        # Truncate runaway multi-clause output at the first comma.
        if len(scrubbed.split()) > 16:
            first_comma = scrubbed.find(",")
            if first_comma > 0:
                scrubbed = scrubbed[:first_comma].strip()
        # Too-short clauses are not useful.
        if len(scrubbed.split()) < 3:
            scrubbed = ""
        # Source-label honesty: if the model claims "rag" but the evidence_note
        # doesn't mention any retrieved element name, downgrade to "inferred".
        style_source = parsed.get("style_source", "inferred")
        evidence_note = parsed.get("evidence_note", "")
        if style_source == "rag" and ctx.rag_hits:
            mentioned = any(
                (h.get("element_name_en", "") or "").lower() in evidence_note.lower()
                for h in ctx.rag_hits
            )
            if not mentioned:
                style_source = "inferred"
        return {
            "target_element": ctx.target_element.name,
            "functional_clause": scrubbed,
            "style_source": style_source,
            "evidence_note": evidence_note,
        }
    return _stage_1_fallback(ctx)


# ---------------------------------------------------------------------------
# Stage 2 — Geometry / relation
# ---------------------------------------------------------------------------

_STAGE_2_PROMPT = """SYSTEM
You are Stage 2 of a three-stage patent definition generator. Your sole
responsibility is to produce the GEOMETRY/RELATION clause of a patent-style
element definition for THIS specific invention. You do not handle function.
You do not produce the final definition.

You are working with a small offline language model. Follow the procedure
exactly. Do not produce content outside the requested JSON.

PROCEDURE
Step 1 — Read the invention source texts. Look for clues about where the
  TARGET ELEMENT sits and how it relates to neighbouring parts. The
  neighbouring parts may be (a) elements already in related_elements or
  (b) parts described in the invention source texts that have not yet been
  added to the element list.
Step 2 — Write the clause from the target's point of view. The clause must
  describe where THE TARGET IS, not where some other part is.
Step 3 — Reference number rule:
    * If a mentioned part IS in related_elements, write its reference
      number in parentheses next to its name, e.g. "the body (5)".
    * If a mentioned part is only in the source texts (not yet in
      related_elements), write its name WITHOUT a reference number — the
      system will inject one later if/when it is added as an element.
Step 4 — Re-read your draft once and remove any violation before output.

HARD CONSTRAINTS (violation = invalid output)
  - LENGTH: maximum 15 words.
  - SINGLE CLAUSE: no subordinate descriptive clauses
    ("when the aircraft is viewed from the front", "such that ...",
    "in such a way that ...", "because ..."). Just the bare position.
  - SUBJECT IS THE TARGET: the clause describes where {target_element_name}
    is. It must NOT have another element as its grammatical subject.
    Forbidden: "the X is mounted on Y", "the X extends along Y".
  - NO FUNCTIONAL VERBS: "configured to", "adapted to", "for ...ing",
    "providing" are FORBIDDEN here.
  - NO TARGET NAME: do not repeat "{target_element_name}".
  - COMPONENT NAMES: only mention parts that appear in related_elements OR
    in the invention source texts above. Do not invent names from outside
    knowledge.
  - START with one of: "located", "disposed", "mounted", "positioned",
    "between", "extending", "spaced", "rotatably", "pivotably", "removably",
    "surrounding", "arranged".
  - NO PERIOD at the end.
  - DO NOT COPY VERBATIM from the source documents. Paraphrase into a single
    bare positional clause. If the source says "positioned along the vertical
    plane when the aircraft is viewed from the front", you write only
    "positioned along the vertical plane".
  - If no clear positional evidence exists in inputs, geometry_clause MUST
    be empty.

INPUT
target_element: {target_element_name}

related_elements (name and reference number):
{related_elements_block}

invention_disclosure.prior_art_and_problems:
{idf_prior_art}

invention_disclosure.novel_features:
{idf_novel_features}

research_report.executive_summary:
{rr_executive_summary}

inventor_qa.questions_and_answers:
{qa_text}

OUTPUT (return strict JSON, nothing else)
{{
  "target_element": "{target_element_name}",
  "geometry_clause": "<one short English clause obeying all hard constraints, or empty string>",
  "evidence_note": "<one sentence>"
}}
"""

_GEOMETRY_KEYWORDS = (
    "located", "disposed", "mounted", "positioned", "between", "on the",
    "in the", "above", "below", "extending", "spaced", "rotatably",
    "pivotably", "removably", "surrounding", "arranged",
)


def _stage_2_fallback(ctx: PipelineContext) -> dict:
    """Lightweight rule-based scan over project documents looking for sentences
    that mention the target name AND a related-element name AND a relation
    keyword. Returns the cleaned sentence or empty.
    """
    sources = " ".join(
        s for s in (
            ctx.inputs.idf_prior_art,
            ctx.inputs.idf_novel_features,
            ctx.inputs.rr_executive_summary,
            ctx.inputs.qa_text,
        ) if s
    )
    if not sources:
        return {
            "target_element": ctx.target_element.name,
            "geometry_clause": "",
            "evidence_note": "Fallback: no source text and no LLM output",
        }

    target_lower = ctx.target_element.name.lower()
    related_names_lower = [r.name.lower() for r in ctx.related_elements if r.name]

    for raw_sentence in re.split(r"(?<=[.!?])\s+", sources):
        s_lower = raw_sentence.lower()
        if target_lower not in s_lower:
            continue
        if not any(k in s_lower for k in _GEOMETRY_KEYWORDS):
            continue
        if not any(rn in s_lower for rn in related_names_lower):
            continue
        cleaned = raw_sentence.strip().rstrip(".")
        return {
            "target_element": ctx.target_element.name,
            "geometry_clause": cleaned[:300],
            "evidence_note": "Fallback: rule-based extraction from source documents",
        }

    return {
        "target_element": ctx.target_element.name,
        "geometry_clause": "",
        "evidence_note": "Fallback: no matching sentence in source documents",
    }


_SUBORDINATE_PATTERNS = (
    re.compile(r",?\s*when\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*such that\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*in such a way that\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*because\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*enabling\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*so that\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*as viewed\b[^,]*", re.IGNORECASE),
    re.compile(r",?\s*viewed from\b[^,]*", re.IGNORECASE),
)


def _strip_subordinate_clauses(text: str) -> str:
    cleaned = text
    for pat in _SUBORDINATE_PATTERNS:
        cleaned = pat.sub("", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip().rstrip(",").rstrip(".")


def run_stage_2_geometry(ctx: PipelineContext) -> dict:
    prompt = _STAGE_2_PROMPT.format(
        target_element_name=ctx.target_element.name,
        related_elements_block=_format_related_elements(ctx.related_elements),
        idf_prior_art=_focused(ctx, "idf_prior_art"),
        idf_novel_features=_focused(ctx, "idf_novel_features"),
        rr_executive_summary=_focused(ctx, "rr_executive_summary"),
        qa_text=_focused(ctx, "qa_text"),
    )
    parsed = _llm_json(prompt, max_tokens=350)
    if parsed and isinstance(parsed.get("geometry_clause"), str):
        clause = parsed["geometry_clause"].strip().rstrip(".")
        # Code-side guard: even with the prompt rule, models sometimes copy
        # verbose subordinate clauses verbatim from source text. Strip them.
        clause = _strip_subordinate_clauses(clause)
        # Drop any trailing stray digits (token corruption: "...vertical plane\n3")
        clause = re.sub(r"\s+\d+\s*$", "", clause).strip()
        # Strip hallucinated components, but keep parts that appear in the
        # invention source text even if they aren't elements yet — those are
        # real parts the inventor described, and the geometry clause should
        # be allowed to reference them.
        allowed = [r.name for r in ctx.related_elements] + [ctx.target_element.name]
        invention_corpus = _build_invention_corpus(ctx)
        unknown = _detect_unknown_components(clause, allowed, invention_corpus)
        if unknown:
            print(f"[PIPE] Stage 2 stripped hallucinated components: {unknown}")
            clause = _strip_unknown_components(clause, allowed, invention_corpus)
        # Same phrase-level contamination guard as Stage 1 — blocks lowercase
        # compound mechanisms ("worm drive", "lead screw") and prepositional
        # phrases ("force for the aircraft flight") that don't actually
        # describe THIS invention's geometry.
        clause, stripped_phrases = _strip_unsupported_phrases(clause, invention_corpus)
        if stripped_phrases:
            print(f"[PIPE] Stage 2 stripped unsupported content phrases: {stripped_phrases}")
        # If the clause is too long (>20 words after cleanup) it's still verbose;
        # truncate at the first comma to keep only the primary positional phrase.
        if len(clause.split()) > 20:
            first_comma = clause.find(",")
            if first_comma > 0:
                clause = clause[:first_comma].strip()
        return {
            "target_element": ctx.target_element.name,
            "geometry_clause": clause,
            "evidence_note": parsed.get("evidence_note", ""),
        }
    return _stage_2_fallback(ctx)


# ---------------------------------------------------------------------------
# Stage 3 — Synthesis
# ---------------------------------------------------------------------------

_STAGE_3_PROMPT = """SYSTEM
You are Stage 3 of a three-stage patent definition generator. Your sole
responsibility is to combine a pre-written FUNCTIONAL clause and a pre-written
GEOMETRY/RELATION clause into ONE final patent-style English definition for
the target element, following a strict template.

You do not invent function. You do not invent geometry. You do not add new
content. You only assemble, smooth, and finalize.

TEMPLATE
[geometry/relation], [function], [quantity phrase] [reference number] [component name]

Allowed quantity phrasings: "at least one", "a", "" (no quantity word)
Pick the most natural phrasing for this element. The element phrase MUST be
the LAST segment of the candidate.

PROCEDURE
Step 1 — Read both clauses. If one is empty, omit that segment.
Step 2 — Light smoothing only (joining words, punctuation, removing duplicate
  phrasing). Do not paraphrase heavily. Preserve any reference numbers
  already present inside the clauses.
Step 3 — Choose the quantity phrase. If unsure, use "a".
Step 4 — Assemble the final candidate using the template:
  - join with commas
  - element phrase last
  - no period at the end
  - single line
  - no preface, no quotes around the result, no explanatory text

INPUT
target_element_name: {target_element_name}
target_element_reference_number: {target_element_reference_number}

geometry_clause: {geometry_clause}
functional_clause: {functional_clause}

OUTPUT (return strict JSON, nothing else)
{{
  "target_element": "{target_element_name}",
  "reference_number": "{target_element_reference_number}",
  "final_candidate": "<final English definition string>",
  "components_used": {{
    "geometry_clause": "{geometry_clause}",
    "functional_clause": "{functional_clause}"
  }}
}}
"""


def run_stage_3_synthesis(
    ctx: PipelineContext,
    functional_clause: str,
    geometry_clause: str,
) -> dict:
    """Deterministic assembly per spec: Stage 3 is mechanical (template fill,
    clause concatenation), so we do NOT delegate to the LLM. This eliminates
    the hallucination risk and the dropped-element-phrase failure mode.

    Template: [geometry], [function], a [name] ([ref#])
    """
    if not functional_clause and not geometry_clause:
        return {
            "target_element": ctx.target_element.name,
            "reference_number": ctx.target_element.reference_number,
            "final_candidate": "",
            "components_used": {
                "geometry_clause": "",
                "functional_clause": "",
            },
            "message": "Insufficient evidence to generate a definition",
        }

    parts: list[str] = []
    if geometry_clause:
        parts.append(geometry_clause.strip().rstrip(",").rstrip("."))
    if functional_clause:
        parts.append(functional_clause.strip().rstrip(",").rstrip("."))
    parts.append(
        f"a {ctx.target_element.name} ({ctx.target_element.reference_number})"
    )
    final = ", ".join(parts)

    return {
        "target_element": ctx.target_element.name,
        "reference_number": ctx.target_element.reference_number,
        "final_candidate": final,
        "components_used": {
            "geometry_clause": geometry_clause,
            "functional_clause": functional_clause,
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

    Rules from spec:
      1. Iterate by descending name length so multi-word names match first.
      2. Match name as a whole word, case-insensitive.
      3. Skip if already followed by ( <digits or alphanumerics> ).
      4. Do NOT inject the target element's own ref number through this pass.
      5. Do NOT inject inside the trailing element phrase
         (the segment after the last comma).
    """
    if not text or not related_elements:
        return text

    # Split off the trailing element phrase (last comma-segment).
    last_comma = text.rfind(",")
    if last_comma == -1:
        head, tail = "", text
    else:
        head = text[: last_comma + 1]
        tail = text[last_comma + 1:]

    # Sort related by descending name length.
    candidates = [
        r for r in related_elements
        if r.name and r.reference_number and r.name.lower() != target_name.lower()
    ]
    candidates.sort(key=lambda r: len(r.name), reverse=True)

    def _inject_in(segment: str) -> str:
        for r in candidates:
            # Whole-word, case-insensitive match for the element name.
            pattern = re.compile(
                r"\b" + re.escape(r.name) + r"\b(\s*\([^)]*\))?",
                re.IGNORECASE,
            )

            def _sub(m: re.Match) -> str:
                # If already followed by ( ... ), leave it alone.
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
    top_k: int = 5,
) -> dict | None:
    """Run the full 3-stage pipeline for one element."""
    ctx = build_context(db, patent_id, element_id, top_k=top_k)
    if ctx is None:
        return None

    stage1 = run_stage_1_functional(ctx)
    stage2 = run_stage_2_geometry(ctx)
    stage3 = run_stage_3_synthesis(
        ctx,
        functional_clause=stage1.get("functional_clause", ""),
        geometry_clause=stage2.get("geometry_clause", ""),
    )

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
        "components_used": stage3.get("components_used", {}),
        "stage_outputs": {
            "stage1_functional": stage1,
            "stage2_geometry": stage2,
            "stage3_synthesis": {
                k: v for k, v in stage3.items()
                if k not in ("final_candidate", "components_used")
            },
        },
        "rag_hits": ctx.rag_hits,
        "message": stage3.get("message"),
    }
