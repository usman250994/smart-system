from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AskResponse(BaseModel):
    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
