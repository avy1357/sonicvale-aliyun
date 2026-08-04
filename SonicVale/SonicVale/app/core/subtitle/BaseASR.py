import json
import logging
import os
import zlib
import tempfile
import threading
from typing import Union

from .ASRData import ASRDataSeg, ASRData


class BaseASR:
    SUPPORTED_SOUND_FORMAT = ["flac", "m4a", "mp3", "wav"]
    # 缓存路径加入用户名区分,避免多用户共享同一缓存导致冲突
    _username = os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown'
    CACHE_FILE = os.path.join(tempfile.gettempdir(), "bk_asr", _username, "asr_cache.json")
    _lock = threading.Lock()

    # 模块级初始化缓存目录,避免在 __init__ 中重复创建
    _CACHE_DIR = os.path.dirname(CACHE_FILE)
    os.makedirs(_CACHE_DIR, exist_ok=True)

    def __init__(self, audio_path: Union[str, bytes], use_cache: bool = False):
        self.audio_path = audio_path
        self.file_binary = None

        self.crc32_hex = None
        self.use_cache = use_cache

        self._set_data()

        self.cache = self._load_cache()

    def _load_cache(self):
        if not self.use_cache:
            return {}
        # 缓存目录已在模块级创建,此处无需重复 makedirs
        with self._lock:
            if os.path.exists(self.CACHE_FILE):
                try:
                    with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                        cache = json.load(f)
                        if isinstance(cache, dict):
                            return cache
                except (json.JSONDecodeError, IOError):
                    return {}
            return {}

    def _save_cache(self):
        if not self.use_cache:
            return
        with self._lock:
            try:
                # 先检查现有缓存文件大小,超限则删除后再写入,避免缓存无限增长
                if os.path.exists(self.CACHE_FILE) and os.path.getsize(self.CACHE_FILE) > 10 * 1024 * 1024:
                    os.remove(self.CACHE_FILE)
                with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
                # 设置缓存文件权限为仅属主可读写(Windows 下 chmod 权限模型不同,跳过)
                if os.name != 'nt':
                    os.chmod(self.CACHE_FILE, 0o600)
            except IOError as e:
                logging.error("Failed to save cache: %s", e)

    def _set_data(self):
        if isinstance(self.audio_path, bytes):
            self.file_binary = self.audio_path
        else:
            ext = self.audio_path.split(".")[-1].lower()
            if ext not in self.SUPPORTED_SOUND_FORMAT:
                raise ValueError(f"不支持的音频格式: {ext}, 支持的格式: {self.SUPPORTED_SOUND_FORMAT}")
            if not os.path.exists(self.audio_path):
                raise FileNotFoundError(f"音频文件不存在: {self.audio_path}")
            with open(self.audio_path, "rb") as f:
                self.file_binary = f.read()
        crc32_value = zlib.crc32(self.file_binary) & 0xFFFFFFFF
        self.crc32_hex = format(crc32_value, '08x')

    def _get_key(self):
        return f"{self.__class__.__name__}-{self.crc32_hex}"

    def run(self):
        k = self._get_key()
        if k in self.cache and self.use_cache:
            resp_data = self.cache[k]
        else:
            resp_data = self._run()
            # Cache the result
            self.cache[k] = resp_data
            self._save_cache()
        segments = self._make_segments(resp_data)
        return ASRData(segments)

    def _make_segments(self, resp_data: dict) -> list[ASRDataSeg]:
        raise NotImplementedError("_make_segments method must be implemented in subclass")

    def _run(self) -> dict:
        """ Run the ASR service and return the response data. """
        raise NotImplementedError("_run method must be implemented in subclass")



