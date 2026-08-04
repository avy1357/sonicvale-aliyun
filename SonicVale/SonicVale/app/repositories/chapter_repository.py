from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.po import ChapterPO

# 允许通过 update 更新的字段白名单,防止主键 id、created_at、updated_at 等被覆盖
UPDATABLE_FIELDS = (
    "title", "text_content", "project_id", "order_index",
)


class ChapterRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, chapter_id: int) -> Optional[ChapterPO]:
        """根据 ID 查询章节"""
        return self.db.get(ChapterPO, chapter_id)

    def get_all(self, project_id: int) -> Sequence[ChapterPO]:
        """获取指定项目下的所有章节"""
        stmt = select(ChapterPO).where(ChapterPO.project_id == project_id)
        return self.db.execute(stmt).scalars().all()

    def create(self, chapter_data: ChapterPO) -> ChapterPO:
        """新建章节"""
        self.db.add(chapter_data)
        self.db.commit()
        self.db.refresh(chapter_data)
        return chapter_data

    def update(self, chapter_id: int, chapter_data: dict) -> Optional[ChapterPO]:
        """更新章节"""
        chapter = self.get_by_id(chapter_id)
        if not chapter:
            return None
        for key, value in chapter_data.items():
            # 只过滤白名单字段,允许显式置 None
            if key in UPDATABLE_FIELDS:
                setattr(chapter, key, value)

        self.db.commit()
        self.db.refresh(chapter)
        return chapter

    def delete(self, chapter_id: int) -> bool:
        """删除章节"""
        chapter = self.get_by_id(chapter_id)
        if not chapter:
            return False
        self.db.delete(chapter)
        self.db.commit()
        return True
    # def delete_all_by_project_id(self, project_id: int) -> bool:
    #     """删除指定项目下的所有章节"""
    #     pos = self.get_all(project_id)
    #     for po in pos:
    #         self.db.delete(po)
    #     self.db.commit()
    #     return True

    def get_by_name(self, name: str, project_id: int) -> Optional[ChapterPO]:
        """根据项目ID和章节名称查找章节"""
        stmt = (
            select(ChapterPO)
            .where(ChapterPO.title == name)
            .where(ChapterPO.project_id == project_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def search(self, keyword: str) -> Sequence[ChapterPO]:
        """模糊搜索"""
        # 限制 keyword 长度,防止性能问题
        if keyword and len(keyword) > 100:
            keyword = keyword[:100]
        # 转义 LIKE 通配符,防止注入
        escaped_keyword = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        stmt = select(ChapterPO).where(ChapterPO.title.ilike(f"%{escaped_keyword}%", escape='\\'))
        return self.db.execute(stmt).scalars().all()