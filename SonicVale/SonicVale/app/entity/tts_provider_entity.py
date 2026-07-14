
from dataclasses import dataclass
from datetime import datetime
from typing import Optional



@dataclass
class TTSProviderEntity:
    """业务实体：TTS"""
    name: str
    id: Optional[int] = None
    provider_type: Optional[str] = "index_tts"  # index_tts / volcano / aliyun
    api_base_url : Optional[str] = None
    api_key: Optional[str] = None
    x_api_key: Optional[str] = None  # X-Api-Key（火山引擎新版鉴权）
    access_key_id: Optional[str] = None  # AccessKey ID（火山引擎/阿里云 OpenAPI 鉴权用）
    access_key_secret: Optional[str] = None  # AccessKey Secret（火山引擎/阿里云 OpenAPI 鉴权用）
    voice_type: Optional[str] = None  # 音色/发音人（speaker）
    resource_id: Optional[str] = None  # 资源ID（火山引擎：seed-tts-2.0 / seed-tts-1.0 / seed-icl-2.0 等）
    voice_clone_appid: Optional[str] = None  # 语音复刻 AppID
    status : Optional[int] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

