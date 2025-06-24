## backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os
import logging
from pathlib import Path
import logging.handlers
import time # 导入 time
import uuid # ADDED
import datetime # ADDED

# --- 新增：启用 LangChain 的详细日志 ---
import langchain
langchain.debug = True
logger = logging.getLogger(__name__) # 获取一个logger实例，确保在这之前定义了langchain.debug
logger.info("LangChain debug mode enabled.") # 记录一下我们启用了它
# --- 结束新增 ---

# 添加项目根目录到Python路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

# 导入配置
from backend.config.base import LOG_DIR
from backend.config.app_config import APP_CONFIG

# 创建logs目录
log_dir = Path(LOG_DIR) # 使用配置中的 LOG_DIR
log_dir.mkdir(parents=True, exist_ok=True)

# 为 app.main logger 创建格式化器
app_main_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# --- BEGIN MODIFICATION ---
# 配置 'backend.app' 命名空间下的日志记录器，使其将 DEBUG 及以上级别日志输出到控制台
# 这将覆盖 backend.app.routers.chat 等子模块的日志记录器
backend_app_logger = logging.getLogger("backend.app")
backend_app_logger.setLevel(logging.DEBUG)

# 创建或复用一个控制台处理器
# 复用 app_main_formatter
general_console_handler = logging.StreamHandler()
general_console_handler.setFormatter(app_main_formatter)
general_console_handler.setLevel(logging.DEBUG) # 确保处理器本身也允许 DEBUG

backend_app_logger.addHandler(general_console_handler)
backend_app_logger.propagate = False # ADDED THIS LINE
# 不需要设置 backend_app_logger.propagate = False，让 app.main 等子记录器可以进一步自定义行为 # This comment is now outdated by the line above
# --- END MODIFICATION ---

# 创建单独的DeepSeek日志记录器
deepseek_logger = logging.getLogger("backend.deepseek")
deepseek_logger.setLevel(logging.DEBUG)
deepseek_file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "deepseek_api.log", # 使用 log_dir 变量
    maxBytes=20*1024*1024,  # 20MB
    backupCount=10,
    encoding='utf-8'
)
deepseek_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
deepseek_logger.addHandler(deepseek_file_handler)
# deepseek_logger.propagate = False # 可选：如果 deepseek 日志不应传播到根

# 工作流处理日志记录器
workflow_logger = logging.getLogger("backend.workflow")
workflow_logger.setLevel(logging.DEBUG)
workflow_file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "workflow.log", # 使用 log_dir 变量
    maxBytes=20*1024*1024,  # 20MB
    backupCount=10,
    encoding='utf-8'
)
workflow_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
workflow_logger.addHandler(workflow_file_handler)
# workflow_logger.propagate = False # 可选：如果 workflow 日志不应传播到根

logger = logging.getLogger(__name__) # 此处的 __name__ 通常是 "app.main"
logger.setLevel(logging.DEBUG) # 为 app.main logger 设置级别

# 为 app.main logger 添加控制台处理器
app_main_console_handler = logging.StreamHandler()
app_main_console_handler.setFormatter(app_main_formatter)
logger.addHandler(app_main_console_handler)

# 为 app.main logger 添加文件处理器 (app.log)
app_main_file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "app.log",
    maxBytes=1*1024*1024,
    backupCount=1,
    encoding='utf-8'
)
app_main_file_handler.setFormatter(app_main_formatter)
logger.addHandler(app_main_file_handler)

logger.propagate = False # 防止 app.main 日志被根记录器（如果将来配置了）重复处理

logger.info("日志系统已配置 (app.main)，将记录到 %s 和控制台", log_dir) # 使用 log_dir 变量

# 检查是否使用最小模式
MINIMAL_MODE = os.environ.get("SKIP_COMPLEX_ROUTERS", "0") == "1"
if MINIMAL_MODE:
    logger.info("使用最小模式启动，将跳过某些复杂路由")

# 确保 base 模块的 LOG_DIR 已经加载
logger.info(f"从配置加载的 LOG_DIR: {LOG_DIR}")

logger.info("开始导入模块...")

