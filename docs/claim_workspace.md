# Claim Workspace Specification

## Purpose
The claim workspace is the main drafting and curation screen used after a patent project has been created.

This page is responsible for:
- managing claim structures
- reviewing automatically extracted elements
- manually adding or deleting elements
- defining patent elements
- linking elements to claims
- drafting claim text manually or with AI assistance

This page is a structured authoring workspace, not a passive viewer.

---

## Main layout
The page is composed of three main areas:

1. **Left panel — Claim Structures**
2. **Center panel — LLM Extraction Queue**
3. **Right panel — Claim Draft Editor**

In addition, the page uses modals for:
- creating a new claim
- editing an element definition

---

## 1. Left panel — Claim Structures

### Responsibility
This panel displays the current claim list and the structural organization of elements under each claim.

### Supported actions
- view existing claims
- select a claim
- create a new claim
- delete a claim
- add elements to a selected claim
- display claim-linked elements in order or structure

### Add Claim behavior
Clicking **Add Claim** must open a modal instead of creating a claim immediately.

The modal must collect at least:
- `claim_dependency_type`
  - `independent`
  - `dependent`
- `claim_category`
  - `apparatus`
  - `method`

If the user selects `dependent`, the modal must also require:
- `parent_claim_id`

This information must be stored in the `claim` table.

---

## 2. Center panel — LLM Extraction Queue

### Responsibility
This panel displays the output of the automatic element extraction module.

The extraction module is expected to analyze the project's source inputs and identify candidate patent elements.

### Supported actions
- show extracted elements
- manually add a missing element
- delete an incorrectly extracted element
- move or link extracted elements into claim structures

This queue must remain editable by the user.
It is not a read-only AI output area.

### Notes
The automatic extraction module may be implemented later.
The page must still support manual element management from the beginning.

---

## 3. Right panel — Claim Draft Editor

### Responsibility
This panel displays the selected claim's draft text area.

The user must be able to:
- manually write the claim text
- manually edit the claim text
- request an AI-generated draft later through an `AI Draft` action

AI drafting is optional.
Manual drafting must always remain available.

---

## Element Definition modal

### Trigger
When the user clicks an element, an element definition modal must open.

### Purpose
This modal is used to manage the core metadata and definition text of a patent element.

### Required element fields
- `element_id`
- `element_name`
- `reference_number`
- `definition_text`

### Supported actions
- manually edit element name if needed
- enter or update the patent reference number
- manually write the element definition
- request an AI-suggested definition later via `AI Suggested Definition`

The final definition must always remain editable by the user.

---

## Claim creation rules

### Claim metadata
Each claim must store the following metadata:
- claim identity
- whether it is independent or dependent
- whether it is an apparatus claim or method claim
- if dependent, which parent claim it depends on

### Dependency rule
If a claim is marked as `independent`, then `parent_claim_id` must be `null`.

If a claim is marked as `dependent`, then `parent_claim_id` must reference another claim in the same patent project.

---

## Element-to-claim relationship model

The system must use a relation table between claims and elements.

### Why
An element may appear in more than one claim.
Therefore:
- the element itself should be stored only once
- its usage inside claims should be stored separately

### Tables involved
- `Claim`
- `Element`
- `Claim_Element`

---

## Suggested database structures

### `Claim`
```text
claim_id PK
patent_id FK
claim_number
claim_dependency_type -> independent | dependent
claim_category -> apparatus | method
parent_claim_id FK nullable
claim_text
created_at
updated_at

Element
element_id PK
patent_id FK
element_name
reference_number
definition_text
created_at
updated_at

Claim_Element

claim_element_id PK
claim_id FK
element_id FK
created_at
updated_at