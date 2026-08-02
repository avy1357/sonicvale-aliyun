import logging
import struct
import json
import uuid
import websocket
import time
from typing import Optional
from io import BytesIO


class VolcanoTTSClient:
    """
    火山引擎豆包语音 TTS 客户端
    使用 WebSocket 双向流式 API V3

    官方文档：https://www.volcengine.com/docs/6561/1329505

    鉴权方式（二选一）：
    - 新版控制台（推荐）：仅需 api_key（X-Api-Key）
    - 旧版控制台：需 app_key（X-Api-App-Id）+ access_key（X-Api-Access-Key）

    配置说明：
    - api_key: 火山引擎控制台 API Key（新版鉴权，推荐）
    - app_key: 火山引擎 APP ID（旧版鉴权）
    - access_key: 火山引擎 Access Token（旧版鉴权）
    - resource_id: 资源 ID，如 seed-tts-2.0 / seed-tts-1.0 / seed-icl-2.0
    - speaker: 音色，如 zh_female_shuangkuaisisi_moon_bigtts
    """

    DEFAULT_SPEAKER = "zh_female_shuangkuaisisi_moon_bigtts"
    DEFAULT_RESOURCE_ID = "seed-tts-2.0"
    DEFAULT_FORMAT = "mp3"
    DEFAULT_SAMPLE_RATE = 24000
    MAX_RETRIES = 3
    RETRY_DELAY = 1

    WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"

    EVENT_FULL_CLIENT_REQUEST = 100
    EVENT_FULL_SERVER_RESPONSE = 101
    EVENT_AUDIO_ONLY_RESPONSE = 111
    EVENT_START_CONNECTION = 1
    EVENT_CONNECTION_STARTED = 11
    EVENT_START_SESSION = 50
    EVENT_SESSION_STARTED = 51
    EVENT_SESSION_FINISHED = 151
    EVENT_FINISH_SESSION = 150
    EVENT_FINISH_CONNECTION = 3
    EVENT_CONNECTION_FINISHED = 13
    EVENT_ERROR = 1000

    MSG_TYPE_FULL_CLIENT_REQUEST = 0b0001
    MSG_TYPE_FULL_SERVER_RESPONSE = 0b1001
    MSG_TYPE_AUDIO_ONLY_RESPONSE = 0b1011
    MSG_TYPE_ERROR = 0b1111

    MSG_FLAGS_HAS_EVENT = 0b0100

    SERIALIZATION_RAW = 0b0000
    SERIALIZATION_JSON = 0b0001

    COMPRESSION_NONE = 0b0000
    COMPRESSION_GZIP = 0b0001

    def __init__(self, api_key: Optional[str] = None,
                 app_key: Optional[str] = None, access_key: Optional[str] = None,
                 resource_id: Optional[str] = None, speaker: Optional[str] = None,
                 model: Optional[str] = None):
        self.api_key = api_key
        self.app_key = app_key
        self.access_key = access_key
        self.resource_id = resource_id or self.DEFAULT_RESOURCE_ID
        self.speaker = speaker or self.DEFAULT_SPEAKER
        self.model = model

        if not api_key and not (app_key and access_key):
            raise ValueError("火山引擎 TTS 鉴权配置无效：请提供 api_key（新版鉴权）或 app_key + access_key（旧版鉴权）")

        self._ws = None
        self._audio_chunks = []
        self._session_started = False
        self._session_finished = False
        self._error = None
        self._session_id = None

        self._pending_text = None
        self._pending_speaker = None
        self._pending_audio_format = None
        self._pending_sample_rate = None
        self._pending_speech_rate = None
        self._pending_loudness_rate = None
        self._pending_emotion = None
        self._pending_emotion_scale = None
        self._pending_enable_timestamp = False
        self._pending_enable_subtitle = False
        self._pending_model = None
        self._pending_bit_rate = None
        self._pending_silence_duration = None
        self._pending_enable_language_detector = False
        self._pending_disable_markdown_filter = False

        auth_mode = "新版(X-Api-Key)" if api_key else "旧版(App-Id+Access-Key)"
        logging.info("火山引擎 TTS 客户端初始化成功，鉴权方式: %s, 音色: %s, resource: %s",
                     auth_mode, self.speaker, self.resource_id)

    def synthesize(self, text: str, speaker: Optional[str] = None,
                   audio_format: str = "mp3", sample_rate: int = 24000,
                   speech_rate: int = 0, loudness_rate: int = 0,
                   emotion: Optional[str] = None, emotion_scale: int = 4,
                   enable_timestamp: bool = False, enable_subtitle: bool = False,
                   model: Optional[str] = None,
                   bit_rate: Optional[int] = None,
                   silence_duration: Optional[int] = None,
                   enable_language_detector: bool = False,
                   disable_markdown_filter: bool = False) -> bytes:
        """
        调用火山引擎 TTS WebSocket API 合成语音

        :param text: 要合成的文本
        :param speaker: 音色（可选，覆盖构造函数中的设置）
        :param audio_format: 音频格式，支持 mp3/ogg_opus/pcm/wav
        :param sample_rate: 采样率，默认 24000
        :param speech_rate: 语速，范围 [-50, 100]，0 为默认
        :param loudness_rate: 音量，范围 [-50, 100]，0 为默认
        :param emotion: 情感（如 "happy", "sad", "angry", "neutral"）
        :param emotion_scale: 情感强度，范围 1~5，默认 4
        :param enable_timestamp: 是否启用时间戳（仅TTS1.0和ICL1.0生效）
        :param enable_subtitle: 是否启用字幕（仅TTS2.0和ICL2.0生效）
        :param model: 模型版本（seed-tts-2.0-standard 或 seed-tts-2.0-expressive）
        :param bit_rate: 音频比特率，如 16000、32000
        :param silence_duration: 句尾静音时长，范围 0~30000ms
        :param enable_language_detector: 是否开启自动语种识别
        :param disable_markdown_filter: 是否关闭 markdown 解析过滤
        :return: 音频二进制数据
        """
        target_speaker = speaker or self.speaker
        target_model = model or self.model

        for attempt in range(self.MAX_RETRIES):
            try:
                self._audio_chunks = []
                self._session_started = False
                self._session_finished = False
                self._error = None
                self._session_id = str(uuid.uuid4())

                return self._do_synthesize(text, target_speaker, audio_format, sample_rate,
                                          speech_rate, loudness_rate, emotion, emotion_scale,
                                          enable_timestamp, enable_subtitle, target_model,
                                          bit_rate, silence_duration,
                                          enable_language_detector, disable_markdown_filter)
            except Exception as e:
                self._close_ws()
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("火山引擎 TTS 合成失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("火山引擎 TTS 合成失败，已达到最大重试次数")
                    raise Exception(f"火山引擎 TTS 合成失败: {str(e)}") from e

        raise Exception("火山引擎 TTS 合成失败")

    def _do_synthesize(self, text: str, speaker: str, audio_format: str, sample_rate: int,
                       speech_rate: int, loudness_rate: int,
                       emotion: Optional[str], emotion_scale: int,
                       enable_timestamp: bool, enable_subtitle: bool,
                       model: Optional[str],
                       bit_rate: Optional[int], silence_duration: Optional[int],
                       enable_language_detector: bool, disable_markdown_filter: bool) -> bytes:
        self._pending_text = text
        self._pending_speaker = speaker
        self._pending_audio_format = audio_format
        self._pending_sample_rate = sample_rate
        self._pending_speech_rate = speech_rate
        self._pending_loudness_rate = loudness_rate
        self._pending_emotion = emotion
        self._pending_emotion_scale = emotion_scale
        self._pending_enable_timestamp = enable_timestamp
        self._pending_enable_subtitle = enable_subtitle
        self._pending_model = model
        self._pending_bit_rate = bit_rate
        self._pending_silence_duration = silence_duration
        self._pending_enable_language_detector = enable_language_detector
        self._pending_disable_markdown_filter = disable_markdown_filter

        self._ws = websocket.WebSocketApp(
            self.WS_URL,
            header=self._build_ws_headers(),
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )

        self._ws.run_forever(ping_timeout=30, ping_interval=10)

        if self._error:
            raise Exception(f"火山引擎 TTS WebSocket 错误: {self._error}")

        if not self._audio_chunks:
            raise Exception("火山引擎 TTS 未返回音频数据")

        audio_bytes = b"".join(self._audio_chunks)

        if len(audio_bytes) < 100:
            raise Exception(f"火山引擎 TTS 返回的音频数据无效，大小: {len(audio_bytes)} 字节")

        logging.info("火山引擎 TTS 合成成功，音频大小: %d 字节", len(audio_bytes))
        return audio_bytes

    def _build_ws_headers(self) -> list:
        headers = []

        if self.api_key:
            headers.append(f"X-Api-Key: {self.api_key}")
        else:
            headers.append(f"X-Api-App-Id: {self.app_key}")
            headers.append(f"X-Api-Access-Key: {self.access_key}")

        headers.append(f"X-Api-Resource-Id: {self.resource_id}")
        headers.append(f"X-Api-Connect-Id: {self._session_id}")

        return headers

    def _on_open(self, ws):
        logging.info("火山引擎 TTS WebSocket 连接已建立")
        frame = self._build_event_frame(self.EVENT_START_CONNECTION, self._session_id)
        ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)

    def _on_message(self, ws, message):
        if isinstance(message, bytes):
            self._handle_binary_frame(message)

    def _on_error(self, ws, error):
        logging.error("火山引擎 TTS WebSocket 错误: %s", error)
        self._error = str(error)

    def _on_close(self, ws, close_status_code, close_msg):
        logging.info("火山引擎 TTS WebSocket 连接已关闭")

    def _handle_binary_frame(self, data: bytes):
        if len(data) < 4:
            return

        protocol_version = (data[0] >> 4) & 0x0F
        header_size = (data[0] & 0x0F) * 4
        message_type = (data[1] >> 4) & 0x0F
        msg_flags = data[1] & 0x0F
        serialization = (data[2] >> 4) & 0x0F
        compression = data[2] & 0x0F

        offset = 4
        event = None
        if msg_flags & self.MSG_FLAGS_HAS_EVENT:
            if len(data) >= offset + 4:
                event = struct.unpack(">I", data[offset:offset + 4])[0]
                offset += 4

        if message_type == self.MSG_TYPE_FULL_SERVER_RESPONSE:
            if serialization == self.SERIALIZATION_JSON and len(data) > offset:
                payload = data[offset:]
                try:
                    payload_json = json.loads(payload.decode("utf-8"))
                    self._handle_server_response(payload_json, event)
                except Exception as e:
                    logging.warning("解析 Full-server response 失败: %s", e)

        elif message_type == self.MSG_TYPE_AUDIO_ONLY_RESPONSE:
            if len(data) > offset:
                audio_data = data[offset:]
                self._audio_chunks.append(audio_data)

        elif message_type == self.MSG_TYPE_ERROR:
            error_msg = "未知错误"
            if len(data) >= offset + 4:
                error_code = struct.unpack(">I", data[offset:offset + 4])[0]
                error_msg = f"错误码: {error_code}"
            self._error = error_msg
            logging.error("火山引擎 TTS 返回错误帧: %s", error_msg)

    def _handle_server_response(self, payload_json: dict, event: Optional[int]):
        if event == self.EVENT_SESSION_STARTED:
            self._session_started = True
            logging.info("火山引擎 TTS Session 已开始，发送 TaskRequest")
            self._send_task_request(
                self._pending_text,
                self._pending_speaker,
                self._pending_audio_format,
                self._pending_sample_rate,
                self._pending_speech_rate,
                self._pending_loudness_rate,
                self._pending_emotion,
                self._pending_emotion_scale,
                self._pending_enable_timestamp,
                self._pending_enable_subtitle,
                self._pending_model,
                self._pending_bit_rate,
                self._pending_silence_duration,
                self._pending_enable_language_detector,
                self._pending_disable_markdown_filter,
            )
        elif event == self.EVENT_SESSION_FINISHED:
            self._session_finished = True
            logging.info("火山引擎 TTS Session 已结束")
            self._close_ws()
        elif event == self.EVENT_CONNECTION_STARTED:
            self._send_start_session()

    def _send_start_session(self):
        frame = self._build_event_frame(self.EVENT_START_SESSION, self._session_id)
        self._ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)

    def _build_event_frame(self, event: int, session_id: Optional[str] = None) -> bytes:
        header_size = 4
        msg_flags = self.MSG_FLAGS_HAS_EVENT
        serialization = self.SERIALIZATION_JSON
        compression = self.COMPRESSION_NONE

        msg_type = self.MSG_TYPE_FULL_CLIENT_REQUEST
        if event in (self.EVENT_START_CONNECTION, self.EVENT_FINISH_CONNECTION):
            msg_type = self.MSG_TYPE_FULL_CLIENT_REQUEST

        header = bytes([
            (1 << 4) | (header_size // 4),
            (msg_type << 4) | msg_flags,
            (serialization << 4) | compression,
            0,
        ])

        event_bytes = struct.pack(">I", event)

        frame = header + event_bytes

        if session_id:
            session_id_bytes = session_id.encode("utf-8")
            session_id_size = struct.pack(">I", len(session_id_bytes))
            frame += session_id_size + session_id_bytes

        return frame

    def _build_task_request_frame(self, text: str, speaker: str, audio_format: str,
                                   sample_rate: int, speech_rate: int, loudness_rate: int,
                                   emotion: Optional[str], emotion_scale: int,
                                   enable_timestamp: bool, enable_subtitle: bool,
                                   model: Optional[str],
                                   bit_rate: Optional[int],
                                   silence_duration: Optional[int],
                                   enable_language_detector: bool,
                                   disable_markdown_filter: bool) -> bytes:
        payload = {
            "user": {
                "uid": str(uuid.uuid4()),
            },
            "event": 100,
            "namespace": "BidirectionalTTS",
            "req_params": {
                "text": text,
                "speaker": speaker,
                "audio_params": {
                    "format": audio_format,
                    "sample_rate": sample_rate,
                    "speech_rate": speech_rate,
                    "loudness_rate": loudness_rate,
                },
            },
        }

        if model:
            payload["req_params"]["model"] = model

        if bit_rate is not None:
            payload["req_params"]["audio_params"]["bit_rate"] = bit_rate

        if emotion:
            payload["req_params"]["audio_params"]["emotion"] = emotion
            payload["req_params"]["audio_params"]["emotion_scale"] = emotion_scale

        if enable_timestamp:
            payload["req_params"]["audio_params"]["enable_timestamp"] = True

        if enable_subtitle:
            payload["req_params"]["audio_params"]["enable_subtitle"] = True

        additions = {}
        if silence_duration is not None and silence_duration > 0:
            additions["silence_duration"] = silence_duration
        if enable_language_detector:
            additions["enable_language_detector"] = True
        if disable_markdown_filter:
            additions["disable_markdown_filter"] = True

        if additions:
            payload["req_params"]["additions"] = json.dumps(additions, ensure_ascii=False)

        header_size = 4
        msg_flags = self.MSG_FLAGS_HAS_EVENT
        serialization = self.SERIALIZATION_JSON
        compression = self.COMPRESSION_NONE

        msg_type = self.MSG_TYPE_FULL_CLIENT_REQUEST

        header = bytes([
            (1 << 4) | (header_size // 4),
            (msg_type << 4) | msg_flags,
            (serialization << 4) | compression,
            0,
        ])

        event = 100
        event_bytes = struct.pack(">I", event)

        session_id = self._session_id or str(uuid.uuid4())
        session_id_bytes = session_id.encode("utf-8")
        session_id_size = struct.pack(">I", len(session_id_bytes))

        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        frame = header + event_bytes + session_id_size + session_id_bytes + payload_bytes

        return frame

    def _send_task_request(self, text: str, speaker: str, audio_format: str,
                            sample_rate: int, speech_rate: int, loudness_rate: int,
                            emotion: Optional[str], emotion_scale: int,
                            enable_timestamp: bool, enable_subtitle: bool,
                            model: Optional[str],
                            bit_rate: Optional[int],
                            silence_duration: Optional[int],
                            enable_language_detector: bool,
                            disable_markdown_filter: bool):
        frame = self._build_task_request_frame(
            text, speaker, audio_format, sample_rate,
            speech_rate, loudness_rate, emotion, emotion_scale,
            enable_timestamp, enable_subtitle, model,
            bit_rate, silence_duration,
            enable_language_detector, disable_markdown_filter
        )
        self._ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)

        finish_frame = self._build_event_frame(self.EVENT_FINISH_SESSION, self._session_id)
        self._ws.send(finish_frame, opcode=websocket.ABNF.OPCODE_BINARY)

    def _close_ws(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def test_connection(self) -> bool:
        try:
            self.synthesize("测试", self.speaker)
            return True
        except Exception as e:
            logging.error("火山引擎 TTS 连接测试失败: %s", str(e))
            return False
