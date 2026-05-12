# Offline Document Q&A Module

## 1. Purpose

The Offline Document Q&A module is a guided question-answering subsystem that allows the user to ask targeted, patent-drafting-relevant questions about the structured project documents uploaded into the system — primarily the **invention disclosure (BBF)** and the **research report**.

Its purpose is to support the patent drafter and inventor during the review phase of uploaded source material, when they need to quickly verify what the documents actually say before drafting claims or a specification.

The module is designed around three firm principles:

1. **Fully offline.** No external API calls. All retrieval and generation happens locally.
2. **Evidence-grounded.** Every answer is accompanied by the source excerpts it was derived from. The user must be able to verify the answer against the document without leaving the page.
3. **Explainable.** Every answer carries a support-level label — `explicit`, `inferred`, or `insufficient` — so the user immediately understands how strongly the document backs the answer.

The module is intended to reduce hallucination risk, make offline local models usable in a professional drafting context, and give the user a fast, structured way to interrogate uploaded documents.

---

## 2. Why pattern-based, not free-form

The module is explicitly **not** a free-form chatbot.

The user does not type arbitrary natural-language questions. Instead, the user selects one of a small set of predefined question patterns, and then fills in any required slots (for example, a feature number) before generating the answer.

This choice is deliberate and is driven by four considerations:

1. **Offline-model robustness.** Small local models perform significantly better on constrained tasks than on open-ended questions. Patterns reduce the input space so the model's job becomes closer to structured extraction than to open reasoning.
2. **Real drafting value.** A patent drafter does not browse documents with arbitrary curiosity. Drafting work produces a small set of recurring questions about the source material. Patterns capture those recurring questions directly.
3. **Defensibility.** A pattern-based system has a clear, measurable taxonomy. It can be evaluated, documented, and presented as a principled design rather than a thin wrapper over a chat model.
4. **UI predictability.** A fixed pattern catalogue allows the frontend to render a specific, appropriate interface per pattern (slot forms, result shapes, evidence layouts) instead of a generic chat transcript.

V1 intentionally restricts the user to three patterns. Additional patterns may be added in future versions, but the module is not intended to evolve into an open chat interface.

---

## 3. Supported document types

The module operates over structured project documents as defined in `docs/patent_inputs_specification.md`.

V1 supports two document types:

1. **Invention disclosure (BBF)** — source of invention motivation, prior-art framing, the closest prior patents, and the invention's novel features.
2. **Research report** — source of the executive summary, domain classification, and the feature-by-feature comparison between novel features and cited prior patents.

A third document type, **Inventor Q&A**, is defined in the input specification but is **out of scope for V1**. It will be introduced in a later version together with its own patterns (see §15).

The module must tolerate **partial document availability**:

- Only the BBF may be uploaded.
- Only the research report may be uploaded.
- Both may be uploaded.

The module must return useful, well-labelled results in all three cases and must never fabricate information from a document that is not present.

---

## 4. Supported question patterns (V1)

V1 defines exactly three patterns.

### P1 — Problem & Motivation
> *What problem does the document identify, and what limitation of prior art motivates the invention?*

Used by the drafter to frame the Background / Problem section of the patent specification.

### P2 — Novel Features & Differentiators
> *What features does the document present as novel, and how do they differ from prior art?*

Used by the drafter to decide claim subject matter and to identify which features carry the novelty argument.

### P3 — Prior-Art Mapping for a Specific Feature
> *For feature X, which prior patent(s) are cited, and what do they teach?*

Used for comparative claim language and for anticipating examiner citations. Requires the user to specify which feature is being asked about.

No other patterns are exposed in V1.

---

## 5. Field routing per pattern

Because the input documents have a known, structured field layout, the module does not perform blind vector search. Each pattern is routed to specific fields of specific documents. This is the single most important design decision: it keeps retrieval faithful, the context window small, and the answers traceable.

The field routing table is the authoritative source of which fields a pattern may consult.

