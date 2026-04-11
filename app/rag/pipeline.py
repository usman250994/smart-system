import json

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI

from app.config import settings
from app.rag import index_store
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
    """Retrieve top relevant chunks from FAISS and answer using LLM with context."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    docs = index_store.search(question, k=3)
    context = "\n\n".join(doc.page_content for doc in docs)

    user_prompt = RAG_USER_TEMPLATE.format(context=context, question=question)

    client = OpenAI(api_key=settings.openai_api_key)
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
    return AskResponse.model_validate(payload)
