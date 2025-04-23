#!/usr/bin/env python3
# backend/run_backend.py

import sys
import os
import uvicorn
import warnings
import argparse
from pathlib import Path
from dotenv import load_dotenv
# 添加后端目录到Python模块搜索路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

import re
import subprocess
import json

# Ensure the DATABASE_URL is set, default to a relative path within the backend folder
# if "DATABASE_URL" not in os.environ:
# os.environ["DATABASE_URL"] = "sqlite:///database/flow_editor.db"

# 显式加载项目根目录的.env文件，确保所有环境变量统一配置
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=workspace_env_path)

# 根据环境变量决定是否输出调试信息，避免在reload模式下重复输出
PRINT_DEBUG_INFO = os.environ.get("PRINT_DEBUG_INFO", "1") == "1"

# 从.bashrc文件中尝试读取API密钥
def read_key_from_bashrc():
    try:
        home = os.path.expanduser("~")
        bashrc_path = os.path.join(home, ".bashrc")
        if os.path.exists(bashrc_path):
            with open(bashrc_path, 'r') as file:
                content = file.read()
                # 查找类似 export DEEPSEEK_API_KEY=value 或 DEEPSEEK_API_KEY=value 的行
                matches = re.findall(r'(?:export\s+)?DEEPSEEK_API_KEY=[\'"](.*?)[\'"]', content)
                if matches:
                    return matches[0]
                # 或者使用环境变量导出方式读取
                try:
                    result = subprocess.check_output("source ~/.bashrc && echo $DEEPSEEK_API_KEY", 
                                                    shell=True, executable="/bin/bash")
                    api_key = result.decode('utf-8').strip()
                    if api_key and len(api_key) > 10:  # 简单验证密钥长度
                        return api_key
                except:
                    pass
        return None
    except Exception as e:
        print(f"读取.bashrc时出错: {str(e)}")
        return None

