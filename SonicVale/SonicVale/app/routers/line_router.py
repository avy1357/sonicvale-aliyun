import os
import logging
import shutil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body, Request, Query
from sqlalchemy.orm import Session

from app.core.config import getConfigPath
from app.core.path_security import assert_path_not_system_critical, validate_path_within_root
from app.core.response import Res
from app.core.ws_manager import manager
from app.db.database import get_db, SessionLocal
from app.dto.line_dto import LineResponseDTO, LineCreateDTO, LineOrderDTO, LineAudioProcessDTO, LineAudioPathUpdateDTO
from app.entity.line_entity import LineEntity
from app.repositories.chapter_repository import ChapterRepository
from app.repositories.llm_provider_repository import LLMProviderRepository
from app.repositories.multi_emotion_voice_repository import MultiEmotionVoiceRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.line_repository import LineRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.tts_provider_repository import TTSProviderRepository
from app.repositories.voice_repository import VoiceRepository
from app.services.chapter_service import ChapterService
from app.services.project_service import ProjectService
from app.services.line_service import LineService
from app.services.role_service import RoleService
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lines", tags=["Lines"])


# 依赖注入（实际项目可用 DI 容器）

def get_line_service(db: Session = Depends(get_db)) -> LineService:
    repository = LineRepository(db)
    role_repository = RoleRepository(db)
    tts_repository = TTSProviderRepository(db)
    llm_repository = LLMProviderRepository(db)
    return LineService(repository, role_repository, tts_repository, llm_repository)
def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    repository = ProjectRepository(db)
    return ProjectService(repository)

def get_chapter_service(db: Session = Depends(get_db)) -> ChapterService:
    repository = ChapterRepository(db)
    return ChapterService(repository)

def get_voice_service(db: Session = Depends(get_db)) -> VoiceService:
    repository = VoiceRepository(db)
    multi_emotion_voice_repository = MultiEmotionVoiceRepository(db)
    return VoiceService(repository, multi_emotion_voice_repository)

def get_role_service(db: Session = Depends(get_db)) -> RoleService:
    repository = RoleRepository(db)
    return RoleService(repository)
@router.post("/{project_id}", response_model=Res[LineResponseDTO],
             summary="创建台词",
             description="根据项目ID创建台词" )
def create_line(project_id:int,dto: LineCreateDTO, line_service: LineService = Depends(get_line_service),
                   project_service: ProjectService = Depends(get_project_service),
                    chapter_service : ChapterService = Depends(get_chapter_service)):
    """创建台词"""
    try:
        # 校验 chapter_id 必填
        if dto.chapter_id is None:
            return Res(data=None, code=400, message="chapter_id 不能为空")
        # DTO -> Entity
        entity = LineEntity(**dto.model_dump())
        # 判断project_id是否存在
        project = project_service.get_project(project_id)
        if project is None:
            return Res(data=None, code=400, message=f"项目 '{project_id}' 不存在")

        chapter = chapter_service.get_chapter(dto.chapter_id)
        if chapter is None:
            return Res(data=None, code=400, message=f"章节 '{dto.chapter_id}' 不存在")
        # 调用 Service 创建项目（返回 True/False）

        entity_res = line_service.create_line(entity)
        if entity_res is None:
            return Res(data=None, code=400, message=f"台词 '{entity.name}' 已存在")

        # 新增台词,这里搞个audio_path
        audio_path = os.path.join(project.project_root_path, str(project_id), str(dto.chapter_id), "audio")
        # 路径白名单校验:防止路径穿越,确保音频目录在允许的根目录下
        try:
            audio_path = validate_path_within_root(audio_path, getConfigPath())
            assert_path_not_system_critical(audio_path)
        except ValueError as e:
            return Res(data=None, code=400, message="项目根路径非法,拒绝操作")
        os.makedirs(audio_path, exist_ok=True)
        res_path = os.path.join(audio_path, "id_" + str(entity_res.id) + ".wav")
        line_service.update_line(entity_res.id, {"audio_path": res_path})

        # 返回统一 Response
        res = LineResponseDTO(**entity_res.__dict__)
        return Res(data=res, code=200, message="创建成功")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{line_id}", response_model=Res[LineResponseDTO],
            summary="查询台词",
            description="根据台词id查询台词信息")
