import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session
import os
import threading
from threading import RLock

# 从 backend.config 导入配置读取函数
# 注意：避免直接导入 DB_CONFIG 字典以防止在导入时触发 os.getenv
# from backend.config import DB_CONFIG # 移除直接导入

# 设置日志
logger = logging.getLogger(__name__)

# ---- 全局变量用于缓存 Engine 和 SessionLocal ----
_engine = None
_session_local_factory = None
_engine_lock = RLock() # 使用可重入锁

# ---- 新增：获取数据库 URL 的函数 ----
def get_database_url() -> str:
    """从环境变量或默认值获取数据库 URL"""
    # 注意：这里的逻辑直接从 backend.config.db_config.py 复制过来
    # 更好的方式可能是从一个统一的配置加载器获取
    default_url = "sqlite:///database/flow_editor.db"
    database_url = os.getenv("DATABASE_URL", default_url)
    
    # 在实际项目中，可能还需要处理从 .env 文件加载等逻辑
    # if database_url != default_url:
    #     logger.info(f"使用数据库 URL: {database_url}")
    # else:
    #     logger.info(f"使用默认数据库 URL: {default_url}")

    return database_url

# ---- 新增：创建或获取数据库引擎的函数 ----
def get_db_engine():
    """获取或创建单例数据库引擎"""
    global _engine
    if _engine is None:
        with _engine_lock:
            # 再次检查，防止多线程竞争时重复创建
            if _engine is None:
                db_url = get_database_url()
                logger.info(f"创建数据库引擎，连接到: {db_url}")
                connect_args = {}
                if db_url.startswith('sqlite'):
                    connect_args={'check_same_thread': False}
                    # 这里不再需要处理权限，交给 Docker 或用户管理
                
                # 建议为 PostgreSQL 配置连接池
                pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
                max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
                
                _engine = create_engine(
                    db_url,
                    connect_args=connect_args,
                    pool_size=pool_size if not db_url.startswith('sqlite') else 5, # SQLite通常不需要复杂池
                    max_overflow=max_overflow if not db_url.startswith('sqlite') else 2,
                    pool_recycle=3600, # 可选：池连接回收时间（秒）
                    echo=False, # 生产环境通常设为 False
                )
    return _engine

# ---- 新增：获取 Session 工厂的函数 ----
def get_session_local_factory():
    """获取或创建单例 Session 工厂"""
    global _session_local_factory
    if _session_local_factory is None:
        with _engine_lock:
            # 再次检查
            if _session_local_factory is None:
                engine = get_db_engine() # 确保引擎已创建
                logger.info("创建 SessionLocal 工厂")
                _session_local_factory = sessionmaker(
                    autocommit=False, autoflush=False, bind=engine
                )
    return _session_local_factory

# ---- 保留 Base ----
# Base class for declarative models
Base = declarative_base()

# ---- 修改 get_db 和 get_db_context ----
def get_db():
    """
    获取数据库会话的依赖函数 (FastAPI)
    
    Returns:
        Session: 数据库会话
    """
    SessionLocal = get_session_local_factory() # 获取工厂
    db = SessionLocal() # 创建会话
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """
    获取数据库会话的上下文管理器
    
    Yields:
        Session: 数据库会话
    """
    SessionLocal = get_session_local_factory() # 获取工厂
    db = SessionLocal() # 创建会话
    try:
        yield db
    finally:
        db.close()

# ---- 保持 verify_connection 不变 ----
def verify_connection():
    """
    验证数据库连接是否正常
    
    Returns:
        bool: 连接是否正常
    """
    try:
        # 确保引擎可以被创建（即使之前没有连接过）
        engine = get_db_engine()
        # 尝试建立连接并执行简单查询
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            logger.info("数据库连接正常")
            return True
    except Exception as e:
        logger.error(f"数据库连接异常: {str(e)}")
        # 打印更详细的错误，帮助诊断
        # import traceback
        # logger.error(traceback.format_exc())
        return False 