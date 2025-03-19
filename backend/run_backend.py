#!/usr/bin/env python3
## backend/run_backend.py

import sys
import os
import uvicorn
import warnings

# 忽略PyTorch的TypedStorage警告
warnings.filterwarnings("ignore", message="TypedStorage is deprecated")

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# 删除可能存在的旧SQLite数据库文件（开发环境下可以这样做）
sqlite_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flow_editor.db")
if os.path.exists(sqlite_db_path):
    try:
        os.remove(sqlite_db_path)
        print(f"已删除旧数据库文件: {sqlite_db_path}")
    except:
        print(f"警告: 无法删除旧数据库文件: {sqlite_db_path}")

if __name__ == "__main__":
    # 使用uvicorn直接运行FastAPI应用
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )