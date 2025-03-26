#!/usr/bin/env python3
import argparse
import os
import uvicorn
import sys

# 获取包含主应用的目录
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 将后端目录添加到Python路径，确保可以导入应用
sys.path.insert(0, os.path.dirname(BACKEND_DIR))

def main():
    """
    主函数，解析命令行参数并启动应用
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="启动后端服务")
    parser.add_argument("--minimal", action="store_true", help="使用最小模式启动，跳过某些路由")
    parser.add_argument("--port", type=int, default=8000, help="指定启动的端口号")
    args = parser.parse_args()
    
    # 设置最小模式环境变量
    if args.minimal:
        os.environ["MINIMAL_MODE"] = "1"
        print("使用最小模式启动，部分路由将被禁用")
    else:
        os.environ["MINIMAL_MODE"] = "0"
        
    # 删除数据库文件（在开发环境使用，不要在生产环境使用！）
    db_file = os.path.join(BACKEND_DIR, "database.db")
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print(f"已删除数据库文件: {db_file}")
        except Exception as e:
            print(f"无法删除数据库文件: {e}")
            
    # 配置uvicorn，启动FastAPI应用
    # 注意：这里的"backend.main:app"指向backend/main.py文件中的app对象
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=True,  # 启用热重载
        reload_dirs=[BACKEND_DIR],  # 监控backend目录变化
    )

if __name__ == "__main__":
    main() 