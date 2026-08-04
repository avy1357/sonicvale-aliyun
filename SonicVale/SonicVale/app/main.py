# app/main.py
import asyncio
import hmac
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware

from app.core.response import Res

# 可选 API Key 认证：仅当环境变量 SVC_API_KEY 设置时启用
SVC_API_KEY = os.getenv("SVC_API_KEY")
# 若 SVC_REQUIRE_AUTH=true,则未设置 SVC_API_KEY 时拒绝启动
SVC_REQUIRE_AUTH = os.getenv("SVC_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
# 允许的本地回环地址白名单(用于未启用 API Key 时校验请求来源)
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _warn_no_auth():
    """未启用 API Key 认证时打印显著警告"""
    logging.warning("=" * 72)
    logging.warning("⚠️  安全警告:未设置 SVC_API_KEY 环境变量,所有接口无认证")
    logging.warning("⚠️  此模式仅适用于本地单用户桌面场景")
    logging.warning("⚠️  如部署到服务器或多人环境,务必设置 SVC_API_KEY")
    logging.warning("⚠️  强制认证可设置 SVC_REQUIRE_AUTH=true(未设置 key 时拒绝启动)")
    logging.warning("=" * 72)


if not SVC_API_KEY:
    if SVC_REQUIRE_AUTH:
        raise RuntimeError("SVC_REQUIRE_AUTH=true 但未设置 SVC_API_KEY,拒绝启动")
    _warn_no_auth()

from app.core.config import getConfigPath
from app.core.prompts import get_prompt_str
from app.core.tts_runtime import tts_worker
from app.core.ws_manager import manager
from app.db.database import Base, engine, SessionLocal, get_db
from app.entity.emotion_entity import EmotionEntity
from app.entity.strength_entity import StrengthEntity
from app.models.po import *
from app.repositories.llm_provider_repository import LLMProviderRepository
from app.repositories.tts_provider_repository import TTSProviderRepository
from app.routers import project_router, chapter_router, role_router, voice_router, llm_provider_router, \
    tts_provider_router, line_router, emotion_router, strength_router, multi_emotion_voice_router, prompt_router
from app.routers.voice_clone_router import router as voice_clone_router
from app.routers.volcano_voice_manager_router import router as volcano_voice_manager_router
from app.routers.aliyun_voice_clone_router import router as aliyun_voice_clone_router
from app.routers.aliyun_voice_manager_router import router as aliyun_voice_manager_router
from app.routers.chapter_router import get_strength_service, get_prompt_service, get_project_service
from app.routers.emotion_router import get_emotion_service
from app.routers.llm_provider_router import get_llm_service
from app.services.llm_provider_service import LLMProviderService

from app.services.tts_provider_service import TTSProviderService

import sys

root_path = os.getcwd()
sys.path.append(root_path)

# =========================
# 日志配置（同时输出到控制台和文件）
# =========================
# 使用当前项目目录下的 logs 文件夹
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 控制台输出
        logging.FileHandler(log_file_path, encoding='utf-8')  # 文件输出
    ]
)
logging.info(f"日志文件路径: {log_file_path}")

# =========================
# FastAPI 实例
# =========================
app = FastAPI(
    title="轻语云配 - AI多角色小说配音",
    description="桌面端小说多角色配音系统，支持 TTS、GPT 提取角色、台词管理及字幕生成",
    version="1.0.0",
)
# 跨域
# 允许的前端地址:支持通过环境变量 SVC_ALLOWED_ORIGINS 配置(逗号分隔)
# 未配置时使用默认本地开发地址
_cors_origins_env = os.getenv("SVC_ALLOWED_ORIGINS", "")
if _cors_origins_env:
    origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
else:
    origins = [
        "http://localhost:5173",  # Vue 开发服务器
        "http://127.0.0.1:5173",  # 有些浏览器可能会用这个
    ]

# CORS 安全校验:allow_credentials=True 与通配符 "*" origin 组合存在安全风险
# 若同时配置了两者,自动降级为不带 credentials,避免凭据泄露
_allow_credentials = True
if "*" in origins:
    logging.warning(
        "⚠️  CORS 安全警告:SVC_ALLOWED_ORIGINS 包含通配符 \"*\" 且 allow_credentials=True,"
        "存在安全风险。已自动降级为 allow_credentials=False。"
    )
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # 允许的源
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],   # 限定允许的方法
    allow_headers=["Authorization", "Content-Type", "Accept"],   # 限定允许的请求头
)


