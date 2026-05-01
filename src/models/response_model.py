from pydantic import BaseModel
from typing import List

class ResearchDocument(BaseModel):
    content: str
    references: List[str]