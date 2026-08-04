from fastapi import APIRouter, Depends, HTTPException
from typing import List
import logging
from sqlalchemy.orm import Session

from app.core.response import Res
from app.db.database import get_db
from app.dto.tts_provider_dto import TTSProviderCreateDTO, TTSProviderResponseDTO
from app.entity.tts_provider_entity import TTSProviderEntity
from app.services.tts_provider_service import TTSProviderService
from app.repositories.tts_provider_repository import TTSProviderRepository

# 初始化 router
router = APIRouter(prefix="/tts_providers", tags=["TTSProviders"])

_SECRET_FIELDS = ("api_key", "x_api_key", "access_key_id", "access_key_secret")

# 默认 TTS provider 的 ID(不允许删除)
DEFAULT_TTS_PROVIDER_ID = 1


def _mask_secrets(entity) -> dict:
    """返回脱敏后的字段字典,敏感凭证改用布尔标志(配合 ResponseDTO 的 has_* 字段)"""
    data = {k: v for k, v in entity.__dict__.items() if not k.startswith("_")}
    data["has_api_key"] = bool(data.get("api_key"))
    data["has_x_api_key"] = bool(data.get("x_api_key"))
    data["has_access_key_id"] = bool(data.get("access_key_id"))
    data["has_access_key_secret"] = bool(data.get("access_key_secret"))
    for field in _SECRET_FIELDS:
        data.pop(field, None)
    return data

# 依赖注入（实际TTS供应商可用 DI 容器）

def get_service(db: Session = Depends(get_db)) -> TTSProviderService:
    repository = TTSProviderRepository(db)  # ✅ 传入 db
    return TTSProviderService(repository)


# 按id查找
@router.get("/{tts_provider_id}", response_model=Res[TTSProviderResponseDTO],
            summary="查询TTS供应商",
            description="根据TTS供应商ID查询TTS供应商信息")
def get_tts_provider(tts_provider_id: int, service: TTSProviderService = Depends(get_service)):
    entity = service.get_tts_provider(tts_provider_id)
    if entity:
        res = TTSProviderResponseDTO(**_mask_secrets(entity))
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=None, code=404, message="TTS供应商不存在")

@router.get("/", response_model=Res[List[TTSProviderResponseDTO]],
            summary="查询所有TTS供应商",
            description="查询所有TTS供应商信息")
def get_all_tts_providers(service: TTSProviderService = Depends(get_service)):
    entities = service.get_all_tts_providers()
    dtos = [TTSProviderResponseDTO(**_mask_secrets(e)) for e in entities]
    return Res(data=dtos, code=200, message="查询成功")


# ------------------- 新增TTS供应商 -------------------
@router.post("/", response_model=Res[TTSProviderResponseDTO],
            summary="新增TTS供应商",
            description="新增TTS供应商信息")
def create_tts_provider(dto: TTSProviderCreateDTO, service: TTSProviderService = Depends(get_service)):

    # 检查名称是否已存在
    existing = service.get_tts_provider_by_name(dto.name)
    if existing:
        return Res(data=None, code=400, message="TTS供应商名称已存在")

    success = service.create_tts_provider(dto)
    if success:
        # 查询创建后的实体并脱敏返回,配合 ResponseDTO 的 has_* 字段
        entity = service.get_tts_provider_by_name(dto.name)
        if entity:
            masked_data = _mask_secrets(entity)
            return Res(data=masked_data, code=200, message="创建成功")
        return Res(data=None, code=200, message="创建成功")
    else:
        return Res(data=None, code=400, message="创建失败")


# ------------------- 删除TTS供应商 -------------------
@router.delete("/{tts_id}", response_model=Res[bool],
            summary="删除TTS供应商",
            description="删除TTS供应商信息")
def delete_tts_provider(tts_id: int, service: TTSProviderService = Depends(get_service)):
    # 不允许删除默认的index_tts (id=1)
    if tts_id == DEFAULT_TTS_PROVIDER_ID:
        return Res(data=False, code=400, message="默认TTS供应商不可删除")

    success = service.delete_tts_provider(tts_id)
    if success:
        return Res(data=True, code=200, message="删除成功")
    else:
        return Res(data=False, code=404, message="TTS供应商不存在")


# ------------------- 修改TTS供应商 -------------------
@router.put("/{tts_provider_id}", response_model=Res[TTSProviderResponseDTO],
            summary="修改TTS供应商",
            description="根据TTS供应商ID修改TTS供应商信息")
def update_tts_provider(tts_provider_id: int, dto: TTSProviderCreateDTO, service: TTSProviderService = Depends(get_service)):

    # 先根据id进行查找
    tts_provider = service.get_tts_provider(tts_provider_id)
    if not tts_provider:
        return Res(data=None, code=400, message="TTS供应商不存在")

    success = service.update_tts_provider(tts_provider_id,dto.model_dump(exclude_unset=True))
    if success:
        # 返回更新后的实体(脱敏),而非入参 dto
        updated = service.get_tts_provider(tts_provider_id)
        masked_data = _mask_secrets(updated)
        return Res(data=masked_data, code=200, message="更新成功")
    else:
        return Res(data=None, code=400, message="更新失败")



# 测试tts是否正常
@router.post("/test", response_model=Res)
def test_tts_provider(dto: TTSProviderCreateDTO, service: TTSProviderService = Depends(get_service)):
    logging.info(
        "测试 TTS 配置: name=%s, provider_type=%s, voice_type=%s, api_key=%s, x_api_key=%s",
        dto.name, dto.provider_type, dto.voice_type,
        "[有]" if dto.api_key else "[空]",
        "[有]" if dto.x_api_key else "[空]",
    )
    entity = TTSProviderEntity(**dto.model_dump())
    success = service.test_tts_provider(entity)
    if success:
        return Res(data=None, code=200, message="测试成功")
    else:
        return Res(data=None, code=400, message="测试失败")



# ------------------- 删除TTS供应商 -------------------
# @router.delete("/{tts_provider_id}", response_model=Res,
#                summary="删除TTS供应商",
#                description="根据TTS供应商ID删除TTS供应商,并且级联删除TTS供应商下所有章节以及内容")
# def delete_tts_provider(tts_provider_id: int, service: TTSProviderService = Depends(get_service)):
#     success = service.delete_tts_provider(tts_provider_id)
#     # todo 级联删除TTS供应商所有相关内容，比如TTS供应商下所有章节以及内容
#     if success:
#         return Res(data=None, code=200, message="删除成功")
#     else:
#         return Res(data=None, code=400, message="删除失败或TTS供应商不存在")