from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class ErrorBody(BaseModel):
    code: str
    message: str
    hint: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AskResponse(BaseModel):
    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    source_page: int | None = None
    source_snippet: str | None = None


class UploadResponse(BaseModel):
    filename: str
    chunks_indexed: int


class SystemStatusResponse(BaseModel):
    provider_configured: bool
    indexed_pdf_available: bool
    message: str


class RagAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class RetrievedChunk(BaseModel):
    page: int | None
    content_preview: str = Field(max_length=300)


class DebugRetrievalResponse(BaseModel):
    question: str
    chunks_retrieved: list[RetrievedChunk]
    total_chunks: int
