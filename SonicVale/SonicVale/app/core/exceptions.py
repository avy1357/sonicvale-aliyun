"""统一异常体系"""

import requests


class SVCError(Exception):
    """SVC 业务异常基类"""


class TTSError(SVCError):
    """TTS 相关异常"""


class TTSConnectionError(TTSError):
    """TTS 连接异常"""


class TTSRequestError(TTSError):
    """TTS 请求异常"""


class LLMError(SVCError):
    """LLM 相关异常"""


class ASRError(SVCError):
    """ASR 相关异常"""


class DecryptError(SVCError):
    """解密失败异常"""


class VolcanoAPIError(SVCError):
    """火山引擎 API 调用异常"""


# 可重试的网络异常元组
try:
    import dashscope.exceptions
    _DASHSCOPE_EXC = (dashscope.exceptions.DashScopeAPIError,)
except ImportError:
    _DASHSCOPE_EXC = ()


RETRYABLE_NETWORK_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.RequestException,
    OSError,
    TimeoutError,
    *_DASHSCOPE_EXC,
)
