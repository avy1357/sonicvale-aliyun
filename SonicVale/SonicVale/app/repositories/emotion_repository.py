from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.po import EmotionPO

# 允许通过 update 更新的字段白名单,防止主键 id、is_active、created_at、updated_at 等被覆盖
UPDATABLE_FIELDS = (
    "name", "description",
)


class EmotionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, record_id: int) -> Optional[EmotionPO]:
        """通过id获取情绪"""
        return self.db.query(EmotionPO).filter(EmotionPO.id == record_id).first()

    def get_by_name(self, name: str) -> Optional[EmotionPO]:
        """通过名称获取情绪"""
        return self.db.query(EmotionPO).filter(EmotionPO.name == name).first()

    def get_all(self) -> Sequence[EmotionPO]:
        """获取所有情绪"""
        return self.db.query(EmotionPO).all()

    def create(self, emotion: EmotionPO) -> EmotionPO:
        """创建情绪"""

        self.db.add(emotion)
        self.db.commit()
        self.db.refresh(emotion)
        return emotion

    def update(self, record_id: int, data: dict) -> Optional[EmotionPO]:
        """更新情绪"""
        emotion = self.get_by_id(record_id)
        if not emotion:
            return None
        for key, value in data.items():
            # 只过滤白名单字段,允许显式置 None
            if key in UPDATABLE_FIELDS:
                setattr(emotion, key, value)
        self.db.commit()
        self.db.refresh(emotion)
        return emotion

    def delete(self, record_id: int) -> bool:
        """删除情绪"""
        emotion = self.get_by_id(record_id)
        if not emotion:
            return False
        self.db.delete(emotion)
        self.db.commit()
        return True


