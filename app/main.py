from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.patents import router as patents_router

app = FastAPI(title="Patent Drafting Tool")

# API routes
app.include_router(patents_router)

# Serve static frontend files (JS, CSS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Serve the single-page frontend
@app.get("/")
def serve_home():
    return FileResponse("static/home.html")