# 如果环境变量中没有API密钥，尝试从.bashrc读取
if not os.environ.get("DEEPSEEK_API_KEY"):
    bashrc_key = read_key_from_bashrc()
    if bashrc_key:
        print("已从.bashrc文件读取DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = bashrc_key
    else:
        print("\033[91m错误: 未设置DEEPSEEK_API_KEY环境变量!\033[0m")
        print("请通过以下方式之一设置API密钥:")
        print("1. 在终端中执行: export DEEPSEEK_API_KEY='你的密钥'")
        print("2. 在.env文件中添加: DEEPSEEK_API_KEY=你的密钥")
        print("3. 在~/.bashrc中添加: export DEEPSEEK_API_KEY='你的密钥'")
        print("注意: 不要在代码中明文存储API密钥")
        sys.exit(1)

# 忽略PyTorch的TypedStorage警告
warnings.filterwarnings("ignore", message="TypedStorage is deprecated")

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# 导入数据库模型和引擎，确保表结构会被创建
from database.connection import Base, get_db_context
from database.models import User, Flow, FlowVariable, VersionInfo
from backend.config import APP_CONFIG

# 将版本信息保存到数据库的函数
def save_version_to_db(version_data):
    try:
        with get_db_context() as db:
            try:
                # 查找已有的版本记录
                db_version = db.query(VersionInfo).first()
                
                if db_version:
                    # 更新现有记录
                    db_version.version = version_data.get("version", "0.0.0")
                    db_version.last_updated = version_data.get("lastUpdated", "未知")
                else:
                    # 创建新记录
                    db_version = VersionInfo(
                        version=version_data.get("version", "0.0.0"),
                        last_updated=version_data.get("lastUpdated", "未知")
                    )
                    db.add(db_version)
                
                db.commit()
                print(f"版本信息已保存到数据库: {db_version.version}, {db_version.last_updated}")
            except Exception as e:
                db.rollback()
                print(f"保存版本信息到数据库时出错: {e}")
    except Exception as e:
        print(f"获取数据库连接或执行操作时出错: {e}")

# 全局变量文件将在读取或创建流程图时动态处理，不在服务启动时初始化

# 删除可能存在的旧SQLite数据库文件（开发环境下可以这样做）
# 注释掉这段代码，防止每次启动时删除数据库，导致表结构丢失
# sqlite_db_path = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)), "flow_editor.db"
# )
# if os.path.exists(sqlite_db_path):
#     try:
#         os.remove(sqlite_db_path)
#         print(f"已删除旧数据库文件: {sqlite_db_path}")
#     except Exception:
#         print(f"警告: 无法删除旧数据库文件: {sqlite_db_path}")

if __name__ == "__main__":
    # 读取版本信息
    try:
        # 从database目录读取version.json
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        version_path = os.path.join(workspace_dir, 'database', 'version.json')
        
        version_info = {"version": "0.0.0", "lastUpdated": "未知"}
        if os.path.exists(version_path):
            with open(version_path, 'r') as f:
                version_info = json.load(f)
                print(f"系统版本: {version_info.get('version', '0.0.0')}")
                print(f"最后更新: {version_info.get('lastUpdated', '未知')}")
                
                # 将版本信息保存到数据库
                save_version_to_db(version_info)
        else:
            print(f"警告: 未找到版本文件 {version_path}")
            print("使用默认版本信息")
        
        # 设置为环境变量，使其他模块可以使用
        os.environ["APP_VERSION"] = version_info.get("version", "0.0.0")
        os.environ["APP_LAST_UPDATED"] = version_info.get("lastUpdated", "未知")
    except Exception as e:
        print(f"读取版本信息失败: {e}")
        print("使用默认版本信息")
    
    # 只在主脚本直接运行时输出调试信息
    if PRINT_DEBUG_INFO:
        print("===== 环境变量调试信息 =====")
        import datetime
        print(f"时间: {datetime.datetime.now().isoformat()}")
        import platform
        print(f"Python版本: {sys.version}")
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if api_key:
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "无效密钥"
            print(f"DEEPSEEK_API_KEY: {masked_key} (长度: {len(api_key)}字符)")
        else:
            print("DEEPSEEK_API_KEY: 未设置")
        print(f"DEEPSEEK_BASE_URL: {os.environ.get('DEEPSEEK_BASE_URL', '')}")
        print(f"所有环境变量: {sorted(list(os.environ.keys()))}")
        print("=======================")
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="启动后端服务")
    parser.add_argument(
        "--minimal", action="store_true", help="使用最小模式启动，跳过某些路由"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="指定启动的端口号"
    )
    args = parser.parse_args()
    
    # 如果使用最小模式，设置环境变量
    if args.minimal:
        print("使用最小模式启动，跳过一些复杂路由...")
        os.environ["SKIP_COMPLEX_ROUTERS"] = "1"
    
    # 配置需要监视的目录，只包含后端代码目录
    backend_dir = Path(__file__).parent.resolve()
    reload_dirs = [str(backend_dir)]
    
    # <<< 添加调试：在启动 Uvicorn 前再次检查数据库连接 >>>
    print("准备启动 Uvicorn...")
    from database.connection import verify_connection
    if verify_connection():
        print("数据库连接在启动 Uvicorn 前验证成功。")
    else:
        print("\033[91m错误：数据库连接在启动 Uvicorn 前验证失败！请检查数据库服务和配置。\033[0m")
        # 可以选择在这里退出，或者让 Uvicorn 尝试启动（可能会失败）
        # sys.exit(1)
    # <<< 结束调试 >>>

    # 使用uvicorn直接运行FastAPI应用
    uvicorn.run(
        "app.main:app",  # 使用app目录下的main.py入口
        host="0.0.0.0",
        port=args.port,
        reload=True,
        reload_dirs=reload_dirs,  # 只监视后端代码目录
        reload_excludes=["*.git*", "*.pyc", "__pycache__"]  # 排除不需要监视的目录和文件
    )