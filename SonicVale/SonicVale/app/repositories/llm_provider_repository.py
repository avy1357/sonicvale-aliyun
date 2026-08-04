from typing import Optional, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.po import LLMProviderPO
from app.core.crypto import (
    LLM_PROVIDER_SECRET_FIELDS,
    encrypt_provider_fields,
    decrypt_provider_fields,
    encrypt_provider_dict,
)

# 允许通过 update 更新的字段白名单,防止主键 id、created_at、updated_at 等被覆盖
UPDATABLE_FIELDS = (
    "name", "api_base_url", "api_key", "model_list", "status", "custom_params",
)


class LLMProviderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, llm_provider_id: int) -> Optional[LLMProviderPO]:
        """根据 ID 查询LLM供应商"""
        po = self.db.get(LLMProviderPO, llm_provider_id)
        if po is None:
            return None
        # 关键：解密前先 expunge,避免明文回写数据库
        self.db.expunge(po)
        return decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)

    def get_all(self) -> Sequence[LLMProviderPO]:
        """获取所有LLM供应商"""
        pos = self.db.execute(select(LLMProviderPO)).scalars().all()
        for po in pos:
            # 解密前先脱离 session,避免解密后的明文被 session 跟踪并回写数据库
            self.db.expunge(po)
            decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)
        return pos

    def create(self, llm_provider_data: LLMProviderPO) -> LLMProviderPO:
        """新建LLM供应商"""
        # 写库前对敏感字段加密
        encrypt_provider_fields(llm_provider_data, LLM_PROVIDER_SECRET_FIELDS)
        self.db.add(llm_provider_data)
        self.db.commit()
        self.db.refresh(llm_provider_data)
        # 关键：解密前先 expunge,避免明文回写数据库
        self.db.expunge(llm_provider_data)
        # 读出后解密,返回给上层明文
        decrypt_provider_fields(llm_provider_data, LLM_PROVIDER_SECRET_FIELDS)
        return llm_provider_data

    def update(self, llm_provider_id: int, llm_provider_data: dict) -> Optional[LLMProviderPO]:
        """更新LLM供应商"""
        # 直接从 DB 获取密文 PO,避免 get_by_id 解密后明文被 commit 回写数据库
        llm_provider = self.db.get(LLMProviderPO, llm_provider_id)
        if not llm_provider:
            return None
        # 对 dict 中的敏感字段加密(只加密存在的字段)
        encrypt_provider_dict(llm_provider_data, LLM_PROVIDER_SECRET_FIELDS)
        for key, value in llm_provider_data.items():
            # 只过滤白名单字段,允许显式置 None
            if key in UPDATABLE_FIELDS:
                setattr(llm_provider, key, value)
        self.db.commit()
        self.db.refresh(llm_provider)
        # 关键：解密前先 expunge,避免明文回写数据库
        self.db.expunge(llm_provider)
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
        if po is None:
            return None
        # 关键：解密前先 expunge,避免明文回写数据库
        self.db.expunge(po)
        return decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)

    def search(self, keyword: str) -> Sequence[LLMProviderPO]:
        """模糊搜索"""
        # 限制 keyword 长度,防止性能问题
        if keyword and len(keyword) > 100:
            keyword = keyword[:100]
        # 转义 LIKE 通配符,防止注入
        escaped_keyword = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        stmt = select(LLMProviderPO).where(LLMProviderPO.name.ilike(f"%{escaped_keyword}%", escape='\\'))
        pos = self.db.execute(stmt).scalars().all()
        for po in pos:
            # 解密前先脱离 session,避免解密后的明文被 session 跟踪并回写数据库
            self.db.expunge(po)
            decrypt_provider_fields(po, LLM_PROVIDER_SECRET_FIELDS)
        return pos
