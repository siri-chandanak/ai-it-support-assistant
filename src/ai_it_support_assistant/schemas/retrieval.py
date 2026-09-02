from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    score: float


class RetrievalResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]
