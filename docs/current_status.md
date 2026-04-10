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

## Implemented
- Home page backend and frontend are implemented
- `GET /api/patents`
- `GET /api/patents/{id}`
- `POST /api/patents`
- `DELETE /api/patents/{id}`
- `static/home.html` is served at `/`
- New Project modal works
- Dynamic document fields work
- Patent + optional nested documents are created transactionally
- Project list refresh works after creation

---

## Not fully implemented yet
- Project open flow is not complete
- `openProject()` is still a stub
- Claim workspace is not yet connected
- Patent draft composer is not yet connected

---

## Next intended step
- Implement the project open flow
- Connect home page project selection to the claim workspace

---

Use this file together with the docs in `docs/` to understand what is already built and what remains to be implemented.