| Pattern | Invention disclosure (BBF) fields | Research report fields |
|---|---|---|
| P1 | `prior_art_and_problems` | `executive_summary` |
| P2 | `novel_features` (primary), `prior_art_and_problems` (differentiation context) | `executive_summary` (novelty/inventive-step paragraph), `element_patent_analysis` (per-feature comparisons) |
| P3 | `closest_prior_patents` (list context only), `prior_art_and_problems` (optional background) | `element_patent_analysis` (primary), `executive_summary` (secondary) |

Fields not listed for a given pattern must not be used as evidence for that pattern, even if they are available.

For P3, `closest_prior_patents` is a list-only field. A prior patent appearing only in that list — without a corresponding mapping in `element_patent_analysis` — cannot support an `explicit` answer. At best, such evidence supports an `inferred` result.

---

## 6. Behaviour under partial document availability

The module's behaviour must be deterministic and clearly communicated to the user for each availability case.

### Case A — BBF only

| Pattern | Expected behaviour |
|---|---|
| P1 | Answer derived from `prior_art_and_problems`. Typically `explicit`. Strong case. |
| P2 | Feature list derived from `novel_features`. Differentiators derived from `prior_art_and_problems` where possible; where not, the affected feature is marked `inferred` or `insufficient`. Overall support level is often degraded. |
| P3 | Usually degraded. `element_patent_analysis` is absent. Best available is `closest_prior_patents` plus any incidental mentions in `prior_art_and_problems`. Expected support level: `inferred` or `insufficient`. The UI must clearly indicate that P3 is under-supported without the research report. |

### Case B — Research report only

| Pattern | Expected behaviour |
|---|---|
| P1 | Answer derived from `executive_summary`. Typically `explicit`. |
| P2 | Features and differentiators drawn from `executive_summary` and `element_patent_analysis`. Typically mostly `explicit`. Feature labels are taken from `element_patent_analysis`. |
| P3 | Strong case. `element_patent_analysis` is exactly the field P3 is designed to exploit. Typically `explicit`. |

### Case C — Both documents available

| Pattern | Expected behaviour |
|---|---|
| P1 | Both fields are considered. The source with the more direct problem statement is used as primary; the other appears as corroborating evidence. |
| P2 | BBF's `novel_features` provides the canonical feature list (with original labels such as *Feature 2* or *Unsur 2*). Differentiators are drawn preferentially from the research report's `element_patent_analysis`. Strongest case. |
| P3 | Research report remains primary. BBF's `closest_prior_patents` corroborates the cited patent identifiers. Strongest case. |

### Case D — No relevant field populated

If the intersection of the pattern's field routing and the user's uploaded documents is empty, the backend must short-circuit: return an `insufficient` result without calling the model. This prevents the module from generating speculative answers when there is literally nothing to ground them in.

### Degraded-mode signalling

Whenever a pattern's answer is produced without a document that the pattern would normally rely on, the response must set `notes.degraded_mode = true` and list the missing document(s) in `notes.missing_documents`. The UI uses this to render a clear banner such as *"Answered from BBF only — research report not uploaded."*

---

## 7. Retrieval and evidence selection

Evidence selection is organized in three layers, from strictest to most general:

1. **Field selection (always first).** The pattern's field routing table determines which document fields are candidates.
2. **Structural segmentation.** Two fields are segmented by their natural unit:
   - `novel_features` is segmented into one chunk per feature entry.
   - `element_patent_analysis` is segmented into one chunk per feature-to-patent comparison block.
   This segmentation preserves the feature-level correspondence that patterns P2 and P3 depend on. Each resulting chunk carries a `feature_id` metadata tag.
   Other fields are chunked by size (approximately 400–600 tokens with ~80-token overlap), respecting section headings as hard boundaries.
3. **Retrieval within the selected field set.**
   - When the selected field is short and self-contained (for example, the entire `prior_art_and_problems` field), the whole field is passed to the model directly. Vector retrieval is skipped. This is faster and more faithful than retrieving from a field that easily fits in context.
   - When the selected field set is large (for example, a long `element_patent_analysis`), hybrid retrieval is used: vector similarity plus lexical (BM25-style) overlap with the filled slot. The top candidates are reranked by a cheap combined score that includes keyword overlap and feature-id match, and the top 3–4 chunks are retained.
   - For P3 specifically, chunks matching the resolved `feature_id` are always retained, regardless of their vector score.