# 首先导入数据库模型
try:
    from database.connection import Base 
    logger.info("导入database成功")
    
    # 导入数据库模型
    from database.models import User, Flow, FlowVariable, VersionInfo, Chat
    logger.info("导入models成功")
    
    # 导入embeddings模型
    # 注释掉不存在的embeddings模块
    # from backend.app.embeddings.models import JsonEmbedding
    # logger.info("导入embedding模型成功")
    
    # 现在可以导入backend包
    from backend.config import APP_CONFIG
    logger.info("导入config成功")
    from backend.app.routers import (
        user, flow, email, auth, node_templates,
        flow_variables, chat, langgraph_chat
    )
    logger.info("导入基本路由成功")
    
    # 只在非最小模式下导入复杂路由
    if not MINIMAL_MODE:
        try:
            # from backend.app.routers import workflow_router
            logger.info("导入workflow_router成功")
        except ImportError as e:
            logger.error(f"导入workflow_router失败: {e}")
    
    from backend.app.utils import get_version, get_version_info
    logger.info("导入utils成功")
    from backend.app.dependencies import get_node_template_service
    logger.info("导入dependencies成功")
except Exception as e:
    logger.error(f"导入模块时出错: {e}")
    raise

# --- 新增：导入 Pydantic 模型和依赖 --- 
from backend.langgraphchat.memory.db_chat_memory import DbChatMemory
from backend.app.services.chat_service import ChatService # 确保 ChatService 已导入

# --- 新增：解析 Pydantic 前向引用 --- 
try:
    logger.info("尝试重建 Pydantic 模型以解析前向引用...")
    DbChatMemory.model_rebuild()
    # 如果 ChatService 或其他模型也使用了前向引用，也在此调用
    # ChatService.model_rebuild()
    logger.info("Pydantic 模型重建成功")
except Exception as e:
    logger.error(f"重建 Pydantic 模型时出错: {e}", exc_info=True)
    # 根据需要处理错误，例如退出应用。目前仅记录错误。

logger.info("初始化FastAPI应用...")
# Initialize FastAPI app
app = FastAPI(
    title=APP_CONFIG['PROJECT_NAME'],
    version=get_version(),  # 动态读取版本号
)

# 添加这个中间件来记录所有请求
@app.middleware("http")
async def log_requests_detailed(request: Request, call_next):
    client_host = request.client.host if request.client else "Unknown"
    logger.info(f"收到请求: {request.method} {request.url.path} (来自: {client_host})")
    logger.debug(f"请求头: {dict(request.headers)}") # 打印请求头 (DEBUG级别)

    start_time = time.time()
    try:
        response = await call_next(request) # 调用后续处理或路由
        process_time = time.time() - start_time
        logger.info(f"请求完成: {request.method} {request.url.path} - {response.status_code} (耗时: {process_time:.4f}s)")
        # 如果需要，可以记录响应头 (DEBUG级别)
        # logger.debug(f"响应头: {dict(response.headers)}")
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"请求处理出错: {request.method} {request.url.path} - {e} (耗时: {process_time:.4f}s)", exc_info=True) # 记录异常信息
        # 重新抛出异常，让 FastAPI 的错误处理接管
        raise e from None
    return response

# CORS configuration - 配置更加明确的CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CONFIG['CORS_ORIGINS'],
    allow_credentials=APP_CONFIG.get('CORS_CREDENTIALS', True),
    allow_methods=APP_CONFIG.get('CORS_METHODS', ["*"]),
    allow_headers=APP_CONFIG.get('CORS_HEADERS', ["*"]),
    expose_headers=["*"],
)

logger.info("注册路由...")
# Include routers
try:
    app.include_router(user.router)
    logger.info("注册user路由成功")
    app.include_router(flow.router)
    logger.info("注册flow路由成功")
    app.include_router(email.router)
    logger.info("注册email路由成功")
    app.include_router(auth.router)
    logger.info("注册auth路由成功")
    app.include_router(node_templates.router)  # 添加节点模板路由
    logger.info("注册node_templates路由成功")
    
    # 只在非最小模式下注册复杂路由
    if not MINIMAL_MODE:
        try:
            # app.include_router(workflow_router.router)  # 添加工作流路由
            logger.info("注册workflow路由成功")
        except Exception as e:
            logger.error(f"注册workflow路由失败: {e}")
    else:
        logger.info("跳过注册workflow路由")

    # 加载API路由
    app.include_router(flow_variables.router)  # 添加流程图变量路由
    app.include_router(chat.router)  # 添加聊天路由
    app.include_router(langgraph_chat.router)  # 添加LangGraph聊天路由
    logger.info("注册flow_variables路由成功")
    logger.info("注册chat路由成功")
    logger.info("注册langgraph_chat路由成功")
except Exception as e:
    logger.error(f"注册路由时出错: {e}")
    raise

