
from datetime import datetime

from pydantic import BaseModel
from typing import Optional



class StrengthCreateDTO(BaseModel):
    name: str
    id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[int] = 1



class StrengthResponseDTO(StrengthCreateDTO):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None