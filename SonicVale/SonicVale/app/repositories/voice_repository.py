from typing import Optional

from sqlalchemy import Sequence, select
from sqlalchemy.orm import Session

from app.models.po import VoicePO


class VoiceRepository:
    # 允许通过 update 更新的字段白名单,防止主键 id、外键 tts_provider_id 等被覆盖
    UPDATABLE_FIELDS = {"name", "reference_path", "description", "is_multi_emotion"}

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: int) -> Optional[VoicePO]:
        """根据 ID 查询音色"""
        return self.db.get(VoicePO, id)

    def get_all(self, tts_provider_id: int) -> Sequence[VoicePO]:
        """获取tts下所有音色"""
        return self.db.execute(select(VoicePO).where(VoicePO.tts_provider_id == tts_provider_id)).scalars().all()

    def get_by_ids(self, tts_provider_id: int, ids: list[int]) -> Sequence[VoicePO]:
        """根据ids获取tts下的音色"""
        if not ids:
            return []
        return self.db.execute(
            select(VoicePO).where(VoicePO.tts_provider_id == tts_provider_id, VoicePO.id.in_(ids))
        ).scalars().all()


    def create(self, data: VoicePO) -> VoicePO:
        """新增音色"""
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        return data


    def update(self, voice_id: int, voice_data: dict) -> Optional[VoicePO]:
        """更新音色信息(仅允许白名单字段,防止主键/外键被覆盖)"""
        voice = self.get_by_id(voice_id)
        if not voice:
            return None
        for key, value in voice_data.items():
            # 只更新白名单字段,过滤 id、tts_provider_id、created_at、updated_at 等
            if key in self.UPDATABLE_FIELDS:
                setattr(voice, key, value)

        self.db.commit()
        self.db.refresh(voice)
        return voice

    def delete(self, voice_id: int) -> bool:
        """删除项目"""
        voice = self.get_by_id(voice_id)
        if not voice:
            return False
        self.db.delete(voice)
        self.db.commit()
        return True


    def get_by_name(self, name: str, tts_provider_id: int) -> Optional[VoicePO]:
        """根据名称查找tts供应商下的音色信息"""
        return self.db.execute(select(VoicePO).where(VoicePO.name == name, VoicePO.tts_provider_id == tts_provider_id)).scalars().first()


