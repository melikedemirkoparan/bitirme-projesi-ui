# CLAUDE.md

## Project identity
This project is an offline patent drafting application for structured patent authoring.

It is designed as a local drafting workspace where users can:
- create patent projects
- enter and manage patent-related source documents
- draft claims
- define patent elements
- generate complete patent drafts

The long-term goal is to combine:
- structured document-driven workflows
- local database-backed project management
- embedding and retrieval support
- local LLM-assisted drafting modules

This is not a generic writing app.
It is a purpose-built patent drafting system.

The project is being developed incrementally.
Some modules are already defined in `docs/`, while others will be added later as the system grows.

---

## Current technology direction
The project is expected to use:
- **FastAPI** for the backend/application API layer
- **PostgreSQL** for the relational database
- **Python ORM models** for persistence
- **Docker** for containerized development/deployment
- **plain JavaScript + CSS** for the current frontend
- **embedding models** for retrieval/vectorization workflows
- **a local LLM** for future AI-assisted drafting features
- **ChromaDB** for the vector database layer when the ingestion/indexing module is added

---

## Source of truth
Use the files under `docs/` as the main project specification.

At the moment, the valid page, workflow, and database definitions are documented there.

Examples include:
- `docs/home_page.md`
- `docs/claim_workspace.md`
- `docs/patent_draft_composer.md`
- `docs/navbar.md`
- `docs/postgresql_schema.md`
- `docs/frontend_refactor.md`
- `docs/current_status.md`
- `docs/excel_upload_ingestion.md`

These docs may continue to evolve as the product grows.

When implementation details are unclear, prefer the `docs/` files over assumptions.

---

## Documentation rule
As new modules are designed and added, create or update dedicated `.md` files under `docs/`.

Do not overload this root file with detailed feature-specific instructions.

Use this file for:
- project identity
- stack direction
- global implementation rules
- where to find project specifications

Use `docs/` for:
- page specifications
- database specifications
- module-specific behavior
- future feature documentation

---

## Development rule
Implement the system in a modular and practical way.

Write code so that the application can grow over time without becoming difficult to understand or maintain.

Prefer:
- small focused modules
- clear separation of concerns
- readable route/service/model structure
- explicit data flow
- consistent naming

Avoid:
- unnecessary over-engineering
- premature complexity
- speculative architecture for features that do not exist yet

Build only what the current product definition requires.

---

## Modularity rule
Build the system so that major modules can be changed later without rewriting the whole application.

This is especially important for:
- embedding models
- local LLM integrations
- retrieval logic
- extraction modules
- drafting modules
- indexing / vector database workflows

Do not hard-bind the codebase to one permanent implementation.

Prefer practical modularity:
- clear boundaries between modules
- configurable components
- replaceable implementations
- low coupling between subsystems

The goal is not over-engineering.
The goal is to keep the system flexible as modules evolve over time.

When implementing a module, do not assume its first implementation will be permanent.

---

## Frontend rule
A frontend prototype already exists and can be reused where helpful for:
- layout
- visual styling
- modal patterns
- page structure

However, frontend logic must follow the finalized product and database design documented in `docs/`.

Do not preserve incorrect prototype assumptions if they conflict with the current docs.

The frontend source of truth should align as closely as practical with:
- the active patent/project
- claims
- elements
- claim-element links
- patent draft
- upload/index status

---

## Backend rule
Use FastAPI cleanly and practically.

Keep backend code modular as the application grows.

Prefer clear separation between:
- routes
- schemas
- ORM models
- services
- future AI/retrieval modules

Do not introduce unnecessary service complexity.

---

## Database rule
Use the PostgreSQL schema defined in `docs/postgresql_schema.md`.

Keep database logic aligned with the agreed model structure and relationships.

Do not silently rename models or tables without updating the docs.

Keep naming consistent with the agreed project terminology.

---

## AI and retrieval rule
Some features are planned for later integration, including:
- automatic element extraction
- AI-suggested element definitions
- AI-assisted claim drafting
- full patent draft generation
- embedding-based retrieval
- local LLM integration
- ChromaDB vector database creation

Prepare code so these modules can be added cleanly later.

If a module is not yet implemented:
- keep the integration point clean
- do not fake a completed production feature
- document the planned behavior in `docs/` when needed

---

## Editing behavior
When changing code:
- preserve working structure unless the docs require change
- prefer small, targeted edits
- avoid rewriting unrelated parts
- keep naming consistent with the agreed docs
- do not silently change workflows or data assumptions

---

## Priority order
When making implementation decisions, prioritize in this order:

1. correctness relative to the docs
2. simplicity
3. modularity
4. maintainability
5. consistency with the agreed stack and data model

---

## Final instruction
Build a clean, practical patent drafting system that matches the current docs.

Do not overcomplicate the architecture.
Do not underbuild the agreed functionality.

Keep the code modular so the system can grow cleanly as new modules and docs are added over time.
