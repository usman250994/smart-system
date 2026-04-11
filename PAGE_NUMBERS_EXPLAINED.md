# Phase 3 Deep Dive: How Page Numbers & Metadata Work

This guide explains the exact mechanics of page extraction, with step-by-step examples so you understand what happens behind the scenes.

---

## Part 1: What is a "Document" with Metadata?

When LangChain loads and chunks a PDF, each chunk is a **Document object** containing:

```python
# This is what a single chunk looks like internally
chunk = Document(
    page_content="This is the actual text from page 2...",
    metadata={
        "page": 1,                    # 0-indexed: page 1 means the 2nd page
        "source": "sample.pdf",
        # ... other metadata ...
    }
)
```

### Key insight: page_content vs metadata

- `page_content`: The actual text snippet (the paragraph you want to answer with)
- `metadata["page"]`: Where that text came from (which page number)

These are **separate** — one is text, one is location info.

---

## Part 2: How Retrieval Returns Multiple Chunks

When you ask a question, FAISS retrieves the **top 3 most similar chunks**:

```python
# Ask: "What is machine learning?"
docs = index_store.search("What is machine learning?", k=3)

# FAISS returns 3 chunks (most similar first):
docs[0] = Document(
    page_content="Machine learning is a subfield of AI...",
    metadata={"page": 2}
)

docs[1] = Document(
    page_content="Supervised learning uses labeled data...",
    metadata={"page": 3}
)

docs[2] = Document(
    page_content="Algorithms learn patterns from data...",
    metadata={"page": 5}
)
```

So we have **3 chunks from 3 different pages**: 2, 3, and 5 (using 0-indexed).

---

## Part 3: Extracting Page Numbers with Metadata Functions

In [app/rag/metadata.py](app/rag/metadata.py), we have two helper functions:

### Function 1: `get_page_number(doc) -> int | None`

Safely extracts page number from one chunk:

```python
def get_page_number(doc) -> int | None:
    if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
        return doc.metadata.get("page")
    return None
```

**Step-by-step execution**:

```python
# Input
doc = docs[0]  # First chunk

# Step 1: Check if doc has a "metadata" attribute
hasattr(doc, "metadata")  # True ✓

# Step 2: Check if metadata is a dictionary
isinstance(doc.metadata, dict)  # True ✓

# Step 3: Get the "page" key from metadata
doc.metadata.get("page")  # 2

# Output
get_page_number(doc)  # Returns: 2
```

**Why these checks?**
- `hasattr()`: Makes sure the attribute exists (safe).
- `isinstance()`: Confirms it's a dict (safe).
- `.get()`: Returns None if key missing (safe).

### Function 2: `get_all_page_numbers(docs: list) -> list[int]`

Extracts page numbers from **all 3 chunks** and deduplicates:

```python
def get_all_page_numbers(docs: list) -> list[int]:
    pages = set()  # Start with empty set
    for doc in docs:
        page = get_page_number(doc)  # Get single page
        if page is not None:
            pages.add(page)  # Add to set (auto-deduplicates)
    return sorted(pages)  # Return sorted list
```

**Step-by-step execution with our example**:

```python
# Input: our 3 chunks
docs = [
    Document(..., metadata={"page": 2}),
    Document(..., metadata={"page": 3}),
    Document(..., metadata={"page": 5}),
]

# Step 1: Start with empty set
pages = set()  # {}

# Step 2: Loop and extract
for doc in docs:
    page = get_page_number(doc)
    if page is not None:
        pages.add(page)

# After loop 1: page = 2, pages.add(2)   → pages = {2}
# After loop 2: page = 3, pages.add(3)   → pages = {2, 3}
# After loop 3: page = 5, pages.add(5)   → pages = {2, 3, 5}

# Step 3: Sort and return
return sorted(pages)  # [2, 3, 5]

# Output
get_all_page_numbers(docs)  # Returns: [2, 3, 5]
```

---

## Part 4: Converting to Display-Friendly Page Range