All retained chunks are packaged as **evidence blocks** before being sent to the model. Each evidence block carries a stable `evidence_id`, its `document_type`, its originating `field`, and where relevant a `feature_id`. The model is required to cite evidence by id; the excerpts it returns must be verbatim substrings of the corresponding evidence block.

The context budget target for each call is approximately 1.5k–2.5k tokens of evidence. This is comfortably within the working range of small local models.

---

## 8. Safe use of smaller offline models

Small local models are assumed. The module is designed around their limits rather than around the capabilities of large hosted models.

Safety measures, in order of impact:

1. **Pattern constraint.** The user's question is never free-form. The model sees a fixed task description per pattern.
2. **Field-routed evidence.** The model only sees evidence from the fields relevant to the pattern. Unrelated context is never passed in.
3. **Strict system rules.** Every prompt carries an identical set of global rules: use only the evidence provided, cite by id, verbatim excerpts only, mark `insufficient` when appropriate, output JSON only.
4. **Cite-by-id enforcement.** The model emits `evidence_id` references. A post-validator verifies that every cited id was present in the context. Unknown ids trigger a corrective retry, then fall back to `insufficient`.
5. **Verbatim excerpt verification.** Every `excerpt` string returned by the model must be a substring of the evidence block it came from. Excerpts that fail this check cause the answer to be downgraded or rejected.
6. **Short answers.** Answers are capped (120 words for the main answer, short per-field entries for P2 and P3). Short answers have less room to drift.
7. **Low temperature.** Generation runs at a low temperature (approximately 0.1–0.2).
8. **Deterministic short-circuits.** When no relevant field is available, the backend returns `insufficient` without calling the model at all.

These measures together convert the model's output from *trusted text* into *verified structured data*.

---

## 9. Support-level classification

Every answer carries one of three support levels. The definitions are operational and must be stated verbatim in every prompt.

- **`explicit`** — the answer is literally stated in at least one cited evidence excerpt. No interpretive leap is required.
- **`inferred`** — the answer is not literally stated, but follows logically from combining or interpreting cited evidence excerpts. When this label is used, the response must include a short `reasoning` note describing how the inference was made.
- **`insufficient`** — the cited evidence does not support an answer. The `answer` field must be empty in this case.

For P2, each feature carries its own support level, and the overall answer-level support is derived from those per-feature levels:

- Overall `explicit` if every extracted feature is `explicit`.
- Overall `inferred` if at least one feature is `inferred` and none are `insufficient`.
- Overall `insufficient` if no features could be extracted.

The backend recomputes the overall level from the per-feature levels and corrects the model's value if it disagrees.

---

## 10. Response structure

The module uses a single JSON response contract for all three patterns. The frontend branches on `pattern_id` when rendering.

```json
{
  "pattern_id": "P1 | P2 | P3",
  "document_types_used": ["bbf", "research_report"],
  "support_level": "explicit | inferred | insufficient",
  "answer": "string (empty if insufficient; for P2, a short overview sentence)",
  "reasoning": "string, required when support_level == 'inferred', otherwise empty",

  "features": [
    {
      "feature_label": "Feature 2",
      "statement": "...",
      "differentiator": "...",
      "support_level": "explicit | inferred | insufficient",
      "evidence_ids": ["E3", "E5"]
    }
  ],

  "cited_patents": [
    {
      "patent_id": "US5940222A",
      "teaching": "...",
      "evidence_ids": ["E1"]
    }
  ],

  "evidence": [
    {
      "evidence_id": "E1",
      "document_type": "bbf | research_report",
      "field": "prior_art_and_problems | novel_features | executive_summary | element_patent_analysis | closest_prior_patents",
      "feature_id": "2 | null",
      "excerpt": "verbatim span from the evidence block, <= 400 chars",
      "locator": "section/paragraph hint for UI display"
    }
  ],

  "notes": {
    "available_documents": ["bbf"],
    "missing_documents": ["research_report"],
    "degraded_mode": true
  }
}
```

Rules:

