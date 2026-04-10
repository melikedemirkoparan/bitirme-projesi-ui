# Current Status

## Configuration and infrastructure completed
The initial project configuration is already set up and working.

Completed setup includes:
- FastAPI base application setup
- PostgreSQL database setup
- Docker-based PostgreSQL container setup
- working database connection
- sync SQLAlchemy engine/session setup
- Alembic migration setup
- initial database schema created successfully

The database is live and the current schema is already created in PostgreSQL.

---

## Backend implemented
The backend foundation for the claim workspace is implemented.

Completed backend includes:

### Patent/project backend
- `GET /api/patents`
- `GET /api/patents/{id}`
- `POST /api/patents`
- `DELETE /api/patents/{id}`

### Claim backend
- claim schemas implemented
- claim service implemented
- claim routes implemented
- claim text update support implemented
- patent-scoped claim ownership validation implemented

### Element backend
- element schemas implemented
- element service implemented
- element routes implemented
- patent-scoped element ownership validation implemented

### Claim-element linking backend
- claim-element schemas implemented
- claim-element service implemented
- claim-element routes implemented
- patent-scoped linking / unlinking validation implemented

### Ordered claim-element relation support
- `claim_element.order_index` has been introduced as the relation-level order field
- new claim-element links append to the end of the selected claim’s local order
- linked elements for a claim are returned in `order_index` order
- unlink behavior compacts remaining `order_index` values so order stays contiguous
- relation-level ordering is now part of the backend direction for future claim-local structure handling

---

## Frontend implemented

### Home page
- Home page backend and frontend are implemented
- `static/home.html` is served at `/`
- New Project modal works
- Dynamic document fields work
- Patent + optional nested documents are created transactionally
- Project list refresh works after creation
- home page project selection navigates to the workspace

### Workspace foundation
- `static/workspace.html` exists
- `/workspace` is served from FastAPI
- `openProject()` is connected to workspace navigation
- workspace page shell is implemented
- top navbar is implemented
- 3-panel layout is implemented
- active patent/project context loading is implemented in the workspace

### Claim workspace — implemented so far
- Phase 5 is implemented
- left panel claim list is implemented
- Add Claim modal is implemented
- claim selection is implemented
- claim deletion is implemented
- claim metadata rendering is implemented
- claim cards were visually improved

### Center panel — implemented so far
- Phase 6A.1 is implemented
- patent-level element pool is rendered in the center panel
- center-panel selected-claim hint bar is implemented
- element creation is implemented from the center panel
- patent-level element deletion is implemented from the center panel
- basic element cards are implemented in the center panel

---

## In progress / partially implemented
The project is beyond the initial workspace-connection stage.

The current state is:
- workspace navigation is connected
- backend foundation for claims, elements, and claim-element linking is complete
- relation-level element ordering (`claim_element.order_index`) is introduced
- claim-side left panel is working
- center panel patent-level element pool foundation is working
- the next work is moving from simple pool rendering toward richer element editing and claim-side linked-element structure

---

## Not fully implemented yet

### Claim workspace
- claim-side linked element rendering inside claim cards is not implemented yet
- click-based link / unlink UI is not implemented yet
- drag-and-drop linking is not implemented yet
- explicit up/down reorder UI is not implemented yet
- right panel claim draft editor frontend is not implemented yet
- richer Element Definition modal is not implemented yet

### Element modal direction
- the old simple Add Element modal direction is no longer the intended final direction
- the target is now a richer **Element Definition** modal
- this richer modal is intended to support both:
  - create mode (opened from Add Element)
  - edit mode (opened from an existing element)
- the future modal should include:
  - element name
  - reference number
  - definition textarea
  - linked-claim context
  - relation-level slot/order display from `claim_element.order_index`
  - `AI Suggest Definition` button (stub at first)
  - `AI Suggested Info` button (stub at first)
  - `Copy`
  - `Clear`
  - `Save & Close`

### AI / advanced modules
- AI Suggest Definition is not implemented yet
- AI Suggested Info is not implemented yet
- Excel upload ingestion flow is not implemented yet
- ChromaDB ingestion module is not implemented yet
- definition generator pipeline is not implemented yet
- local offline LLM Docker integration is not implemented yet
- patent draft composer is not yet connected

---

## Current phased position
The project is currently at:

- Phase 5 complete
- Phase 6A.0 complete
- Phase 6A.1 complete
- next step planning is underway

### Completed recent steps
#### Phase 6A.0
- introduced `claim_element.order_index`
- implemented append-to-end relation ordering
- implemented ordered listing by `order_index`
- implemented compact ordering after unlink

#### Phase 6A.1
- implemented the center-panel patent-level element pool
- implemented center-panel selected-claim hint bar
- implemented create/delete element actions
- implemented the current basic center-panel element card layout

---

## Current agreed next direction
The next work should not jump directly to drag-and-drop or AI.

The next direction should be incremental and should move toward the richer screenshot-aligned claim-centric workspace.

### Near-term priorities
- support claim-side linked-element rendering inside claim cards
- support click-based link / unlink
- keep claim-side element rendering compatible with future ordered/tree-like structure
- then add drag-and-drop
- then add reorder controls
- then add the richer Element Definition modal
- later connect AI-related actions

---

## Updated target direction for claim-side element structure

The intended final workspace behavior is more than a flat claim-to-element display.

### Target interaction model
Each claim card is expected to contain an **Element Tree / ordered element structure** area.

This means:
- linked elements should be shown inside the claim card
- the claim card should behave like the local structural workspace of that claim
- elements inside a claim should have an explicit order
- that order should be changeable by the user
- later claim text generation/composition should follow that same stored order

### Important database modeling note
To support ordered claim-side element structure, the database stores element order at the **claim-element relation level**, not at the claim level itself.

The correct place is:

- `claim_element.order_index`

not the `claim` table.

### Why
Because:
- one claim contains many linked elements
- each linked element has its own position inside that specific claim
- the same element may appear in another claim with a different order

So order belongs to the relation:
- `claim ↔ element`

not to the claim record alone.

---

## Intended claim-side ordered behavior
Inside each claim card, the element area should behave like an ordered claim-local structure.

The intended behavior includes:
- linked elements shown inside the claim card
- each linked element rendered in stored order
- user can move an element up
- user can move an element down
- the order updates in the database
- claim-side rendering refreshes in that same order

A likely interaction pattern is:
- click/select an element row inside the claim card
- use an “up” control to move it one position higher
- use a “down” control to move it one position lower

This still does **not yet** require a true nested backend tree model.
At the current planning stage, it remains an **ordered claim-local list / tree-like structure**.

---

## Claim writing implication
When claim text is later composed from the element structure inside a claim card:

- the linked elements should be read in `order_index` order
- the claim-side structure should guide the order in which elements are mentioned
- this order should be preserved in the drafting logic

So the claim card’s element structure is not only visual.
It is intended to become an input to later claim drafting/composition.

---

## Architectural notes
- Elements are patent-level entities, not claim-level entities
- claims and elements are linked through the `claim_element` relation table
- the backend now supports ordered claim-local linked elements through `claim_element.order_index`
- the target direction is an ordered claim-local structure, not a fake premature nested backend tree
- future claim-side tree behavior should be supported incrementally
- the richer Element Definition modal should become the main element editing surface
- the workspace and related modals should visually follow the provided screenshots, while docs remain the source of truth for product behavior

---

Use this file together with `CLAUDE.md` and the docs in `docs/` to understand what is already built, what phase the project is currently in, what structural direction is now established, and what should be implemented next.