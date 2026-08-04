import requests
from typing import Optional, List
import os
import logging

from app.core import path_security, url_security
from app.core.exceptions import TTSError, TTSConnectionError, TTSRequestError

# 有效音频数据的最小字节数,用于校验 TTS 返回内容
MIN_AUDIO_SIZE = 100
# 单次响应最大字节数(50MB),防止异常大响应耗尽内存
MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024

class TTSEngine:
    def __init__(self, base_url: str):
        """
        初始化 TTS 引擎
        :param base_url: TTS 服务的基础 URL，如 http://127.0.0.1:8000
        """
        # 校验 base_url 是否指向公网地址(防止 SSRF)
        url_security.validate_public_url(base_url)
        self.base_url = base_url.rstrip("/")

    def synthesize(
        self,
        text: str,
        filename: str,
        emo_text: Optional[str] = None,
        emo_vector: Optional[List[float]] = None,
        save_path: Optional[str] = None,
        allowed_root: Optional[str] = None
    ) -> bytes:
        """
        调用 /v2/synthesize 接口进行语音合成
        :param text: 要合成的文本
        :param filename: 参考音频文件名（服务端已存在）
        :param emo_text: 情绪文本（可选）
        :param emo_vector: 8维情绪向量（可选，优先级高于 emo_text）
        :param save_path: 如果指定，将保存生成的音频文件到本地
        :param allowed_root: 允许保存的根目录（可选），提供时将校验 save_path 位于该目录下
        :return: 音频二进制数据
        """
        # save_path 安全校验:路径穿越防护 + 系统关键目录防护
        if save_path:
            if allowed_root:
                # 校验 save_path 必须位于业务允许的根目录下,防止路径穿越
                path_security.validate_path_within_root(save_path, allowed_root)
            path_security.assert_path_not_system_critical(save_path)

        url = f"{self.base_url}/v2/synthesize"

        payload = {"text": text, "audio_path": filename}

        if emo_vector is not None:
            payload["emo_vector"] = emo_vector
        elif emo_text:
            payload["emo_text"] = emo_text

        try:
            # 使用 stream=True 配合 iter_content 限制响应大小,防止异常大响应耗尽内存
            with requests.post(url, json=payload, timeout=120, stream=True) as resp:
                if resp.status_code != 200:
                    # 尝试解析错误信息
                    try:
                        error_data = resp.json()
                        error_msg = error_data.get('detail') or error_data.get('message') or error_data.get('msg') or resp.text
                    except (ValueError, KeyError):
                        error_msg = resp.text
                    raise TTSRequestError(f"TTS服务返回错误({resp.status_code}): {error_msg}")

                # 流式读取并限制总大小,防止异常大响应
                audio_chunks = []
                total_size = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        total_size += len(chunk)
                        if total_size > MAX_AUDIO_SIZE_BYTES:
                            raise TTSRequestError(f"TTS服务响应超过最大限制 {MAX_AUDIO_SIZE_BYTES} 字节")
                        audio_chunks.append(chunk)
                audio_bytes = b"".join(audio_chunks)

                # 检查返回的内容是否为有效音频
                if len(audio_bytes) < MIN_AUDIO_SIZE:
                    raise TTSRequestError(f"TTS服务返回的音频数据无效，大小: {len(audio_bytes)} 字节")

                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(audio_bytes)

                return audio_bytes

        except requests.exceptions.ConnectionError:
            raise TTSConnectionError(f"TTS服务连接失败，请检查TTS服务是否已启动 ({self.base_url})")
        except requests.exceptions.Timeout:
            raise TTSConnectionError(f"TTS服务请求超时，请检查TTS服务是否正常运行")
        except requests.exceptions.RequestException as e:
            raise TTSRequestError(f"TTS服务请求异常: {str(e)}")

    def get_models(self) -> dict:
        """
        调用 /v1/models 获取模型列表
        :return: 模型信息
        """
        url = f"{self.base_url}/v1/models"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            raise TTSRequestError(f"获取模型列表失败: {str(e)}")

    def check_audio_exists(self, filename: str) -> bool:
        """
        调用 /v1/check/audio 检查参考音频是否存在
        :param filename: 原始文件名
        :return: True or False
        """
        url = f"{self.base_url}/v1/check/audio"
        params = {"file_name": filename}
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json().get("exists", False)
        except requests.exceptions.RequestException as e:
            raise TTSRequestError(f"检查音频是否存在失败: {str(e)}")

    def upload_audio(self, file_path: str, full_path=None) -> dict:
        """
                调用 /v1/upload_audio 上传音频
                :param file_path: 本地音频文件路径
                :param full_path: 用于唯一标识的全路径（可选，如果不传则使用 file_path）
                :return: 服务端响应 JSON
                """
        # 路径安全校验:防止路径穿越和写入系统关键目录
        path_security.assert_path_not_system_critical(file_path)
        if not os.path.isfile(file_path):
            # 统一以异常形式上报错误,避免调用方依赖魔法字典
            raise TTSError(f"文件不存在: {file_path}")

        url = f"{self.base_url}/v1/upload_audio"
        try:
            with open(file_path, "rb") as f:
                files = {
                    "audio": (os.path.basename(file_path), f, "audio/wav")
                }
                # 如果需要额外传 fullpath 参数
                data = {}
                if full_path:
                    data["full_path"] = full_path

                resp = requests.post(url, files=files, data=data, timeout=30)
                resp.raise_for_status()
                return resp.json()
        except requests.exceptions.RequestException as e:
            raise TTSRequestError(f"请求失败: {str(e)}")
        except Exception as e:
            raise TTSError(f"上传异常: {str(e)}")
