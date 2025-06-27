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

# 显式加载项目根目录的.env文件，确保所有环境变量统一配置
workspace_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(workspace_env_path): # Check if .env exists before loading
    load_dotenv(dotenv_path=workspace_env_path)
else:
    print(f"Warning: .env file not found at {workspace_env_path}. Proceeding with environment variables or defaults.")


# 确保LOG_LEVEL设置为DEBUG或从环境变量读取，供新的logging_config使用
# logging_config.py会读取此环境变量
os.environ["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "DEBUG").upper()
# 确保 PRINT_DEBUG_INFO 也是从环境变量读取，默认为 "0" (关闭)
# 因为详细的启动信息现在应该通过标准日志系统输出
PRINT_DEBUG_INFO = os.environ.get("PRINT_DEBUG_INFO", "0") == "1"


# 从.bashrc文件中尝试读取API密钥
def read_key_from_bashrc():
    try:
        home = os.path.expanduser("~")
        bashrc_path = os.path.join(home, ".bashrc")
        if os.path.exists(bashrc_path):
            with open(bashrc_path, 'r') as file:
                content = file.read()
                matches = re.findall(r'(?:export\\s+)?DEEPSEEK_API_KEY=[\'"](.*?)[\'"]', content)
                if matches:
                    return matches[0]
                try:
                    result = subprocess.check_output("source ~/.bashrc && echo $DEEPSEEK_API_KEY", 
                                                    shell=True, executable="/bin/bash")
                    api_key = result.decode('utf-8').strip()
                    if api_key and len(api_key) > 10:
                        return api_key
                except:
                    pass
        return None
    except Exception as e:
        # It's better to log this error if a logger is available early,
        # but print is fine here as this is very early in startup.
        print(f"Error reading from .bashrc: {str(e)}")
        return None

if not os.environ.get("DEEPSEEK_API_KEY"):
    bashrc_key = read_key_from_bashrc()
    if bashrc_key:
        print("INFO: DEEPSEEK_API_KEY read from .bashrc file.") # Changed to INFO like print
        os.environ["DEEPSEEK_API_KEY"] = bashrc_key
    else:
        # These print statements are critical error messages before logging is fully set up, so they are fine.
        print("\\033[91mERROR: DEEPSEEK_API_KEY environment variable is not set!\\033[0m")
        print("Please set the API key via one of the following methods:")
        print("1. In your terminal: export DEEPSEEK_API_KEY='your_key'")
        print("2. In the .env file: DEEPSEEK_API_KEY=your_key")
        print("3. In ~/.bashrc: export DEEPSEEK_API_KEY='your_key'")
        print("Note: Do not store API keys in plaintext in code.")
        sys.exit(1)

# 忽略PyTorch的TypedStorage警告
warnings.filterwarnings("ignore", message="TypedStorage is deprecated")

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# 导入数据库模型和引擎，确保表结构会被创建
# These imports might trigger logging if models use getLogger at import time.
# from database.connection import Base, get_db_context # Keep if needed for save_version_to_db
# from database.models import User, Flow, FlowVariable, VersionInfo # Keep if needed for save_version_to_db

# 将版本信息保存到数据库的函数
def save_version_to_db(version_data):
    # This function uses print for its own errors, which is acceptable if it's called
    # before the main app logging is fully established or if it's considered a utility script function.
    # For consistency with app logging, it could be refactored to use logging if called after setup.
    try:
        # Ensure imports are within function if they are only used here and to avoid top-level side effects
        from database.connection import get_db_context
        from database.models import VersionInfo

        with get_db_context() as db:
            try:
                db_version = db.query(VersionInfo).first()
                if db_version:
                    db_version.version = version_data.get("version", "0.0.0")
                    db_version.last_updated = version_data.get("lastUpdated", "未知")
                else:
                    db_version = VersionInfo(
                        version=version_data.get("version", "0.0.0"),
                        last_updated=version_data.get("lastUpdated", "未知")
                    )
                    db.add(db_version)
                db.commit()
                print(f"INFO: Version information saved to database: {db_version.version}, {db_version.last_updated}")
            except Exception as e:
                db.rollback()
                print(f"ERROR: Failed to save version information to database: {e}")
    except Exception as e:
        print(f"ERROR: Database connection or operation failed during version save: {e}")

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
    try:
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        version_path = os.path.join(workspace_dir, 'database', 'version.json')
        version_info = {"version": "0.0.0", "lastUpdated": "未知"}
        if os.path.exists(version_path):
            with open(version_path, 'r') as f:
                version_info = json.load(f)
                # These prints are fine for CLI script output before full app logging is up
                print(f"INFO: System Version: {version_info.get('version', '0.0.0')}")
                print(f"INFO: Last Updated: {version_info.get('lastUpdated', '未知')}")
                save_version_to_db(version_info)
        else:
            print(f"WARNING: Version file {version_path} not found. Using default version info.")
        os.environ["APP_VERSION"] = version_info.get("version", "0.0.0")
        os.environ["APP_LAST_UPDATED"] = version_info.get("lastUpdated", "未知")
    except Exception as e:
        print(f"ERROR: Failed to read version information: {e}. Using default version info.")
    
    # Debug info printing, controlled by PRINT_DEBUG_INFO (now defaults to off)
    if PRINT_DEBUG_INFO:
        # These are explicit debug prints, keep them if PRINT_DEBUG_INFO is true
        print("===== Environment Variable Debug Information =====")
        import datetime
        print(f"Time: {datetime.datetime.now().isoformat()}")
        import platform
        print(f"Python Version: {sys.version}")
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if api_key:
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "Invalid Key"
            print(f"DEEPSEEK_API_KEY: {masked_key} (Length: {len(api_key)} chars)")
        else:
            print("DEEPSEEK_API_KEY: Not Set")
        print(f"DEEPSEEK_BASE_URL: {os.environ.get('DEEPSEEK_BASE_URL', '')}")
        print(f"LOG_LEVEL: {os.environ.get('LOG_LEVEL')}") # Print the LOG_LEVEL being used
        # print(f"All Environment Variables: {sorted(list(os.environ.keys()))}") # Can be very verbose
        print("==============================================")
    
    parser = argparse.ArgumentParser(description="Start Backend Service")
    parser.add_argument(
        "--minimal", action="store_true", help="Start in minimal mode, skipping some routers"
    )
    parser.add_argument(
        "--port", type=int, default=os.environ.get("BACKEND_PORT", 8000), help="Specify the port number to start on"
    )
    args = parser.parse_args()
    
    if args.minimal:
        # This print is fine for CLI feedback
        print("INFO: Starting in minimal mode, some complex routers will be skipped...")
        os.environ["SKIP_COMPLEX_ROUTERS"] = "1"
    
    backend_dir_path = Path(__file__).parent.resolve() # Renamed to avoid conflict
    reload_dirs_list = [str(backend_dir_path)] # Renamed to avoid conflict
    
    # <<< REMOVE Pre-Uvicorn DB Check Prints >>>
    # These print statements are now redundant. Errors/success during app startup (including DB connection)
    # will be handled by the new logging system configured in app.main via logging_config.py.
    # print("Preparing to start Uvicorn...")
    # from database.connection import verify_connection # This import might be heavy here
    # if verify_connection():
    #     print("Database connection verified successfully before Uvicorn start.")
    # else:
    #     print("\\033[91mERROR: Database connection verification FAILED before Uvicorn start! Check DB service and config.\\033[0m")
    #     # sys.exit(1) # Optionally exit if DB is critical before Uvicorn even tries
    # <<< END REMOVE >>>

    # Uvicorn will pick up logging configuration from the app ("app.main:app")
    # Ensure app.main calls setup_app_logging() from backend.logging_config early.
    # We don't need to set log_level here for uvicorn if logging_config.py handles uvicorn loggers.
    print(f"INFO: Starting Uvicorn server on host 0.0.0.0:{args.port}. LOG_LEVEL={os.environ.get('LOG_LEVEL')}")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=args.port,
        reload=False, # Set to True for development if preferred, logging_config handles reload
        reload_dirs=reload_dirs_list,
        reload_excludes=["*.git*", "*.pyc", "__pycache__"]
        # log_level=os.environ.get("LOG_LEVEL", "info").lower(), # Not strictly needed if logging_config handles uvicorn loggers
    )