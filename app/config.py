from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://patent_user:patent_pass@localhost:5432/patent_db"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Vector store — path for the persistent ChromaDB client
    chroma_storage_path: str = "./storage"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
