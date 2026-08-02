from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LLMProviderCreateDTO(BaseModel):
    """业务实体：LLM"""
    name: str
    id: Optional[int] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_list: Optional[str] = None
    status: Optional[int] = None
    custom_params: Optional[str] = None


class LLMProviderResponseDTO(BaseModel):
    """业务实体：LLM"""
    name: str
    id: Optional[int] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_list: Optional[str] = None
    status: Optional[int] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    custom_params: Optional[str] = None