from sqlalchemy import Column, Integer, String, Text, DateTime, Index, ForeignKey
from datetime import datetime, timezone
from app.db.database import Base


class VoiceClonePO(Base):
    """声音复刻记录表"""
    __tablename__ = "voice_clones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tts_provider_id = Column(Integer, ForeignKey("tts_provider.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    speaker_id = Column(String(100), nullable=False, unique=True, index=True)
    reference_path = Column(String(255), nullable=True)
    model_type = Column(Integer, nullable=False, default=1)
    language = Column(Integer, nullable=False, default=0)
    status = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    demo_audio_url = Column(String(500), nullable=True)
    version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), 
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        Index("idx_tts_provider_status", "tts_provider_id", "status"),
    )
