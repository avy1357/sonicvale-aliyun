from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VoiceCloneCreateDTO(BaseModel):
    """创建声音复刻请求"""
    tts_provider_id: int
    name: str
    speaker_id: str
    reference_path: Optional[str] = None
    model_type: int = Field(default=1, ge=1, le=4, description="模型类型: 1=ICL1.0, 2=DiT标准, 3=DiT还原, 4=ICL2.0")
    language: int = Field(default=0, ge=0, le=2, description="语种: 0=中文, 1=英文, 2=日语")
    description: Optional[str] = None


class VoiceCloneResponseDTO(BaseModel):
    """声音复刻响应"""
    id: Optional[int] = None
    tts_provider_id: int
    name: str
    speaker_id: str
    reference_path: Optional[str] = None
    model_type: int
    language: int
    status: int
    description: Optional[str] = None
    demo_audio_url: Optional[str] = None
    version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VoiceCloneUploadDTO(BaseModel):
    """上传音频训练请求"""
    clone_id: int
    reference_path: str
    text: Optional[str] = None
    enable_denoise: bool = True
    denoise_model_id: str = ""
    enable_mss: bool = False
    enable_crop_by_asr: bool = False


class VoiceCloneStatusDTO(BaseModel):
    """查询训练状态响应"""
    clone_id: int
    speaker_id: str
    status: int
    version: Optional[str] = None
    demo_audio_url: Optional[str] = None
    message: str


class VoiceCloneTrainDTO(BaseModel):
    """提交训练并等待完成请求"""
    clone_id: int
    reference_path: str
    text: Optional[str] = None
    max_wait_seconds: int = Field(default=120, le=600, description="最大等待秒数，默认120，上限600")
    poll_interval: int = 5
    enable_denoise: bool = True
    denoise_model_id: str = ""
    enable_mss: bool = False
    enable_crop_by_asr: bool = False


class AliyunVoiceCreateDTO(BaseModel):
    """阿里云声音复刻创建请求"""
    tts_provider_id: int
    target_model: str = Field(description="语音合成模型，如 cosyvoice-v3-plus。必须与后续语音合成接口使用的模型一致，否则合成会失败")
    prefix: str = Field(description="音色名称前缀，仅允许数字和英文字母，不超过10个字符", pattern=r'^[a-zA-Z0-9]{1,10}$')
    url: str = Field(description="音频文件URL（公网可访问）")
    language_hints: Optional[List[str]] = Field(default=None, description="样本音频语种提示列表")
    max_prompt_audio_length: Optional[float] = Field(default=None, ge=3.0, le=30.0, description="参考音频最大时长（秒）")
    enable_preprocess: Optional[bool] = Field(default=None, description="是否开启音频预处理")


class AliyunVoiceUpdateDTO(BaseModel):
    """阿里云声音复刻更新请求"""
    tts_provider_id: int
    voice_id: str
    url: str = Field(description="新的音频文件URL")
    language_hints: Optional[List[str]] = Field(default=None, description="样本音频语种提示列表")
    max_prompt_audio_length: Optional[float] = Field(default=None, ge=3.0, le=30.0, description="参考音频最大时长（秒）")
    enable_preprocess: Optional[bool] = Field(default=None, description="是否开启音频预处理")
