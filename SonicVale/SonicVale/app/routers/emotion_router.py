from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import Res
from app.db.database import get_db
from app.dto.emotion_dto import EmotionResponseDTO, EmotionCreateDTO
from app.entity.emotion_entity import EmotionEntity
from app.repositories.emotion_repository import EmotionRepository
from app.services.emotion_service import EmotionService

router = APIRouter(prefix="/emotions", tags=["Emotions"])


# 依赖注入（实际项目可用 DI 容器）

def get_emotion_service(db: Session = Depends(get_db)) -> EmotionService:
    repository = EmotionRepository(db)
    return EmotionService(repository)

@router.post("", response_model=Res[EmotionResponseDTO],
             summary="创建情绪枚举",
             description="根据项目ID创建情绪枚举，情绪枚举名称在同一项目下不可重复" )
def create_emotion(dto: EmotionCreateDTO, emotion_service: EmotionService = Depends(get_emotion_service)):
    """创建情绪枚举"""
    try:
        # DTO → Entity
        entity = EmotionEntity(**dto.model_dump())

        # 调用 Service 创建项目（返回 True/False）
        entity_res = emotion_service.create_emotion(entity)

        # 返回统一 Response
        if entity_res is not None:
            # 创建成功，可以返回 DTO 或者部分字段
            res = EmotionResponseDTO(**entity_res.__dict__)
            return Res(data=res, code=200, message="创建成功")
        else:
            return Res(data=None, code=400, message=f"情绪枚举 '{entity.name}' 已存在")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{emotion_id}", response_model=Res[EmotionResponseDTO],
            summary="查询情绪枚举",
            description="根据情绪枚举id查询情绪枚举信息")
def get_emotion(emotion_id: int, emotion_service: EmotionService = Depends(get_emotion_service)):
    entity = emotion_service.get_emotion(emotion_id)
    if entity:
        res = EmotionResponseDTO(**entity.__dict__)
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=None, code=404, message="情绪枚举不存在")

@router.get("", response_model=Res[List[EmotionResponseDTO]],
            summary="查询所有情绪枚举",
            description="根据所有情绪枚举信息")
def get_all_emotions(emotion_service: EmotionService = Depends(get_emotion_service)):
    entities = emotion_service.get_all_emotions()
    if entities:
        res = [EmotionResponseDTO(**e.__dict__) for e in entities]
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=[], code=200, message="查询成功")

# 修改，传入的参数是id
@router.put("/{emotion_id}", response_model=Res[EmotionResponseDTO],
            summary="修改情绪枚举信息",
            description="根据情绪枚举id修改情绪枚举信息,并且不能修改项目id")
def update_emotion(emotion_id: int, dto: EmotionCreateDTO, emotion_service: EmotionService = Depends(get_emotion_service)):
    emotion = emotion_service.get_emotion(emotion_id)
    if emotion is None:
        return Res(data=None, code=404, message="情绪枚举不存在")
    res = emotion_service.update_emotion(emotion_id, dto.model_dump(exclude_unset=True))
    if res:
        # 返回更新后的实体,而非入参 dto
        updated = emotion_service.get_emotion(emotion_id)
        return Res(data=EmotionResponseDTO(**updated.__dict__), code=200, message="修改成功")
    else:
        return Res(data=None, code=400, message="修改失败,情绪枚举已存在")


# 根据id，删除
@router.delete("/{emotion_id}", response_model=Res,
               summary="删除情绪枚举",
               description="根据情绪枚举id删除情绪枚举信息。已被台词引用时返回 409,需先解除引用")
def delete_emotion(emotion_id: int, emotion_service: EmotionService = Depends(get_emotion_service)):
    # 引用检查已移至 service 层,确保检查与删除在同一事务中
    success = emotion_service.delete_emotion(emotion_id)
    if success:
        return Res(data=None, code=200, message="删除成功")
    else:
        raise HTTPException(status_code=409, detail="该情绪枚举已被台词引用或不存在,无法删除")



