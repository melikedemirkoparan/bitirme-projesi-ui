# Patent Draft Composer Specification

## Purpose
The patent draft composer is the full-document drafting screen used to generate a complete patent draft from the claims already created inside a patent project.

This page is intended to assemble a full patent text after claim drafting has reached a usable stage.

Its main role is:
- to use the saved claims of the current project as input
- to trigger the future full-draft generation module
- to display the generated full patent draft in a dedicated drafting area

This page is not for claim-level editing. It is for full patent document composition.

---

## Main responsibility
The page must take the currently saved claims of the active patent project and use them as the default draft input.

The user should not need to manually reselect claims one by one for V1.

### Input rule
`Selected Claims` should automatically represent:
- all claims currently saved in the active patent project
- especially the claims saved from the claim workspace/editor

This means the composer should pull the current project's saved claim records directly from the database.

---

## Simplified page layout for V1
The first version only needs two main conceptual areas:

1. **Claims Input**
2. **Draft Output**

The following areas shown in the visual concept are **not required** for V1:
- `Sections`
- `Citations`

These should be omitted unless a later version explicitly introduces them.

---

## Claims Input area

### Responsibility
This area displays the full set of currently saved claims belonging to the active patent project.

### Data source
The claims shown here must come from the project's persisted claim records.

### Expected behavior
- automatically load all saved claims for the project
- show them in a readable combined input area
- allow the user to review the claims before generation
- optionally allow import/refresh from the editor if needed

For V1, this is not a manual selection interface.
It is a project-level claim aggregation view.

---

## Draft Output area

### Responsibility
This area displays the generated full patent text.

When the future generation module is ready, clicking `Generate Draft` must produce a full patent draft using the project's saved claims and prompt-based drafting logic.

### Expected generated content
The generation module is expected to produce a complete patent draft including at least:
- abstract / summary
- description/specification text
- claims section

The user described this as generating the full patent text using claims and prompt templates.

For V1 specification purposes, the page should be prepared for a full-document output area rather than section-by-section micro-panels.

---

## Generate Draft behavior

### Action
The page must provide a `Generate Draft` action.

### Future behavior
Once the drafting module is implemented, this action should:
1. collect all saved claims for the active patent project
2. prepare the required prompt input
3. call the future patent drafting module
4. generate the full patent draft text
5. display the result in the draft output area
6. optionally allow saving/exporting later

### Important note
The page should be implemented now with the correct structure even if the generation module is not ready yet.

---

## Relationship to existing project data
The draft composer depends on previously created project content.

At minimum it should rely on:
- the current patent/project record
- all saved claims in the project

Later versions may also incorporate:
- invention disclosure data
- research report data
- inventor Q&A data
- element definitions
- claim metadata

But the core V1 behavior is based on the saved claims of the active project.

---

## Related data expectations

### Required existing data
- `patent_id`
- all claim records linked to that patent

### Relevant table
```text
Claim
-----
claim_id PK
patent_id FK
claim_number
claim_dependency_type
claim_category
parent_claim_id FK nullable
claim_text
created_at
updated_at