In [app/rag/pipeline.py](app/rag/pipeline.py#L40), we convert from code to human-readable:

```python
page_numbers = get_all_page_numbers(docs)  # [2, 3, 5]
page_range = ", ".join(str(p + 1) for p in page_numbers)  # "3, 4, 6"
```

**Why `p + 1`?**

Users see pages starting from 1, but Python indexes start from 0:
- Internally in code: page 0 = first page
- Displayed to humans: page 1 = first page

**Step-by-step**:

```python
# Input
page_numbers = [2, 3, 5]

# Step 1: Add 1 to each (for display)
[p + 1 for p in page_numbers]  # [3, 4, 6]

# Step 2: Convert to strings
[str(p) for p in [3, 4, 6]]  # ["3", "4", "6"]

# Step 3: Join with commas
", ".join(["3", "4", "6"])  # "3, 4, 6"

# Output
page_range = "3, 4, 6"
```

So if your PDF's 3rd, 4th, and 6th pages are where the answer came from, `page_range = "3, 4, 6"`.

---

## Part 5: How Page Range Helps the LLM

Now we have:
- `context`: The actual text snippets (paragraphs)
- `page_range`: Which pages those snippets came from ("3, 4, 6")

We pass **both** to the prompt template:

```python
user_prompt = RAG_USER_TEMPLATE.format(
    context=context,
    question=question,
    page_numbers=page_range,  # Pass the range
)
```

### The template [app/rag/prompts.py](app/rag/prompts.py#L15):

```
Context (from pages {page_numbers}):
{context}

Question:
{question}
```

### After formatting with real data:

```
Context (from pages 3, 4, 6):
Machine learning is a subfield of AI that enables systems to learn from data...

Supervised learning uses labeled data to train models...

Algorithms learn patterns from data without explicit programming...

Question:
What is machine learning?
```

---

## Part 6: Why Page Range Improves LLM Response

### Without page_range (Phase 2 approach):

```
Context:
[just the text paragraphs]

Question:
What is machine learning?
```

LLM thinks:
- "I have some text, but I don't know where it came from."
- Might hallucinate by saying "According to Wikipedia..." or "In general..."
- Less anchored to source.

### With page_range (Phase 3):

```
Context (from pages 3, 4, 6):
[same text paragraphs]

Question:
What is machine learning?

IMPORTANT: If you cannot answer from the context above, respond with NOT FOUND
```

LLM thinks:
- "I have text from pages 3, 4, and 6. I should answer from ONLY this text."
- "If I'm not sure, I should say NOT FOUND, not make something up."
- "I'm accountable to specific sources."
- Responds with `"source_page": 3` or `"source_page": 4`, not something random.

---

## Part 7: Complete Flow with Real Example

### Setup
```python
# PDF: "AI_Basics.pdf" has 10 pages
# Upload and index it
POST /upload → ingest_pdf() → chunks created and indexed

# Each chunk has metadata like:
# Chunk 1: page 0 (internally) = page 1 (for display)
# Chunk 47: page 2 (internally) = page 3 (for display)
# ... and so on
```

### Ask a question
```python
# User asks:
POST /rag/ask → {"question": "What is supervised learning?"}
```

### Behind the scenes
```python
# Step 1: Retrieve
docs = index_store.search("What is supervised learning?", k=3)

# FAISS returns these 3 chunks:
# docs[0] from page 2 (internally) — best match
# docs[1] from page 3 (internally)
# docs[2] from page 5 (internally)

# Step 2: Extract page numbers
page_numbers = get_all_page_numbers(docs)  # [2, 3, 5]

# Step 3: Convert to display range
page_range = ", ".join(str(p + 1) for p in page_numbers)  # "3, 4, 6"

# Step 4: Build context
context = "\n\n".join([docs[0].page_content, docs[1].page_content, docs[2].page_content])
# Result: three paragraphs about supervised learning

# Step 5: Format prompt with page range
user_prompt = RAG_USER_TEMPLATE.format(
    context=context,
    question="What is supervised learning?",
    page_numbers="3, 4, 6"
)

# Resulting prompt sent to LLM:
"""
Context (from pages 3, 4, 6):
[three paragraphs about supervised learning]

Question:
What is supervised learning?

IMPORTANT: ... NOT FOUND ...
"""

# Step 6: LLM responds
{
  "answer": "Supervised learning is training models with labeled data where...",
  "confidence": 0.92,
  "source_page": 3
}
```

### Response back to user
```json
{
  "answer": "Supervised learning is training models with labeled data where each input has a corresponding output label...",
  "confidence": 0.92,
  "source_page": 3
}
```

---

## Part 8: Why This is Better Than Just Text

| Aspect | Without page_range | With page_range |
|---|---|---|
| LLM knows scope | "I have some text" | "I have text from pages 3, 4, 6" |
| Hallucination risk | Higher (makes stuff up) | Lower (anchored to pages) |
| NOT FOUND handling | Rare | Expected when needed |
| Source attribution | Vague | Specific (page number) |
| User trust | "Where did this come from?" | "It's from page 3, I can verify" |

---

## Part 9: Metadata Safety Practices

The helper functions are **defensive**:

```python
def get_page_number(doc) -> int | None:
    if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
        return doc.metadata.get("page")
    return None
```

**Why each check?**

1. `hasattr(doc, "metadata")`:
   - Not all objects have metadata.
   - Prevents `AttributeError`.

2. `isinstance(doc.metadata, dict)`:
   - Metadata might be a weird type.
   - Prevents indexing errors.

3. `.get("page")` instead of `["page"]`:
   - Safely returns None if key missing.
   - Prevents `KeyError`.

**In practice**:
- If chunk has no metadata → returns None → page filtered out.
- If metadata is corrupted → returns None → page filtered out.
- If page key missing → returns None → page filtered out.
- System continues to work, just without that page info.

---

## Part 10: FAQ

### Q: What if all chunks come from the same page?

```python
docs = [
    Document(..., metadata={"page": 2}),
    Document(..., metadata={"page": 2}),
    Document(..., metadata={"page": 2}),
]

page_numbers = [2, 2, 2]  # Before deduplication
sorted(set([2, 2, 2]))    # [2]
page_range = "3"          # After +1 for display

# Prompt includes: "Context (from pages 3):"
```

Good! We deduplicate, so prompt is cleaner.

### Q: What if chunks have no page metadata?

```python
docs = [
    Document(..., metadata={}),  # No "page" key
    Document(..., metadata={}),
    Document(..., metadata={}),
]

page_numbers = []  # get_page_number returns None for all
page_range = ""    # Empty string

# Prompt includes: "Context (from pages ):"
# Still works, just less informative.
```

Graceful degradation.

### Q: Why not just tell the LLM "pages 3, 4, 6" without context?

```
Context (from pages 3, 4, 6):
[NO TEXT INCLUDED]

Question: What is supervised learning?
```

This fails because:
- LLM knows page numbers but has no text to answer from.
- Can't generate a real answer.
- Falls back to hallucination or NOT FOUND.

You **need both**: text (context) + location (page_range).

### Q: Can source_page be different from page_range pages?

Yes, potentially:
- `page_range = "3, 4, 6"` (what was retrieved)
- `source_page = 5` (what the model says answered it)

This is a **red flag** — might indicate:
- Model hallucinating a page number.
- Retrieval quality issue.
- Model misunderstanding scope.

Phase 4 can add validation: reject answers where `source_page` is not in retrieved pages.

---

## Summary: The Data Flow

```
PDF file
  ↓
PyPDFLoader: Extract pages
  ↓
RecursiveCharacterTextSplitter: Create chunks with metadata={"page": X}
  ↓
OpenAIEmbeddings: Convert text to vectors
  ↓
FAISS.from_documents: Store (text + metadata)
  ↓
---
User asks question
  ↓
FAISS.similarity_search: Find top 3 chunks (returns docs with metadata)
  ↓
get_all_page_numbers(docs): Extract [2, 3, 5]
  ↓
page_range = "3, 4, 6": Convert to display format
  ↓
context + page_range + question → Format template
  ↓
LLM receives: "Context (from pages 3, 4, 6): [text]"
  ↓
LLM returns: {"answer": "...", "source_page": 3, ...}
  ↓
Response sent to user with full traceability
```

---

## Next: Using This in Phase 4

In Phase 4 (React UI), we'll display:
- Answer text
- Confidence score
- **Source page (clickable → show that page in PDF viewer)**

So users can instantly verify where the answer came from. That's the power of tracking page_range and source_page together.
