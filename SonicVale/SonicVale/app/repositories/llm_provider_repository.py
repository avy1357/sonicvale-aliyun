from typing import List, Optional, Sequence, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, Row, RowMapping
from app.models.po import LLMProviderPO
from app.core.crypto import (
    LLM_PROVIDER_SECRET_FIELDS,
    encrypt_provider_fields,
    decrypt_provider_fields,
    encrypt_provider_dict,
)


class LLMProviderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, llm_provider_id: int) -> Optional[LLMProviderPO]:
        """根据 ID 查询LLM供应商"""
        po = self.db.get(LLMProviderPO, llm_provider_id)
        return decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)

    def get_all(self) -> Sequence[LLMProviderPO]:
        """获取所有LLM供应商"""
        pos = self.db.execute(select(LLMProviderPO)).scalars().all()
        for po in pos:
            decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)
        return pos

    def create(self, llm_provider_data: LLMProviderPO) -> LLMProviderPO:
        """新建LLM供应商"""
        # 写库前对敏感字段加密
        encrypt_provider_fields(llm_provider_data, LLM_PROVIDER_SECRET_FIELDS)
        self.db.add(llm_provider_data)
        self.db.commit()
        self.db.refresh(llm_provider_data)
        # 读出后解密,返回给上层明文
        decrypt_provider_fields(llm_provider_data, LLM_PROVIDER_SECRET_FIELDS)
        return llm_provider_data

    def update(self, llm_provider_id: int, llm_provider_data: dict) -> Optional[LLMProviderPO]:
        """更新LLM供应商"""
        llm_provider = self.get_by_id(llm_provider_id)
        if not llm_provider:
            return None
        # 对 dict 中的敏感字段加密(只加密存在的字段)
        encrypt_provider_dict(llm_provider_data, LLM_PROVIDER_SECRET_FIELDS)
        for key, value in llm_provider_data.items():
            if value is not None:  # 只更新不为空的字段
                setattr(llm_provider, key, value)
        self.db.commit()
        self.db.refresh(llm_provider)
        decrypt_provider_fields(llm_provider, LLM_PROVIDER_SECRET_FIELDS)
        return llm_provider

    def delete(self, llm_provider_id: int) -> bool:
        """删除LLM供应商"""
        llm_provider = self.db.get(LLMProviderPO, llm_provider_id)
        if not llm_provider:
            return False
        self.db.delete(llm_provider)
        self.db.commit()
        return True

    def get_by_name(self, name: str) -> Optional[LLMProviderPO]:
        """根据名称查找LLM供应商"""
        stmt = select(LLMProviderPO).where(LLMProviderPO.name == name)
        po = self.db.execute(stmt).scalar_one_or_none()
        return decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)

    def search(self, keyword: str) -> Sequence[LLMProviderPO]:
        """模糊搜索"""
        stmt = select(LLMProviderPO).where(LLMProviderPO.name.ilike(f"%{keyword}%"))
        pos = self.db.execute(stmt).scalars().all()
        for po in pos:
            decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)
        return pos
