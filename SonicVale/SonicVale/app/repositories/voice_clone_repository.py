from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.voice_clone_po import VoiceClonePO


class VoiceCloneRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: int) -> Optional[VoiceClonePO]:
        """根据 ID 查询声音复刻记录"""
        return self.db.get(VoiceClonePO, id)

    def get_by_speaker_id(self, speaker_id: str) -> Optional[VoiceClonePO]:
        """根据 speaker_id 查询声音复刻记录"""
        return self.db.execute(
            select(VoiceClonePO).where(VoiceClonePO.speaker_id == speaker_id)
        ).scalars().first()

    def get_by_name(self, name: str, tts_provider_id: int) -> Optional[VoiceClonePO]:
        """根据名称查询声音复刻记录（同 TTS 提供商下）"""
        return self.db.execute(
            select(VoiceClonePO).where(
                VoiceClonePO.name == name,
                VoiceClonePO.tts_provider_id == tts_provider_id
            )
        ).scalars().first()

    def get_all_by_tts_provider(self, tts_provider_id: int) -> Sequence[VoiceClonePO]:
        """查询指定 TTS 提供商下的所有声音复刻记录"""
        return self.db.execute(
            select(VoiceClonePO).where(VoiceClonePO.tts_provider_id == tts_provider_id)
            .order_by(VoiceClonePO.created_at.desc())
        ).scalars().all()

    def create(self, data: VoiceClonePO) -> VoiceClonePO:
        """新增声音复刻记录"""
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        return data

    def update(self, clone_id: int, clone_data: dict) -> Optional[VoiceClonePO]:
        """更新声音复刻记录"""
        clone = self.get_by_id(clone_id)
        if not clone:
            return None
        for key, value in clone_data.items():
            setattr(clone, key, value)
        self.db.commit()
        self.db.refresh(clone)
        return clone

    def delete(self, clone_id: int) -> bool:
        """删除声音复刻记录"""
        clone = self.get_by_id(clone_id)
        if not clone:
            return False
        self.db.delete(clone)
        self.db.commit()
        return True
