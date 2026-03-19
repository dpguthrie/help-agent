from __future__ import annotations
from pydantic import BaseModel


class Topic(BaseModel):
    id: str
    name: str
    classification_description: str
    instructions: str
    tools: list[str]
