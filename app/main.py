from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.error_handlers import register_exception_handlers
from app.errors import UserInputError
from app.llm_client import ask_llm
from app.config import settings
from app.rag.index_store import index_exists
from app.rag.pipeline import ingest_pdf, ask_with_context, inspect_retrieval
from app.schemas import (
    AskRequest,
    AskResponse,
    RagAskRequest,
    SystemStatusResponse,
    UploadResponse,
    DebugRetrievalResponse,
    RetrievedChunk,
)

DATA_DIR = Path("data")

app = FastAPI(title="GenAI Learning API", version="0.1.0")
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):517[0-9]$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def status() -> SystemStatusResponse:
    provider_configured = bool(settings.openai_api_key)
    indexed_pdf_available = index_exists()
    if not provider_configured:
        message = "Live indexing and answer generation are disabled until OPENAI_API_KEY is configured."
    elif not indexed_pdf_available:
        message = "Backend is ready. Upload a PDF to build the FAISS index."
    else:
        message = "Backend is ready. A PDF index is available for RAG questions."

    return SystemStatusResponse(
        provider_configured=provider_configured,
        indexed_pdf_available=indexed_pdf_available,
        message=message,
    )


@app.post(
    "/ask",
    responses={
        502: {"description": "LLM returned invalid structured output"},
        503: {"description": "LLM provider auth or availability issue"},
    },
)
def ask(payload: AskRequest) -> AskResponse:
    return ask_llm(payload.question)


@app.post(
    "/upload",
    responses={
        400: {"description": "Uploaded file is not a PDF"},
        500: {"description": "Failed to process or index the PDF"},
    },
)
async def upload(file: Annotated[UploadFile, File(description="PDF file to index")]) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise UserInputError(
            message="Only PDF files are accepted.",
            hint="Upload a file whose name ends with .pdf.",
        )
    DATA_DIR.mkdir(exist_ok=True)
    save_path = DATA_DIR / file.filename
    contents = await file.read()
    save_path.write_bytes(contents)
    chunks = ingest_pdf(str(save_path))
    return UploadResponse(filename=file.filename, chunks_indexed=chunks)


@app.post(
    "/rag/ask",
    responses={
        400: {"description": "No PDF has been indexed yet"},
        502: {"description": "LLM returned invalid structured output"},
        503: {"description": "LLM provider auth or availability issue"},
    },
)
def rag_ask(payload: RagAskRequest) -> AskResponse:
    return ask_with_context(payload.question)


@app.post(
    "/rag/debug",
    responses={
        400: {"description": "No PDF has been indexed yet"},
        503: {"description": "Live provider configuration is unavailable"},
    },
)
def rag_debug(payload: RagAskRequest) -> DebugRetrievalResponse:
    """Debug endpoint: show which chunks are retrieved for a question (before LLM generation)."""
    chunks = inspect_retrieval(payload.question)
    retrieved = [
        RetrievedChunk(
            page=chunk["page"],
            content_preview=chunk["content_preview"],
        )
        for chunk in chunks
    ]
    return DebugRetrievalResponse(
        question=payload.question,
        chunks_retrieved=retrieved,
        total_chunks=len(retrieved),
    )
