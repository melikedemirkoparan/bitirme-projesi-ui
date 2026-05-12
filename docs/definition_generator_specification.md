# Definition Generator Specification

## Purpose
This module generates a **single patent-style definition candidate** for a target element, using a strictly staged pipeline that separates *what the part does* (function) from *where and how it sits* (geometry), and only fuses them in a final synthesis step.

The generator is designed for **small offline LLMs (7B–14B class)**. The architecture compensates for limited model capacity by:

- decomposing reasoning into narrow, single-purpose stages
- restricting each stage to a clearly bounded I/O contract
- forbidding free-form speculation
- treating retrieval evidence as **stylistic reference only**, never as ground truth
- moving deterministic operations (reference number injection, template assembly checks) out of the LLM and into code

---

## High-level architecture

The pipeline has exactly **three stages**:

| Stage | Name              | Produces                                                  | Uses RAG? |
|-------|-------------------|-----------------------------------------------------------|-----------|
| 1     | Functional        | Functional definition fragment (function only)            | Yes       |
| 2     | Geometry/Relation | Geometry/positional fragment (relations only)             | No        |
| 3     | Synthesis         | One final candidate definition + reference-number inject  | No        |

Each stage has:
- a strict input contract
- a strict output contract
- a prompt that pins the model to a single bounded task
- a deterministic fallback when the LLM output is malformed or empty

The output of Stage 3 is **a single candidate definition** — not multiple variants.

---

## Shared inputs (built once, reused across stages)

Before the pipeline runs, the orchestrator assembles a single normalized context object:

```
PipelineContext {
  target_element: { name: str, reference_number: int | null },
  related_elements: [ { name: str, reference_number: int | null }, ... ],
  invention_disclosure: {
    prior_art_and_problems: str,
    closest_prior_patents: str,
    novel_features: str
  },
  research_report: {
    executive_summary: str,
    search_strategy: str,
    classification_and_keywords: str,
    element_patent_analysis: str
  },
  inventor_qa: {
    questions_and_answers: str
  },
  rag_hits: [
    { element_name_en: str, definition_en: str, title_en: str, context_en: str, score: float },
    ...
  ]
}
```

`rag_hits` are produced by a **2-stage ChromaDB retrieval** (`app/retrieval/chroma_retrieval.py`):

- **Stage A — domain → titles.** The patent's free-text `domain` field is semantically searched against the `patent_description_title_en` collection. Up to 5 **distinct** titles whose cosine similarity is above the threshold (`SIMILARITY_THRESHOLD`, default 0.55) are kept as a filter set. If `domain` is empty, this stage is skipped.
- **Stage B — element_name → filtered definitions.** The target element name is semantically searched against the `patent_definition_en` collection, restricted by `where description_title_en $in [Stage A titles]`. Results are returned as `rag_hits`.

If domain is provided but Stage A finds nothing above threshold, Stage B falls back to an unfiltered search so a novel domain term does not kill the suggestion entirely.

`rag_hits` are passed *only* into Stage 1 and only as stylistic reference — never as factual content.

All free-text fields must be **trimmed and bounded** before being inserted into prompts (suggested per-field cap: ~1500 chars; per-prompt cap: ~6000 chars). If a field is empty, the orchestrator passes the literal token `(none)` so the model never sees an unlabeled blank.

---

## Stage 1 — Functional candidate

### Goal
Produce a short English clause describing **what the target element functionally does inside this specific invention**.

The model must:

1. read the structured invention/project inputs **first**
2. infer the function of the target element from *this* invention's evidence
3. only then look at the RAG hits, treating them as **style/pattern reference**
4. adopt phrasing from a RAG hit only if its underlying function genuinely matches the function inferred in step 2
5. write the functional clause

### Inputs
- `target_element.name`
- `invention_disclosure.*`
- `research_report.executive_summary`
- `research_report.element_patent_analysis`
- `inventor_qa.questions_and_answers`
- `rag_hits` (top-K, already domain-filtered by name)

