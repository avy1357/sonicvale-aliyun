import logging

from app.core.aliyun_voice_manager_client import AliyunVoiceManagerClient


class AliyunVoiceCloneClient(AliyunVoiceManagerClient):
    """
    阿里云声音复刻客户端
    继承 AliyunVoiceManagerClient，功能完全一致，保留此类以兼容已有引用。

    用途说明:
    - 历史代码中可能存在对 AliyunVoiceCloneClient 的直接引用,为保持向后兼容而保留
    - 新代码应直接使用 AliyunVoiceManagerClient
    - 本类不添加额外逻辑,仅为兼容性存在
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)
        logging.info("阿里云声音复刻客户端初始化成功（继承自 AliyunVoiceManagerClient）")
