import time
import logging
import threading
from typing import Optional

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

# 保护 dashscope.api_key 全局状态的线程锁（C3: 并发安全）
_dashscope_lock = threading.Lock()


class AliyunTTSClient:
    """
    阿里云 CosyVoice TTS 客户端
    使用 DashScope Python SDK 进行语音合成

    鉴权方式：API Key（与声音复刻共用同一个 DashScope API Key）
    官方文档：https://help.aliyun.com/zh/model-studio/voice-clone-design-python-sdk

    支持的模型：
    - cosyvoice-v3-plus: 多语种高质量合成
    - cosyvoice-v3.5-plus: 最新版，支持更多语种和音频预处理
    - cosyvoice-v3.5-flash: 低延迟版
    - cosyvoice-v3-flash: 低延迟版
    """

    DEFAULT_MODEL = "cosyvoice-v3-plus"
    DEFAULT_VOICE = "longxiaochun"
    DEFAULT_FORMAT = "wav"
    DEFAULT_SAMPLE_RATE = 22050
    MAX_RETRIES = 3
    RETRY_DELAY = 1

    def __init__(self, api_key: str, model: Optional[str] = None,
                 voice: Optional[str] = None,
                 base_url: str = "https://dashscope.aliyuncs.com/api/v1"):
        """
        初始化阿里云 CosyVoice TTS 客户端

        :param api_key: DashScope API Key（与声音复刻共用）
        :param model: 合成模型（必须与声音复刻时的 target_model 一致）
        :param voice: 默认音色（可以是内置音色名或复刻得到的 voice_id）
        :param base_url: DashScope API 基础地址
        """
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.voice = voice or self.DEFAULT_VOICE

        dashscope.api_key = api_key
        dashscope.base_http_api_url = base_url

        logging.info("阿里云 CosyVoice TTS 客户端初始化成功，模型: %s, 默认音色: %s",
                     self.model, self.voice)

    def synthesize(self, text: str, voice: Optional[str] = None,
                   audio_format: str = "wav",
                   sample_rate: int = None,
                   instruction: Optional[str] = None,
                   volume: int = 50,
                   speech_rate: float = 1.0,
                   pitch_rate: float = 1.0) -> bytes:
        """
        使用 DashScope SpeechSynthesizer 合成语音

        :param text: 要合成的文本
        :param voice: 音色（可选，可以是内置音色名或复刻 voice_id，覆盖默认值）
        :param audio_format: 音频格式（wav/mp3/pcm），默认 wav
        :param sample_rate: 采样率，默认 22050
        :param instruction: 语音风格指令（自然语言，如"用温柔的语气说"、"带点兴奋感"）
        :param volume: 音量 0-100，默认 50
        :param speech_rate: 语速，默认 1.0
        :param pitch_rate: 语调，默认 1.0
        :return: 音频二进制数据
        """
        target_voice = voice or self.voice
        target_sample_rate = sample_rate or self.DEFAULT_SAMPLE_RATE

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._do_synthesize(text, target_voice, audio_format, target_sample_rate,
                                           instruction=instruction, volume=volume,
                                           speech_rate=speech_rate, pitch_rate=pitch_rate)
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("阿里云 CosyVoice 合成失败，第 %d 次重试: %s",
                                    attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("阿里云 CosyVoice 合成失败，已达到最大重试次数")
                    raise Exception(f"阿里云 CosyVoice 合成失败: {str(e)}")

        raise Exception("阿里云 CosyVoice 合成失败")

    def _do_synthesize(self, text: str, voice: str,
                       audio_format: str, sample_rate: int,
                       instruction: Optional[str] = None,
                       volume: int = 50,
                       speech_rate: float = 1.0,
                       pitch_rate: float = 1.0) -> bytes:
        """
        执行 DashScope SpeechSynthesizer 合成

        :param text: 要合成的文本
        :param voice: 音色
        :param audio_format: 音频格式
        :param sample_rate: 采样率
        :param instruction: 语音风格指令（自然语言描述）
        :param volume: 音量 0-100
        :param speech_rate: 语速倍率
        :param pitch_rate: 语调倍率
        :return: 音频二进制数据
        """
        kwargs = dict(
            model=self.model,
            voice=voice,
            format=audio_format,
            sample_rate=sample_rate,
            volume=volume,
            speech_rate=speech_rate,
            pitch_rate=pitch_rate,
        )
        if instruction:
            kwargs["instruction"] = instruction

        with _dashscope_lock:
            dashscope.api_key = self.api_key
            synthesizer = SpeechSynthesizer(**kwargs)
            audio = synthesizer.call(text)

        if audio is None:
            request_id = synthesizer.get_last_request_id()
            raise Exception(f"阿里云 CosyVoice 返回空数据，request_id: {request_id}")

        audio_bytes = audio if isinstance(audio, bytes) else bytes(audio)

        if len(audio_bytes) < 100:
            raise Exception(f"音频数据无效，大小: {len(audio_bytes)} 字节")

        logging.info("阿里云 CosyVoice 合成成功，音色: %s, 模型: %s, 音频大小: %d 字节",
                     voice, self.model, len(audio_bytes))
        return audio_bytes

    def test_connection(self) -> bool:
        """
        测试阿里云 CosyVoice TTS 连接是否正常

        :return: True 表示连接正常，False 表示连接失败
        """
        try:
            self.synthesize("测试连接", self.voice)
            return True
        except Exception as e:
            logging.error("阿里云 CosyVoice TTS 连接测试失败: %s", str(e))
            return False
