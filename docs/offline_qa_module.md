# Workspace Document Assistant

## 1. Purpose

The Workspace Document Assistant is a lightweight offline helper panel inside the patent workspace.

It is not intended to be a complex research chatbot. Its purpose is to help the patent drafter quickly use the uploaded project documents while working on claims.

The assistant answers three practical drafting questions:

1. What is the core technical problem?
2. What claim structure should be drafted from the disclosed features?
3. Where is a specific element discussed in the research report?

The module should be useful, fast, and easy to explain. It should run fully offline using the existing local model where model reasoning is needed.

---

## 2. Product behaviour

The assistant appears inside the existing workspace page.

It should open from a small button in the workspace, preferably near the lower-right corner or in the workspace toolbar. When clicked, a compact side panel opens from the right side of the screen.

The panel behaves like a small assistant/chat drawer, but it is not a free-form general chatbot. The user selects one of three predefined modes and optionally enters a short term for lookup.

The assistant panel should not replace the main workspace. The user should still be able to see and edit claims while the assistant is open.

---

## 3. Supported inputs

The module uses the project input fields already stored for the active patent.

### Invention Disclosure

Used fields:

- `prior_art_and_problems`
- `novel_features`
- `closest_prior_patents`

### Research Report

Used fields:

- `executive_summary`
- `element_patent_analysis`

The module does not require a new database structure for V1. It reads the existing text fields from the active patent project.

---

## 4. Assistant modes

V1 supports three modes.

| Mode | Name | Purpose | LLM used |
|---|---|---|---|
| P1 | Core Problem | Identify the main technical problem and why the invention matters | Yes |
| P2 | Claim Structure | Suggest an independent/dependent claim structure from the features | Yes |
| P3 | Element Lookup | Find where a user-entered element appears in `element_patent_analysis` | Optional ranking only |

---

## 5. P1 — Core Problem

### Goal

P1 answers the question:

> What is the core technical problem that a patent expert should focus on?

This mode helps the drafter understand the invention's central problem before writing claims or the background section.

### Inputs

P1 uses:

- `prior_art_and_problems`
- `executive_summary`

If both fields are available, both are used. If only one is available, the assistant uses that one and clearly notes that the answer is based on limited documents.

P1 uses a second evaluation step after generation. The evaluator checks whether both the core problem and the proposed solution are directly stated in the uploaded documents. P1 does not use `inferred`; if the problem or solution is only implied, the result is `insufficient`.

### Expected answer

The answer should be short and practical.

It should include:

- the core technical problem
- the solution or improvement proposed by the system/invention

Example style:

> The core problem appears to be that existing mechanisms cannot maintain stable positioning under repeated load without increasing structural complexity. The invention focuses on solving this by introducing a more controlled support/locking arrangement.

### Rules

- Do not invent a problem that is not supported by the uploaded text.
- If the documents are too empty, return an insufficient result.
- Keep the answer focused on patent drafting value, not general summarization.
- If either the problem or proposed solution is not directly stated, return `insufficient`.

---

## 6. P2 — Claim Structure

### Goal

P2 answers the question:

> How should the claim structure be organized?

This is the most drafting-oriented mode. It should help the user decide which features may belong in an independent claim and which features are better suited as dependent claim limitations.

### Inputs

P2 uses:

- `executive_summary`

P2 does not use `element_patent_analysis` in V1. The claim-structure recommendation is extracted from the research report's executive summary only. This keeps the behaviour simple and avoids forcing the local model to reason over a very long comparative analysis field.

The backend uses a second evaluation step after generation. The evaluator checks whether the recommendation is directly stated in the executive summary or only inferred as a drafting suggestion. The UI must say `Explicitly Stated` only when the executive summary really states the relevant feature role clearly.

### Expected answer

The answer should produce a practical claim drafting recommendation.

It should include:

1. **Independent claim candidate**
   - Which feature or combination of features should likely form the independent claim.
   - Why this feature set appears central.

2. **Dependent claim candidates**
   - Which additional features should be attached as dependent claims.
   - Which independent claim they should depend from.

3. **Drafting caution**
   - Any feature that seems weak, optional, unclear, or only narrowly supported.

Example style:

