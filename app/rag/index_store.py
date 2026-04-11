from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from app.config import settings
from app.errors import ConfigurationError, ProviderAuthError, ProviderUnavailableError, ResourceNotReadyError

INDEX_DIR = Path("faiss_index")

_vectorstore: FAISS | None = None


def _get_embeddings() -> OpenAIEmbeddings:
    if not settings.openai_api_key:
        raise ConfigurationError(
            message="Live answer generation is currently unavailable.",
            hint="Set a valid OPENAI_API_KEY in the backend environment to enable live answers.",
        )
    return OpenAIEmbeddings(api_key=settings.openai_api_key)


def build_and_save(documents: list) -> int:
    """Build FAISS index from document chunks and persist to disk. Returns total vectors stored."""
    global _vectorstore
    embeddings = _get_embeddings()
    try:
        _vectorstore = FAISS.from_documents(documents, embeddings)
        INDEX_DIR.mkdir(exist_ok=True)
        _vectorstore.save_local(str(INDEX_DIR))
        return _vectorstore.index.ntotal
    except AuthenticationError as exc:
        raise ProviderAuthError() from exc
    except (APIConnectionError, RateLimitError) as exc:
        raise ProviderUnavailableError() from exc
    except APIStatusError as exc:
        if exc.status_code in {401, 403}:
            raise ProviderAuthError() from exc
        raise ProviderUnavailableError() from exc


def _load_from_disk() -> None:
    global _vectorstore
    embeddings = _get_embeddings()
    _vectorstore = FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def search(query: str, k: int = 3) -> list:
    """Return top-k most relevant document chunks for the given query."""
    global _vectorstore
    if _vectorstore is None:
        if (INDEX_DIR / "index.faiss").exists():
            _load_from_disk()
        else:
            raise ResourceNotReadyError(
                message="No indexed PDF is available yet.",
                hint="Upload a PDF first using POST /upload before asking RAG questions.",
            )
    return _vectorstore.similarity_search(query, k=k)


def index_exists() -> bool:
    return (INDEX_DIR / "index.faiss").exists()
