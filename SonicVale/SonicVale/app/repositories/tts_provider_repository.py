from typing import Optional

from sqlalchemy import Sequence, select
from sqlalchemy.orm import Session

from app.models.po import TTSProviderPO
from app.core.crypto import (
    TTS_PROVIDER_SECRET_FIELDS,
    encrypt_provider_fields,
    decrypt_provider_fields,
    encrypt_provider_dict,
)


class TTSProviderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: int) -> Optional[TTSProviderPO]:
        """根据 ID 查询tts供应商"""
        po = self.db.get(TTSProviderPO, id)
        return decrypt_provider_fields(po, TTS_PROVIDER_SECRET_FIELDS)

    def get_all(self) -> Sequence[TTSProviderPO]:
        """获取tts下所有tts供应商"""
        pos = self.db.execute(select(TTSProviderPO)).scalars().all()
        for po in pos:
            decrypt_provider_fields(po, TTS_PROVIDER_SECRET_FIELDS)
        return pos


    def create(self, data: TTSProviderPO) -> TTSProviderPO:

        """新增tts供应商"""
        # 写库前对敏感字段加密
        encrypt_provider_fields(data, TTS_PROVIDER_SECRET_FIELDS)
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        # 读出后解密,返回给上层明文
        decrypt_provider_fields(data, TTS_PROVIDER_SECRET_FIELDS)
        return data


    def update(self, tts_provider_id: int, voice_data: dict) -> Optional[TTSProviderPO]:
        """更新tts供应商信息"""
        voice = self.get_by_id(tts_provider_id)
        if not voice:
            return None
        # 对 dict 中的敏感字段加密(只加密存在的字段)
        encrypt_provider_dict(voice_data, TTS_PROVIDER_SECRET_FIELDS)
        for key, value in voice_data.items():
            if value is not None:  # 只更新不为空的字段
                setattr(voice, key, value)

        self.db.commit()
        self.db.refresh(voice)
        decrypt_provider_fields(voice, TTS_PROVIDER_SECRET_FIELDS)
        return voice

    # def delete(self, voice_id: int) -> bool:
    #     """删除项目"""
    #     voice = self.get_by_id(voice_id)
    #     if not voice:
    #         return False
    #     self.db.delete(voice)
    #     self.db.commit()
    #     return True
    #
    #
    def get_by_name(self, name: str) -> Optional[TTSProviderPO]:
        """根据名称查找项目下的tts供应商信息"""
        po = self.db.execute(select(TTSProviderPO).where(TTSProviderPO.name == name)).scalars().first()
        return decrypt_provider_fields(po, TTS_PROVIDER_SECRET_FIELDS)


