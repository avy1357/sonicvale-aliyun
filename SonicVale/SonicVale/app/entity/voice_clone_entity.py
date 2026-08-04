from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VoiceCloneEntity:
    """声音复刻业务实体"""
    tts_provider_id: int
    name: str
    speaker_id: str
    id: Optional[int] = None
    model_type: int = 1
    language: int = 0
    status: int = 0
    reference_path: Optional[str] = None
    description: Optional[str] = None
    demo_audio_url: Optional[str] = None
    version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
