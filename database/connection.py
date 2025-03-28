import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

# 导入配置 - 需要修改为新位置
from backend.app.config import Config

# 设置日志
logger = logging.getLogger(__name__)

# 默认数据库URL，使用新的路径
DEFAULT_DATABASE_URL = "sqlite:///database/flow_editor.db"
# Database URL from config or default
DATABASE_URL = Config.DATABASE_URL if hasattr(Config, 'DATABASE_URL') else DEFAULT_DATABASE_URL

# 确保使用新路径
if DATABASE_URL != DEFAULT_DATABASE_URL:
    logger.warning(f"配置的数据库URL不是默认值。当前使用: {DATABASE_URL}, 默认值: {DEFAULT_DATABASE_URL}")

print(f"使用数据库: {DATABASE_URL}")

# Create the database engine with connection parameters to ensure write access
engine = create_engine(
    DATABASE_URL, 
    connect_args={'check_same_thread': False},
    poolclass=None,  # 默认连接池
    echo=False,  # 设置为True可以看到所有SQL查询日志
)

# 如果使用SQLite并且数据库文件存在，确保有写入权限
_db_permission_set = False  # 添加一个全局变量标记是否已设置权限

if DATABASE_URL.startswith('sqlite:///'):
    # 提取文件路径（移除sqlite:///前缀）
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    # 如果是相对路径，转换为绝对路径
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)
    
    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"创建数据库目录: {db_dir}")
    
    # 确保数据库文件有写入权限
    if os.path.exists(db_path) and not _db_permission_set:
        try:
            # 设置数据库文件权限为可读写
            os.chmod(db_path, 0o666)
            print(f"已设置数据库文件 {db_path} 权限为可读写")
            _db_permission_set = True  # 标记已经设置过权限
        except Exception as e:
            print(f"无法设置数据库文件权限: {e}")

# Create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

def get_db():
    """
    获取数据库会话的依赖函数
    
    Returns:
        Session: 数据库会话
    """
    db = SessionLocal()
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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_connection():
    """
    验证数据库连接是否正常
    
    Returns:
        bool: 连接是否正常
    """
    try:
        with get_db_context() as db:
            db.execute("SELECT 1")
            logger.info("数据库连接正常")
            return True
    except Exception as e:
        logger.error(f"数据库连接异常: {str(e)}")
        return False 