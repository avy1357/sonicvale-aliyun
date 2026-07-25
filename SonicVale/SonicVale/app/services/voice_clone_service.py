import logging
from typing import List, Optional

from app.core.volcano_voice_clone_client import VolcanoVoiceCloneClient
from app.dto.voice_clone_dto import VoiceCloneCreateDTO, VoiceCloneUploadDTO, VoiceCloneTrainDTO
from app.entity.voice_clone_entity import VoiceCloneEntity
from app.models.voice_clone_po import VoiceClonePO
from app.repositories.voice_clone_repository import VoiceCloneRepository
from app.services.tts_provider_service import TTSProviderService


class VoiceCloneService:
    def __init__(self, repository: VoiceCloneRepository, tts_provider_service: TTSProviderService):
        self.repository = repository
        self.tts_provider_service = tts_provider_service

    def _get_volcano_client(self, clone: VoiceClonePO) -> VolcanoVoiceCloneClient:
        """根据声音复刻记录所属的 TTS 提供商获取火山引擎声音复刻客户端

        - 统一校验 tts_provider 存在、provider_type 为 volcano、x_api_key 已配置
        - 在 upload_and_train / query_training_status / train_and_wait 中复用,消除重复代码
        """
        tts_provider = self.tts_provider_service.get_tts_provider(clone.tts_provider_id)
        if not tts_provider:
            raise ValueError(f"TTS 提供商不存在，ID: {clone.tts_provider_id}")

        if not getattr(tts_provider, "provider_type", None) == "volcano":
            raise ValueError("声音复刻仅支持火山引擎 TTS 提供商")

        x_api_key = getattr(tts_provider, "x_api_key", None)
        if not x_api_key:
            raise ValueError("火山引擎 TTS 提供商的 X-Api-Key 未配置")

        resource_id = "seed-icl-2.0" if clone.model_type == 4 else "seed-icl-1.0"

        return VolcanoVoiceCloneClient(
            x_api_key=x_api_key,
            resource_id=resource_id,
            model_type=clone.model_type,
        )

    def create_voice_clone(self, entity: VoiceCloneEntity) -> Optional[VoiceCloneEntity]:
        """创建声音复刻记录"""
        existing = self.repository.get_by_name(entity.name, entity.tts_provider_id)
        if existing:
            return None

        existing_speaker = self.repository.get_by_speaker_id(entity.speaker_id)
        if existing_speaker:
            raise ValueError(f"音色 ID '{entity.speaker_id}' 已存在")

        po = VoiceClonePO(**entity.__dict__)
        res = self.repository.create(po)

        data = {k: v for k, v in res.__dict__.items() if not k.startswith("_")}
        return VoiceCloneEntity(**data)

    def get_voice_clone(self, clone_id: int) -> Optional[VoiceCloneEntity]:
        """根据 ID 查询声音复刻记录"""
        po = self.repository.get_by_id(clone_id)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        return VoiceCloneEntity(**data)

    def get_all_voice_clones(self, tts_provider_id: int) -> List[VoiceCloneEntity]:
        """查询指定 TTS 提供商下的所有声音复刻记录"""
        pos = self.repository.get_all_by_tts_provider(tts_provider_id)
        entities = [
            VoiceCloneEntity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")})
            for po in pos
        ]
        return entities

    def upload_and_train(self, dto: VoiceCloneUploadDTO) -> dict:
        """上传音频并提交训练

        - 先调用外部 API 上传音频,成功后再更新数据库状态为"训练中"
        - 避免 API 失败时数据库状态与事实不符
        """
        clone = self.repository.get_by_id(dto.clone_id)
        if not clone:
            raise ValueError(f"声音复刻记录不存在，ID: {dto.clone_id}")

        client = self._get_volcano_client(clone)

        # 先调用外部 API,失败则直接抛异常,不更新数据库
        result = client.upload_audio(
            speaker_id=clone.speaker_id,
            audio_path=dto.reference_path,
            language=clone.language,
            text=dto.text,
            enable_denoise=dto.enable_denoise,
            denoise_model_id=dto.denoise_model_id,
            enable_mss=dto.enable_mss,
            enable_crop_by_asr=dto.enable_crop_by_asr,
        )

        # API 调用成功后再更新数据库状态
        update_data = {"status": 1}
        if dto.reference_path:
            update_data["reference_path"] = dto.reference_path
        self.repository.update(clone.id, update_data)

        logging.info("声音复刻音频上传成功，clone_id: %s, speaker_id: %s", clone.id, clone.speaker_id)
        return result

    def query_training_status(self, clone_id: int) -> dict:
        """查询训练状态并更新数据库"""
        clone = self.repository.get_by_id(clone_id)
        if not clone:
            raise ValueError(f"声音复刻记录不存在，ID: {clone_id}")

        client = self._get_volcano_client(clone)

        result = client.query_status(clone.speaker_id)
        status = result.get("status", 0)

        update_data = {
            "status": status,
            "version": result.get("version"),
            "demo_audio_url": result.get("demo_audio"),
        }
        self.repository.update(clone_id, update_data)

        return result

    def train_and_wait(self, dto: VoiceCloneTrainDTO) -> dict:
        """上传音频并等待训练完成"""
        self.upload_and_train(VoiceCloneUploadDTO(
            clone_id=dto.clone_id,
            reference_path=dto.reference_path,
            text=dto.text,
            enable_denoise=dto.enable_denoise,
            denoise_model_id=dto.denoise_model_id,
            enable_mss=dto.enable_mss,
            enable_crop_by_asr=dto.enable_crop_by_asr,
        ))

        # upload_and_train 已校验 x_api_key,此处直接复用 _get_volcano_client
        clone = self.repository.get_by_id(dto.clone_id)
        client = self._get_volcano_client(clone)

        result = client.wait_for_training(
            clone.speaker_id,
            max_wait_seconds=dto.max_wait_seconds,
            poll_interval=dto.poll_interval,
        )

        status = result.get("status", 0)
        self.repository.update(dto.clone_id, {
            "status": status,
            "version": result.get("version"),
            "demo_audio_url": result.get("demo_audio"),
        })

        return result

    def delete_voice_clone(self, clone_id: int) -> bool:
        """删除声音复刻记录"""
        return self.repository.delete(clone_id)

    def update_voice_clone(self, clone_id: int, update_data: dict) -> Optional[VoiceCloneEntity]:
        """更新声音复刻记录"""
        po = self.repository.update(clone_id, update_data)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        return VoiceCloneEntity(**data)