```text
Independent claim candidate:
- Feature 1 and Feature 2 should be combined in the independent apparatus claim because they appear to define the main technical improvement.

Dependent claim candidates:
- Feature 3 can depend from the independent claim as a refinement of the locking mechanism.
- Feature 4 can depend from the independent claim as an optional material or geometry limitation.

Drafting caution:
- Feature 5 should not be used as the only independent point unless the research report clearly supports novelty over the cited prior art.
```

### Rules

- The assistant may suggest claim organization, but it must not present the suggestion as a final legal conclusion.
- It should use cautious language such as `appears`, `likely`, `candidate`, and `should be considered`.
- It must not draft full claim text in V1.
- It must not say that a feature is patentable unless the uploaded report explicitly supports that conclusion.

---

## 7. P3 — Element Lookup

### Goal

P3 answers the question:

> Where does this element appear in the research report, and what does the report say around it?

This mode uses deterministic term matching first, then optionally uses the local language model only to rank the matched source blocks by drafting usefulness. The model does not create new evidence and does not answer from unmatched text.

### User input

The user enters a technical term, component name, mechanism name, or material name.

Examples:

- `pad`
- `hub`
- `locking nut`
- `slider crank`
- `support arm`

### Input field

P3 searches only:

- `element_patent_analysis`

### Behaviour

The backend performs case-insensitive substring search over `element_patent_analysis`.

When a match is found:

- return the paragraph or nearby comparison block containing the term
- show the source field as `element_patent_analysis`
- include the searched term so the UI can highlight it
- return all matching blocks, not only the first one
- send only the matched blocks to the local model for ranking
- order the cards from most useful to least useful for understanding the element
- optionally show a short usefulness note for each ranked card

When no match is found:

- return a clear message saying the term was not found
- suggest trying an alternative term because the research report may use different wording

The LLM ranking layer must never add new facts. If ranking fails, the backend returns the original deterministic match order.

### Example answer

```text
'locking nut' was found in 2 places in the element patent analysis.
```

The important content is the evidence cards shown below the answer.

---

## 8. Response contract

The backend should use one response shape for all three modes.

```json
{
  "pattern_id": "P1 | P2 | P3",
  "title": "Core Problem | Claim Structure | Element Lookup",
  "support_level": "explicit | inferred | insufficient",
  "answer": "assistant answer or short lookup summary",
  "insufficient_message": "shown when the documents do not contain enough information",
  "claim_structure": {
    "independent_candidates": [
      {
        "label": "Independent Claim 1",
        "features": ["Feature 1", "Feature 2"],
        "reason": "why these features appear central",
        "support_level": "explicit | inferred",
        "support_note": "why this is explicitly stated or why it is only a drafting inference"
      }
    ],
    "dependent_candidates": [
      {
        "label": "Dependent Claim",
        "depends_on": "Independent Claim 1",
        "features": ["Feature 3"],
        "reason": "why this is better as a dependent limitation",
        "support_level": "explicit | inferred",
        "support_note": "why this is explicitly stated or why it is only a drafting inference"
      }
    ],
    "cautions": ["short caution text"]
  },
  "evidence": [
    {
      "evidence_id": "E1",
      "document_type": "invention_disclosure | research_report",
      "field": "prior_art_and_problems | novel_features | executive_summary | element_patent_analysis",
      "excerpt": "verbatim source text shown to the user",
      "match_term": "only populated for P3"
    }
  ]
}
```

Rules:

- `claim_structure` is populated mainly for P2.
- P1 may return an empty `claim_structure`.
- P3 always returns an empty `claim_structure`.
- `evidence` should be shown whenever possible.
- If there is not enough source text, return `support_level = insufficient`.
- `explicit` must be used only when the source text clearly states the point. Drafting recommendations inferred from the executive summary should use `inferred`.
- For P1 and P2, every successful response must pass a second evaluator step and must include at least one verbatim evidence excerpt that exists in the original source field.
- P1 can return only `explicit` or `insufficient`. It should not return `inferred`.
- P3 does not need an evaluator because the factual match is deterministic. It returns `explicit` only when the searched term is literally found in `element_patent_analysis`; the optional LLM layer may only reorder matched cards and add usefulness notes.

---

## 9. Request contract

The frontend sends one request shape.

