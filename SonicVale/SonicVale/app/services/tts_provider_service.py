import requests
import logging
from sqlalchemy import Sequence

from app.entity.tts_provider_entity import TTSProviderEntity
from app.models.po import TTSProviderPO
from app.repositories.tts_provider_repository import TTSProviderRepository


class TTSProviderService:

    def __init__(self, repository: TTSProviderRepository):
        """注入 repository"""
        self.repository = repository

    def get_all_tts_providers(self) -> list[TTSProviderEntity]:
        """查询所有tts供应商"""
        pos = self.repository.get_all()
        res = [TTSProviderEntity(**{k: v for k, v in po.__dict__.items() if not k.startswith("_")}) for po in pos]
        return res

    def get_tts_provider(self, tts_provider_id: int) -> TTSProviderEntity | None:
        """根据 ID 查询tts供应商"""
        po = self.repository.get_by_id(tts_provider_id)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        res = TTSProviderEntity(**data)
        return res


    def update_tts_provider(self, tts_provider_id: int, data:dict) -> bool:
        """更新tts供应商
        - 可以只更新部分字段
        - 检查同名冲突
        - 检查project_id不能改变
        """
        name = data["name"]
        if self.repository.get_by_name(name) and self.repository.get_by_name(name).id != tts_provider_id:
            return False
        self.repository.update(tts_provider_id, data)
        return True

    def delete_tts_provider(self, tts_provider_id: int) -> bool:
        """删除tts供应商
        """
        res = self.repository.delete(tts_provider_id)
        return res

    def create_default_tts_provider(self):
        """创建默认的tts供应商"""
        if self.repository.get_by_name("index_tts") :
            return
        if self.repository.get_by_id(1) :
            return
        po = TTSProviderPO(name="index_tts", id=1, provider_type="index_tts", status=1, api_base_url="", api_key="")
        self.repository.create(po)

    def create_tts_provider(self, dto) -> bool:
        """创建新的TTS供应商"""
        # 检查名称是否已存在
        if self.repository.get_by_name(dto.name):
            return False

        po = TTSProviderPO(
            name=dto.name,
            provider_type=dto.provider_type or "index_tts",
            api_base_url=dto.api_base_url or "",
            api_key=dto.api_key or "",
            x_api_key=dto.x_api_key or "",
            access_key_id=getattr(dto, "access_key_id", None) or "",
            access_key_secret=getattr(dto, "access_key_secret", None) or "",
            voice_type=dto.voice_type or "",
            resource_id=dto.resource_id or "",
            voice_clone_appid=dto.voice_clone_appid or "",
            status=dto.status if dto.status is not None else 1
        )
        self.repository.create(po)
        return True

    def get_tts_provider_by_name(self, name: str) -> TTSProviderEntity | None:
        """根据名称查询TTS供应商"""
        po = self.repository.get_by_name(name)
        if not po:
            return None
        data = {k: v for k, v in po.__dict__.items() if not k.startswith("_")}
        return TTSProviderEntity(**data)

    def test_tts_provider(self, entity: TTSProviderEntity):
        # 根据 provider_type 执行不同的测试逻辑
        provider_type = entity.provider_type or "index_tts"
        
        if provider_type == "index_tts":
            return self._test_index_tts(entity)
        elif provider_type == "volcano":
            return self._test_volcano_tts(entity)
        elif provider_type == "aliyun":
            return self._test_aliyun_tts(entity)
        else:
            logging.error("不支持的TTS提供商类型: %s", provider_type)
            return False
    
    def _test_index_tts(self, entity: TTSProviderEntity):
        """测试 IndexTTS 连接"""
        api_base_url = entity.api_base_url
        if not api_base_url:
            return False
        try:
            resp = requests.get(api_base_url, timeout=5)
            if 200 <= resp.status_code < 400:
                try:
                    data = resp.json()
                    if "endpoints" in data:
                        return True
                    else:
                        logging.error("TTS provider test failed: 'endpoints' missing in response")
                        return False
                except ValueError:
                    logging.error("TTS provider test failed: response is not valid JSON")
                    return False
            else:
                logging.error("TTS provider test failed: status %s", resp.status_code)
                return False
        except Exception as e:
            logging.exception("TTS provider test failed: %s", e)
            return False
    
    def _test_volcano_tts(self, entity: TTSProviderEntity):
        x_api_key = entity.x_api_key
        api_key = entity.api_key
        voice_type = entity.voice_type
        resource_id = getattr(entity, "resource_id", None)

        if x_api_key:
            try:
                from app.core.volcano_tts_client import VolcanoTTSClient
                client = VolcanoTTSClient(
                    api_key=x_api_key,
                    resource_id=resource_id,
                    speaker=voice_type,
                )
                return client.test_connection()
            except Exception as e:
                logging.exception("火山引擎 TTS 连接测试失败（新版鉴权）: %s", e)
                return False
        elif api_key:
            try:
                from app.core.volcano_tts_client import VolcanoTTSClient
                app_id = getattr(entity, "voice_clone_appid", None)
                client = VolcanoTTSClient(
                    app_key=app_id,
                    access_key=api_key,
                    resource_id=resource_id,
                    speaker=voice_type,
                )
                return client.test_connection()
            except Exception as e:
                logging.exception("火山引擎 TTS 连接测试失败（旧版鉴权）: %s", e)
                return False
        else:
            logging.error("火山引擎 TTS 配置无效，x_api_key 或 api_key 未配置")
            return False
    
    def _test_aliyun_tts(self, entity: TTSProviderEntity):
        """测试阿里云 CosyVoice TTS 连接（DashScope SDK）"""
        api_key = entity.api_key
        if not api_key:
            logging.error("阿里云 TTS 的 API Key 未配置")
            return False

        try:
            model = entity.api_base_url or "cosyvoice-v3-plus"
            if model.startswith("http"):
                model = "cosyvoice-v3-plus"

            from app.core.aliyun_tts_client import AliyunTTSClient
            client = AliyunTTSClient(
                api_key=api_key,
                model=model,
            )

            return client.test_connection()
        except Exception as e:
            logging.exception("阿里云 CosyVoice TTS 连接测试失败: %s", e)
            return False



