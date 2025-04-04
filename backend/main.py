from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import user, flow, email, auth, node_templates, workflow_router

# 导入LangChain聊天路由
from langchainchat.api.chat_router import router as chat_router

def create_application() -> FastAPI:
    application = FastAPI(
        title="Visual Workflow Editor API",
        description="提供可视化工作流编辑和处理API",
        version="0.1",
    )
    
    # 配置跨域
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",      # 本地开发环境
            "http://127.0.0.1:3000",      # 本地开发环境(另一种URL)
            "http://localhost:8000",      # 后端API地址
            "http://172.18.0.2:3000",     # Docker网络中的前端容器
            "http://workflow-editor-frontend:3000"  # 容器名称访问
        ],  # 移除"*"通配符
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    application.include_router(user.router)
    application.include_router(flow.router)
    application.include_router(email.router)
    application.include_router(auth.router)
    # application.include_router(embedding_routes.router)
    application.include_router(node_templates.router)
    application.include_router(workflow_router.router)
    
    # 注册LangChain聊天路由
    application.include_router(chat_router)
    
    return application

app = create_application() 