```json
{
  "pattern_id": "P1 | P2 | P3",
  "term": "optional, required only for P3"
}
```

Suggested endpoint:

```text
POST /api/patents/{patent_id}/document-assistant/ask
```

---

## 10. UI design

The assistant is opened from the workspace page.

### Entry point

Add a small button in the workspace:

```text
Document Assistant
```

The button can be placed:

- in the navbar actions, or
- as a floating button at the lower-right corner of the workspace

### Panel layout

When opened, a drawer appears from the right side.

The drawer contains:

1. header with title and close button
2. mode selector with three options:
   - Core Problem
   - Claim Structure
   - Element Lookup
3. P3 term input, shown only when Element Lookup is selected
4. Ask button
5. answer area
6. evidence cards

The panel should feel like a compact chat/helper panel, but without open-ended chat input.

### Result rendering

For P1:

- show the core problem answer
- show source excerpts below it

For P2:

- show independent claim candidate cards
- show dependent claim candidate cards
- show drafting cautions
- show supporting source excerpts

For P3:

- show the match count summary
- show each matching block as an evidence card
- highlight the searched term if feasible

---

## 11. Backend implementation approach

V1 should be simple.

### Step 1 — Load fields

For the active patent:

- load `invention_disclosure`
- load `research_report`

No new storage is required.

### Step 2 — Build source package

For P1:

- include `prior_art_and_problems`
- include `executive_summary`

For P2:

- include `executive_summary`
- do not include `element_patent_analysis`
- run a second evaluator pass; P1 accepts only explicitly stated answers

For P3:

- load full `element_patent_analysis`
- do direct text matching

### Step 3 — Call local model for P1/P2

Use the existing local LLM client.

Model settings:

- low temperature
- JSON output
- short answer
- evidence-grounded instruction

If the model fails, return a clean insufficient/error message instead of crashing the UI.

### Step 3b — Evaluate model-assisted answers

P1 and P2 must run a second evaluator pass after the first model response.

The evaluator decides:

- `explicit`: the relevant point is directly and clearly stated in the uploaded source text.
- `inferred`: the point is a reasonable drafting interpretation, but not directly stated.
- `insufficient`: the point is unsupported or cannot be verified.

For P1, `inferred` is not allowed. If the core problem and proposed solution are not directly stated, the evaluator must return `insufficient`.

The backend must also verify that every returned evidence excerpt is a verbatim substring of the original source field. If the evidence cannot be verified, the response falls back to `insufficient`.

### Step 4 — P3 match and ranking

P3 first performs deterministic matching. It may then call the model only to rank the matched blocks.

Implementation can use:

- case-insensitive search
- paragraph splitting by blank lines
- fallback to a surrounding text window if paragraphs are too large
- LLM ranking over matched evidence IDs only
- fallback to original match order if the LLM ranking fails

---

## 12. Prompt direction

### P1 prompt intent

The model should behave like a patent expert reviewing source documents.

It should identify:

- the central technical problem
- the relevant prior-art limitation
- the invention's apparent direction of solution

It should avoid broad summaries.

### P2 prompt intent

The model should behave like a patent claim drafting assistant.

It should recommend:

- candidate independent claim feature set
- candidate dependent claim refinements
- features that require caution

It should not write final claim text.

It should use conservative wording and cite source excerpts.

---

## 13. Out of scope for V1

The following are not required:

- free-form chatbot
- multi-turn memory
- saved chat history
- vector search over all documents
- new chunk tables
- cross-patent retrieval
- automatic claim creation
- final claim drafting
- legal patentability opinion

The goal is a working assistant that helps the user make drafting decisions faster inside the workspace.

---

## 14. Implementation stages

### Stage 0 — Document and route skeleton

- Add schemas for request and response.
- Add route:
  - `POST /api/patents/{patent_id}/document-assistant/ask`
- Return simple canned responses first.

### Stage 1 — P3 lookup

- Implement deterministic search in `element_patent_analysis`.
- Return matching paragraphs as evidence cards.
- Add UI mode and result rendering.

### Stage 2 — P1 core problem

- Load `prior_art_and_problems` and `executive_summary`.
- Call local model.
- Return short answer with evidence excerpts.

### Stage 3 — P2 claim structure

