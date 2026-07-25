import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.volcano_voice_manager_client import VolcanoVoiceManagerClient
from app.models.po import VoicePO, TTSProviderPO
from app.services.tts_provider_service import TTSProviderService


class VolcanoVoiceManagerService:

    def __init__(self, tts_provider_service: TTSProviderService):
        self.tts_provider_service = tts_provider_service

    def _get_volcano_client(self, tts_provider_id: int) -> VolcanoVoiceManagerClient:
        tts_provider = self.tts_provider_service.get_tts_provider(tts_provider_id)
        if not tts_provider:
            raise ValueError(f"TTS 提供商不存在，ID: {tts_provider_id}")

        if tts_provider.provider_type != "volcano":
            raise ValueError("仅支持火山引擎 TTS 提供商")

        # 优先从新字段读取
        access_key_id = getattr(tts_provider, "access_key_id", None)
        access_key_secret = getattr(tts_provider, "access_key_secret", None)

        # 向后兼容：从旧字段读取
        if not access_key_id or not access_key_secret:
            api_key = getattr(tts_provider, "api_key", None)
            if not api_key or ":" not in api_key:
                raise ValueError("火山引擎 TTS 提供商的 AccessKey 未正确配置，请在 api_key 字段中按 appId:accessToken 格式填写，或分别配置 AccessKey ID 和 AccessKey Secret 字段")

            access_key_id, access_key_secret = api_key.split(":", 1)

        appid = getattr(tts_provider, "voice_type", "") or ""

        return VolcanoVoiceManagerClient(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            appid=appid,
        )

    def batch_list_train_status(
        self,
        tts_provider_id: int,
        page_number: int = 1,
        page_size: int = 10,
        state: Optional[str] = None,
        speaker_ids: Optional[List[str]] = None,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None,
        order_time_start: Optional[int] = None,
        order_time_end: Optional[int] = None,
        expire_time_start: Optional[int] = None,
        expire_time_end: Optional[int] = None,
    ) -> dict:
        client = self._get_volcano_client(tts_provider_id)
        return client.batch_list_train_status(
            speaker_ids=speaker_ids,
            state=state,
            page_number=page_number,
            page_size=page_size,
            next_token=next_token,
            max_results=max_results,
            order_time_start=order_time_start,
            order_time_end=order_time_end,
            expire_time_start=expire_time_start,
            expire_time_end=expire_time_end,
        )

    def order_voices(
        self,
        tts_provider_id: int,
        times: int,
        quantity: int,
        auto_use_coupon: Optional[bool] = None,
        coupon_id: Optional[str] = None,
    ) -> dict:
        client = self._get_volcano_client(tts_provider_id)
        return client.order_access_resource_packs(
            times=times,
            quantity=quantity,
            auto_use_coupon=auto_use_coupon,
            coupon_id=coupon_id,
        )

    def renew_voices(
        self,
        tts_provider_id: int,
        times: int,
        speaker_ids: Optional[List[str]] = None,
        auto_use_coupon: Optional[bool] = None,
        coupon_id: Optional[str] = None,
    ) -> dict:
        client = self._get_volcano_client(tts_provider_id)
        return client.renew_access_resource_packs(
            times=times,
            speaker_ids=speaker_ids,
            auto_use_coupon=auto_use_coupon,
            coupon_id=coupon_id,
        )

    def sync_voices_to_local(self, tts_provider_id: int, db: Session) -> int:
        """批量同步火山引擎音色到本地

        - 整体作为一个事务,任一页失败则回滚,保证数据一致性
        """
        client = self._get_volcano_client(tts_provider_id)

        page_number = 1
        page_size = 100
        total_synced = 0

        try:
            while True:
                result = client.batch_list_train_status(
                    page_number=page_number,
                    page_size=page_size,
                )

                statuses = result.get("Result", {}).get("Statuses", [])

                if not statuses:
                    break

                for status in statuses:
                    speaker_id = status.get("SpeakerID", "")
                    alias = status.get("Alias", "")

                    if not speaker_id:
                        continue

                    existing = db.query(VoicePO).filter(
                        VoicePO.tts_provider_id == tts_provider_id,
                        VoicePO.name == speaker_id,
                    ).first()

                    if not existing:
                        voice = VoicePO(
                            tts_provider_id=tts_provider_id,
                            name=speaker_id,
                            description=alias,
                        )
                        db.add(voice)
                        total_synced += 1
                    else:
                        existing.description = alias

                # 每页统一提交,保证事务性
                db.commit()

                total_count = result.get("Result", {}).get("TotalCount", 0)
                if page_number * page_size >= total_count:
                    break

                page_number += 1
        except Exception:
            db.rollback()
            raise

        logging.info("火山引擎音色同步完成，同步了 %d 个新音色", total_synced)
        return total_synced

    def sync_single_voice_to_local(self, tts_provider_id: int, speaker_id: str, db: Session) -> dict:
        """同步单个火山引擎音色到本地

        - 提交失败时回滚,保证数据一致性
        """
        client = self._get_volcano_client(tts_provider_id)
        result = client.batch_list_train_status(
            speaker_ids=[speaker_id],
            page_number=1,
            page_size=1,
        )

        statuses = result.get("Result", {}).get("Statuses", [])

        if not statuses:
            raise ValueError(f"未找到音色，SpeakerID: {speaker_id}")

        status = statuses[0]
        alias = status.get("Alias", "")

        existing = db.query(VoicePO).filter(
            VoicePO.tts_provider_id == tts_provider_id,
            VoicePO.name == speaker_id,
        ).first()

        try:
            if not existing:
                voice = VoicePO(
                    tts_provider_id=tts_provider_id,
                    name=speaker_id,
                    description=alias,
                )
                db.add(voice)
                db.commit()
                logging.info("火山引擎音色同步成功 (新建)，SpeakerID: %s", speaker_id)
                return {"status": "created", "speaker_id": speaker_id}
            else:
                existing.description = alias
                db.commit()
                logging.info("火山引擎音色同步成功 (更新)，SpeakerID: %s", speaker_id)
                return {"status": "updated", "speaker_id": speaker_id}
        except Exception:
            db.rollback()
            raise
