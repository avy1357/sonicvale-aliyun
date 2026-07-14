import base64
import json
import logging
import os
import requests
import time
from typing import Optional


class VolcanoVoiceCloneClient:
    """
    火山引擎声音复刻客户端
    使用 HTTP REST API 进行音色上传和训练状态查询
    
    官方文档：https://www.volcengine.com/docs/6561/1305191
    
    鉴权方式：X-Api-Key（在 Header 中传递）
    """
    
    BASE_URL = "https://openspeech.bytedance.com"
    UPLOAD_PATH = "/api/v1/mega_tts/audio/upload"
    STATUS_PATH = "/api/v1/mega_tts/status"
    
    MODEL_TYPE_ICL_1_0 = 1
    MODEL_TYPE_DIT_STANDARD = 2
    MODEL_TYPE_DIT_RESTORE = 3
    MODEL_TYPE_ICL_2_0 = 4
    
    RESOURCE_ID_ICL_1_0 = "seed-icl-1.0"
    RESOURCE_ID_ICL_2_0 = "seed-icl-2.0"
    
    LANGUAGE_CN = 0
    LANGUAGE_EN = 1
    LANGUAGE_JA = 2
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    def __init__(self, x_api_key: str,
                 resource_id: Optional[str] = None, model_type: int = MODEL_TYPE_ICL_1_0,
                 appid: Optional[str] = None):
        """
        初始化声音复刻客户端
        
        :param x_api_key: X-Api-Key（用于声音复刻API鉴权）
        :param resource_id: 资源 ID，如 seed-icl-1.0 / seed-icl-2.0
        :param model_type: 模型类型，1=ICL1.0, 2=DiT标准版, 3=DiT还原版, 4=ICL2.0
        :param appid: 火山引擎应用 ID（可选，部分接口需要）
        """
        self.x_api_key = x_api_key
        self.resource_id = resource_id or self.RESOURCE_ID_ICL_1_0
        self.model_type = model_type
        self.appid = appid
        self.session = requests.Session()
        
        logging.info("火山引擎声音复刻客户端初始化成功，model_type: %d", self.model_type)
    
    def _build_headers(self) -> dict:
        """构建请求头"""
        return {
            "X-Api-Key": self.x_api_key,
            "Resource-Id": self.resource_id,
            "Content-Type": "application/json",
        }
    
    def upload_audio(self, speaker_id: str, audio_path: str, 
                     language: int = LANGUAGE_CN,
                     text: Optional[str] = None,
                     enable_denoise: bool = True,
                     denoise_model_id: str = "",
                     enable_mss: bool = False,
                     enable_crop_by_asr: bool = False) -> dict:
        """
        上传音频进行音色训练
        
        :param speaker_id: 音色 ID（S_开头）
        :param audio_path: 音频文件路径
        :param language: 语种，0=中文, 1=英文, 2=日语
        :param text: 参考文本（可选，用于WER校验）
        :param enable_denoise: 是否开启降噪
        :param denoise_model_id: 降噪模型 ID
        :param enable_mss: 是否使用音源分离
        :param enable_crop_by_asr: 是否使用ASR截断
        :return: 上传结果，包含 speaker_id
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        audio_format = os.path.splitext(audio_path)[1].lstrip(".")
        if not audio_format:
            audio_format = "wav"
        
        extra_params = {
            "voice_clone_denoise_model_id": denoise_model_id,
            "voice_clone_enable_mss": enable_mss,
            "enable_crop_by_asr": enable_crop_by_asr,
            "enable_audio_denoise": enable_denoise,
        }
        
        payload = {
            "appid": self.appid,
            "speaker_id": speaker_id,
            "audios": [{
                "audio_bytes": audio_b64,
                "audio_format": audio_format,
            }],
            "source": 2,
            "language": language,
            "model_type": self.model_type,
            "extra_params": json.dumps(extra_params),
        }
        
        if text:
            payload["audios"][0]["text"] = text
        
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.post(
                    f"{self.BASE_URL}{self.UPLOAD_PATH}",
                    headers=self._build_headers(),
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                result = resp.json()
                
                status_code = result.get("BaseResp", {}).get("StatusCode", -1)
                if status_code != 0:
                    status_msg = result.get("BaseResp", {}).get("StatusMessage", "未知错误")
                    raise Exception(f"上传失败: {status_code} - {status_msg}")
                
                logging.info("声音复刻音频上传成功，speaker_id: %s", speaker_id)
                return result
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("上传失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("上传失败，已达到最大重试次数")
                    raise
    
    def query_status(self, speaker_id: str) -> dict:
        """
        查询音色训练状态
        
        :param speaker_id: 音色 ID
        :return: 状态信息，包含 status, create_time, version, demo_audio 等
        """
        payload = {
            "appid": self.appid,
            "speaker_id": speaker_id,
        }
        
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.post(
                    f"{self.BASE_URL}{self.STATUS_PATH}",
                    headers=self._build_headers(),
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                result = resp.json()
                
                status_code = result.get("BaseResp", {}).get("StatusCode", -1)
                if status_code != 0:
                    status_msg = result.get("BaseResp", {}).get("StatusMessage", "未知错误")
                    raise Exception(f"查询状态失败: {status_code} - {status_msg}")
                
                return result
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("查询状态失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("查询状态失败，已达到最大重试次数")
                    raise
    
    def wait_for_training(self, speaker_id: str, max_wait_seconds: int = 600, 
                          poll_interval: int = 5) -> dict:
        """
        等待训练完成
        
        :param speaker_id: 音色 ID
        :param max_wait_seconds: 最大等待时间（秒）
        :param poll_interval: 轮询间隔（秒）
        :return: 最终状态信息
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            result = self.query_status(speaker_id)
            status = result.get("status", 0)
            
            if status == 2 or status == 4:  # Success 或 Active
                logging.info("声音复刻训练成功，speaker_id: %s", speaker_id)
                return result
            elif status == 3:  # Failed
                raise Exception(f"声音复刻训练失败，speaker_id: {speaker_id}")
            
            logging.info("声音复刻训练中，speaker_id: %s，等待 %d 秒后重试...", speaker_id, poll_interval)
            time.sleep(poll_interval)
        
        raise Exception(f"声音复刻训练超时（{max_wait_seconds}秒），speaker_id: {speaker_id}")