### Forbidden in Stage 1 output
- positional, locational, or relational language ("located on", "between", "extending from", etc.)
- reference numbers of any element (target or other)
- restating the target element's name
- ending with a period
- writing more than one clause

### Output contract
```json
{
  "target_element": "<name>",
  "functional_clause": "<single English clause, comma-joinable>",
  "style_source": "rag" | "inferred" | "none",
  "evidence_note": "<short justification, 1 sentence>"
}
```

If the evidence is too weak to commit to a function:
```json
{
  "target_element": "<name>",
  "functional_clause": "",
  "style_source": "none",
  "evidence_note": "Insufficient functional evidence in inputs"
}
```

### Stage 1 prompt

```
SYSTEM
You are a senior patent drafting assistant operating as Stage 1 of a three-stage
definition generator. Your sole responsibility is to produce the FUNCTIONAL
clause of a patent-style element definition. You do not handle geometry,
position, or reference numbering. You do not produce the final definition.

You are working with a small offline language model. Follow the procedure
exactly. Do not improvise. Do not produce content outside the requested JSON.

PROCEDURE
Step 1 — Read the invention evidence.
  Carefully read the invention disclosure, research report, and inventor Q&A.
  Identify what the target element does inside THIS invention: what role it
  plays, what problem it addresses, what behavior it provides.

Step 2 — Form an internal hypothesis of the function.
  State to yourself, in one sentence, the function of the target element in
  this specific invention. Do not write this sentence in the output.

Step 3 — Inspect the retrieved similar definitions.
  Each RAG hit is a definition written for some other element in some other
  patent. Treat them ONLY as stylistic and lexical reference.

Step 4 — Decide whether any RAG hit is functionally aligned.
  A RAG hit is "aligned" only if its underlying function clearly matches the
  function you inferred in Step 2. High similarity score is NOT enough; the
  function must actually match. If no RAG hit aligns, ignore them.

Step 5 — Write the functional clause.
  - Output a single English clause that states the function.
  - Use patent-style phrasing such as "configured to ...", "adapted to ...",
    "operable to ...", "for ...ing ...", "providing ...".
  - The clause must be joinable with a leading comma (e.g. it should fit at
    the position of [F] in: "<geometry>, [F], <element phrase>").
  - Do NOT mention any other element's reference number.
  - Do NOT mention position, location, attachment, extent, orientation,
    spacing, or any geometric relation.
  - Do NOT repeat the target element's name.
  - Do NOT end with a period.
  - One clause only.

Step 6 — Choose the style source label.
  - "rag" if you adopted phrasing from an aligned RAG hit
  - "inferred" if you wrote it purely from the invention evidence
  - "none" if you cannot commit to a function

If evidence is insufficient, return an empty functional_clause and
style_source = "none". Do not fabricate.

INPUT
target_element: {target_element_name}

invention_disclosure.prior_art_and_problems:
{idf_prior_art}

invention_disclosure.novel_features:
{idf_novel_features}

research_report.executive_summary:
{rr_executive_summary}

research_report.element_patent_analysis:
{rr_element_patent_analysis}

inventor_qa.questions_and_answers:
{qa_text}

retrieved_similar_definitions (style reference only):
{rag_hits_block}

OUTPUT (return strict JSON, nothing else)
{
  "target_element": "{target_element_name}",
  "functional_clause": "<one short English clause or empty string>",
  "style_source": "rag" | "inferred" | "none",
  "evidence_note": "<one sentence>"
}
```

### Deterministic fallback (Stage 1)
If the LLM call fails or returns malformed JSON:

1. If at least one RAG hit has score ≥ threshold and its `definition_en` parses cleanly into a function-only fragment (no comma-leading positional pattern), reuse a sanitized version of that fragment.
2. Otherwise, return empty `functional_clause` with `style_source: "none"`.

The fallback must never invent functional content from nothing.

---

## Stage 2 — Geometry / relation candidate

### Goal
Produce a short English clause describing **where the target element sits and how it relates to other components**, derived strictly from the project documents and the related-elements list.