- `features` is populated only for P2; for P1 and P3 it is an empty list.
- `cited_patents` is populated only for P3; for P1 and P2 it is an empty list.
- `evidence` must contain every evidence block referenced anywhere in the response.
- `notes` is filled deterministically by the backend. The model is not asked to reason about what is missing.

Every factual claim in `answer`, `features[*]`, and `cited_patents[*]` must be traceable to one or more `evidence_id`s. This is verified after generation.

---

## 11. UI behaviour

The Q&A page is deliberately simple and predictable.

1. **Document-type selector.** A dropdown or pair of toggles lets the user target BBF, research report, or *whichever is most appropriate for the selected pattern*. Document options that are not uploaded are disabled with an explanatory tooltip.
2. **Pattern selector.** Three cards, one per pattern, each with a short description of what the pattern answers and what it is useful for.
3. **Slot form.** Rendered after the pattern is chosen. P1 has no required slots. P2 has an optional "restrict to feature" slot. P3 requires a feature reference, which may be typed or picked from a dropdown populated from the BBF's `novel_features`.
4. **Ask button.** Triggers the backend call.
5. **Result area**, split two-column:
   - **Left column — Answer.** Shows the answer text and a support-level badge (green for *Explicit*, amber for *Inferred*, grey for *Insufficient evidence*). For P2, one badge appears per feature in addition to the overall badge. For `inferred` results, the reasoning note is shown directly under the answer.
   - **Right column — Evidence.** One card per evidence entry, showing document type, field name, feature id where applicable, and the excerpt. Each card is linked back to the original document location where feasible.
6. **Degraded-mode banner.** When `notes.degraded_mode` is true, a banner at the top of the result area names the missing document(s) and explains that the answer is produced from partial material.
7. **History list (optional).** Previous Q&A pairs for the active patent may be listed for quick recall. This is a convenience feature, not a conversational thread.

Explicitly not part of V1: free-form chat input, multi-turn follow-ups, cross-document synthesis beyond the routing rules, saved conversation threads.

---

## 12. Staged implementation

The module is built in six stages. Each stage has a clear exit condition and is independently useful.

- **Stage 0 — Contract and skeleton.** Write this specification. Define the response contract as Pydantic schemas. Add FastAPI route stubs that return canned responses. Build the frontend page with the pattern selector and result layout, wired to the stub endpoints.
- **Stage 1 — Field-routed retrieval.** Implement the per-field retrieval layer, including structural segmentation of `novel_features` and `element_patent_analysis`. Verify retrieval quality on real uploaded documents without invoking the model.
- **Stage 2 — Pattern prompts and model integration.** Implement the three pattern-specific prompt templates and the shared scaffolding. Wire a thin local-LLM client abstraction so the model is swappable. Start with single-pass JSON generation.
- **Stage 3 — Post-validation.** Implement the validator: cited-id existence, verbatim-excerpt check, patent-id consistency for P3, recomputed overall support level for P2. Add one corrective retry on validation failure before falling back to `insufficient`.
- **Stage 4 — UI polish.** Support-level badges, degraded-mode banner, evidence card links, error states for missing documents and slot-resolution failures.
- **Stage 5 — Evaluation harness.** Build a small annotated gold set of question/answer/support-level triples across real uploaded documents. Report retrieval recall@k, faithfulness (every cited claim supported by its excerpt), and support-level classification accuracy. These numbers are intended to appear in the final project write-up.

Later stages, beyond V1, may introduce the Inventor Q&A document type, additional patterns, or a two-pass classification pipeline if evaluation identifies support-level noise (see §15).

---

## 13. Academic defensibility

The module is designed so that it can be presented as a principled system rather than as a wrapper over a chat model. The defensible elements are:

1. **A clear, non-trivial question taxonomy** — three patterns tied to concrete drafting tasks and explicit document fields, rather than arbitrary example prompts.
2. **Document-structure-aware retrieval** — the field-routing design exploits the known schema of the input documents rather than treating them as opaque text. This is a genuine engineering decision, not a default.
3. **Operational support-level semantics** — explicit, inferred, and insufficient are defined with operational criteria that can be measured against human judgment.
4. **Citation and excerpt verification** — the system does not merely ask the model to cite; it verifies that citations exist and that excerpts are verbatim. This moves the result from "plausible" to "checkable".
5. **Evaluability** — the design supports a straightforward evaluation protocol on a small annotated set: retrieval recall@k, faithfulness, support-level accuracy, per-pattern behaviour under partial document availability.
6. **Offline-first engineering** — the module is built around the limits of small local models, not around cloud-model assumptions. The choice of patterns, field routing, and validation is motivated directly by those limits.

