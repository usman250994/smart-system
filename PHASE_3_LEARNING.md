# Phase 3 Implementation: Source Tracking & Guardrails

## Overview

Phase 3 adds **hallucination safeguards** and **source attribution** so answers are traceable and explainable.

Objectives:
1. Track which page/chunk answered the question.
2. Enforce NOT FOUND response when answer is not in context.
3. Add debug visibility into retrieval quality.

---

## What Changed: File-by-File

### 1. `app/schemas.py` — Enhanced response schema

**Before (Phase 2)**:
```python
class AskResponse(BaseModel):
    answer: str
    confidence: float
```

**After (Phase 3)**:
```python
class AskResponse(BaseModel):
    answer: str
    confidence: float
    source_page: int | None = None        # Which page had the answer
    source_snippet: str | None = None     # Optional snippet
```

New helper schemas:
```python
class RetrievedChunk(BaseModel):
    page: int | None
    content_preview: str

class DebugRetrievalResponse(BaseModel):
    question: str
    chunks_retrieved: list[RetrievedChunk]
    total_chunks: int
```

### 2. `app/rag/prompts.py` — Stricter instructions

**Before (Phase 2)**:
```
"You are a helpful assistant that answers questions strictly from the provided context..."
```

**After (Phase 3)** — explicit NOT FOUND rule:
```
"CRITICAL: You MUST follow these rules EXACTLY:
1. Return response ONLY in JSON format
2. If answer found: {..., "source_page": <page_num>}
3. If NOT found: {"answer": "NOT FOUND", "confidence": 0.0, "source_page": null}
4. DO NOT make up information
5. If uncertain, respond with NOT FOUND rather than guessing"
```

Template now includes page context:
```
"Context (from pages {page_numbers}):\n{context}\n\nQuestion:\n{question}"
```

### 3. `app/rag/metadata.py` — NEW: Page extraction helpers

Utilities to safely extract metadata:
```python
def get_page_number(doc) -> int | None:
    """Extract page number from chunk metadata."""
    if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
        return doc.metadata.get("page")
    return None

def get_all_page_numbers(docs: list) -> list[int]:
    """Get deduplicated page numbers from multiple chunks."""
    pages = set()
    for doc in docs:
        page = get_page_number(doc)
        if page is not None:
            pages.add(page)
    return sorted(pages)
```

### 4. `app/rag/pipeline.py` — Enhanced retrieval and inspection

**ask_with_context() now**:
1. Extracts page numbers from retrieved chunks.
2. Passes page_numbers to prompt template.
3. Handles source_page from model JSON response.
4. Falls back to first doc's page if model didn't provide one.

```python
docs = index_store.search(question, k=3)
page_numbers = get_all_page_numbers(docs)
page_range = ", ".join(str(p + 1) for p in page_numbers)  # 0-indexed -> 1-indexed

user_prompt = RAG_USER_TEMPLATE.format(
    context=context,
    question=question,
    page_numbers=page_range,
)
```

**NEW: inspect_retrieval()** — debug helper:
```python
def inspect_retrieval(question: str) -> list[dict]:
    """Return raw retrieved chunks WITHOUT LLM generation."""
    docs = index_store.search(question, k=3)
    return [
        {
            "page": doc.metadata.get("page"),
            "content_preview": doc.page_content[:300],
        }
        for doc in docs
    ]
```

### 5. `app/main.py` — New endpoints and error handling

**Enhanced /rag/ask**:
```python
def rag_ask(payload: RagAskRequest) -> AskResponse:
    try:
        return ask_with_context(payload.question)
    except RuntimeError as exc:          # No index
        raise HTTPException(status_code=400, ...)
    except ValueError as exc:            # No API key
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}")
    except Exception as exc:             # Other failures
        raise HTTPException(status_code=500, ...)
```

**NEW: /rag/debug** — inspect retrieval quality:
```python
@app.post("/rag/debug")
def rag_debug(payload: RagAskRequest) -> DebugRetrievalResponse:
    """Show which chunks were retrieved for a question (before LLM)."""
    chunks = inspect_retrieval(payload.question)
    return DebugRetrievalResponse(
        question=payload.question,
        chunks_retrieved=[...],
        total_chunks=len(chunks),
    )
```

---

## Concept: Why source_page matters

### Hallucination detection

