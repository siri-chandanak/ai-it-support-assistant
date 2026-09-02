from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    character_count: int
    chunk_count: int
    indexed_chunk_count: int
    status: str


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    character_count: int


class ExtractedDocument(BaseModel):
    document_id: str
    filename: str
    content_type: str
    text: str
    character_count: int
    chunks: list[DocumentChunk] = Field(default_factory=list)
