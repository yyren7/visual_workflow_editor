#!/usr/bin/env python3
# backend/run_backend.py

import sys
import os
import uvicorn
import warnings
import argparse
from pathlib import Path

# 忽略PyTorch的TypedStorage警告
warnings.filterwarnings("ignore", message="TypedStorage is deprecated")

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# 删除可能存在的旧SQLite数据库文件（开发环境下可以这样做）
sqlite_db_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "flow_editor.db"
)
if os.path.exists(sqlite_db_path):
    try:
        os.remove(sqlite_db_path)
        print(f"已删除旧数据库文件: {sqlite_db_path}")
    except Exception:
        print(f"警告: 无法删除旧数据库文件: {sqlite_db_path}")

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="启动后端服务")
    parser.add_argument(
        "--minimal", action="store_true", help="使用最小模式启动，跳过某些路由"
    )
    args = parser.parse_args()
    
    # 如果使用最小模式，设置环境变量
    if args.minimal:
        print("使用最小模式启动，跳过一些复杂路由...")
        os.environ["SKIP_COMPLEX_ROUTERS"] = "1"
    
    # 配置需要监视的目录，只包含后端代码目录
    backend_dir = Path(__file__).parent.resolve()
    reload_dirs = [str(backend_dir)]
    
    # 使用uvicorn直接运行FastAPI应用
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=reload_dirs,  # 只监视后端代码目录
        reload_excludes=["*.git*", "*.pyc", "__pycache__"]  # 排除不需要监视的目录和文件
    )