from typing import Optional, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.po import PromptPO

# 允许通过 update 更新的字段白名单,防止主键 id、created_at、updated_at 等被覆盖
UPDATABLE_FIELDS = (
    "name", "task", "content", "description",
)


class PromptRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, prompt_id: int) -> Optional[PromptPO]:
        """根据 ID 查询提示词"""
        return self.db.get(PromptPO, prompt_id)

    def get_all(self) -> Sequence[PromptPO]:
        """获取所有提示词"""
        return self.db.execute(select(PromptPO)).scalars().all()

    def create(self, prompt_data: PromptPO) -> PromptPO:
        """新建提示词"""
        self.db.add(prompt_data)
        self.db.commit()
        self.db.refresh(prompt_data)
        return prompt_data

    def update(self, prompt_id: int, prompt_data: dict) -> Optional[PromptPO]:
        """更新提示词"""
        prompt = self.get_by_id(prompt_id)
        if not prompt:
            return None
        for key, value in prompt_data.items():
            # 只过滤白名单字段,允许显式置 None
            if key in UPDATABLE_FIELDS:
                setattr(prompt, key, value)
        self.db.commit()
        self.db.refresh(prompt)
        return prompt

    def delete(self, prompt_id: int) -> bool:
        """删除提示词"""
        prompt = self.get_by_id(prompt_id)
        if not prompt:
            return False
        self.db.delete(prompt)
        self.db.commit()
        return True

    def get_by_name(self, name: str) -> Optional[PromptPO]:
        """根据名称查找提示词"""
        stmt = select(PromptPO).where(PromptPO.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    # 根据任务查询，返回多个提示词
    def get_by_task(self, task: str) -> Sequence[PromptPO]:
        stmt = select(PromptPO).where(PromptPO.task == task)
        return self.db.execute(stmt).scalars().all()


    def search(self, keyword: str) -> Sequence[PromptPO]:
        """模糊搜索"""
        # 限制 keyword 长度,防止性能问题
        if keyword and len(keyword) > 100:
            keyword = keyword[:100]
        # 转义 LIKE 通配符,防止注入
        escaped_keyword = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        stmt = select(PromptPO).where(PromptPO.name.ilike(f"%{escaped_keyword}%", escape='\\'))
        return self.db.execute(stmt).scalars().all()
