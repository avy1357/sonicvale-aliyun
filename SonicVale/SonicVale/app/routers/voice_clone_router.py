import logging
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import Res
from app.db.database import get_db
from app.dto.voice_clone_dto import (
    VoiceCloneCreateDTO, VoiceCloneResponseDTO, VoiceCloneUploadDTO,
    VoiceCloneStatusDTO, VoiceCloneTrainDTO
)
from app.entity.voice_clone_entity import VoiceCloneEntity
from app.repositories.voice_clone_repository import VoiceCloneRepository
from app.repositories.tts_provider_repository import TTSProviderRepository
from app.services.voice_clone_service import VoiceCloneService
from app.services.tts_provider_service import TTSProviderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-clones", tags=["VoiceClones"])


def get_voice_clone_service(db: Session = Depends(get_db)) -> VoiceCloneService:
    repo = VoiceCloneRepository(db)
    tts_repo = TTSProviderRepository(db)
    tts_service = TTSProviderService(tts_repo)
    return VoiceCloneService(repo, tts_service)


@router.post("", response_model=Res[VoiceCloneResponseDTO],
             summary="创建声音复刻记录",
             description="创建新的声音复刻记录，需要提供火山引擎 TTS 提供商 ID、音色名称和 Speaker ID")
def create_voice_clone(dto: VoiceCloneCreateDTO,
                       service: VoiceCloneService = Depends(get_voice_clone_service)):
    try:
        entity = VoiceCloneEntity(**dto.__dict__)
        result = service.create_voice_clone(entity)
        if result:
            res = VoiceCloneResponseDTO(**result.__dict__)
            return Res(data=res, code=200, message="创建成功")
        else:
            return Res(data=None, code=400, message=f"音色名称 '{dto.name}' 已存在")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("创建声音复刻记录失败")
        return Res(data=None, code=500, message="创建失败:服务器内部错误")


@router.get("/{clone_id}", response_model=Res[VoiceCloneResponseDTO],
            summary="查询声音复刻记录",
            description="根据 ID 查询声音复刻记录")
def get_voice_clone(clone_id: int, service: VoiceCloneService = Depends(get_voice_clone_service)):
    entity = service.get_voice_clone(clone_id)
    if entity:
        res = VoiceCloneResponseDTO(**entity.__dict__)
        return Res(data=res, code=200, message="查询成功")
    else:
        return Res(data=None, code=404, message="声音复刻记录不存在")


@router.get("/tts/{tts_provider_id}", response_model=Res[List[VoiceCloneResponseDTO]],
            summary="查询 TTS 提供商下的所有声音复刻记录",
            description="查询指定火山引擎 TTS 提供商下的所有声音复刻记录")
def get_all_voice_clones(tts_provider_id: int, 
                         service: VoiceCloneService = Depends(get_voice_clone_service)):
    entities = service.get_all_voice_clones(tts_provider_id)
    res = [VoiceCloneResponseDTO(**e.__dict__) for e in entities]
    return Res(data=res, code=200, message="查询成功")


@router.post("/upload", response_model=Res[dict],
             summary="上传音频训练",
             description="上传参考音频到火山引擎进行音色训练")
def upload_audio(dto: VoiceCloneUploadDTO,
                 service: VoiceCloneService = Depends(get_voice_clone_service)):
    try:
        result = service.upload_and_train(dto)
        return Res(data=result, code=200, message="音频上传成功，训练中")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except FileNotFoundError as e:
        return Res(data=None, code=404, message=str(e))
    except Exception:
        logger.exception("上传音频训练失败")
        return Res(data=None, code=500, message="上传失败:服务器内部错误")


@router.post("/status", response_model=Res[VoiceCloneStatusDTO],
             summary="查询训练状态",
             description="查询音色训练状态并更新本地记录")
def query_status(clone_id: int = Query(..., ge=1),
                 service: VoiceCloneService = Depends(get_voice_clone_service)):
    try:
        result = service.query_training_status(clone_id)
        status = result.get("status", 0)
        status_map = {0: "未找到", 1: "训练中", 2: "成功", 3: "失败", 4: "已激活"}
        status_msg = status_map.get(status, "未知")

        clone = service.get_voice_clone(clone_id)
        if not clone:
            return Res(data=None, code=404, message="声音复刻记录不存在")
        res = VoiceCloneStatusDTO(
            clone_id=clone_id,
            speaker_id=clone.speaker_id,
            status=status,
            version=result.get("version"),
            demo_audio_url=result.get("demo_audio"),
            message=f"训练{status_msg}",
        )
        return Res(data=res, code=200, message="查询成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("查询训练状态失败")
        return Res(data=None, code=500, message="查询失败:服务器内部错误")


@router.post("/train-and-wait", response_model=Res[dict],
             summary="训练并等待完成",
             description="上传音频并等待训练完成（同步，可能耗时较长）")
def train_and_wait(dto: VoiceCloneTrainDTO,
                   service: VoiceCloneService = Depends(get_voice_clone_service)):
    try:
        result = service.train_and_wait(dto)
        return Res(data=result, code=200, message="训练完成")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except FileNotFoundError as e:
        return Res(data=None, code=404, message=str(e))
    except Exception:
        logger.exception("训练并等待失败")
        return Res(data=None, code=500, message="训练失败:服务器内部错误")


@router.put("/{clone_id}", response_model=Res[VoiceCloneResponseDTO],
            summary="更新声音复刻记录",
            description="更新声音复刻记录信息")
def update_voice_clone(clone_id: int, dto: VoiceCloneCreateDTO,
                       service: VoiceCloneService = Depends(get_voice_clone_service)):
    try:
        update_data = {
            "name": dto.name,
            "description": dto.description,
        }
        entity = service.update_voice_clone(clone_id, update_data)
        if entity:
            res = VoiceCloneResponseDTO(**entity.__dict__)
            return Res(data=res, code=200, message="更新成功")
        else:
            return Res(data=None, code=404, message="声音复刻记录不存在")
    except Exception:
        logger.exception("更新声音复刻记录失败")
        return Res(data=None, code=500, message="更新失败:服务器内部错误")


@router.delete("/{clone_id}", response_model=Res[bool],
               summary="删除声音复刻记录",
               description="删除声音复刻记录（仅删除本地记录，不影响火山引擎上的音色）")
def delete_voice_clone(clone_id: int,
                       service: VoiceCloneService = Depends(get_voice_clone_service)):
    try:
        success = service.delete_voice_clone(clone_id)
        if success:
            return Res(data=True, code=200, message="删除成功")
        else:
            return Res(data=False, code=404, message="声音复刻记录不存在")
    except Exception:
        logger.exception("删除声音复刻记录失败")
        return Res(data=None, code=500, message="删除失败:服务器内部错误")
