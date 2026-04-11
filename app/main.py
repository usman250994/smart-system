import os
from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.llm_client import ask_llm
from app.rag.pipeline import ingest_pdf, ask_with_context, inspect_retrieval
from app.schemas import (
    AskRequest,
    AskResponse,
    RagAskRequest,
    UploadResponse,
    DebugRetrievalResponse,
    RetrievedChunk,
)

DATA_DIR = Path("data")

app = FastAPI(title="GenAI Learning API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/ask",
    responses={500: {"description": "LLM request failed or returned invalid output"}},
)
def ask(payload: AskRequest) -> AskResponse:
    try:
        return ask_llm(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM request failed: {exc}") from exc


@app.post(
    "/upload",
    responses={400: {"description": "Uploaded file is not a PDF"},
               500: {"description": "Failed to process or index the PDF"}},
)
async def upload(file: Annotated[UploadFile, File(description="PDF file to index")]) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    DATA_DIR.mkdir(exist_ok=True)
    save_path = DATA_DIR / file.filename
    try:
        contents = await file.read()
        save_path.write_bytes(contents)
        chunks = ingest_pdf(str(save_path))
        return UploadResponse(filename=file.filename, chunks_indexed=chunks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {exc}") from exc


@app.post(
    "/rag/ask",
    responses={400: {"description": "No PDF has been indexed yet"},
               500: {"description": "RAG pipeline or LLM request failed"}},
)
def rag_ask(payload: RagAskRequest) -> AskResponse:
    try:
        return ask_with_context(payload.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG request failed: {exc}") from exc


@app.post(
    "/rag/debug",
    responses={400: {"description": "No PDF has been indexed yet"},
               500: {"description": "Retrieval inspection failed"}},
)
def rag_debug(payload: RagAskRequest) -> DebugRetrievalResponse:
    """Debug endpoint: show which chunks are retrieved for a question (before LLM generation)."""
    try:
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
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Debug request failed: {exc}") from exc
