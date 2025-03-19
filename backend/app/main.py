## backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

# 现在可以导入backend包
from backend.app.config import Config
from backend.app.routers import user, flow, llm, email, auth, embedding_routes, node_templates # 导入节点模板路由
from backend.app.database import engine
from backend.app.models import Base
from backend.app.utils import get_version, get_version_info
from backend.app.dependencies import get_node_template_service  # 导入节点模板服务依赖

# Create the database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=Config.PROJECT_NAME,
    version=get_version(),  # 动态读取版本号
)

# CORS configuration - 配置更加明确的CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # 本地开发环境
        "http://localhost:8000",      # 后端API地址
        "http://172.18.0.3:3000",     # Docker网络中的前端容器
        "http://workflow-editor-frontend:3000",  # 容器名称访问
        "*"                          # 允许所有源
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(user.router)
app.include_router(flow.router)
app.include_router(llm.router)
app.include_router(email.router)
app.include_router(auth.router)
app.include_router(embedding_routes.router)  # 添加 embedding 路由
app.include_router(node_templates.router)  # 添加节点模板路由

@app.on_event("startup")
async def startup_event():
    """
    应用启动时执行的事件
    预加载节点模板数据
    """
    # 预加载节点模板
    get_node_template_service()
    print("Node templates loaded successfully")

@app.get("/")
async def root():
    return {"message": "Flow Editor API"}

# 添加一个新的端点，提供版本信息
@app.get("/api/version")
async def version(request: Request):
    # 记录请求信息以便调试
    origin = request.headers.get("origin", "未知来源")
    print(f"接收到版本请求，来源: {origin}")
    
    version_data = get_version_info()
    print(f"返回版本信息: {version_data}")
    
    # 明确设置CORS响应头
    response = JSONResponse(content=version_data)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
