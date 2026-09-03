from pydantic import BaseModel, ConfigDict, Field

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
    insufficient_context: bool
    sources: list[RAGSource]
    retrieved_chunks: list[RetrievedChunk]


class GroundedLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    cited_source_numbers: list[int]
    insufficient_context: bool