# =========================
# 可选 API Key 认证中间件
# =========================
class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    仅当环境变量 SVC_API_KEY 设置时启用认证。
    - HTTP 请求需携带 Authorization: Bearer <SVC_API_KEY>
    - WebSocket 请求需在 query 中携带 api_key=<SVC_API_KEY>
    - 放行 OPTIONS 预检请求与健康检查接口 GET /
    未设置环境变量时:
    - 放行本机回环来源(127.0.0.1/localhost/::1)
    - 拒绝非本机来源,防止同机恶意网页跨域访问或远程未授权访问
    """

    async def dispatch(self, request: Request, call_next):
        # 放行 CORS 预检
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 放行健康检查
        if path == "/" and request.method == "GET":
            return await call_next(request)

        if not SVC_API_KEY:
            # 未启用 API Key:校验请求来源必须是本机回环
            # 优先看 Host 头(去掉端口),再看 Origin
            host_header = (request.headers.get("Host") or "").split(":")[0].lower()
            origin = request.headers.get("Origin") or ""
            if origin:
                # Origin 形如 http://127.0.0.1:5173,提取 host
                try:
                    host_header = urlparse(origin).hostname.lower() or host_header
                except Exception:
                    pass
            client = request.client.host if request.client else ""
            # 客户端 IP 必须是回环,且 Host/Origin 也必须是回环
            is_local_client = client in _LOCAL_HOSTS or client == "::ffff:127.0.0.1"
            is_local_host = not host_header or host_header in _LOCAL_HOSTS
            if not (is_local_client and is_local_host):
                logging.warning(
                    "拒绝非本机访问(未启用认证): client=%s host=%s origin=%s path=%s",
                    client, host_header, origin, path
                )
                return JSONResponse(
                    status_code=403,
                    content=Res(code=403, message="未启用认证,仅允许本机访问。如需远程访问请设置 SVC_API_KEY", data=None).dict(),
                )
            return await call_next(request)

        # 已启用 API Key:校验 token
        # WebSocket:认证交给 ws_endpoint 内部处理
        # 中间件不拦截 WebSocket 升级请求,避免 JSONResponse 不适用于 WS 协议
        if path == "/ws":
            return await call_next(request)

        # HTTP：校验 Authorization: Bearer <key>
        auth = request.headers.get("Authorization", "")
        prefix = "Bearer "
        token = auth[len(prefix):] if auth.startswith(prefix) else ""
        if not token or not isinstance(SVC_API_KEY, str) or not hmac.compare_digest(token, SVC_API_KEY):
            return JSONResponse(status_code=401, content=Res(code=401, message="未授权：API Key 无效或缺失", data=None).dict())

        return await call_next(request)


app.add_middleware(APIKeyMiddleware)


# =========================
# 全局异常处理器（统一返回 Res 格式）
# =========================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """处理路由中显式 raise 的 HTTPException，统一为 Res 格式"""
    logging.warning("HTTPException %s %s -> %s: %s", request.method, request.url.path, exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=Res(code=exc.status_code, message=str(exc.detail), data=None).dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验失败，统一为 Res 格式"""
    logging.warning("参数校验失败 %s %s: %s", request.method, request.url.path, exc.errors())
    # 仅返回简化错误信息（字段名 + 提示），避免泄露 type/url 等内部结构
    simplified_errors = [
        {"field": ".".join(str(x) for x in e.get("loc", [])), "msg": e.get("msg", "")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=Res(code=422, message="请求参数校验失败", data=simplified_errors).dict(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底处理未捕获异常，避免向前端泄露堆栈信息"""
    logging.exception("未处理异常 %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content=Res(code=500, message="服务器内部错误，请查看后端日志", data=None).dict(),
    )



# =========================
# 数据库初始化（创建表）
# =========================

# 启动时创建表
# @app.on_event("startup")
# def startup():
#     Base.metadata.create_all(bind=engine)

WORKERS = int(os.getenv("SVC_WORKERS", "2"))
QUEUE_CAPACITY = int(os.getenv("SVC_QUEUE_CAPACITY", "100"))

from sqlalchemy import text


def _add_column(conn, table: str, column: str, col_type: str, default=None, backfill=None):
    """通用列迁移辅助：检查列是否存在，不存在则添加，可选回填已有行。

    注意:此处 table/column/col_type/default 均为代码内硬编码常量(非用户输入),
    backfill 通过参数化绑定传递,不存在 SQL 注入风险。
    """
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result.fetchall()]
    if column in columns:
        return False
    default_clause = f" DEFAULT {default}" if default is not None else ""
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"))
    if backfill is not None:
        conn.execute(text(f"UPDATE {table} SET {column} = :val WHERE {column} IS NULL"), {"val": backfill})
    logging.info("已添加 %s.%s 列", table, column)
    return True


def _run_migrations():
    """执行所有增量数据库迁移"""
    import json as _json

    with engine.begin() as conn:
        # v1.0.5
        _add_column(conn, "projects", "prompt_id", "INTEGER")
        # v1.0.6
        _add_column(conn, "lines", "is_done", "INTEGER", default=0)
        # v1.0.7
        if _add_column(conn, "llm_provider", "custom_params", "TEXT"):
            default_json = _json.dumps({
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
                "top_p": 0.9,
            }, ensure_ascii=False)
            conn.execute(text("UPDATE llm_provider SET custom_params = :val"), {"val": default_json})
        _add_column(conn, "projects", "is_precise_fill", "INTEGER", default=0)
        _add_column(conn, "projects", "project_root_path", "TEXT")
        # v1.0.8
        _add_column(conn, "tts_provider", "provider_type", "TEXT", default="'index_tts'", backfill="index_tts")
        _add_column(conn, "tts_provider", "voice_type", "TEXT")
        # v1.0.9
        _add_column(conn, "tts_provider", "x_api_key", "TEXT")
        # v1.0.10
        _add_column(conn, "tts_provider", "voice_clone_appid", "TEXT")
        # v1.0.11
        _add_column(conn, "tts_provider", "access_key_id", "TEXT")
        _add_column(conn, "tts_provider", "access_key_secret", "TEXT")
        # v1.0.12
        _add_column(conn, "tts_provider", "resource_id", "TEXT")
        # v1.1.6
        _add_column(conn, "roles", "instruction", "TEXT")
        _add_column(conn, "lines", "instruction", "TEXT")

    from sqlalchemy import inspect
    from app.models.voice_clone_po import VoiceClonePO
    inspector = inspect(engine)
    if "voice_clones" not in inspector.get_table_names():
        logging.info("创建 voice_clones 表...")
        VoiceClonePO.__table__.create(engine)
        logging.info("voice_clones 表创建成功")
    else:
        logging.info("voice_clones 表已存在，跳过创建")


def get_tts_service(db: Session = Depends(get_db)) -> TTSProviderService:
    return TTSProviderService(TTSProviderRepository(db))

# 注意:@app.on_event 已废弃,后续应迁移到 lifespan 上下文管理器
@app.on_event("startup")
async def startup_event():
    # 0) 启动时再次确认认证状态(此时 logging 已配置,警告会同时写入日志文件)
    if not SVC_API_KEY:
        _warn_no_auth()
    # 1) 建表
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logging.exception("❌ 数据库建表失败: %s", e)

    # 2) 增量迁移
    try:
        _run_migrations()
    except Exception as e:
        logging.exception("❌ 数据库迁移失败: %s", e)

    # 3) 初始化共享运行时
    try:
        app.state.tts_queue = asyncio.Queue(maxsize=QUEUE_CAPACITY)
        app.state.tts_executor = ThreadPoolExecutor(max_workers=WORKERS)
    except Exception as e:
        logging.exception("❌ 初始化队列/线程池失败: %s", e)

    # 4) 启动后台 worker
    try:
        app.state.tts_workers = [
            asyncio.create_task(tts_worker(app)) for _ in range(WORKERS)
        ]
    except Exception as e:
        logging.exception("❌ 启动 worker 失败: %s", e)

    # 5) 初始化默认数据
    db = SessionLocal()
    try:
        try:
            tts_service = get_tts_service(db)
            tts_service.create_default_tts_provider()
        except Exception as e:
            logging.warning("⚠️ 默认 TTS provider 初始化失败: %s", e)

        try:
            emotion_service = get_emotion_service(db)
            for name in [
                # 8种基础情绪
                "高兴", "生气", "伤心", "害怕", "厌恶", "低落", "惊喜", "平静",
                # 2种独特复合情绪
                "嘲讽", "悲愤",
            ]:
                try:
                    emotion_service.create_emotion(EmotionEntity(name=name))
                except Exception as e:
                    logging.debug("情绪 %s 已存在或创建失败: %s", name, e)
        except Exception as e:
            logging.warning("⚠️ 情绪初始化失败: %s", e)

        try:
            strength_service = get_strength_service(db)
            for name in ["微弱","稍弱","中等","较强","强烈"]:
                try:
                    strength_service.create_strength(StrengthEntity(name=name))
                except Exception as e:
                    logging.debug("强度 %s 已存在或创建失败: %s", name, e)
        except Exception as e:
            logging.warning("⚠️ 强度初始化失败: %s", e)

    #     创建默认提示词
        try:
            prompt_service = get_prompt_service(db)
            if not prompt_service.get_all_prompts():
                logging.info("创建默认提示词")
                prompt_service.create_default_prompt()
            else:
                default_prompt =  prompt_service.get_prompt_by_name("默认拆分台词提示词")
                if not default_prompt:
                    prompt_service.create_default_prompt()
                else:
                    #修改默认提示词
                    default_prompt_content = get_prompt_str()
                    default_prompt.content = default_prompt_content
                    prompt_service.update_prompt(default_prompt.id, default_prompt.__dict__)

        except Exception as e:
            logging.warning("⚠️ 默认提示词创建失败: %s", e)
    # 兼容之前版本，已有的项目的project_root_path 为 getConfigPath()
        try:
            project_service = get_project_service(db)
            for project in project_service.get_all_projects():
                if not project.project_root_path:
                    project.project_root_path = getConfigPath()
                    project_service.update_project(project.id, project.__dict__)
                    logging.info("项目 %s 默认项目路径已修改为 %s", project.name, project.project_root_path)

        #             todo:修改所有的保存路径，然后前端请求添加保存路径（利用electron读取文件夹路径）
        except Exception as e:
            logging.warning("⚠️ 项目默认项目路径初始化失败: %s", e)

    except Exception as e:
        logging.exception("❌ 默认数据初始化异常: %s", e)
    finally:
        db.close()

# 注意:@app.on_event 已废弃,后续应迁移到 lifespan 上下文管理器
@app.on_event("shutdown")
async def shutdown_event():
    # 优雅退出
    for t in getattr(app.state, "tts_workers", []):
        t.cancel()
    ex = getattr(app.state, "tts_executor", None)
    if ex:
        ex.shutdown(wait=False, cancel_futures=True)
# =========================
# 注册路由
# =========================
app.include_router(project_router.router)
app.include_router(chapter_router.router)
app.include_router(role_router.router)
app.include_router(voice_router.router)
app.include_router(llm_provider_router.router)
app.include_router(tts_provider_router.router)
app.include_router(line_router.router)
app.include_router(emotion_router.router)
app.include_router(strength_router.router)
app.include_router(multi_emotion_voice_router.router)
app.include_router(prompt_router.router)
app.include_router(voice_clone_router)
app.include_router(volcano_voice_manager_router)
app.include_router(aliyun_voice_clone_router)
app.include_router(aliyun_voice_manager_router)
# =========================
# 健康检查接口
# =========================
@app.get("/")
def read_root():
    return Res(code=200, message="轻语云配 后端服务运行中！", data={"status": "running"})


import json
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    # WebSocket 认证:若启用 SVC_API_KEY,校验 query 参数
    if SVC_API_KEY:
        token = ws.query_params.get("api_key")
        if not token or not isinstance(SVC_API_KEY, str) or not hmac.compare_digest(token, SVC_API_KEY):
            await ws.close(code=1008)  # Policy Violation
            return
    await manager.connect(ws)
    logging.info("WebSocket 客户端已连接")
    try:
        while True:
            msg_text = await ws.receive_text()
            try:
                data = json.loads(msg_text)
            except json.JSONDecodeError:
                data = {}

            # 👇 心跳处理：收到 ping 立即回复 pong
            if data.get("type") == "ping":
                logging.debug("receive ping")
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            # 这里可以扩展处理订阅/其他消息

    except WebSocketDisconnect:
        logging.info("WebSocket 客户端主动断开")
        manager.disconnect(ws)
    except Exception as e:
        logging.warning(f"WebSocket 连接异常: {e}")
        manager.disconnect(ws)



if __name__ == "__main__":

    # uvicorn.run(app, host="127.0.0.1", port=8200)
    # 使用自定义 logger，避免 uvicorn 自动配置失败
    # logging.basicConfig(level=logging.INFO)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8200, log_config=None)
