from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import user, flow, llm, email, auth, embedding_routes, node_templates, workflow_router

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
        allow_origins=["*"],  # 生产环境应指定域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    application.include_router(user.router)
    application.include_router(flow.router)
    application.include_router(llm.router)
    application.include_router(email.router)
    application.include_router(auth.router)
    application.include_router(embedding_routes.router)
    application.include_router(node_templates.router)
    application.include_router(workflow_router.router)
    
    # 注册LangChain聊天路由
    application.include_router(chat_router)
    
    return application

app = create_application() 