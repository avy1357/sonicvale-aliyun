import os
from typing import Any, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import NullPool

# 显式导入需要的函数,避免通配符 import 污染命名空间
from app.core.config import getConfigPath

config_path = getConfigPath()

# SQLite 数据库文件名可通过环境变量配置,默认为 app.db
DB_FILENAME = os.environ.get("SONICVALE_DB_FILENAME", "app.db")
# SQLite 数据库文件,存储在用户目录下的 SonicVale
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(config_path, DB_FILENAME)}"


# echo=False 不打印执行的 SQL 语句,生产环境用
# SQLite 是文件型数据库, 使用 NullPool 避免多线程连接复用问题
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False,
    poolclass=NullPool,
)

# C7: 为每个连接启用 SQLite 外键约束(默认关闭)
@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

# SessionLocal 用于依赖注入
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 类,所有 ORM 模型继承它
Base = declarative_base()

# 依赖函数
def get_db() -> Generator[Session, Any, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
