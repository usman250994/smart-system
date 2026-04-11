from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    source_page: int | None = None
    source_snippet: str | None = None


class UploadResponse(BaseModel):
    filename: str
    chunks_indexed: int


class RagAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class RetrievedChunk(BaseModel):
    page: int | None
    content_preview: str = Field(max_length=300)


class DebugRetrievalResponse(BaseModel):
    question: str
    chunks_retrieved: list[RetrievedChunk]
    total_chunks: int
