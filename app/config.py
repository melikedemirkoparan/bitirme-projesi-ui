from pathlib import Path

from pydantic_settings import BaseSettings

# Project root — this file is app/config.py, so the root is two
# parents up. Storage/upload paths are anchored here so they stay
# stable no matter which directory uvicorn is launched from. A
# relative "./storage" resolves against the process CWD, so ChromaDB
# silently pointed at a different (empty) folder whenever the server
# started elsewhere — the cause of the recurring "No Data" / data
# lost-on-restart bug.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://patent_user:patent_pass_password123@localhost:5433/patent_db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Vector store — absolute path for the persistent ChromaDB client.
    chroma_storage_path: str = str(_PROJECT_ROOT / "storage")

    # Local filesystem root for user-uploaded patent input documents.
    uploads_path: str = str(_PROJECT_ROOT / "uploads")

    # Local LLM — Ollama inference endpoint and model selection
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    # Per-request timeout in seconds. Long-context prompts (e.g. P2 over a
    # full element-patent analysis) on a 7B model can take several minutes
    # on consumer hardware, so the default is generous. Lower it on faster
    # GPUs.
    ollama_timeout: float = 600.0

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
