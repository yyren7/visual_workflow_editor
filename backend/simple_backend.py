#!/usr/bin/env python3
# simple_backend.py - 简化版后端启动脚本

import os
import sys
import uvicorn

# 确保使用新的数据库路径
os.environ["DATABASE_URL"] = "sqlite:///database/flow_editor.db"

# 添加后端目录到Python模块搜索路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

# 使用uvicorn直接运行FastAPI应用
if __name__ == "__main__":
    port = 8000
    print(f"启动后端服务，端口: {port}")
    print(f"使用数据库: {os.environ[\"DATABASE_URL\"]}")
    
    uvicorn.run(
        "main:app",  # 使用当前目录下的main.py入口
        host="0.0.0.0",
        port=port,
        reload=False,  # 关闭自动重载，减少复杂性
    )