This stage **does not use RAG**. Geometry is invention-specific and historical retrieval is not a reliable source for it.

### Inputs
- `target_element.name`
- `related_elements` (with names and reference numbers)
- `invention_disclosure.*`
- `research_report.executive_summary`
- `research_report.element_patent_analysis`
- `inventor_qa.questions_and_answers`

### Forbidden in Stage 2 output
- functional language ("configured to ...", "adapted to ...", "for ...ing")
- restating the target element's name
- ending with a period
- writing more than one clause
- inventing related elements not present in `related_elements`

### Allowed and encouraged
- using related elements' names and reference numbers, e.g. `on the body (5)`, `between the body (5) and the table (8)`
- standard patent geometry patterns:
  - located on / disposed on / mounted on
  - located between / positioned between
  - spaced apart from / at a distance from
  - rotatably positioned / pivotably attached / removably attached
  - extending outward from / extending along / extending through
  - arranged in sequence / positioned at equal intervals / surrounding

### Output contract
```json
{
  "target_element": "<name>",
  "geometry_clause": "<single English clause, comma-joinable>",
  "evidence_note": "<short justification, 1 sentence>"
}
```

If no geometric relation can be inferred from inputs, return empty:
```json
{
  "target_element": "<name>",
  "geometry_clause": "",
  "evidence_note": "No positional or relational evidence in inputs"
}
```

### Stage 2 prompt

```
SYSTEM
You are Stage 2 of a three-stage patent definition generator. Your sole
responsibility is to produce the GEOMETRY/RELATION clause of a patent-style
element definition for THIS specific invention. You do not handle function.
You do not produce the final definition.

You are working with a small offline language model. Follow the procedure
exactly. Do not improvise. Do not produce content outside the requested JSON.

PROCEDURE
Step 1 — Read the invention evidence.
  Read the invention disclosure, research report, and inventor Q&A. Look ONLY
  for clues about position, attachment, spacing, orientation, extent, and
  inter-part relations involving the target element.

Step 2 — Match against the related elements list.
  Use ONLY the elements present in the related_elements list when writing
  geometric relations. Do not invent components. When you reference another
  element, write its reference number in parentheses next to its name, e.g.
  "the body (5)".

Step 3 — Identify standard relation patterns.
  Prefer patent-conventional phrasings:
  - located on / disposed on / mounted on / positioned on
  - located between / positioned between
  - spaced apart from / at a distance from
  - rotatably positioned / pivotably attached / removably attached
  - extending outward from / extending along / extending through
  - arranged in sequence / positioned at equal intervals / surrounding

Step 4 — Write the geometry clause.
  - Output a single English clause that states position/relation only.
  - The clause must be joinable with a trailing comma (e.g. it should fit at
    the position of [G] in: "[G], <function>, <element phrase>").
  - Do NOT include any functional language ("configured to", "adapted to",
    "for ...ing", "providing").
  - Do NOT repeat the target element's name.
  - Do NOT end with a period.
  - One clause only.

If no positional or relational evidence exists in the inputs, return empty
geometry_clause. Do not fabricate.

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

research_report.element_patent_analysis:
{rr_element_patent_analysis}

inventor_qa.questions_and_answers:
{qa_text}

OUTPUT (return strict JSON, nothing else)
{
  "target_element": "{target_element_name}",
  "geometry_clause": "<one short English clause or empty string>",
  "evidence_note": "<one sentence>"
}
```

### Deterministic fallback (Stage 2)
If the LLM output is malformed or empty:

1. Run a lightweight rule-based scan on the project documents for sentences containing the target element name AND any related-element name AND any keyword from the standard relation pattern list.
2. If a clean match is found, return its translated/cleaned form.
3. Otherwise, return empty `geometry_clause`.

The fallback must never invent geometric relations from nothing.

---

## Stage 3 — Final synthesis

### Goal
Combine the Stage 1 functional clause and the Stage 2 geometry clause into **one** final candidate definition that follows the project's required template.

