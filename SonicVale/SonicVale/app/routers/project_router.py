import os
import shutil
import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from sqlalchemy.orm import Session

from app.core.config import getConfigPath
from app.core.path_security import validate_path_within_root
from app.core.response import Res
from app.db.database import get_db
from app.dto.project_dto import ProjectCreateDTO, ProjectResponseDTO, ProjectImportDTO
from app.entity.chapter_entity import ChapterEntity
from app.entity.project_entity import ProjectEntity
from app.models.po import ChapterPO
from app.repositories.chapter_repository import ChapterRepository
from app.services.chapter_service import ChapterService
from app.services.project_service import ProjectService
from app.repositories.project_repository import ProjectRepository

# 初始化 router
router = APIRouter(prefix="/projects", tags=["Projects"])

# 依赖注入（实际项目可用 DI 容器）

def get_service(db: Session = Depends(get_db)) -> ProjectService:
    repository = ProjectRepository(db)  # ✅ 传入 db
    return ProjectService(repository)

def get_chapter_service(db: Session = Depends(get_db)) -> ChapterService:
    repository = ChapterRepository(db)  # ✅ 传入 db
    return ChapterService(repository)


@router.post("/", response_model=Res[ProjectResponseDTO],
             summary="创建项目",
             description="根据项目信息创建项目，项目名称不可重复")
def create_project(dto: ProjectCreateDTO, service: ProjectService = Depends(get_service)):
    """
    创建项目
    - dto: 前端 POST JSON 传入参数
    - service: Service 层注入
    """
    try:
        # DTO → Entity
        entity = ProjectEntity(**dto.model_dump())

        # 调用 Service 创建项目（返回 True/False）
        entity_res,message = service.create_project(entity)

        # 返回统一 Response
        if entity_res is not None:
            # 创建成功，可以返回 DTO 或者部分字段
            res = ProjectResponseDTO(**entity_res.__dict__)
            return Res(data=res, code=200, message="创建成功")
        else:
            return Res(data=None, code=400, message=message)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# 按id查找
@router.get("/{project_id}", response_model=Res[ProjectResponseDTO],
            summary="查询项目",
            description="根据项目ID查询项目信息")
def get_project(project_id: int, service: ProjectService = Depends(get_service)):
    entity = service.get_project(project_id)
    if entity:
        res = ProjectResponseDTO(**entity.__dict__)
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=None, code=404, message="项目不存在")

@router.get("/", response_model=Res[List[ProjectResponseDTO]],
            summary="查询所有项目",
            description="查询所有项目信息")
def get_all_projects(service: ProjectService = Depends(get_service)):
    entities = service.get_all_projects()
    dtos = [ProjectResponseDTO(**e.__dict__) for e in entities]
    return Res(data=dtos, code=200, message="查询成功")


# ------------------- 修改项目 -------------------
@router.put("/{project_id}", response_model=Res[ProjectResponseDTO],
            summary="修改项目",
            description="根据项目ID修改项目信息")
def update_project(project_id: int, dto: ProjectCreateDTO, service: ProjectService = Depends(get_service)):

    # 先根据id进行查找
    project = service.get_project(project_id)
    if not project:
        return Res(data=None, code=400, message="项目不存在")

    success = service.update_project(project_id,dto.model_dump(exclude_unset=True))
    if success:
        updated_project = service.get_project(project_id)
        return Res(data=ProjectResponseDTO(**updated_project.__dict__), code=200, message="更新成功")
    else:
        return Res(data=None, code=400, message="更新失败")


# ------------------- 删除项目 -------------------
@router.delete("/{project_id}", response_model=Res,
               summary="删除项目",
               description="根据项目ID删除项目,并且级联删除项目下所有章节以及内容")
def delete_project(project_id: int, service: ProjectService = Depends(get_service)):

    try:
        # 1. 先查项目,不存在直接返回 404
        project = service.get_project(project_id)
        if not project:
            return Res(data=None, code=404, message="项目不存在")

        # 2. 路径白名单校验:project_root_path 必须在用户目录的 SonicVale 下
        #    防止被污染的路径导致任意目录被删
        root = getConfigPath()
        try:
            validate_path_within_root(project.project_root_path, root)
        except ValueError as e:
            logging.warning("拒绝删除项目 %s,根路径超出允许范围: %s", project_id, project.project_root_path)
            return Res(data=None, code=400, message=f"项目根路径非法,拒绝删除")

        project_path = os.path.join(project.project_root_path, str(project_id))
        try:
            validate_path_within_root(project_path, project.project_root_path)
        except ValueError as e:
            return Res(data=None, code=400, message=f"项目路径非法,拒绝删除")

        # 3. DB 操作:由 service 层统一级联删除章节(及台词)、角色和项目本身
        success = service.delete_project(project_id)
        if not success:
            return Res(data=None, code=400, message="删除失败或项目不存在")

        # 4. 文件操作:DB 已提交后再删除目录
        #    文件删除失败仅记日志,不回滚 DB(数据已清,残留目录可手动清理)
        if os.path.exists(project_path):
            try:
                shutil.rmtree(project_path)
                logging.info("已删除目录及内容: %s", project_path)
            except Exception as e:
                logging.exception("删除项目目录失败(数据已清,文件残留): %s", e)
                return Res(data=None, code=200, message="项目数据已删除,但目录清理失败,请手动清理")
        else:
            logging.info("目录不存在: %s", project_path)

        return Res(data=None, code=200, message="删除成功")
    except Exception as e:
        logging.exception("删除项目失败: %s", e)
        return Res(data=None, code=500, message="删除失败")

# 直接导入整本小说内容，然后解析，创建章节
@router.post("/{project_id}/import")
def import_project(project_id: int, dto: ProjectImportDTO,service: ProjectService = Depends(get_service),
                   chapter_service: ChapterService = Depends(get_chapter_service)):
    try:
        content = dto.content
        # 删除该项目下的所有章节
        # chapters = chapter_service.get_all_chapters(project_id)
        # for chapter in chapters:
        #     chapter_service.delete_chapter(chapter.id)
        # 解析content
        chapter_contents = service.parse_content(content)
        if len(chapter_contents) == 0:
            return Res(data=None, code=400, message="导入失败")

        # 批量创建章节
        for chapter_content in chapter_contents:
            name = chapter_content["chapter_name"]
            content = chapter_content["content"]
            logging.info("批量创建章节 %s", name)
            chapter_service.create_chapter(ChapterEntity(project_id=project_id, title=name, text_content=content))
        return Res(data=None, code=200, message="导入成功")
    except Exception:
        logging.exception("导入项目失败")
        return Res(data=None, code=500, message="导入失败:服务器内部错误")