def get_line(line_id: int, line_service: LineService = Depends(get_line_service)):
    entity = line_service.get_line(line_id)
    if entity:
        res = LineResponseDTO(**entity.__dict__)
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=None, code=404, message="台词不存在")

@router.get("/chapter/{chapter_id}", response_model=Res[List[LineResponseDTO]],
            summary="查询章节下的所有台词",
            description="根据章节id查询章节下的所有台词信息")
def get_all_lines(chapter_id: int, line_service: LineService = Depends(get_line_service)):
    entities = line_service.get_all_lines(chapter_id)
    if entities:
        res = [LineResponseDTO(**e.__dict__) for e in entities]
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=[], code=200, message="章节不存在台词")

# 修改，传入的参数是id
@router.put("/{line_id}", response_model=Res[LineResponseDTO],
            summary="修改台词信息",
            description="根据台词id修改台词信息,并且不能修改章节id")
def update_line(line_id: int, dto: LineCreateDTO, line_service: LineService = Depends(get_line_service)):
    line = line_service.get_line(line_id)
    if line is None:
        return Res(data=None, code=404, message="台词不存在")
    res = line_service.update_line(line_id, dto.model_dump(exclude_unset=True))
    if res:
        # 返回更新后的实体,而非入参 dto
        updated_line = line_service.get_line(line_id)
        return Res(data=LineResponseDTO(**updated_line.__dict__), code=200, message="修改成功")
    else:
        return Res(data=None, code=400, message="修改失败")


# 根据id，删除
@router.delete("/{line_id}", response_model=Res,
               summary="删除台词",
               description="根据台词id删除台词信息")
def delete_line(line_id: int, line_service: LineService = Depends(get_line_service)):
    success = line_service.delete_line(line_id)
    if success:
        return Res(data=None, code=200, message="删除成功")
    else:
        return Res(data=None, code=400, message="删除失败或台词不存在")

# 删除章节下所有台词
@router.delete("/chapter/{chapter_id}", response_model=Res,summary="删除章节下所有台词",description="根据章节id删除章节下的所有台词信息")
def delete_all_lines(chapter_id: int, line_service: LineService = Depends(get_line_service)):
    success = line_service.delete_all_lines(chapter_id)
    if success:
        return Res(data=None, code=200, message="删除成功")
    else:
        return Res(data=None, code=400, message="删除失败或台词不存在")





@router.put("/batch/orders", response_model=Res[bool])
def batch_update_line_order(
    line_orders: List[LineOrderDTO] = Body(...),  # 关键：明确从 body 读取“数组”
    line_service: LineService = Depends(get_line_service),
):
    # 数量上限校验,防止超大请求造成阻塞
    if len(line_orders) > 1000:
        return Res(code=400, message="单次批量更新数量不能超过 1000", data=None)
    try:
        res = line_service.batch_update_line_order(line_orders)
        return Res(data=res, code=200, message="更新成功")
    except Exception:
        logger.exception("批量更新台词顺序失败")
        return Res(data=None, code=500, message="更新失败:服务器内部错误")

# 完成配音时候，更新音频路径，保证顺序一致
@router.put("/{line_id}/audio_path", response_model=Res[bool])
def update_line_audio_path(
        line_id: int,
    dto: LineAudioPathUpdateDTO,  # 使用专用 DTO,包含 audio_path 字段
    line_service: LineService = Depends(get_line_service),
):
    res = line_service.update_audio_path(line_id,dto)
    if not res:
        return Res(data=None, code=400, message="更新失败")
    return Res(data=res, code=200, message="更新成功")



