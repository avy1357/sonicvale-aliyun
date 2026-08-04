import os
import logging
import time
import requests
from typing import Union

from .ASRData import ASRDataSeg
from .BaseASR import BaseASR

# API URL 抽取到环境变量,便于测试与切换环境
API_URL = os.getenv("KUAI_SHOU_ASR_API_URL", "https://ai.kuaishou.com/api/effects/subtitle_generate")


class KuaiShouASR(BaseASR):
    # 音频文件大小上限 50MB
    MAX_AUDIO_SIZE = 50 * 1024 * 1024

    def __init__(self, audio_path: Union[str, bytes], use_cache: bool = False):
        super().__init__(audio_path, use_cache)

    def _run(self) -> dict:
        return self._submit()

    def _make_segments(self, resp_data: dict) -> list[ASRDataSeg]:
        return [ASRDataSeg(u['text'], u['start_time'], u['end_time']) for u in resp_data['data']['text']]

    def _submit(self) -> dict:
        # 校验音频文件大小,避免上传超大文件导致接口失败
        file_size = len(self.file_binary) if self.file_binary else 0
        if file_size > self.MAX_AUDIO_SIZE:
            raise ValueError(f"音频文件过大: {file_size} 字节，最大支持 {self.MAX_AUDIO_SIZE} 字节")

        payload = {
            "typeId": "1"
        }
        # 从 audio_path 提取实际文件名,避免硬编码 'test.mp3'
        if isinstance(self.audio_path, bytes):
            audio_name = "audio.mp3"
        else:
            audio_name = os.path.basename(self.audio_path) or "audio.mp3"
        files = [('file', (audio_name, self.file_binary, 'audio/mpeg'))]
        # 捕获网络异常并重试 2 次,HTTPError 一并捕获以便重试
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                result = requests.post(API_URL, data=payload, files=files, timeout=120)
                result.raise_for_status()
                return result.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                   requests.exceptions.HTTPError, OSError) as e:
                if attempt < max_retries:
                    logging.warning("快手 ASR 提交失败,第 %d 次重试: %s", attempt + 1, e)
                    time.sleep(1)
                else:
                    raise
        # 理论上不会到达此处
        raise RuntimeError("快手 ASR 提交失败")