logger.info("FastAPI应用初始化完成，准备开始处理请求...")

@app.on_event("startup")
async def startup_event():
    """
    应用启动时执行的事件
    预加载节点模板数据
    """
    log_id = str(uuid.uuid4())
    current_time = datetime.datetime.now().isoformat()
    logger.info(f"🚀 STARTUP EVENT 1 (startup_event) CALLED - ID: {log_id} at {current_time}")
    # 预加载节点模板
    template_service = get_node_template_service()
    # print("节点模板加载成功") # REPLACED
    logger.info(f"Node templates loaded by startup_event (ID: {log_id}).")
    
    # 不再需要初始化节点类型提示服务
    # 它将在langgraphchat/prompts/chat_prompts.py中按需创建

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
    
    # 返回版本信息，使用全局CORS配置
    return version_data

# 在应用启动前验证API配置
@app.on_event("startup")
async def validate_api_configuration():
    """验证API配置，确保必要的服务可以正常工作"""
    log_id = str(uuid.uuid4())
    current_time = datetime.datetime.now().isoformat()
    logger.info(f"🚀 STARTUP EVENT 2 (validate_api_configuration) CALLED - ID: {log_id} at {current_time}")
    import logging # This import is fine here or at top
    logger_local = logging.getLogger("backend.app.startup") # Use a more specific logger or the global one
    
    from backend.config import APP_CONFIG, AI_CONFIG, DB_CONFIG
    
    # 验证DeepSeek配置
    if AI_CONFIG['USE_DEEPSEEK']:
        logger_local.info("正在验证DeepSeek API配置")
        
        invalid_key = not AI_CONFIG['DEEPSEEK_API_KEY'] or AI_CONFIG['DEEPSEEK_API_KEY'] == "your_deepseek_api_key_here" or AI_CONFIG['DEEPSEEK_API_KEY'].startswith("sk-if-you-see-this")
        
        if invalid_key:
            logger_local.warning("⚠️ 未设置有效的DeepSeek API密钥，请设置DEEPSEEK_API_KEY环境变量")
            logger_local.warning("⚠️ 当前API密钥值不是有效的密钥，API调用将失败")
        else:
            logger_local.info(f"✓ DeepSeek API密钥已设置 (前4位: {AI_CONFIG['DEEPSEEK_API_KEY'][:4]}***)")
            
        # 检查基础URL是否正确
        base_url = AI_CONFIG['DEEPSEEK_BASE_URL'].rstrip('/')
        logger_local.info(f"DeepSeek API基础URL: {base_url}")
        
        if '/v1/' in base_url or base_url.endswith('/v1'):
            logger_local.warning(f"⚠️ 检测到基础URL中包含/v1路径: {base_url}")
            logger_local.warning("⚠️ 这可能会导致API路径重复，因为代码中会自动添加/v1/chat/completions")
            
        logger_local.info(f"DeepSeek模型: {AI_CONFIG['DEEPSEEK_MODEL']}")
        
        # 尝试验证 DeepSeek 客户端模块
        try:
            # 尝试导入新的 DeepSeekLLM 类来验证模块是否存在
            from backend.langgraphchat.llms.deepseek_client import DeepSeekLLM
            # 之前获取实例的代码不再需要
            # logger.info("✓ DeepSeek客户端服务初始化成功") # 旧日志
            logger_local.info("✓ DeepSeek客户端模块 (DeepSeekLLM) 导入成功") # 新日志
        except Exception as e:
            # logger.error(f"⚠️ DeepSeek客户端服务初始化失败: {str(e)}") # 旧日志
            logger_local.error(f"⚠️ DeepSeek客户端模块 (DeepSeekLLM) 导入或验证失败: {str(e)}") # 新日志
    
    # 验证数据库配置
    logger_local.info(f"数据库URL: {DB_CONFIG['DATABASE_URL'] if 'DATABASE_URL' in DB_CONFIG and DB_CONFIG['DATABASE_URL'] else '未设置'}")
    
    # 记录调试模式状态
    if APP_CONFIG['DEBUG']:
        logger_local.info("⚠️ 调试模式已启用")
    else:
        logger_local.info("✓ 调试模式已禁用")
        
    # 记录API前缀
    logger_local.info(f"API前缀: {APP_CONFIG['API_PREFIX']}")
    
    # 验证CORS配置
    logger_local.info(f"CORS允许的源: {', '.join(APP_CONFIG['CORS_ORIGINS'])}")
