from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app import schemas
from database.connection import get_db
from database.models import User, Flow
from config import Config
import json
import os

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

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
    encoded_jwt = jwt.encode(to_encode, Config.SECRET_KEY, algorithm=Config.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get the current user from a JWT token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.ALGORITHM])
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
    从项目根目录的version.json文件中读取版本信息
    
    Returns:
        dict: 包含'version'和'lastUpdated'的字典，如果读取失败则返回默认值
    """
    try:
        # 尝试找到项目根目录的version.json（相对于当前文件的位置）
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        version_path = os.path.join(base_dir, 'version.json')
        
        with open(version_path, 'r') as f:
            version_data = json.load(f)
            return version_data
    except Exception as e:
        print(f"读取版本信息失败: {e}")
        # 返回默认版本信息
        return {"version": "0.0.0", "lastUpdated": "未知"}

def get_version():
    """简单获取版本号"""
    return get_version_info().get("version", "0.0.0")