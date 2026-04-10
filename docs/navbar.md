# Navbar Specification

## Purpose
The navbar is a shared top-level navigation component used across the patent drafting system.

Its purpose is to provide:
- product identity
- current system/data status visibility
- context-aware back navigation
- access to the upload flow

The navbar should be reusable across multiple pages.

---

## Core responsibilities
The navbar must:
- display the product name
- show a lightweight status indicator
- provide a context-aware back button
- provide an Upload Data action

It should remain visually consistent across the application.

---

## Main visual structure
From left to right, the navbar should contain:

1. product logo / icon
2. product title
3. status badge
4. context-aware back navigation action
5. upload data action

A repeated product title or right-aligned branding label may be preserved if required by the visual design.

---

## Product identity
The navbar must show the system name:
- `PATENT DRAFTING TOOL`

This should function as stable product branding across pages.

---

## Status badge
A small status badge should be displayed near the title.

### Initial example state
- `No Data`

### Purpose
This badge is used to communicate lightweight project/data state at the UI level.

### Initial meaning of `No Data`
The active project does not yet contain uploaded structured data required by downstream modules.

### Future extensibility
Later versions may support other states such as:
- `Data Uploaded`
- `Indexed`
- `Ready for Drafting`
- `Vector DB Ready`

These future states are not required for the first version, but the component should be designed so that they can be added later.

---

## Back navigation behavior
The navbar must include a back navigation action.

### Context-aware rule
The label and destination of the back action must depend on the current page.

This means the back button is **not globally fixed**.
It should adapt to the current screen context.

### Examples
- on a project workspace screen, it may appear as `Back to Home`
- on a drafting subpage, it may appear as `Back to Dashboard`
- on an editor page, it may appear as `Back to Editor`

### Requirement
The navbar component must accept page-aware navigation configuration so that the correct back label and target can be rendered depending on the screen in which the navbar is used.

---

## Upload Data action
The navbar must include an `Upload Data` action.

### Behavior
When the user clicks `Upload Data`, the system must navigate to a dedicated Excel upload page.

This upload page is intended for structured data ingestion.

### Initial scope
For the first version, the upload flow only needs to support the page transition and the upload entry point.

### Future processing direction
After this upload capability is integrated with later modules, the uploaded Excel content is expected to support a pipeline that:
1. reads the uploaded structured data
2. processes it through a future ingestion/indexing module
3. creates a vector database using **ChromaDB**

This future vectorization/indexing behavior does not need to be fully implemented in the first version, but the navbar action should be designed with this long-term flow in mind.

---

## Upload page expectation
The destination page opened by `Upload Data` should be treated as a dedicated data ingestion screen.

Its role is to:
- allow Excel file upload
- prepare uploaded data for future processing
- later support ChromaDB-based vector database creation

This page is outside the scope of the navbar itself, but the navbar must route to it.

---

## Reusability requirements
The navbar should be implemented as a reusable shared component.

It should accept configurable props or inputs for at least:
- current page context
- back button label
- back button target
- current status badge text

This keeps the component reusable without rewriting it per page.

---

## Non-goals for V1
The navbar does **not** need to:
- run upload logic directly inside the component
- create the vector database itself
- perform background indexing
- infer navigation context automatically from hidden heuristics

Its job is only to:
- display shared navigation UI
- reflect current status
- route the user correctly

---

## Future extensions
Possible later additions include:
- richer project status tracking
- user/session menu
- project switcher
- indexing progress indicator
- upload progress feedback
- vector database readiness status

These are out of scope for the first version.