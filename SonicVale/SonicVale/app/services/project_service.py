import os
import re
import logging

from sqlalchemy import select, delete
from typing import Sequence

from app.core.config import getConfigPath
from app.core.path_security import assert_path_not_system_critical

from app.entity.project_entity import ProjectEntity
from app.models.po import ProjectPO, ChapterPO, RolePO, LinePO

from app.repositories.project_repository import ProjectRepository


class ProjectService:

    def __init__(self, repository: ProjectRepository):
        """注入 repository"""
        self.repository = repository

    def create_project(self,  entity: ProjectEntity):
        """创建新项目
        - 检查同名项目是否存在
        - 如果存在，抛出异常或返回错误
        - 调用 repository.create 插入数据库
        """
        project = self.repository.get_by_name(entity.name)
        if project:
            return None, "项目已存在"
        # 项目根路径为空时默认使用配置目录
        if not entity.project_root_path:
            entity.project_root_path = getConfigPath()
        # 安全校验:防止项目根路径指向系统关键目录
        try:
            assert_path_not_system_critical(entity.project_root_path)
        except ValueError:
            logging.warning("拒绝创建项目,根路径指向系统关键目录: %s", entity.project_root_path)
            return None, "项目根路径非法"
        # 判断项目根路径是否存在
        if not os.path.exists(entity.project_root_path):
            logging.info("项目根路径不存在")
            return  None, "项目根路径不存在"
        # 手动将entity转化为po
        po = ProjectPO(**entity.__dict__)
        res = self.repository.create(po)

        # res(po) --> entity
        data = {k: v for k, v in res.__dict__.items() if not k.startswith("_")}
        entity = ProjectEntity(**data)

        # 将po转化为entity
        return entity, "创建成功"


    def get_project(self, project_id: int) -> ProjectEntity | None:
        """根据 ID 查询项目"""
        po = self.repository.get_by_id(project_id)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        res = ProjectEntity(**data)
        return res

    def get_all_projects(self) -> Sequence[ProjectEntity]:
        """获取所有项目列表"""
        pos = self.repository.get_all()
        # pos -> entities

        entities = [
            ProjectEntity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")})
            for po in pos
        ]
        return entities

    def update_project(self, project_id: int, data:dict) -> bool:
        """更新项目
        - 可以只更新部分字段
        - 检查同名冲突
        """
        name = data.get("name")
        if name:
            existing = self.repository.get_by_name(name)
            if existing and existing.id != project_id:
                return False
        self.repository.update(project_id, data)
        return True

    def delete_project(self, project_id: int) -> bool:
        """删除项目
        - 级联删除关联的 chapters(及其 lines) 和 roles
        - 然后删除项目本身
        """
        db = self.repository.db
        # 先确认项目存在
        project = self.repository.get_by_id(project_id)
        if not project:
            return False
        try:
            # 1. 查询该项目下的所有章节 id
            chapter_ids = db.execute(
                select(ChapterPO.id).where(ChapterPO.project_id == project_id)
            ).scalars().all()
            # 2. 删除这些章节关联的 lines
            if chapter_ids:
                db.execute(
                    delete(LinePO).where(LinePO.chapter_id.in_(chapter_ids))
                )
            # 3. 删除 chapters
            db.execute(
                delete(ChapterPO).where(ChapterPO.project_id == project_id)
            )
            # 4. 删除 roles
            db.execute(
                delete(RolePO).where(RolePO.project_id == project_id)
            )
            # 5. 删除 project 本身并提交
            db.delete(project)
            db.commit()
            return True
        except Exception as e:
            logging.exception("删除项目失败: %s", e)
            db.rollback()
            raise


    def search_projects(self, keyword: str) -> Sequence[ProjectEntity]:
        """模糊搜索项目"""
        pos = self.repository.search(keyword)
        entities = [
            ProjectEntity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")})
            for po in pos
        ]
        return entities

    # 解析content，按照章节
    def parse_content(self, content):
        """解析内容，按照章节"""
        # 正则匹配常见章节格式（支持中英文数字）
        chapter_pattern = re.compile(
            r'(第[\d一二三四五六七八九十百千]+[章回节部卷].*?)(?=\n|$)'
        )
        # 找到所有章节标题位置
        matches = list(chapter_pattern.finditer(content))
        chapters = []
        # 如果没找到章节，直接返回整个文本
        if not matches:
            return chapters

        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)

            chapter_name = match.group(1).strip()
            chapter_content = content[start:end].strip()
            chapters.append({
                "chapter_name": chapter_name,
                "content": chapter_content
            })
        # 排序
        # chapters.sort(key=lambda x: x["chapter_name"])
        # 不需要排序了，因为是顺序解析得到的
        return  chapters