After the model produces the final clause, the orchestrator runs a deterministic post-processing pass that injects reference numbers next to any related-element name appearing in the output.

### Inputs
- `target_element.name`
- `target_element.reference_number`
- `related_elements`
- `functional_clause` (from Stage 1)
- `geometry_clause` (from Stage 2)

### Final definition template
```
[geometry/relation], [function], [quantity phrase] [reference number] [component name]
```

Allowed quantity phrasings (chosen by the model based on plausibility):
- `at least one <name> (<ref>)`
- `a <name> (<ref>)`
- `<name> (<ref>)`

The element phrase **must appear at the end** of the candidate.

### Synthesis rules
- If `geometry_clause` is empty, omit the geometry segment and start with the functional clause.
- If `functional_clause` is empty, omit the functional segment.
- If both are empty, return an explicit insufficient-evidence result.
- The final candidate must be a single sentence (one comma-separated clause string), no period at the end.

### Output contract
```json
{
  "target_element": "<name>",
  "reference_number": <int|null>,
  "final_candidate": "<final English definition string>",
  "components_used": {
    "geometry_clause": "<from Stage 2>",
    "functional_clause": "<from Stage 1>"
  }
}
```

If both clauses are empty:
```json
{
  "target_element": "<name>",
  "reference_number": <int|null>,
  "final_candidate": "",
  "components_used": { "geometry_clause": "", "functional_clause": "" },
  "message": "Insufficient evidence to generate a definition"
}
```

### Stage 3 prompt

```
SYSTEM
You are Stage 3 of a three-stage patent definition generator. Your sole
responsibility is to combine a pre-written FUNCTIONAL clause and a pre-written
GEOMETRY/RELATION clause into ONE final patent-style English definition for
the target element, following a strict template.

You do not invent function. You do not invent geometry. You do not add new
content. You only assemble, smooth, and finalize.

You are working with a small offline language model. Follow the procedure
exactly. Do not produce content outside the requested JSON.

TEMPLATE
[geometry/relation], [function], [quantity phrase] [reference number] [component name]

Allowed quantity phrasings:
  - "at least one"
  - "a"
  - "" (no quantity word, just the bare name)
Choose the phrasing that reads most naturally for the target element. The
element phrase MUST be the last segment of the candidate.

PROCEDURE
Step 1 — Read the two pre-written clauses.
  geometry_clause: invention-specific positional/relational fragment
  functional_clause: invention-specific functional fragment

Step 2 — Validate clause shapes.
  - If geometry_clause is empty, you will omit the geometry segment.
  - If functional_clause is empty, you will omit the function segment.
  - Do not paraphrase the clauses heavily. Light smoothing only (joining
    words, punctuation, removing duplicate phrasing). Preserve any reference
    numbers already present inside the clauses.

Step 3 — Choose the quantity phrase.
  Pick the phrasing that fits the element naturally. If unsure, use "a".

Step 4 — Assemble the final candidate using the template.
  - Join with commas.
  - Element phrase is last.
  - No period at the end.
  - Output a single line.
  - Do NOT add any explanatory text, no preface, no quotes around the result.

INPUT
target_element_name: {target_element_name}
target_element_reference_number: {target_element_reference_number}

geometry_clause: {geometry_clause}
functional_clause: {functional_clause}

OUTPUT (return strict JSON, nothing else)
{
  "target_element": "{target_element_name}",
  "reference_number": {target_element_reference_number},
  "final_candidate": "<final English definition string>",
  "components_used": {
    "geometry_clause": "{geometry_clause}",
    "functional_clause": "{functional_clause}"
  }
}
```

### Deterministic fallback (Stage 3)
If the LLM call fails or returns malformed JSON, the orchestrator assembles the candidate directly:

```
<geometry_clause>, <functional_clause>, a <element_name> (<reference_number>)
```

with empty segments dropped and commas normalized. This always succeeds when at least one clause is present.

---

## Reference-number injection (post-processing)

