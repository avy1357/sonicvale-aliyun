# ws_manager.py
import logging
from fastapi import WebSocket
from typing import List

class WSManager:
    def __init__(self):
        self.conns: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        if ws not in self.conns:
            self.conns.append(ws)

    def disconnect(self, ws: WebSocket):
        try:
            self.conns.remove(ws)
        except ValueError:
            pass  # 已被其他任务移除,无需重复操作

    async def broadcast(self, data: dict):
        # 遍历快照,避免 broadcast 在 await 期间被 connect/disconnect 修改原列表
        dead = []
        for ws in list(self.conns):
            try:
                await ws.send_json(data)
            except Exception as e:
                logging.debug("WebSocket 发送失败,准备清理: %s", e)
                dead.append(ws)
        for d in dead:
            self.disconnect(d)

manager = WSManager()
