from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.config import Config
import os

# Database URL from config
DATABASE_URL = Config.DATABASE_URL

# Create the database engine with connection parameters to ensure write access
# connect_args={'check_same_thread': False} 允许SQLite在多线程环境中使用
# 去掉任何可能导致只读模式的设置，确保有写入权限
engine = create_engine(
    DATABASE_URL, 
    connect_args={'check_same_thread': False},
    poolclass=None  # 默认连接池
)

# 如果使用SQLite并且数据库文件存在，确保有写入权限
_db_permission_set = False  # 添加一个全局变量标记是否已设置权限

if DATABASE_URL.startswith('sqlite:///'):
    # 提取文件路径（移除sqlite:///前缀）
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    # 如果是相对路径，转换为绝对路径
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)
    
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

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
