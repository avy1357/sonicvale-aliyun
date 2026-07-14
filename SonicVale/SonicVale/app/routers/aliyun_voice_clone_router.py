from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.response import Res
from app.db.database import get_db
from app.repositories.tts_provider_repository import TTSProviderRepository
from app.services.tts_provider_service import TTSProviderService
from app.services.aliyun_voice_clone_service import AliyunVoiceCloneService
from app.dto.voice_clone_dto import AliyunVoiceCreateDTO, AliyunVoiceUpdateDTO


router = APIRouter(prefix="/aliyun-voices", tags=["AliyunVoiceClone"])


def get_service(db: Session = Depends(get_db)) -> AliyunVoiceCloneService:
    repo = TTSProviderRepository(db)
    tts_service = TTSProviderService(repo)
    return AliyunVoiceCloneService(tts_service)


@router.get("/list", response_model=Res[dict],
            summary="查询阿里云音色列表",
            description="查询指定阿里云 TTS 提供商下的音色列表")
def list_voices(
    tts_provider_id: int,
    prefix: Optional[str] = None,
    page_index: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    service: AliyunVoiceCloneService = Depends(get_service)
):
    try:
        result = service.list_voices(
            tts_provider_id=tts_provider_id,
            prefix=prefix,
            page_index=page_index,
            page_size=page_size
        )
        return Res(data=result, code=200, message="查询成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"查询失败: {str(e)}")


@router.get("/detail", response_model=Res[dict],
            summary="获取阿里云音色详情",
            description="获取指定阿里云音色的详细信息")
def query_voice(
    tts_provider_id: int,
    voice_id: str,
    service: AliyunVoiceCloneService = Depends(get_service)
):
    try:
        result = service.query_voice(tts_provider_id=tts_provider_id, voice_id=voice_id)
        return Res(data=result, code=200, message="查询成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"查询失败: {str(e)}")


@router.post("/create", response_model=Res[dict],
             summary="创建阿里云音色",
             description="通过声音复刻创建新的音色。注意：target_model 必须与后续语音合成接口使用的模型一致，否则合成会失败")
def create_voice(body: AliyunVoiceCreateDTO,
                 service: AliyunVoiceCloneService = Depends(get_service)):
    try:
        voice_id = service.create_voice(
            tts_provider_id=body.tts_provider_id,
            target_model=body.target_model,
            prefix=body.prefix,
            url=body.url,
            language_hints=body.language_hints,
            max_prompt_audio_length=body.max_prompt_audio_length,
            enable_preprocess=body.enable_preprocess
        )
        return Res(data={"voice_id": voice_id}, code=200, message="创建成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"创建失败: {str(e)}")


@router.put("/update", response_model=Res[bool],
            summary="更新阿里云音色",
            description="更新阿里云音色的参考音频")
def update_voice(body: AliyunVoiceUpdateDTO,
                 service: AliyunVoiceCloneService = Depends(get_service)):
    try:
        service.update_voice(
            tts_provider_id=body.tts_provider_id,
            voice_id=body.voice_id,
            url=body.url,
            language_hints=body.language_hints,
            max_prompt_audio_length=body.max_prompt_audio_length,
            enable_preprocess=body.enable_preprocess
        )
        return Res(data=True, code=200, message="更新成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"更新失败: {str(e)}")


@router.delete("/delete", response_model=Res[bool],
               summary="删除阿里云音色",
               description="删除阿里云音色")
def delete_voice(
    tts_provider_id: int,
    voice_id: str,
    service: AliyunVoiceCloneService = Depends(get_service)
):
    try:
        service.delete_voice(tts_provider_id=tts_provider_id, voice_id=voice_id)
        return Res(data=True, code=200, message="删除成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"删除失败: {str(e)}")


@router.post("/sync", response_model=Res[int],
             summary="同步阿里云音色到本地",
             description="将阿里云平台的音色批量同步到本地数据库")
def sync_voices(
    tts_provider_id: int,
    db: Session = Depends(get_db),
    service: AliyunVoiceCloneService = Depends(get_service)
):
    try:
        count = service.sync_voices_to_local(
            tts_provider_id=tts_provider_id,
            db=db,
        )
        return Res(data=count, code=200, message=f"同步成功，共同步了 {count} 个音色")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"同步失败: {str(e)}")


@router.post("/sync-single", response_model=Res[dict],
             summary="同步单个阿里云音色到本地",
             description="将阿里云平台的单个音色同步到本地数据库")
def sync_single_voice(
    tts_provider_id: int,
    voice_id: str,
    db: Session = Depends(get_db),
    service: AliyunVoiceCloneService = Depends(get_service)
):
    try:
        result = service.sync_single_voice_to_local(
            tts_provider_id=tts_provider_id,
            voice_id=voice_id,
            db=db,
        )
        status_msg = "新建" if result["status"] == "created" else "更新"
        return Res(data=result, code=200, message=f"同步成功，{status_msg}音色")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception as e:
        return Res(data=None, code=500, message=f"同步失败: {str(e)}")
