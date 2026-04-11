from pydantic import BaseModel


class CollectionResultResponse(BaseModel):
    collection_name: str
    status: str       # "created" | "skipped" | "error"
    doc_count: int = 0
    reason: str = ""


class IngestResponse(BaseModel):
    filename: str
    success: bool
    error: str = ""
    collections: list[CollectionResultResponse] = []


class CollectionInfo(BaseModel):
    name: str
    doc_count: int


class IngestStatusResponse(BaseModel):
    has_data: bool
    collections: list[CollectionInfo] = []