@router.post("/generate-audio/{project_id}/{chapter_id}")
async def generate_audio(request: Request, project_id: int, chapter_id: int, dto: LineCreateDTO,
                         line_service: LineService = Depends(get_line_service),
                         chapter_service: ChapterService = Depends(get_chapter_service)):
    # 对象级授权:校验台词存在且属于该 project(通过 chapter 中转)
    if dto.id is None:
        return Res(data=None, code=400, message="台词 id 不能为空")
    line = line_service.get_line(dto.id)
    if line is None:
        return Res(data=None, code=404, message="台词不存在")
    chapter = chapter_service.get_chapter(line.chapter_id)
    if chapter is None or chapter.project_id != project_id:
        return Res(data=None, code=403, message="无权操作")
    # 校验 tts_queue 已初始化
    if not hasattr(request.app.state, 'tts_queue'):
        return Res(data=None, code=500, message="TTS 队列未初始化")
    q = request.app.state.tts_queue  # 永远拿到已初始化的同一份队列
    if q.full():
        # 可选：带上 Retry-After 头
        raise HTTPException(status_code=429, detail="队列已满，请稍后重试")
    q.put_nowait((project_id, dto))
    queue_size = q.qsize()  # 入队后的队列大小
    line_service.update_line(dto.id, {"status": "processing"})

    # 入队后立即广播队列大小，让前端实时看到更新
    await manager.broadcast({
        "event": "line_update",
        "line_id": dto.id,
        "status": "queued",
        "progress": queue_size,
        "meta": f"已入队，等待生成"
    })

    logger.info("队列剩余数量: %s", queue_size)
    return Res(data={"line_id": dto.id}, code=200, message="已入队")


# 改为异步任务

# 处理音频文件，传入倍速，音量大小，以及line_id
@router.post("/process-audio/{line_id}")
def process_audio(line_id: int, dto: LineAudioProcessDTO, line_service: LineService = Depends(get_line_service)):
    res = line_service.process_audio(line_id,dto)
    if not res:
        return Res(data=None, code=400, message="处理失败")
    return Res(data=res, code=200, message="处理成功")

# 导出音频与字幕
@router.get("/export-audio/{chapter_id}")
def export_audio(chapter_id: int,
                       single: bool = Query(False, description="是否导出单条音频字幕"),
                       line_service: LineService = Depends(get_line_service)):
    res = line_service.export_audio(chapter_id, single)
    # res 现在返回 dict，包含 success, message, audio_path 等字段
    if isinstance(res, dict):
        if res.get("success"):
            return Res(data=res, code=200, message=res.get("message", "导出成功"))
        else:
            return Res(data=res, code=400, message=res.get("message", "导出失败"))
    # 兼容旧的返回格式
    if not res:
        return Res(data=None, code=400, message="导出失败")
    return Res(data=res, code=200, message="导出成功")


# 生成单条音频的字幕（已经有音频）
#

# 矫正字幕 - 拼音匹配矫正
@router.post("/correct-subtitle-pinyin/{chapter_id}")
def correct_subtitle_pinyin(
    chapter_id: int,
    line_service: LineService = Depends(get_line_service)
):
    """使用拼音匹配算法矫正字幕"""
    lines = line_service.get_all_lines(chapter_id)
    if not lines:
        logger.info("无台词记录")
        return Res(data=None, code=400, message="无台词记录")
    paths = [line.audio_path for line in lines]
    if not paths or not paths[0]:
        logger.info("未找到有效音频路径")
        return Res(data=None, code=400, message="未找到有效音频路径")

    # 读取所有台词，组成一个文本
    text = "\n".join([line.text_content for line in lines])
    output_dir_path = os.path.join(os.path.dirname(paths[0]), "result")
    output_subtitle_path = os.path.join(output_dir_path, "result.srt")

    if not os.path.exists(output_subtitle_path):
        logger.info("请先导出音频")
        return Res(data=None, code=400, message="请先导出音频")

    # 拼音矫正输出到独立文件
    pinyin_subtitle_path = os.path.join(output_dir_path, "result_pinyin.srt")
    # 文件操作前校验路径不指向系统关键目录
    try:
        assert_path_not_system_critical(output_subtitle_path)
        assert_path_not_system_critical(pinyin_subtitle_path)
    except ValueError:
        logger.warning("拒绝矫正字幕,路径非法: %s", pinyin_subtitle_path)
        return Res(data=None, code=400, message="字幕路径非法,拒绝操作")
    shutil.copy(output_subtitle_path, pinyin_subtitle_path)
    line_service.correct_subtitle_pinyin(text, pinyin_subtitle_path)
    logger.info("整体字幕矫正完成（拼音匹配）：%s", pinyin_subtitle_path)

    # 将单条字幕也进行矫正
    logger.info("开始对单条字幕进行矫正")
    for line in lines:
        subtitle_path = line.subtitle_path
        line_text = line.text_content
        if subtitle_path is not None and line_text is not None and os.path.exists(subtitle_path):
            # 单条字幕也输出到 _pinyin 文件
            base, ext = os.path.splitext(subtitle_path)
            pinyin_single_path = f"{base}_pinyin{ext}"
            try:
                assert_path_not_system_critical(subtitle_path)
                assert_path_not_system_critical(pinyin_single_path)
            except ValueError:
                logger.warning("跳过单条字幕矫正,路径非法: %s", subtitle_path)
                continue
            shutil.copy(subtitle_path, pinyin_single_path)
            line_service.correct_subtitle_pinyin(line_text, pinyin_single_path)
            logger.info("单条字幕矫正完成：%s", line.id)

    return Res(data=None, code=200, message="拼音匹配矫正完成")


