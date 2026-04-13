from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://patent_user:patent_pass_password123@localhost:5433/patent_db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Vector store — path for the persistent ChromaDB client
    chroma_storage_path: str = "./storage"

    # Local filesystem root for user-uploaded patent input documents
    uploads_path: str = "./uploads"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
