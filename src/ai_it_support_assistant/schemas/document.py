from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str
    character_count: int
    status: str


class ExtractedDocument(BaseModel):
    document_id: str
    filename: str
    content_type: str
    text: str
    character_count: int
