from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.patents import router as patents_router
from app.routes.claims import router as claims_router
from app.routes.elements import router as elements_router
from app.routes.claim_elements import router as claim_elements_router
from app.routes.rag import router as rag_router
from app.routes.bbf_pipeline import router as bbf_pipeline_router
from app.routes.inventor_qa import router as inventor_qa_router
from app.routes.invention_disclosure import router as invention_disclosure_router
from app.routes.research_report import router as research_report_router
from app.routes.assistant import router as assistant_router

app = FastAPI(title="Patent Drafting Tool")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(patents_router)
app.include_router(claims_router)
app.include_router(elements_router)
app.include_router(claim_elements_router)
app.include_router(rag_router)
app.include_router(bbf_pipeline_router)
app.include_router(inventor_qa_router)
app.include_router(invention_disclosure_router)
app.include_router(research_report_router)
app.include_router(assistant_router)

# Serve static frontend files (JS, CSS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Serve the single-page frontend
@app.get("/")
def serve_home():
    return FileResponse("static/home.html", headers={"Cache-Control": "no-store"})


@app.get("/workspace")
def serve_workspace():
    return FileResponse("static/workspace.html", headers={"Cache-Control": "no-store"})