Together, these points make the module presentable as a focused, evidence-grounded offline QA system specifically tailored to patent drafting.

---

## 14. Why evidence display is mandatory

Showing the supporting evidence is not a convenience feature. It is part of the module's core guarantee.

The module is used during the review phase of uploaded source material. In that phase, the drafter or inventor must be able to verify any answer against the original document before using it. An answer without its source cannot be verified and therefore cannot be safely relied upon in drafting.

For this reason:

- Every answer must be accompanied by the evidence excerpts it was produced from.
- Every factual claim in the answer must be traceable to at least one cited evidence id.
- Every excerpt shown to the user must be verbatim text from the evidence block that was sent to the model.
- The UI must display the evidence alongside the answer, not hidden behind an additional click.

Responses that cannot provide evidence are not valid responses. In such cases the module must return `insufficient` rather than an unsupported answer.

---

## 15. Architectural notes and future extensions

### Integration points

- **Ingestion reuse.** The module reuses the existing embedding and ChromaDB ingestion pipeline. Each chunk's metadata must include `document_type`, `field`, and where applicable `feature_id`. No new embedding model is introduced for this feature.
- **Patent scope.** Q&A always runs in the context of the active patent project. Document availability is determined per patent.
- **LLM client abstraction.** Generation is routed through a thin, swappable local-LLM client. The rest of the module does not depend on any particular model implementation.

### Modularity

The module is organized along the project's modularity rule. The main seams are:

- Retrieval (field routing, segmentation, hybrid scoring) is independent of the model.
- Prompt templates are data, not code paths; adding a new pattern is a matter of adding a new template and a routing entry, not rewriting the service.
- The validator operates on the response JSON and is independent of the model and the prompts.

### Future extensions

- **Inventor Q&A support.** Once the Inventor Q&A input is activated, two additional patterns become appropriate:
  - **P4 — Design-Intent Query.** *Why was a particular design choice made?*
  - **P5 — Fixed vs. Flexible.** *Which aspects of a given element are fixed, and which are still flexible?*
  Both patterns route into `questions_and_answers` and must handle the less formal, more fragmented nature of inventor notes.
- **Two-pass support classification.** If evaluation shows that single-pass support-level classification is noisy, a second model call (draft answer → classify) can be introduced. This doubles inference cost and should only be adopted if justified by measurement.
- **Cross-document synthesis patterns.** Patterns that deliberately combine BBF and research report content (for example, cross-checking BBF-stated novelty claims against research-report conclusions) can be added once the V1 patterns are stable.
- **Persistent Q&A history.** A small `qa_history` table keyed by `patent_id` and `document_id` may be introduced if the user wants to revisit prior answers across sessions.

### Explicit non-goals

- The module is not a conversational assistant. It does not handle multi-turn dialogue, clarification questions, or follow-ups in V1.
- The module does not perform cross-patent retrieval. It answers only over the documents uploaded to the active patent.
- The module does not rewrite or redraft content. Answer generation stops at structured evidence-grounded responses; downstream drafting modules are separate.

---

## 16. Summary

The Offline Document Q&A module is a guided, pattern-based, evidence-grounded question-answering system for uploaded patent documents. It supports three predefined patterns in V1 — Problem & Motivation, Novel Features & Differentiators, and Prior-Art Mapping for a Specific Feature — each routed to specific fields of the invention disclosure and the research report. It handles partial document availability deterministically, classifies every answer as explicit, inferred, or insufficient, and requires every answer to be accompanied by verifiable source excerpts. Its design is shaped by the limits of small offline models and by the realistic needs of patent drafting work, and it is intended to be presentable, measurable, and incrementally extensible as the system grows.
