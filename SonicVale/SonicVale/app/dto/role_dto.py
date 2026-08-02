from datetime import datetime

from pydantic import BaseModel
from typing import Optional


class RoleCreateDTO(BaseModel):
    name: str
    project_id: int
    id: Optional[int] = None
    default_voice_id: Optional[int] = None
    instruction: Optional[str] = None  # 语音风格指令

class RoleResponseDTO(RoleCreateDTO):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

