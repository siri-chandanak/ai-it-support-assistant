from pydantic import BaseModel, Field

from ai_it_support_assistant.schemas.retrieval import RetrievedChunk


class RAGRequest(BaseModel):
    question: str = Field(min_length=1)


class RAGSource(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    score: float


class RAGResponse(BaseModel):
    question: str
    answer: str
    sources: list[RAGSource]
    retrieved_chunks: list[RetrievedChunk]
