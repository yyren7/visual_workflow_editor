from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from backend.app.config import Config
from backend.app import database, models, schemas
from sqlalchemy.orm import Session
from backend.app.utils import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

@router.get("/verify-token", response_model=schemas.User)
async def verify_token(current_user: schemas.User = Depends(get_current_user)):
    """
    验证当前用户的token是否有效。
    如果token有效，返回用户信息。
    如果token无效，返回401未授权错误。
    """
    return current_user

@router.get("/test-401")
async def test_401():
    """
    测试端点，始终返回401未授权错误。
    用于前端测试错误处理。
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="测试未授权响应",
        headers={"WWW-Authenticate": "Bearer"},
    )