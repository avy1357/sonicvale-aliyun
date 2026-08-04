from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.dto.line_dto import LineOrderDTO
from app.models.po import LinePO

# 允许通过 update 更新的字段白名单,防止主键 id、外键 chapter_id、created_at、updated_at 等被覆盖
UPDATABLE_FIELDS = (
    "text_content", "role_id", "voice_id", "audio_path", "subtitle_path",
    "emotion_id", "strength_id", "instruction", "line_order",
    "status", "is_done",
)


class LineRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, id: int) -> Optional[LinePO]:
        """根据 ID 查询单行台词"""
        return self.db.get(LinePO, id)

    def get_all(self, chapter_id: int) -> Sequence[LinePO]:
        """获取章节下所有单行台词，按 line_order 排序"""
        stmt = (
            select(LinePO)
            .where(LinePO.chapter_id == chapter_id)
            .order_by(LinePO.line_order.asc())  # 升序
        )
        return self.db.execute(stmt).scalars().all()


    def create(self, data: LinePO) -> LinePO:
        """新增单行台词"""
        self.db.add(data)
        self.db.commit()
        self.db.refresh(data)
        return data


    def update(self, line_id: int, line_data: dict) -> Optional[LinePO]:
        """更新单行台词信息"""
        line = self.get_by_id(line_id)
        if not line:
            return None
        for key, value in line_data.items():
            # 只过滤白名单字段,允许显式置 None(如 clear_role_id 清空 role_id)
            if key in UPDATABLE_FIELDS:
                setattr(line, key, value)

        self.db.commit()
        self.db.refresh(line)
        return line

    def delete(self, line_id: int) -> bool:
        """删除台词"""
        line = self.get_by_id(line_id)
        if not line:
            return False
        self.db.delete(line)
        self.db.commit()
        return True
    def delete_all_by_chapter_id(self, chapter_id: int) -> bool:
        """删除章节下的所有台词"""
        lines = self.get_all(chapter_id)
        for line in lines:
            self.db.delete(line)
        self.db.commit()
        return True

    def get_lines_by_role_id(self, role_id: int):
        return self.db.execute(select(LinePO).where(LinePO.role_id == role_id)).scalars().all()

    def batch_update_line_order(self, line_orders: Sequence[LineOrderDTO]) -> int:
        """批量更新台词的顺序"""
        if not line_orders:
            return 0

        from datetime import datetime, timezone
        from sqlalchemy import bindparam
        stmt = (
            update(LinePO)
            .where(LinePO.id == bindparam("id"))
            .values(
                line_order=bindparam("line_order"),
                # 显式更新 updated_at,因为 Core 的 update() 不会触发 ORM 的 onupdate
                updated_at=datetime.now(timezone.utc),
            )
        )
        params = [{"id": it.id, "line_order": it.line_order} for it in line_orders]
        res = self.db.execute(stmt, params)  # executemany
        self.db.commit()
        return res.rowcount if res.rowcount not in (None, -1) else len(params)
