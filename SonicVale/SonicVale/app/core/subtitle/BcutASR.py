import json
import logging
import os
import time
from typing import List, Optional, Union

import requests

from .ASRData import ASRData, ASRDataSeg
from .BaseASR import BaseASR


__version__ = "0.0.3"

# API URL 抽取到环境变量,便于测试与切换环境,保留默认值
API_BASE_URL = os.getenv("BCUT_API_BASE_URL", "https://member.bilibili.com/x/bcut/rubick-interface")

# 申请上传
API_REQ_UPLOAD = API_BASE_URL + "/resource/create"

# 提交上传
API_COMMIT_UPLOAD = API_BASE_URL + "/resource/create/complete"

# 创建任务
API_CREATE_TASK = API_BASE_URL + "/task"

# 查询结果
API_QUERY_RESULT = API_BASE_URL + "/task/result"


class BcutASR(BaseASR):
    """必剪 语音识别接口"""
    headers = {
        'User-Agent': 'Bilibili/1.0.0 (https://www.bilibili.com)',
        'Content-Type': 'application/json'
    }
    _max_poll_times = 500
    _poll_interval = 1

    def __init__(self, audio_path: Union[str, bytes], use_cache: bool = False):
        super().__init__(audio_path, use_cache=use_cache)
        self.session = requests.Session()
        self.task_id: Optional[str] = None
        self.__etags: List[str] = []

        self.__in_boss_key: Optional[str] = None
        self.__resource_id: Optional[str] = None
        self.__upload_id: Optional[str] = None
        self.__upload_urls: List[str] = []
        self.__per_size: Optional[int] = None
        self.__clips: Optional[int] = None

        self.__download_url: Optional[str] = None

    def close(self):
        """关闭 requests session,释放连接池资源"""
        try:
            self.session.close()
        except Exception:
            pass

    def upload(self) -> None:
        """申请上传"""
        if not self.file_binary:
            raise ValueError("none set data")
        # 从 audio_path 提取实际文件名与扩展名,避免硬编码 "audio.mp3"
        if isinstance(self.audio_path, bytes):
            # bytes 输入无文件名,使用默认值
            audio_name = "audio.mp3"
            file_type = "mp3"
        else:
            audio_name = os.path.basename(self.audio_path) or "audio.mp3"
            file_type = self.audio_path.split(".")[-1].lower() if "." in self.audio_path else "mp3"
        payload = json.dumps({
            "type": 2,
            "name": audio_name,
            "size": len(self.file_binary),
            "ResourceFileType": file_type,
            "model_id": "8",
        })

        resp = self.session.post(
            API_REQ_UPLOAD,
            data=payload,
            headers=self.headers,
            timeout=30
        )
        resp.raise_for_status()
        resp = resp.json()
        resp_data = resp.get("data")
        if not resp_data or not isinstance(resp_data, dict):
            raise RuntimeError(f"BCut ASR 申请上传返回异常: {resp}")

        self.__in_boss_key = resp_data.get("in_boss_key")
        self.__resource_id = resp_data.get("resource_id")
        self.__upload_id = resp_data.get("upload_id")
        self.__upload_urls = resp_data.get("upload_urls", [])
        self.__per_size = resp_data.get("per_size")
        self.__clips = len(self.__upload_urls)

        if not self.__in_boss_key or not self.__upload_urls:
            raise RuntimeError("BCut ASR 申请上传返回数据不完整")

        logging.info(
            "申请上传成功, 总计大小%dKB, %d分片, 分片大小%dKB: %s",
            resp_data.get('size', 0) // 1024, self.__clips, (self.__per_size or 0) // 1024, self.__in_boss_key
        )
        self.__upload_part()
        self.__commit_upload()

    def __upload_part(self) -> None:
        """上传音频数据"""
        for clip in range(self.__clips):
            start_range = clip * self.__per_size
            end_range = (clip + 1) * self.__per_size
            logging.info("开始上传分片%d: %d-%d", clip, start_range, end_range)
            # 单片上传失败重试 3 次,避免偶发网络抖动导致整体上传失败
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    resp = self.session.put(
                        self.__upload_urls[clip],
                        data=self.file_binary[start_range:end_range],
                        headers=self.headers,
                        timeout=120
                    )
                    resp.raise_for_status()
                    etag = resp.headers.get("Etag")
                    if etag is None:
                        raise ValueError(f"分片{clip}上传响应缺少 Etag 头")
                    self.__etags.append(etag)
                    logging.info("分片%d上传成功: %s", clip, etag)
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                        requests.exceptions.HTTPError, OSError) as e:
                    if attempt < max_retries - 1:
                        logging.warning("分片%d上传失败,第 %d 次重试: %s", clip, attempt + 1, e)
                        time.sleep(1)
                    else:
                        raise

    def __commit_upload(self) -> None:
        """提交上传数据"""
        data = json.dumps({
            "InBossKey": self.__in_boss_key,
            "ResourceId": self.__resource_id,
            "Etags": ",".join(self.__etags),
            "UploadId": self.__upload_id,
            "model_id": "8",
        })
        resp = self.session.post(
            API_COMMIT_UPLOAD,
            data=data,
            headers=self.headers,
            timeout=30
        )
        resp.raise_for_status()
        resp = resp.json()
        self.__download_url = resp["data"]["download_url"]
        logging.info("提交成功")

    def create_task(self) -> str:
        """开始创建转换任务"""
        resp = self.session.post(
            API_CREATE_TASK, json={"resource": self.__download_url, "model_id": "8"}, headers=self.headers,
            timeout=30
        )
        resp.raise_for_status()
        resp = resp.json()
        self.task_id = resp["data"]["task_id"]
        logging.info("任务已创建: %s", self.task_id)
        return self.task_id

    def result(self, task_id: Optional[str] = None):
        """查询转换结果"""
        resp = self.session.get(API_QUERY_RESULT, params={"model_id": 7, "task_id": task_id or self.task_id}, headers=self.headers, timeout=30)
        resp.raise_for_status()
        resp = resp.json()
        return resp["data"]

    def _run(self):
        """执行 BCut ASR 任务。

        注意:本方法含 time.sleep 轮询等待,为同步阻塞调用。
        异步路由中应通过 run_in_executor 包装,避免阻塞事件循环。
        """
        self.upload()
        self.create_task()
        # 轮询检查任务状态
        task_resp = None
        for _ in range(self._max_poll_times):
            task_resp = self.result()
            state = task_resp.get("state")
            if state == 4:  # 成功
                break
            elif state in (3, 5):  # 失败状态
                raise Exception(f"BCut ASR 任务失败, 状态码: {state}")
            time.sleep(self._poll_interval)
        else:
            raise TimeoutError("BCut ASR 任务超时, 未在预期时间内完成")

        logging.info("转换成功")
        result = task_resp.get("result")
        if not result:
            raise ValueError("BCut ASR 返回结果为空")
        return json.loads(result)

    def _make_segments(self, resp_data: dict) -> list[ASRDataSeg]:
        return [ASRDataSeg(u['transcript'], u['start_time'], u['end_time']) for u in resp_data['utterances']]
