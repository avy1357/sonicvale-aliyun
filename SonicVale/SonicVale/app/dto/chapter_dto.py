from datetime import datetime

from pydantic import BaseModel, Field
from typing import Optional


class ChapterCreateDTO(BaseModel):
    title: str = Field(max_length=255)
    project_id: int
    order_index: Optional[int] = None
    id: Optional[int] = None
    text_content : Optional[str] = None

class ChapterResponseDTO(ChapterCreateDTO):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