Different response patterns:
```json
// Good: Answer grounded in source
{
  "answer": "RAG improves accuracy by grounding answers in retrieved context.",
  "confidence": 0.95,
  "source_page": 2
}

// Not found: Model correctly refused
{
  "answer": "NOT FOUND",
  "confidence": 0.0,
  "source_page": null
}

// Risk: No source might indicate hallucination
{
  "answer": "Something plausible but unverified",
  "confidence": 0.5,
  "source_page": null  // ⚠️ Red flag
}
```

### How source_page is captured

1. **Retrieval phase**: FAISS returns chunks with metadata (includes page number).
2. **Prompt phase**: Page numbers injected into user message so model "knows" pages.
3. **Response phase**: Model returns JSON with explicit `source_page`.
4. **Fallback**: If model forgets, we use first document's page.

---

## Phase 3 Testing Workflow

### Test 1: In-context question
```bash
# Upload a PDF, then ask a question that IS in the PDF
POST /rag/ask
{
  "question": "What is mentioned on page 2?"
}

# Expected:
{
  "answer": "...",
  "confidence": 0.9+,
  "source_page": 1        # Pages are 0-indexed internally
}
```

### Test 2: Out-of-context question
```bash
POST /rag/ask
{
  "question": "What is the meaning of life?"
}

# Expected:
{
  "answer": "NOT FOUND",
  "confidence": 0.0,
  "source_page": null     # Model correctly refused
}
```

### Test 3: Inspect retrieval
```bash
POST /rag/debug
{
  "question": "What is mentioned on page 2?"
}

# See what chunks FAISS retrieved BEFORE LLM generation
{
  "question": "What is mentioned on page 2?",
  "chunks_retrieved": [
    {
      "page": 1,
      "content_preview": "This page contains..."
    },
    ...
  ],
  "total_chunks": 3
}
```

This is **critical for debugging**: If /rag/debug shows bad retrieval, the answer will be bad even if the LLM is perfect.

---

## Interview perspective: Why this matters

**Question**: "How do you detect and prevent hallucinations in your RAG system?"

**Strong answer** (using Phase 3):
1. Only allow answers grounded in retrieved context (system prompt + validation).
2. Return source_page so answers are traceable.
3. For out-of-context questions, model returns NOT FOUND instead of guessing.
4. Test retrieval quality independently via /rag/debug endpoint.

**Follow-up**: "What if the model doesn't return a source_page?"

**Strong answer**:
1. Fallback: use first document's page.
2. Ideally, validate model response schema strictly and reject incomplete responses.
3. Log mismatches for debugging.

---

## Common gotchas

### 1. Page numbers are 0-indexed in code, 1-indexed in display

```python
# Internally: page 0, 1, 2, ...
# Display: page 1, 2, 3, ... (so humans don't see page 0)
page_range = ", ".join(str(p + 1) for p in page_numbers)
```

### 2. NOT FOUND confidence is strictly 0.0

System prompt enforces:
```
"If NOT found: {"answer": "NOT FOUND", "confidence": 0.0}"
```

### 3. source_page can be None for NOT FOUND cases

Valid response:
```json
{
  "answer": "NOT FOUND",
  "confidence": 0.0,
  "source_page": null
}
```

### 4. /rag/debug bypasses the LLM — shows raw FAISS results

Same retrieval quality, but:
- No prompt template filling.
- No JSON parsing.
- Just chunk text + metadata.

Useful for: "My answer is wrong because the retrieval is wrong" vs. "Retrieval is good but LLM misunderstood."

---

## What's coming in Phase 4+

- React UI to display source pages.
- Multi-document support (track which PDF too, not just page).
- Chat history with source tracking.
- Analytics on hallucination vs. NOT FOUND rates.

---

## Summary of Phase 3 learning

| Concept | What it is | Why it matters |
|---|---|---|
| source_page | which page gave the answer | traceability + detecting hallucination |
| NOT FOUND | explicit refusal when answer not in context | preventing made-up answers |
| /rag/debug | retrieval-only inspection | debugging retrieval quality independently |
| metadata extraction | safe page number reading | robust handling of chunk metadata |
| page_range in prompt | telling model which pages it should use | grounding LLM in specific sources |

---

## Next: Phase 4

Build React frontend that displays:
- Upload PDF.
- Ask question.
- Show answer + source_page + confidence.

This will make the source tracking visible and useful in a real application.
