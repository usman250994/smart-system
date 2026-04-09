from fastapi import FastAPI, HTTPException

from app.llm_client import ask_llm
from app.schemas import AskRequest, AskResponse

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
