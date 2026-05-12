from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://patent_user:patent_pass_password123@localhost:5433/patent_db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Vector store — path for the persistent ChromaDB client
    chroma_storage_path: str = "./storage"

    # Local filesystem root for user-uploaded patent input documents
    uploads_path: str = "./uploads"

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
