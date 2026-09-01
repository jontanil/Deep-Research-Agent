from pydantic import BaseModel


class ResearchRequest(BaseModel):
    query: str = ""


class ResearchResponse(BaseModel):
    content: str
    references: dict[str, int]
