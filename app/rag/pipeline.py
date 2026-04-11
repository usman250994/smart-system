import json

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from app.config import settings
from app.errors import ConfigurationError, ModelOutputError, ProviderAuthError, ProviderUnavailableError
from app.rag import index_store
from app.rag.metadata import get_all_page_numbers
from app.rag.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE
from app.schemas import AskResponse

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def ingest_pdf(file_path: str) -> int:
    """Load a PDF, split into chunks, embed and store in FAISS. Returns chunk count indexed."""
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)
    return index_store.build_and_save(chunks)


def ask_with_context(question: str) -> AskResponse:
    """Retrieve top relevant chunks from FAISS and answer using LLM with context.
    
    Returns answer with confidence and source page tracking for hallucination detection.
    """
    if not settings.openai_api_key:
        raise ConfigurationError(
            message="Live answer generation is currently unavailable.",
            hint="Set a valid OPENAI_API_KEY in the backend environment to enable live answers.",
        )

    docs = index_store.search(question, k=3)
    context = "\n\n".join(doc.page_content for doc in docs)
    page_numbers = get_all_page_numbers(docs)
    page_range = ", ".join(str(p + 1) for p in page_numbers)  # Convert 0-indexed to 1-indexed for display

    user_prompt = RAG_USER_TEMPLATE.format(
        context=context,
        question=question,
        page_numbers=page_range,
    )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = completion.choices[0].message.content
        payload = json.loads(content)
        response = AskResponse.model_validate(payload)
    except AuthenticationError as exc:
        raise ProviderAuthError() from exc
    except (APIConnectionError, RateLimitError) as exc:
        raise ProviderUnavailableError() from exc
    except APIStatusError as exc:
        if exc.status_code in {401, 403}:
            raise ProviderAuthError() from exc
        raise ProviderUnavailableError() from exc
    except json.JSONDecodeError as exc:
        raise ModelOutputError() from exc
    
    # If model did not provide source_page but we have docs, use first doc's page as fallback
    if response.source_page is None and docs:
        response.source_page = docs[0].metadata.get("page")
    
    return response


def inspect_retrieval(question: str) -> list[dict]:
    """Debug helper: return raw retrieved chunks for a question without LLM generation.
    
    Returns list of dicts with page number and content preview.
    """
    if not settings.openai_api_key:
        raise ConfigurationError(
            message="Live answer generation is currently unavailable.",
            hint="Set a valid OPENAI_API_KEY in the backend environment to enable live answers.",
        )

    docs = index_store.search(question, k=3)
    results = []
    for doc in docs:
        page = doc.metadata.get("page") if hasattr(doc, "metadata") else None
        preview = doc.page_content[:300]
        results.append({"page": page, "content_preview": preview})
    return results