After Stage 3 produces the final candidate (whether via LLM or deterministic fallback), the orchestrator runs a **post-processing pass** that scans the candidate text for occurrences of any related element's name and inserts that element's reference number in parentheses immediately after the name.

### Rules
1. Iterate `related_elements` in order of **descending name length** (so multi-word names match before substrings).
2. For each related element with a non-null reference number:
   - Match the element name as a whole word, case-insensitive.
   - Skip the match if it is already followed by `(<digits>)`.
   - Insert ` (<reference_number>)` directly after the matched name.
3. Do NOT inject the **target element's** own reference number through this pass — the template already places it at the end.
4. Do NOT double-inject if the LLM already placed the number correctly.
5. Do NOT inject inside the trailing element phrase (the segment after the last comma).

### Example
Functional clause: `configured to support the optical subsystem along the table`
Geometry clause: `mounted on the body and aligned with the sensor`
Related elements: `body → 5`, `table → 8`, `sensor → 3`
Target: `bracket → 12`

Pre-injection candidate:
```
mounted on the body and aligned with the sensor, configured to support the optical subsystem along the table, a bracket (12)
```

Post-injection candidate:
```
mounted on the body (5) and aligned with the sensor (3), configured to support the optical subsystem along the table (8), a bracket (12)
```

This rule guarantees deterministic, model-independent reference numbering.

---

## Prompt-engineering principles for offline LLMs

These principles apply to all three stage prompts:

1. **Single-task framing.** Each prompt declares exactly one stage and one output. The system message explicitly forbids the model from doing other stages' work.
2. **Hard procedural ladder.** Steps are numbered and ordered. The model is told to follow them sequentially.
3. **Strict JSON output contract.** Every prompt ends with the literal output shape and the instruction "return strict JSON, nothing else".
4. **Negative constraints first-class.** "Do NOT" rules are listed explicitly with concrete forbidden patterns, not just abstract guidance.
5. **Empty-output permitted.** When evidence is insufficient, the model is instructed to return an empty field rather than fabricate. This is repeated across stages.
6. **Bounded inputs.** All free-text inputs are trimmed before insertion. Empty fields are passed as `(none)`.
7. **Style separation.** RAG evidence is always labeled "stylistic reference only", never "ground truth".
8. **Determinism for mechanical operations.** Reference number injection, template assembly, and clause concatenation are handled in code, never delegated to the LLM.
9. **Per-stage fallback.** Every stage has a deterministic fallback so the pipeline produces a usable result even with an unreliable model.

---

## Modularity rule

The generator must be implemented so that the following components can each be replaced without rewriting the pipeline:

- the embedding model
- the retrieval threshold and top-K
- the domain-filtering predicate over the RAG corpus
- the local LLM endpoint
- each stage's prompt template
- the reference-number injection function

The orchestrator should depend on stage interfaces (`run_stage_1(ctx) -> dict`, etc.), not on concrete implementations.

---

## V1 scope

For the first version, the generator must support:

- a single domain-filtered, name-keyed RAG retrieval used as Stage 1 style reference
- Stage 1 functional generation with the prompt above
- Stage 2 geometry generation with the prompt above
- Stage 3 synthesis producing one candidate
- post-processing reference-number injection
- per-stage deterministic fallbacks
- structured input loading from `invention_disclosure`, `research_report`, and `inventor_qa` tables

It does NOT yet need:

- multiple ranked candidates
- confidence scoring
- evidence visualization in the UI
- chain-of-thought exposure
- automatic candidate rejection metrics
- separate `all_elements_context_en` ↔ `definition_en` collections (the existing single-index retrieval is acceptable for V1; the narrowing redesign is a future extension)

---

## Future extensions

- multiple candidate variants with confidence labels
- two-collection retrieval narrowing (`all_elements_context_en` then `definition_en`)
- configurable retrieval thresholds per domain
- novelty-aware filtering of RAG hits
- UI display of per-stage intermediate outputs and evidence
- prompt-version tracking and per-version evaluation metrics
