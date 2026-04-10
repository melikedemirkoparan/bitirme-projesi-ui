# Home Page

## Purpose
The home page is the entry point of the patent drafting system.

It is not only a visual landing page. It also acts as:
- a workspace selector
- a project creation entry point
- an initial document ingestion screen

The page must allow users to:
1. open an existing patent project
2. create a new patent project
3. submit the initial source texts that will populate the database

---

## Main responsibilities

### 1. Display existing workspaces/projects
The left-side panel must list existing patent projects/workspaces.

Each project card should show at least:
- patent/project name
- optional subtitle or environment label
- open action

When the user selects an existing project, the system must navigate to that project's workspace.

### 2. Create a new project
The page must provide a **New Project** action.

When triggered, the system should open a project creation form or modal.

The form must collect at least:
- `patent_name`
- `patent_owner`

After this, the user must be able to choose which source document types will be added during project creation.

### 3. Initial document ingestion
The project creation flow must support structured text entry for the following document types:
- Invention Disclosure
- Research Report
- Inventor Q&A

The UI must dynamically show text areas depending on which document types are selected.

This page is therefore the first ingestion point of the system.

---

## Dynamic input behavior

### A. Invention Disclosure selected
The system must display 3 text inputs mapped to the following database fields:
- `prior_art_and_problems`
- `closest_prior_patents`
- `novel_features`

### B. Research Report selected
The system must display 4 text inputs mapped to the following database fields:
- `executive_summary`
- `search_strategy`
- `classification_and_keywords`
- `element_patent_analysis`

### C. Inventor Q&A selected
The system must display 1 text input mapped to:
- `questions_and_answers`

### D. Multiple document types selected
If the user selects more than one document type, the page must render all corresponding fields together.

The input areas are not generic notes. Each one represents a specific database field and must be stored accordingly.

---

## Database intent of the page
The home page is responsible for creating the initial project record and linking the first uploaded text content to the correct tables.

### Expected high-level flow
1. create patent/project record
2. obtain generated `patent_id`
3. if Invention Disclosure is provided, create linked record in `invention_disclosure`
4. if Research Report is provided, create linked record in `research_report`
5. if Inventor Q&A is provided, create linked record in `inventor_qa`
6. redirect the user to the project workspace

---

## Related database mapping

### `Patent`
- `patent_id`
- `patent_name`
- `patent_owner`

### `Invention_disclosure`
- `idf_id`
- `patent_id`
- `prior_art_and_problems`
- `closest_prior_patents`
- `novel_features`

### `Research_report`
- `research_report_id`
- `patent_id`
- `executive_summary`
- `search_strategy`
- `classification_and_keywords`
- `element_patent_analysis`

### `Inventor_qna`
- `qna_id`
- `patent_id`
- `questions_and_answers`

---

## UX expectations

### Visual role
The page should feel like a premium project entry screen for a patent drafting environment.

It should communicate:
- existing workspaces
- structured drafting workflow
- controlled document-based project setup

### Functional role
The page must clearly separate two actions:
- opening an existing project
- creating a new project

### Form behavior
- show only the fields relevant to the selected document types
- keep labels explicit and domain-specific
- preserve typed text while the modal/form is open
- validate required project metadata before submission

---

## Validation rules

### Minimum required fields
A new project must not be created unless:
- `patent_name` is provided
- `patent_owner` is provided

### Document fields
Document-specific text fields are optional unless that document type is selected.
If selected, the corresponding visible fields should be submitted as part of the create-project workflow.

---

## Non-goals for V1
The home page does **not** need to:
- run AI analysis live while the user types
- classify or rewrite text automatically
- trigger Claude hooks during typing
- infer missing document sections

V1 should remain deterministic and focused on project creation and structured ingestion.

---

## Recommended implementation approach

### Frontend
- workspace list panel
- new project modal or dedicated creation panel
- checkbox or multi-select for document types
- conditional rendering of text areas
- submit action for project creation

### Backend
- one create-project endpoint
- optional nested payloads for selected document types
- transactional creation flow preferred

---

## Suggested payload shape

```json
{
  "patent_name": "...",
  "patent_owner": "...",
  "invention_disclosure": {
    "prior_art_and_problems": "...",
    "closest_prior_patents": "...",
    "novel_features": "..."
  },
  "research_report": {
    "executive_summary": "...",
    "search_strategy": "...",
    "classification_and_keywords": "...",
    "element_patent_analysis": "..."
  },
  "inventor_qna": {
    "questions_and_answers": "..."
  }
}