from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.po import TTSProviderPO
from app.core.crypto import (
    TTS_PROVIDER_SECRET_FIELDS,
    encrypt_provider_fields,
    decrypt_provider_fields,
    encrypt_provider_dict,
)

# 可更新字段白名单, 防止主键/外键/时间戳被误覆盖
UPDATABLE_FIELDS = (
    "name",
    "provider_type",
    "api_base_url",
    "api_key",
    "x_api_key",
    "access_key_id",
    "access_key_secret",
    "voice_type",
    "resource_id",
    "voice_clone_appid",
    "status",
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

    def update(self, tts_provider_id: int, tts_provider_data: dict) -> Optional[TTSProviderPO]:
        """更新tts供应商信息"""
        tts_provider = self.get_by_id(tts_provider_id)
        if not tts_provider:
            return None
        # 对 dict 中的敏感字段加密(只加密存在的字段)
        encrypt_provider_dict(tts_provider_data, TTS_PROVIDER_SECRET_FIELDS)
        for key, value in tts_provider_data.items():
            if key in UPDATABLE_FIELDS and value is not None:
                setattr(tts_provider, key, value)

        self.db.commit()
        self.db.refresh(tts_provider)
        decrypt_provider_fields(tts_provider, TTS_PROVIDER_SECRET_FIELDS)
        return tts_provider

    def delete(self, tts_provider_id: int) -> bool:
        """删除tts供应商"""
        tts_provider = self.db.get(TTSProviderPO, tts_provider_id)
        if not tts_provider:
            return False
        self.db.delete(tts_provider)
        self.db.commit()
        return True

    def get_by_name(self, name: str) -> Optional[TTSProviderPO]:
        """根据名称查找tts供应商信息"""
        po = self.db.execute(select(TTSProviderPO).where(TTSProviderPO.name == name)).scalars().first()
        return decrypt_provider_fields(po, TTS_PROVIDER_SECRET_FIELDS)


