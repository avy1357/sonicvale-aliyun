import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.aliyun_voice_clone_client import AliyunVoiceCloneClient
from app.core.url_security import validate_public_url
from app.services.tts_provider_service import TTSProviderService


class AliyunVoiceCloneService:
    """阿里云声音复刻服务"""
    
    def __init__(self, tts_provider_service: TTSProviderService):
        self.tts_provider_service = tts_provider_service
    
    def _get_client(self, tts_provider_id: int) -> AliyunVoiceCloneClient:
        """获取阿里云声音复刻客户端"""
        tts_provider = self.tts_provider_service.get_tts_provider(tts_provider_id)
        if not tts_provider:
            raise ValueError(f"TTS 提供商不存在，ID: {tts_provider_id}")
        
        if tts_provider.provider_type != "aliyun":
            raise ValueError("仅支持阿里云 TTS 提供商")
        
        api_key = getattr(tts_provider, "api_key", None)
        if not api_key:
            raise ValueError("阿里云 TTS 提供商的 API Key 未配置")
        
        return AliyunVoiceCloneClient(api_key=api_key)
    
    def list_voices(self, tts_provider_id: int, prefix: Optional[str] = None,
                   page_index: int = 0, page_size: int = 10) -> dict:
        """
        查询阿里云音色列表
        
        :param tts_provider_id: TTS 提供商 ID
        :param prefix: 按音色名称前缀筛选
        :param page_index: 页码索引
        :param page_size: 每页条数
        :return: 音色列表
        """
        client = self._get_client(tts_provider_id)
        return client.list_voices(prefix=prefix, page_index=page_index, page_size=page_size)
    
    def query_voice(self, tts_provider_id: int, voice_id: str) -> dict:
        """
        查询阿里云音色详情
        
        :param tts_provider_id: TTS 提供商 ID
        :param voice_id: 音色 ID
        :return: 音色详情
        """
        client = self._get_client(tts_provider_id)
        return client.query_voice(voice_id)
    
    def create_voice(self, tts_provider_id: int, target_model: str, prefix: str, url: str,
                    language_hints: Optional[List[str]] = None,
                    max_prompt_audio_length: Optional[float] = None,
                    enable_preprocess: Optional[bool] = None) -> str:
        """
        创建阿里云音色

        :param tts_provider_id: TTS 提供商 ID
        :param target_model: 驱动音色的语音合成模型
        :param prefix: 音色名称前缀
        :param url: 音频文件URL
        :param language_hints: 语种提示
        :param max_prompt_audio_length: 参考音频最大时长
        :param enable_preprocess: 是否开启预处理
        :return: 音色 ID
        """
        # SSRF 防护:校验 URL 必须为公网地址
        validate_public_url(url)
        client = self._get_client(tts_provider_id)
        return client.create_voice(
            target_model=target_model,
            prefix=prefix,
            url=url,
            language_hints=language_hints,
            max_prompt_audio_length=max_prompt_audio_length,
            enable_preprocess=enable_preprocess
        )

    def update_voice(self, tts_provider_id: int, voice_id: str, url: str,
                   language_hints: Optional[List[str]] = None,
                   max_prompt_audio_length: Optional[float] = None,
                   enable_preprocess: Optional[bool] = None) -> bool:
        """
        更新阿里云音色

        :param tts_provider_id: TTS 提供商 ID
        :param voice_id: 音色 ID
        :param url: 新的音频文件URL
        :return: 是否成功
        """
        # SSRF 防护:校验 URL 必须为公网地址
        validate_public_url(url)
        client = self._get_client(tts_provider_id)
        return client.update_voice(
            voice_id=voice_id,
            url=url,
            language_hints=language_hints,
            max_prompt_audio_length=max_prompt_audio_length,
            enable_preprocess=enable_preprocess
        )
    
    def delete_voice(self, tts_provider_id: int, voice_id: str) -> bool:
        """
        删除阿里云音色
        
        :param tts_provider_id: TTS 提供商 ID
        :param voice_id: 音色 ID
        :return: 是否成功
        """
        client = self._get_client(tts_provider_id)
        return client.delete_voice(voice_id)
    
    def get_last_request_id(self, tts_provider_id: int) -> str:
        """获取最近一次请求 ID"""
        client = self._get_client(tts_provider_id)
        return client.get_last_request_id()

    def sync_voices_to_local(self, tts_provider_id: int, db: Session) -> int:
        """批量同步阿里云音色到本地 voices 表

        - 整体作为一个事务,任一页失败则回滚已 add 的记录,保证数据一致性
        """
        from app.models.po import VoicePO

        client = self._get_client(tts_provider_id)
        page_index = 0
        page_size = 100
        total_synced = 0

        try:
            while True:
                result = client.list_voices(prefix=None, page_index=page_index, page_size=page_size)
                voices = result.get("voices", [])

                if not voices:
                    break

                for voice in voices:
                    voice_id = voice.get("voice_id", "") if isinstance(voice, dict) else getattr(voice, "voice_id", "")
                    voice_name = voice.get("name", "") if isinstance(voice, dict) else getattr(voice, "name", "")

                    if not voice_id:
                        continue

                    # 以 voice_id 作为 name 字段查找本地是否已存在
                    existing = db.query(VoicePO).filter(
                        VoicePO.tts_provider_id == tts_provider_id,
                        VoicePO.name == voice_id,
                    ).first()

                    if not existing:
                        voice_record = VoicePO(
                            tts_provider_id=tts_provider_id,
                            name=voice_id,
                            description=voice_name,
                        )
                        db.add(voice_record)
                        total_synced += 1
                    else:
                        existing.description = voice_name

                # 每页统一提交,保证事务性
                db.commit()

                page_count = result.get("page_count", 0)
                if page_count < page_size:
                    break

                page_index += 1
        except Exception:
            db.rollback()
            raise

        logging.info("阿里云音色同步完成，同步了 %d 个新音色", total_synced)
        return total_synced

    def sync_single_voice_to_local(self, tts_provider_id: int, voice_id: str, db: Session) -> dict:
        """同步单个阿里云音色到本地 voices 表

        - 提交失败时回滚,保证数据一致性
        """
        from app.models.po import VoicePO

        client = self._get_client(tts_provider_id)
        details = client.query_voice(voice_id)

        voice_name = details.get("name", "") if isinstance(details, dict) else getattr(details, "name", "")

        existing = db.query(VoicePO).filter(
            VoicePO.tts_provider_id == tts_provider_id,
            VoicePO.name == voice_id,
        ).first()

        try:
            if not existing:
                voice_record = VoicePO(
                    tts_provider_id=tts_provider_id,
                    name=voice_id,
                    description=voice_name,
                )
                db.add(voice_record)
                db.commit()
                logging.info("阿里云音色同步成功 (新建)，voice_id: %s", voice_id)
                return {"status": "created", "voice_id": voice_id}
            else:
                existing.description = voice_name
                db.commit()
                logging.info("阿里云音色同步成功 (更新)，voice_id: %s", voice_id)
                return {"status": "updated", "voice_id": voice_id}
        except Exception:
            db.rollback()
            raise