# 矫正字幕 - LLM矫正
@router.post("/correct-subtitle-llm/{chapter_id}")
def correct_subtitle_llm(
    chapter_id: int,
    batch_size: int = Query(20, description="LLM分批处理时每批的条数"),
    line_service: LineService = Depends(get_line_service),
    chapter_service: ChapterService = Depends(get_chapter_service),
    project_service: ProjectService = Depends(get_project_service)
):
    """使用LLM矫正字幕，自动从项目配置获取LLM信息"""
    # 获取章节信息
    chapter = chapter_service.get_chapter(chapter_id)
    if not chapter:
        return Res(data=None, code=400, message="章节不存在")

    # 获取项目信息，从中读取LLM配置
    project = project_service.get_project(chapter.project_id)
    if not project:
        return Res(data=None, code=400, message="项目不存在")

    if not project.llm_provider_id:
        return Res(data=None, code=400, message="项目未配置LLM提供商，请在项目设置中配置")

    if not project.llm_model:
        return Res(data=None, code=400, message="项目未配置LLM模型，请在项目设置中选择模型")

    lines = line_service.get_all_lines(chapter_id)
    if not lines:
        logger.info("无台词记录")
        return Res(data=None, code=400, message="无台词记录")
    paths = [line.audio_path for line in lines]
    if not paths or not paths[0]:
        logger.info("未找到有效音频路径")
        return Res(data=None, code=400, message="未找到有效音频路径")

    # 读取所有台词，组成一个文本
    text = "\n".join([line.text_content for line in lines])
    output_dir_path = os.path.join(os.path.dirname(paths[0]), "result")
    output_subtitle_path = os.path.join(output_dir_path, "result.srt")

    if not os.path.exists(output_subtitle_path):
        logger.info("请先导出音频")
        return Res(data=None, code=400, message="请先导出音频")

    # LLM矫正输出到独立文件
    llm_subtitle_path = os.path.join(output_dir_path, "result_llm.srt")
    # 文件操作前校验路径不指向系统关键目录
    try:
        assert_path_not_system_critical(output_subtitle_path)
        assert_path_not_system_critical(llm_subtitle_path)
    except ValueError:
        logger.warning("拒绝矫正字幕,路径非法: %s", llm_subtitle_path)
        return Res(data=None, code=400, message="字幕路径非法,拒绝操作")
    shutil.copy(output_subtitle_path, llm_subtitle_path)
    line_service.correct_subtitle_llm(
        text, llm_subtitle_path,
        llm_provider_id=project.llm_provider_id,
        llm_model=project.llm_model,
        batch_size=batch_size
    )
    logger.info("整体字幕矫正完成（LLM）：%s", llm_subtitle_path)

    # 将单条字幕也进行矫正
    logger.info("开始对单条字幕进行矫正")
    for line in lines:
        subtitle_path = line.subtitle_path
        line_text = line.text_content
        if subtitle_path is not None and line_text is not None and os.path.exists(subtitle_path):
            # 单条字幕也输出到 _llm 文件
            base, ext = os.path.splitext(subtitle_path)
            llm_single_path = f"{base}_llm{ext}"
            try:
                assert_path_not_system_critical(subtitle_path)
                assert_path_not_system_critical(llm_single_path)
            except ValueError:
                logger.warning("跳过单条字幕矫正,路径非法: %s", subtitle_path)
                continue
            shutil.copy(subtitle_path, llm_single_path)
            line_service.correct_subtitle_llm(
                line_text, llm_single_path,
                llm_provider_id=project.llm_provider_id,
                llm_model=project.llm_model,
                batch_size=batch_size
            )
            logger.info("单条字幕矫正完成：%s", line.id)

    return Res(data=None, code=200, message="LLM矫正完成")

