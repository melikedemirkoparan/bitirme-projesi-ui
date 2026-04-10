# Definition Generator Specification

## Purpose
This module is responsible for generating patent-style element definitions from structured project inputs and retrieval-supported evidence.

The goal is not to produce a definition in one uncontrolled step.

Instead, the generator should use a staged architecture so that:
- retrieval evidence is prepared first
- functional candidates are generated separately
- geometry / relation candidates are generated separately
- final candidate definitions are produced only after both sides are analyzed

This design is intended to improve:
- grounding
- modularity
- interpretability
- offline local-model reliability
- replaceability of submodules over time

---

## High-level architecture
The definition generation workflow is divided into four parts:

1. **Retrieval / RAG preparation**
2. **Functional candidate generation**
3. **Geometry / relation candidate generation**
4. **Final definition generation**

Each stage must use structured inputs and produce structured outputs.

Input/output contracts are important.
The system should validate that the expected structure is present before sending data from one stage to the next.

---

## Core generation idea
The final definition should be generated from a combination of:
- structured invention/project inputs
- retrieval-supported patent evidence
- function candidates
- geometry / relation candidates

The generator should aim to produce multiple candidate definitions, not just one.

For the initial version, the final stage should produce:
- **3 candidate definitions**
- strongest candidate first

These candidate definitions are intended to be shown in the modal so the user can choose one.

---

## Stage 1 — Retrieval / RAG preparation

### Purpose
This stage prepares retrieval-supported evidence before function generation begins.

Its job is to:
- build a semantic context query from the patent's known elements
- search the `all_elements_context_en` collection
- keep only strong matches above a threshold
- use those context matches to narrow the candidate scope
- then search `definition_en` for the target element within that filtered scope

This stage is evidence preparation, not final definition generation.

---

### Input
This stage should receive:
- target element name
- current patent element list
- access to vector collections:
  - `all_elements_context_en`
  - `definition_en`

The current patent element list may look like:
- `body(5)`
- `table(8)`
- `sensor(3)`
- `control unit(10)`

The retrieval query should be built from the known element names, not from the target element alone.

---

### Retrieval flow
1. Build a context query from the patent's known elements  
   Example:
   - `body, table, heat source assembly, sensor, control unit, magnetic sputtering device`

2. Run semantic search on `all_elements_context_en`

3. Apply threshold filtering

4. Keep top relevant context matches  
   Suggested initial setting:
   - top 3 matches above threshold

5. Use those matches to narrow the candidate pool for the `definition_en` collection

6. Run semantic retrieval for the target element over the filtered `definition_en` subset

---

### Retrieval narrowing rule
The system should **not** search `definition_en` globally first.

The intended retrieval order is:

1. build a context query from the patent's known elements
2. search `all_elements_context_en`
3. keep top threshold-qualified context results
4. use those results to filter the candidate scope
5. then search `definition_en` for the target element within that filtered scope
6. send the resulting definition candidates to the functional generation stage

This narrowing step is a core design principle.

---

### Output
This stage should output structured retrieval evidence.

#### Output contract
If sufficient candidates are found:
```json
{
  "target_element": "body",
  "context_matches": [...],
  "definition_matches": [...]
}
```

If sufficient candidates are not found, return a controlled result instead of noisy weak evidence.

Example insufficient-result output

```json
{
  "target_element": "body",
  "context_matches": [],
  "definition_matches": [],
  "message": "No sufficient definition candidates found"
}
```

This stage should not hallucinate fallback matches.
Weak or irrelevant retrieval should be rejected.

---

## Stage 2 — Functional candidate generation

### Purpose
This stage generates candidate functional interpretations for the target element.

Its job is to infer:
- what the target element functionally does
- what technical role it plays in the invention
- whether similar prior definitions can provide useful pattern/style support

This stage focuses on function, not geometry.

---

### Input
This stage should receive structured project evidence such as:
- `Invention_disclosure.prior_art_and_problems`
- `Invention_disclosure.novel_features`
- `Research_report.executive_summary`
- `Inventor_QA.questions_and_answers`
- current patent element list
- retrieval outputs from Stage 1

Before prompting the local model, these inputs should be:
- trimmed
- cleaned
- separated into structured sections
- clearly labeled

The model should not receive one large unstructured text dump.

---

### Functional generation rule
The local model should first be told:
- what system it is operating in
- what the task is
- that the goal is to contribute toward a patent-style definition with a `[geometry/relation] + [function]` structure
- that this stage is only responsible for the functional side

Then it should:
1. inspect the invention/project inputs
2. understand the likely function of the target component
3. inspect RAG-retrieved similar definitions
4. use them only if they are actually relevant in function and style

---

### Critical rule for RAG use
RAG-retrieved definitions must be treated as optional functional/style support only.

The model must not rely on RAG if:
- the retrieval is contextually irrelevant
- the retrieved result is about the wrong kind of component
- the retrieved result has a high score but does not match the current function candidate
- the retrieved definitions belong to unrelated structures or systems

If retrieval evidence is not relevant, the model should ignore it.

