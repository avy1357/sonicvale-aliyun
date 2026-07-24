from typing import Any, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import *

config_path = getConfigPath()
# SQLite 数据库文件，存储在用户目录下的 SonicVale
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(config_path, 'app_test.db')}"



# echo=True 会打印执行的 SQL 语句，调试用
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, echo=False
)

# C7: 为每个连接启用 SQLite 外键约束（默认关闭）
@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# SessionLocal 用于依赖注入
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 类，所有 ORM 模型继承它
Base = declarative_base()

# 依赖函数
def get_db() -> Generator[Session, Any, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()