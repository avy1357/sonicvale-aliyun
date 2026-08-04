# ws_manager.py
import asyncio
import logging
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# 最大连接数上限,防止资源耗尽
MAX_CONNECTIONS = 100

class WSManager:
    def __init__(self):
        # 使用 set 存储连接,O(1) 添加/删除
        self._conns: set = set()
        # 使用 Lock 保护连接/断开操作,防止竞态条件
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        # 使用 Lock 保护:确保上限检查与添加连接是原子操作
        # 避免在 await ws.accept() 挂起点期间多个协程同时通过上限检查
        async with self._lock:
            if len(self._conns) >= MAX_CONNECTIONS:
                await ws.close(code=1013, reason="连接数已达上限")
                logging.warning("WebSocket 连接被拒绝:已达上限 %d", MAX_CONNECTIONS)
                return
        # 在锁外 accept,避免长时间持有锁
        await ws.accept()
        async with self._lock:
            # accept 后再次检查,防止在等待锁期间已达上限
            if len(self._conns) >= MAX_CONNECTIONS:
                await ws.close(code=1013, reason="连接数已达上限")
                logging.warning("WebSocket 连接被拒绝:accept 后再次检查已达上限")
                return
            self._conns.add(ws)

    def disconnect(self, ws: WebSocket):
        # discard 不会在元素不存在时抛异常,无需 try-except
        self._conns.discard(ws)

    async def broadcast(self, data: dict):
        # 遍历快照,避免 broadcast 在 await 期间被 connect/disconnect 修改原集合
        dead = []
        for ws in list(self._conns):
            try:
                await ws.send_json(data)
            except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError) as e:
                # 仅捕获 WebSocket 相关异常,其他异常向上抛出
                logging.debug("WebSocket 发送失败,准备清理: %s", e)
                dead.append(ws)
        for d in dead:
            self.disconnect(d)

    @property
    def conns(self):
        """兼容外部对 conns 属性的访问"""
        return list(self._conns)

manager = WSManager()