---

### Functional output rule
This stage should output:
- 3 or 4 functional candidates
- ranked strongest first
- each labeled with confidence

Allowed confidence labels:
- `high`
- `medium`
- `low`

Example output shape

```json
{
  "target_element": "body",
  "functional_candidates": [
    {
      "candidate_text": "a structural component configured to support and carry relevant system parts",
      "confidence": "high",
      "evidence_note": "Supported by prior art and executive summary"
    },
    {
      "candidate_text": "a housing component adapted to position and support optical subsystems",
      "confidence": "medium",
      "evidence_note": "Supported by invention disclosure and partial retrieval similarity"
    },
    {
      "candidate_text": "a carrier component enabling system-level arrangement of optical units",
      "confidence": "low",
      "evidence_note": "Weak support, partly inferred"
    }
  ]
}
```

### Important functional restriction
The functional stage must not include other elements’ reference numbers such as `(3)`, `(4)`, `(8)` inside the candidate text.

This stage is about the target element’s own function.
It should not leak external reference numbering into the functional candidate text.

---

## Stage 3 — Geometry / relation candidate generation

### Purpose
This stage generates candidate geometry / relation interpretations for the target element.

Its job is to infer:
- where the component is located
- how it is positioned relative to other parts
- whether it extends, surrounds, supports, rotates, is removably attached, etc.
- which standard geometric / positional expression patterns apply

This stage focuses on geometry, structure, and inter-part relations, not function.

---

### Input
This stage should use the same structured project evidence as the functional stage, especially:
- `Invention_disclosure.prior_art_and_problems`
- `Invention_disclosure.novel_features`
- `Research_report.executive_summary`
- `Inventor_QA.questions_and_answers`
- current patent element list with reference numbers

Example current patent element list:
- `body(5)`
- `table(8)`
- `sensor(3)`
- `control unit(10)`

These reference-numbered elements are important for the geometry stage.

---

### Geometry generation rule
This stage should analyze the inputs to identify:
- positional clues
- relation clues
- structural arrangement clues
- part-to-part geometry

It should especially look for standard patent relation patterns such as the English equivalents of:
- located on / disposed on
- located between
- spaced apart from
- rotatably positioned
- removably attached
- extending outward from
- arranged in sequence
- positioned at equal intervals

The system should pay special attention to these standard pattern families because they frequently appear in patent-style geometry expressions.

---

### Reference-number rule for geometry
Unlike the functional stage, the geometry stage may and should use other elements’ reference numbers when relevant.

If the geometry of the target element is defined relative to another known component, and that other component exists in the current system input, then the geometry candidate should include that reference number.

Example:
If the system knows:
- `body(5)`
- `table(8)`

and the target element is located on the body or between the body and the table, the geometry candidate may use:
- `on the body (5)`
- `between the body (5) and the table (8)`

This is allowed and desirable in the geometry stage.

---

### Geometry output rule
This stage should output:
- 3 or 4 geometry / relation candidates
- ranked strongest first
- confidence labels included

Allowed confidence labels:
- `high`
- `medium`
- `low`

Example output shape

```json
{
  "target_element": "wing",
  "geometry_candidates": [
    {
      "candidate_text": "located on the body (5) and extending outward from the body (5)",
      "confidence": "high",
      "evidence_note": "Strong support from inventor notes and existing component list"
    },
    {
      "candidate_text": "positioned on the body (5) at a distance from the table (8)",
      "confidence": "medium",
      "evidence_note": "Partially supported by discussion notes"
    },
    {
      "candidate_text": "arranged in a root region shorter than the root region (301)",
      "confidence": "low",
      "evidence_note": "Weak support, partly inferred from comparative structure notes"
    }
  ]
}
```

---

## Stage 4 — Final definition generation

### Purpose
This stage receives:
- structured project inputs
- functional candidates from Stage 2
- geometry candidates from Stage 3

Its role is to:
- inspect the invention context again
- inspect the ranked candidates and their confidence levels
- choose the strongest valid combinations
- produce final patent-style candidate definitions

This stage is the final synthesis layer.

---

### Input
This stage should receive:
- target element name
- target element reference number
- structured trimmed project inputs
- `functional_candidates`
- `geometry_candidates`

Input structure validation is important here.
The final stage should ensure that:
- candidate structures are present
- confidence labels are valid
- target element information is complete
- malformed upstream outputs are not passed blindly into generation

---

## Final definition structure
The final generated candidate definitions should follow this structure:
- `[geometry/relation]`
- `[function]`
- `[quantity phrase]`
- `[reference number]`
- `[component name]`

### Notes
The final element phrase should appear at the end of the candidate definition.

This final element phrase may be:
- `at least one wing (4)`
- `a wing (4)`
- `wing (4)`

depending on the chosen candidate style.

The system may produce stylistic variants, but the element phrase should remain at the end of the final candidate.

---

### Example conceptual structure
A final candidate may look like:

> `located on the body (2) and extending outward from the body (2), configured to provide lifting force, at least one wing (4)`

