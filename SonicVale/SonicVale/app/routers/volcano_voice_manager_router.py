import logging
import os
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.response import Res
from app.db.database import get_db
from app.repositories.tts_provider_repository import TTSProviderRepository
from app.services.tts_provider_service import TTSProviderService
from app.services.volcano_voice_manager_service import VolcanoVoiceManagerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/volcano-voices", tags=["VolcanoVoiceManager"])


class OrderRequest(BaseModel):
    tts_provider_id: int
    times: int = Field(ge=1, description="购买次数,必须 >= 1")
    quantity: int = Field(ge=1, description="音色数量,必须 >= 1")
    auto_use_coupon: Optional[bool] = None
    coupon_id: Optional[str] = None


class RenewRequest(BaseModel):
    tts_provider_id: int
    times: int = Field(ge=1, description="续费次数,必须 >= 1")
    speaker_ids: Optional[List[str]] = None
    auto_use_coupon: Optional[bool] = None
    coupon_id: Optional[str] = None


def get_voice_manager_service(db: Session = Depends(get_db)) -> VolcanoVoiceManagerService:
    repo = TTSProviderRepository(db)
    tts_service = TTSProviderService(repo)
    return VolcanoVoiceManagerService(tts_service)


@router.get("/list", response_model=Res[dict],
            summary="查询火山引擎音色列表",
            description="查询指定火山引擎 TTS 提供商下的音色训练状态列表")
def batch_list_train_status(
    tts_provider_id: int,
    page_number: int = Query(default=1, ge=1, le=100),
    page_size: int = Query(default=10, ge=1, le=500),
    state: Optional[str] = None,
    speaker_ids: Optional[str] = Query(default=None, max_length=1000),
    next_token: Optional[str] = None,
    max_results: Optional[int] = None,
    order_time_start: Optional[int] = None,
    order_time_end: Optional[int] = None,
    expire_time_start: Optional[int] = None,
    expire_time_end: Optional[int] = None,
    service: VolcanoVoiceManagerService = Depends(get_voice_manager_service)
):
    try:
        parsed_speaker_ids = None
        if speaker_ids:
            parsed_speaker_ids = [s.strip() for s in speaker_ids.split(",") if s.strip()]

        result = service.batch_list_train_status(
            tts_provider_id=tts_provider_id,
            page_number=page_number,
            page_size=page_size,
            state=state,
            speaker_ids=parsed_speaker_ids,
            next_token=next_token,
            max_results=max_results,
            order_time_start=order_time_start,
            order_time_end=order_time_end,
            expire_time_start=expire_time_start,
            expire_time_end=expire_time_end,
        )
        return Res(data=result, code=200, message="查询成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("查询火山引擎音色列表失败")
        return Res(data=None, code=500, message="查询失败:服务器内部错误")


@router.post("/order", response_model=Res[dict],
             summary="音色下单",
             description="为火山引擎 TTS 提供商下音色订单")
def order_voices(
    req: OrderRequest,
    service: VolcanoVoiceManagerService = Depends(get_voice_manager_service)
):
    # 付费操作前置检查:必须设置 SVC_API_KEY 环境变量,防止未授权调用造成资损
    if not os.getenv("SVC_API_KEY"):
        raise HTTPException(status_code=403, detail="付费操作要求设置 SVC_API_KEY 环境变量")
    # 审计日志:记录操作人、时间、资源ID、金额相关参数(当前无用户体系,operator 标记为 unknown)
    logger.info(
        "付费审计 - 下单请求: operator=unknown(无用户体系), time=%s, tts_provider_id=%s, times=%s, quantity=%s, coupon_id=%s",
        datetime.now().isoformat(), req.tts_provider_id, req.times, req.quantity, req.coupon_id,
    )
    try:
        result = service.order_voices(
            tts_provider_id=req.tts_provider_id,
            times=req.times,
            quantity=req.quantity,
            auto_use_coupon=req.auto_use_coupon,
            coupon_id=req.coupon_id,
        )
        logger.info(
            "付费审计 - 下单成功: tts_provider_id=%s, times=%s, quantity=%s, result=%s",
            req.tts_provider_id, req.times, req.quantity, result,
        )
        return Res(data=result, code=200, message="下单成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("火山引擎音色下单失败")
        return Res(data=None, code=500, message="下单失败:服务器内部错误")


@router.post("/renew", response_model=Res[dict],
             summary="音色续费",
             description="为火山引擎 TTS 提供商的音色续费")
def renew_voices(
    req: RenewRequest,
    service: VolcanoVoiceManagerService = Depends(get_voice_manager_service)
):
    # 付费操作前置检查:必须设置 SVC_API_KEY 环境变量,防止未授权调用造成资损
    if not os.getenv("SVC_API_KEY"):
        raise HTTPException(status_code=403, detail="付费操作要求设置 SVC_API_KEY 环境变量")
    # 审计日志:记录操作人、时间、资源ID、金额相关参数(当前无用户体系,operator 标记为 unknown)
    logger.info(
        "付费审计 - 续费请求: operator=unknown(无用户体系), time=%s, tts_provider_id=%s, times=%s, speaker_ids=%s, coupon_id=%s",
        datetime.now().isoformat(), req.tts_provider_id, req.times, req.speaker_ids, req.coupon_id,
    )
    try:
        result = service.renew_voices(
            tts_provider_id=req.tts_provider_id,
            times=req.times,
            speaker_ids=req.speaker_ids,
            auto_use_coupon=req.auto_use_coupon,
            coupon_id=req.coupon_id,
        )
        logger.info(
            "付费审计 - 续费成功: tts_provider_id=%s, times=%s, speaker_ids=%s, result=%s",
            req.tts_provider_id, req.times, req.speaker_ids, result,
        )
        return Res(data=result, code=200, message="续费成功")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("火山引擎音色续费失败")
        return Res(data=None, code=500, message="续费失败:服务器内部错误")


@router.post("/sync", response_model=Res[int],
             summary="同步火山引擎音色到本地",
             description="将火山引擎平台的音色同步到本地数据库")
def sync_voices(
    tts_provider_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    service: VolcanoVoiceManagerService = Depends(get_voice_manager_service)
):
    try:
        count = service.sync_voices_to_local(
            tts_provider_id=tts_provider_id,
            db=db,
        )
        return Res(data=count, code=200, message=f"同步成功，共同步了 {count} 个音色")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("同步火山引擎音色到本地失败")
        return Res(data=None, code=500, message="同步失败:服务器内部错误")


@router.post("/sync-single", response_model=Res[dict],
             summary="同步单个火山引擎音色到本地",
             description="将火山引擎平台的单个音色同步到本地数据库")
def sync_single_voice(
    tts_provider_id: int = Query(..., ge=1),
    speaker_id: str = Query(..., max_length=255),
    db: Session = Depends(get_db),
    service: VolcanoVoiceManagerService = Depends(get_voice_manager_service)
):
    try:
        result = service.sync_single_voice_to_local(
            tts_provider_id=tts_provider_id,
            speaker_id=speaker_id,
            db=db,
        )
        status_msg = "新建" if result["status"] == "created" else "更新"
        return Res(data=result, code=200, message=f"同步成功，{status_msg}音色")
    except ValueError as e:
        return Res(data=None, code=400, message=str(e))
    except Exception:
        logger.exception("同步单个火山引擎音色到本地失败")
        return Res(data=None, code=500, message="同步失败:服务器内部错误")
