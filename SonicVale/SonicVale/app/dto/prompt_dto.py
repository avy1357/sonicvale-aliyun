from datetime import datetime

from pydantic import BaseModel, Field
from typing import Optional


class PromptCreateDTO(BaseModel):

    """业务实体：提示词"""
    name: str
    task: str = Field(pattern=r'^[\u4e00-\u9fa5a-zA-Z0-9_]{1,255}$')
    description: Optional[str] = None
    content: Optional[str] = Field(default=None, max_length=50000)
    id: Optional[int] = None


class PromptResponseDTO(BaseModel):

    """业务实体：提示词"""
    name: str
    task: str
    description: Optional[str] = None
    content: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None