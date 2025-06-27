from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app import schemas
from database.connection import get_db, get_db_context
from database.models import User, Flow, VersionInfo
from backend.config import APP_CONFIG
import json
import os
import logging
import uuid
from backend.sas.state import RobotFlowAgentState

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login", auto_error=False)

SECRET_KEY = APP_CONFIG['SECRET_KEY']
ALGORITHM = APP_CONFIG['ALGORITHM']
ACCESS_TOKEN_EXPIRE_MINUTES = APP_CONFIG['ACCESS_TOKEN_EXPIRE_MINUTES']

def hash_password(password: str) -> str:
    """
    Hash a password for storing.
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a stored password against a provided password.
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get the current user from a JWT token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 添加对token的空值检查
    if token is None:
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def optional_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get the current user from a JWT token.
    Returns None if the token is invalid or missing.
    """
    if token is None:
        return None
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        token_data = schemas.TokenData(username=username)
    except JWTError:
        return None
    
    user = db.query(User).filter(User.username == token_data.username).first()
    return user

def verify_flow_ownership(flow_id: str, current_user: schemas.User, db: Session):
    """
    验证当前用户是否是流程图的所有者。
    如果不是所有者，则抛出403异常。
    
    Args:
        flow_id: 流程图ID(字符串形式的UUID)
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        models.Flow: 流程图对象
        
    Raises:
        HTTPException: 如果流程图不存在或用户不是所有者
    """
    # 先检查流程图是否存在
    flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="流程图不存在")
    
    # 验证所有权
    if flow.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有访问此流程图的权限"
        )
    
    return flow

def get_version_info():
    """
    获取系统版本信息，优先从数据库读取，其次使用环境变量，最后尝试从文件读取
    
    Returns:
        dict: 包含'version'和'lastUpdated'的字典，如果读取失败则返回默认值
    """
    # 1. 优先从数据库读取
    try:
        with get_db_context() as db:
            try:
                db_version = db.query(VersionInfo).first()
                if db_version:
                    logger.info(f"从数据库获取版本信息: {db_version.version}")
                    return {
                        "version": db_version.version,
                        "lastUpdated": db_version.last_updated
                    }
            except Exception as inner_e:
                logger.warning(f"数据库查询版本信息时出错: {inner_e}")
    except Exception as e:
        logger.warning(f"获取数据库会话或连接时出错: {e}")
    
    # 2. 尝试从环境变量读取
    if os.environ.get("APP_VERSION") and os.environ.get("APP_LAST_UPDATED"):
        logger.info(f"从环境变量获取版本信息: {os.environ.get('APP_VERSION')}")
        return {
            "version": os.environ.get("APP_VERSION"),
            "lastUpdated": os.environ.get("APP_LAST_UPDATED")
        }
    
    # 3. 尝试从文件读取
    try:
        # 从database目录读取version.json
        workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        version_path = os.path.join(workspace_dir, 'database', 'version.json')
        
        if os.path.exists(version_path):
            with open(version_path, 'r') as f:
                version_data = json.load(f)
                logger.info(f"从文件获取版本信息: {version_data.get('version', '0.0.0')}")
                return version_data
        else:
            logger.warning(f"警告: 未找到版本文件 {version_path}")
    except Exception as e:
        logger.warning(f"读取版本信息文件失败: {e}")
    
    # 4. 返回默认版本信息
    logger.warning("使用默认版本信息")
    return {"version": "0.0.0", "lastUpdated": "未知"}

def get_version():
    """简单获取版本号"""
    return get_version_info().get("version", "0.0.0")

def get_default_agent_state():
    """
    返回一个严格遵循 backend.sas.state.RobotFlowAgentState 定义的默认状态字典。
    这确保了新创建的流程图状态与 LangGraph 子图的期望完全一致。
    """
    # 这个实现通过编程方式从Pydantic模型获取默认值，以确保一致性。
    # 我们实例化模型，然后将其转换为字典。
    # 字段 'sse_event_queue' 被排除，因为它不应被持久化。
    default_state_model = RobotFlowAgentState()
    default_state_dict = default_state_model.model_dump(exclude_none=False) # 使用 .model_dump()
    
    # 手动移除不应包含在持久化状态中的运行时字段
    # sse_event_queue 已经在 Pydantic 模型中通过 exclude=True 处理
    
    return default_state_dict