- Load feature and research report fields.
- Call local model.
- Render independent/dependent claim suggestions in the drawer.

### Stage 4 — UI polish

- Add floating/workspace button.
- Add right-side drawer.
- Add loading/error states.
- Add term highlighting for P3.

---

## 15. Frontend transfer plan

This section exists so the assistant architecture can be copied into another project with minimal ambiguity.

### Required backend contract

The frontend needs one endpoint:

```text
POST /api/patents/{patent_id}/assistant/ask
```

Request:

```json
{
  "pattern_id": "P1 | P2 | P3",
  "term": "required only for P3"
}
```

Response:

```json
{
  "pattern_id": "P1",
  "title": "Core Problem",
  "support_level": "explicit | inferred | insufficient",
  "answer": "string",
  "insufficient_message": "string",
  "claim_structure": null,
  "evidence": [
    {
      "evidence_id": "E1",
      "document_type": "research_report",
      "field": "executive_summary",
      "excerpt": "verbatim source text",
      "match_term": null,
      "usefulness_note": null
    }
  ]
}
```

The other project does not need to copy this project's claim editor, element editor, or ingestion UI. It only needs an active project id, the assistant endpoint, and the drawer component.

### UI components to port

Port these frontend pieces:

- Floating assistant button.
- Right-side drawer.
- Mode selector with P1, P2, P3.
- P3 term input.
- Ask/loading/error state.
- Result renderer.
- Evidence card renderer.
- Term highlighter for P3.
- Support-level badge renderer.

The drawer should be independent from the rest of the workspace. It should require only:

- `patentId`
- an `api(path, opts)` helper
- an HTML escaping helper

### Frontend state

The minimal state is:

```js
let assistantMode = 'P1';
```

P1 and P2 do not require user input. P3 requires:

```js
term: document.getElementById('assistantTermInput').value.trim()
```

### Rendering rules

For all modes:

- Show `support_level` as a badge.
- If `support_level === "insufficient"`, show only `insufficient_message`.
- Always render evidence cards when present.

For P1:

- Render `answer`.
- Render evidence excerpts.

For P2:

- Render `answer`.
- Render `claim_structure.independent_candidates`.
- Render `claim_structure.dependent_candidates`.
- Render `claim_structure.cautions`.
- Show candidate `support_note` when present.

For P3:

- Render the match-count `answer`.
- Render evidence cards in backend-provided order.
- Highlight `match_term` inside each excerpt.
- Show `usefulness_note` above the excerpt when present.

### CSS classes to port

The relevant class group is:

```text
assistant-fab
assistant-overlay
assistant-drawer
assistant-drawer-header
assistant-mode-selector
assistant-mode-btn
assistant-term-row
assistant-ask-row
assistant-result
assistant-insufficient
assistant-support-badge
assistant-answer-block
assistant-cs-section
assistant-cs-card
assistant-evidence-section
assistant-evidence-card
assistant-highlight
```

These classes are intentionally self-contained and can be copied into another stylesheet. They do not require the rest of the patent workspace layout.

### Migration checklist

1. Copy backend files:
   - `app/routes/assistant.py`
   - `app/schemas/assistant.py`
   - `app/services/assistant_service.py`
   - `app/services/faithfulness.py`
2. Ensure `app/main.py` includes the assistant router.
3. Ensure the target project has an Ollama-compatible LLM client or adapt `_call_model`.
4. Add `ollama_base_url` and `ollama_model` settings.
5. Copy the drawer HTML into the target workspace page.
6. Copy the assistant JS functions.
7. Copy the assistant CSS class group.
8. Confirm the target project can provide project inputs equivalent to:
   - `prior_art_and_problems`
   - `executive_summary`
   - `element_patent_analysis`
9. Test P1, P2, and P3 independently.

---

## 16. Summary

The Workspace Document Assistant is a practical offline helper for the patent drafting workspace.

It supports three focused actions:

- P1 identifies the core technical problem.
- P2 suggests a claim structure with independent and dependent claim candidates.
- P3 finds where a specific element appears in the research report and shows the surrounding source text.

The module should be implemented as a compact right-side assistant drawer inside the workspace page. It should stay simple, deterministic where possible, and useful for real drafting work.
