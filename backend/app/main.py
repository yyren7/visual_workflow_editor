## backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import Config
from backend.app.routers import user, flow, llm, email, auth # 导入 auth 路由
from backend.app.database import engine
from backend.app.models import Base
from backend.app.utils import get_version, get_version_info

# Create the database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=Config.PROJECT_NAME,
    version=get_version(),  # 动态读取版本号
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_CREDENTIALS,
    allow_methods=Config.CORS_METHODS,
    allow_headers=Config.CORS_HEADERS,
)

# Include routers
app.include_router(user.router)
app.include_router(flow.router)
app.include_router(llm.router)
app.include_router(email.router) # 引入 email 路由
app.include_router(auth.router) # 引入 auth 路由

@app.get("/")
async def root():
    return {"message": "Flow Editor API"}

# 添加一个新的端点，提供版本信息
@app.get("/api/version")
async def version():
    return get_version_info()
