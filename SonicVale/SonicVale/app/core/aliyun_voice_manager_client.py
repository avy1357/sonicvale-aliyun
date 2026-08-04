import logging
import re
import time
import threading
import dashscope
from typing import Optional, List
from dashscope.audio.tts_v2 import VoiceEnrollmentService

from app.core.exceptions import RETRYABLE_NETWORK_EXCEPTIONS

# 保护 dashscope.api_key 全局状态的线程锁（C3: 并发安全）
_dashscope_lock = threading.Lock()


class AliyunVoiceManagerClient:
    """
    阿里云音色管理客户端
    使用 DashScope Python SDK 进行音色管理（查询、创建、更新、删除、同步）

    官方文档：https://help.aliyun.com/zh/model-studio/voice-clone-design-python-sdk

    鉴权方式：API Key（通过 dashscope.api_key 设置）

    与 AliyunVoiceCloneClient 的区别：
    - AliyunVoiceCloneClient 侧重于声音复刻的创建流程
    - AliyunVoiceManagerClient 侧重于音色的全生命周期管理（查询、更新、删除、批量同步等）
    """

    BASE_URL_CN = "https://dashscope.aliyuncs.com/api/v1"

    # 模型兼容性映射
    MODEL_LANGUAGE_HINTS = {
        "cosyvoice-v3-plus": ["zh", "en", "fr", "de", "ja", "ko", "ru"],
        "cosyvoice-v3.5-plus": ["zh", "en", "fr", "de", "ja", "ko", "ru", "pt", "th", "id", "vi"],
        "cosyvoice-v3.5-flash": ["zh", "en", "fr", "de", "ja", "ko", "ru", "pt", "th", "id", "vi"],
        "cosyvoice-v3-flash": ["zh", "en", "fr", "de", "ja", "ko", "ru", "pt", "th", "id", "vi"],
    }
    # 仅 v3.5 和 v3-flash 系列支持 max_prompt_audio_length 和 enable_preprocess
    V35_MODELS = {"cosyvoice-v3.5-plus", "cosyvoice-v3.5-flash", "cosyvoice-v3-flash"}

    MAX_RETRIES = 3
    RETRY_DELAY = 1

    def __init__(self, api_key: str):
        """
        初始化阿里云音色管理客户端

        :param api_key: DashScope API Key
        """
        self.api_key = api_key
        # 注意：dashscope.api_key 不在 __init__ 中全局设置,避免多客户端并发时互相覆盖。
        # 每次方法调用时通过锁保护设置,保证使用各自的 api_key。
        with _dashscope_lock:
            dashscope.base_http_api_url = self.BASE_URL_CN
            self.service = VoiceEnrollmentService()
        logging.info("阿里云音色管理客户端初始化成功")

    def __repr__(self) -> str:
        # 隐藏 api_key,避免日志/调试输出泄露凭据
        return "AliyunVoiceManagerClient()"

    def list_voices(self, prefix: Optional[str] = None,
                    page_index: int = 0, page_size: int = 10) -> dict:
        """
        查询音色列表

        :param prefix: 按音色名称前缀筛选
        :param page_index: 页码索引，默认0
        :param page_size: 每页条数，默认10
        :return: 音色列表字典，包含 voices 列表、page_count 当前页数量、total 估算总数
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                with _dashscope_lock:
                    dashscope.api_key = self.api_key
                    voices = self.service.list_voice(
                        prefix=prefix,
                        page_index=page_index,
                        page_size=page_size
                    )
                count = len(voices)
                # I7: 不再额外调 API 估算总数，用当前页数据推算
                total = page_index * page_size + count
                if count >= page_size:
                    # 当前页满了，说明可能还有更多，总数至少 +1
                    total += 1

                return {"voices": voices, "page_count": count, "total": total}
            except RETRYABLE_NETWORK_EXCEPTIONS as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("查询音色列表失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("查询音色列表失败，已达到最大重试次数")
                    raise
        # for 循环正常结束(未 return)时显式抛出,避免隐式返回 None
        raise RuntimeError("查询音色列表失败: 重试耗尽")

    def query_voice(self, voice_id: str) -> dict:
        """
        查询音色详情

        :param voice_id: 要查询的音色ID
        :return: 音色详情字典
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                with _dashscope_lock:
                    dashscope.api_key = self.api_key
                    details = self.service.query_voice(voice_id=voice_id)
                return details
            except RETRYABLE_NETWORK_EXCEPTIONS as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("查询音色详情失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("查询音色详情失败，已达到最大重试次数")
                    raise
        # for 循环正常结束(未 return)时显式抛出,避免隐式返回 None
        raise RuntimeError("查询音色详情失败: 重试耗尽")

    def create_voice(self, target_model: str, prefix: str, url: str,
                     language_hints: Optional[List[str]] = None,
                     max_prompt_audio_length: Optional[float] = None,
                     enable_preprocess: Optional[bool] = None) -> str:
        """
        创建音色（声音复刻）

        注意：target_model 必须与后续调用语音合成接口时使用的模型一致，否则合成会失败。

        :param target_model: 驱动音色的语音合成模型（如 "cosyvoice-v3-plus"）
        :param prefix: 音色名称前缀，仅允许数字和英文字母，不超过10个字符
        :param url: 用于复刻音色的音频文件URL（公网可访问）
        :param language_hints: 样本音频语种提示列表
        :param max_prompt_audio_length: 参考音频最大时长（秒），范围 [3.0, 30.0]
        :param enable_preprocess: 是否开启音频预处理（降噪、音频增强、音量规整）
        :return: 音色ID（voice_id）
        """
        # prefix 格式校验
        if not re.match(r'^[a-zA-Z0-9]{1,10}$', prefix):
            raise ValueError("prefix 仅允许数字和英文字母，不超过10个字符")

        # 模型兼容性校验
        if language_hints is not None:
            if target_model not in self.MODEL_LANGUAGE_HINTS:
                raise ValueError(f"模型 {target_model} 不支持 language_hints 参数")
            supported_langs = self.MODEL_LANGUAGE_HINTS[target_model]
            for lang in language_hints:
                if lang not in supported_langs:
                    raise ValueError(f"模型 {target_model} 不支持语种 '{lang}'，支持的语种: {supported_langs}")

        if max_prompt_audio_length is not None and target_model not in self.V35_MODELS:
            raise ValueError(f"模型 {target_model} 不支持 max_prompt_audio_length 参数，支持的模型: {self.V35_MODELS}")

        if enable_preprocess is not None and target_model not in self.V35_MODELS:
            raise ValueError(f"模型 {target_model} 不支持 enable_preprocess 参数，支持的模型: {self.V35_MODELS}")

        for attempt in range(self.MAX_RETRIES):
            try:
                with _dashscope_lock:
                    dashscope.api_key = self.api_key
                    voice_id = self.service.create_voice(
                        target_model=target_model,
                        prefix=prefix,
                        url=url,
                        language_hints=language_hints,
                        max_prompt_audio_length=max_prompt_audio_length,
                        enable_preprocess=enable_preprocess
                    )
                logging.info("阿里云音色创建成功，voice_id: %s", voice_id)
                return voice_id
            except RETRYABLE_NETWORK_EXCEPTIONS as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("创建音色失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("创建音色失败，已达到最大重试次数")
                    raise
        # for 循环正常结束(未 return)时显式抛出,避免隐式返回 None
        raise RuntimeError("创建音色失败: 重试耗尽")

    def update_voice(self, voice_id: str, url: str,
                    language_hints: Optional[List[str]] = None,
                    max_prompt_audio_length: Optional[float] = None,
                    enable_preprocess: Optional[bool] = None) -> bool:
        """
        更新音色

        :param voice_id: 要更新的音色ID
        :param url: 新的音频文件URL
        :param language_hints: 样本音频语种提示
        :param max_prompt_audio_length: 参考音频最大时长
        :param enable_preprocess: 是否开启音频预处理
        :return: 是否成功
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                with _dashscope_lock:
                    dashscope.api_key = self.api_key
                    self.service.update_voice(
                        voice_id=voice_id,
                        url=url,
                        language_hints=language_hints,
                        max_prompt_audio_length=max_prompt_audio_length,
                        enable_preprocess=enable_preprocess
                    )
                logging.info("阿里云音色更新成功，voice_id: %s", voice_id)
                return True
            except RETRYABLE_NETWORK_EXCEPTIONS as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("更新音色失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("更新音色失败，已达到最大重试次数")
                    raise
        # for 循环正常结束(未 return)时显式抛出,避免隐式返回 None
        raise RuntimeError("更新音色失败: 重试耗尽")

    def delete_voice(self, voice_id: str) -> bool:
        """
        删除音色

        :param voice_id: 要删除的音色ID
        :return: 是否成功
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                with _dashscope_lock:
                    dashscope.api_key = self.api_key
                    self.service.delete_voice(voice_id=voice_id)
                logging.info("阿里云音色删除成功，voice_id: %s", voice_id)
                return True
            except RETRYABLE_NETWORK_EXCEPTIONS as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("删除音色失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("删除音色失败，已达到最大重试次数")
                    raise
        # for 循环正常结束(未 return)时显式抛出,避免隐式返回 None
        raise RuntimeError("删除音色失败: 重试耗尽")

    def list_all_voices(self, max_pages: int = 1000) -> list:
        """
        获取所有音色（自动翻页）

        :param max_pages: 最大翻页数,防止异常情况下无限翻页(默认 1000)
        :return: 所有音色列表
        """
        all_voices = []
        page_index = 0
        page_size = 100

        while page_index < max_pages:
            result = self.list_voices(prefix=None, page_index=page_index, page_size=page_size)
            voices = result.get("voices", [])

            if not voices:
                break

            all_voices.extend(voices)

            page_count = result.get("page_count", 0)
            if page_count < page_size:
                break

            page_index += 1

        if page_index >= max_pages:
            logging.warning("获取所有音色达到最大翻页数 %d,可能未获取完整", max_pages)
        logging.info("获取所有音色完成，共计: %d 个", len(all_voices))
        return all_voices

    def get_last_request_id(self) -> str:
        """获取最近一次 SDK 调用的请求 ID"""
        return self.service.get_last_request_id()