or

> `positioned between the body (5) and the support structure (7), configured to support the optical subsystem, a body (5)`

The exact style may vary, but it should combine:
- geometry / relation
- function
- quantity wording
- reference number
- element name

---

### Final output rule
This stage should produce:
- 3 final candidate definitions
- strongest candidate first

Example output shape

```json
{
  "target_element": "wing",
  "final_candidates": [
    {
      "candidate_text": "located on the body (2) and extending outward from the body (2), configured to provide lifting force, at least one wing (4)",
      "confidence": "high"
    },
    {
      "candidate_text": "positioned on the body (2) and adapted to support aerodynamic lifting, a wing (4)",
      "confidence": "medium"
    },
    {
      "candidate_text": "arranged in a root region and configured to generate lift, wing (4)",
      "confidence": "low"
    }
  ]
}
```

---

## Input and output validation rule
At every stage, the system should verify that:
- expected input structure is present
- malformed upstream output is detected
- empty or insufficient candidates are handled safely
- candidate arrays are well-formed
- confidence labels are valid

The generator should prefer a safe structured failure over a misleading malformed output.

---

## Local offline LLM usage rule

### Model expectation
The definition generator is expected to run with a local offline LLM, potentially in the 7B or 14B model range.

Because these models are smaller and more error-prone than large cloud models, the system must be designed so that the model behaves more like a focused patent-engineering assistant than a general conversational assistant.

---

### Core role rule
The local model should be prompted to behave as a narrow-task technical reasoning system whose job is to support patent-style definition generation, not as an open-ended chatbot.

The prompts should keep the model focused on:
- the target component
- the structured invention inputs
- the relevant retrieval evidence
- the exact output contract of the current stage

---

### Best-practice rule for offline LLM use
When using smaller offline models, the system should follow practical best practices:
- keep prompts focused and narrow
- avoid unnecessary prompt length
- avoid mixing multiple loosely related goals in one step
- provide clearly structured inputs
- provide clearly structured output requirements
- state explicit constraints
- reduce opportunities for free-form speculation
- prefer staged reasoning over one-shot generation

---

### Hallucination control rule
Hallucination risk must be treated as a major concern.

The model should be instructed to:
- rely only on the provided inputs and retrieval evidence
- avoid inventing unsupported functional or geometric claims
- avoid using irrelevant retrieval results
- avoid producing confident text when evidence is weak
- return weaker-confidence candidates rather than pretending certainty

If the available evidence is weak, the model should still remain constrained and cautious.

---

### Output-discipline rule
The model must be guided with clear output contracts.
Each stage should define:
- required input structure
- required output structure
- allowed confidence labels
- forbidden content patterns where needed

This is especially important for smaller local models.

---

### Constraint rule
Prompts should explicitly tell the model:
- what its role is
- what stage it is currently in
- what it is allowed to use
- what it must not do
- what the expected output format is

The system should not assume that a small offline model will infer these constraints automatically.

---

## Docker and replaceability rule
The local LLM is expected to run inside a Docker container.

However, the codebase should not be tightly coupled to one permanent model implementation.

The system should be implemented so that:
- the model can be swapped later
- containerized local inference can be changed later
- prompt-building logic remains separable from model-calling logic
- the generator pipeline does not need to be rewritten when the local model changes

---

## Practical design goal
The goal is not over-engineering.
The goal is to keep the system:
- modular
- replaceable
- prompt-disciplined
- safe for smaller offline models
- easy to adapt as local model choices evolve

---

## Why this architecture is preferred
This staged architecture is preferred because it:
- separates retrieval from generation
- separates function from geometry
- makes RAG usage more controlled
- reduces the chance of irrelevant retrieval corrupting the final result
- gives more interpretable intermediate outputs
- makes the system safer for offline local-model use

---

## Modularity rule
The definition generator must be implemented in a modular way.

Do not hard-bind:
- the embedding model
- the retrieval threshold
- the collection names
- the functional generator implementation
- the geometry generator implementation
- the final composition logic

These should remain replaceable.

The goal is practical modularity, not unnecessary abstraction.

---

## V1 scope
For the first version, the generator only needs to support:
- retrieval preparation
- structured retrieval output
- functional candidate generation
- geometry / relation candidate generation
- final generation of 3 ranked candidate definitions

It does not yet need:
- advanced UI evidence visualization
- automatic candidate rejection controls
- chain-of-thought exposure
- advanced ranking metrics
- detailed observability dashboards

---

## Future extensions
Possible later improvements include:
- configurable thresholds
- configurable top-k retrieval
- multiple embedding model options
- stronger evidence ranking
- explicit novelty-aware candidate filtering
- UI display of candidate evidence
- user selection of preferred candidate
- logging and evaluation metrics for generated definitions

---

## Final implementation rule
Implement the system so that each stage can be tested independently.

The architecture should remain strong enough for offline local-model use, while flexible enough that:
- retrieval strategies can change
- embedding models can change
- local LLMs can change
- stage logic can evolve

without redesigning the full system.
