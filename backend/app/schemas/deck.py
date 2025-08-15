from pydantic import BaseModel, Field
from typing import List, Optional

class Slide(BaseModel):
    title: str
    bullets: List[str] = Field(default_factory=list)

class DeckOut(BaseModel):
    id: int
    prospect_id: int
    title: str
    slides: List[Slide]
    pdf_url: Optional[str] = None
