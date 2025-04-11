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

# 创建logs目录
log_dir = Path("backend/app/logs")
log_dir.mkdir(parents=True, exist_ok=True)

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # 控制台输出
        logging.StreamHandler(),
        # 文件输出
        logging.handlers.RotatingFileHandler(
            log_dir / "app.log", 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

# 创建单独的DeepSeek日志记录器
deepseek_logger = logging.getLogger("backend.deepseek")
deepseek_logger.setLevel(logging.DEBUG)
deepseek_file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "deepseek_api.log",
    maxBytes=20*1024*1024,  # 20MB
    backupCount=10,
    encoding='utf-8'
)
deepseek_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
deepseek_logger.addHandler(deepseek_file_handler)

# 工作流处理日志记录器
workflow_logger = logging.getLogger("backend.workflow")
workflow_logger.setLevel(logging.DEBUG)
workflow_file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "workflow.log",
    maxBytes=20*1024*1024,  # 20MB
    backupCount=10,
    encoding='utf-8'
)
workflow_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
workflow_logger.addHandler(workflow_file_handler)

logger = logging.getLogger(__name__)
logger.info("日志系统已配置，将记录到 %s", log_dir)

# 检查是否使用最小模式
MINIMAL_MODE = os.environ.get("SKIP_COMPLEX_ROUTERS", "0") == "1"
if MINIMAL_MODE:
    logger.info("使用最小模式启动，将跳过某些复杂路由")

# 添加项目根目录到Python路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

logger.info("开始导入模块...")

# 首先导入数据库模型
try:
    from database.connection import engine, Base
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
        flow_variables, chat
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

logger.info("创建数据库表...")
# Create the database tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建成功")
except Exception as e:
    logger.error(f"创建数据库表失败: {e}")
    raise

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
    allow_origins=[
        "http://localhost:3000",      # 本地开发环境
        "http://127.0.0.1:3000",      # 本地开发环境(另一种URL)
        "http://localhost:8000",
        "http://127.0.0.1:8000",      # 后端API地址
        "http://172.18.0.3:3000",     # Docker网络中的前端容器
        "http://workflow-editor-frontend:3000",  # 容器名称访问
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    logger.info("注册flow_variables路由成功")
    logger.info("注册chat路由成功")
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
    # 预加载节点模板
    template_service = get_node_template_service()
    print("节点模板加载成功")
    
    # 不再需要初始化节点类型提示服务
    # 它将在langchainchat/prompts/chat_prompts.py中按需创建

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
    import logging
    logger = logging.getLogger("backend.app.startup")
    
    from backend.config import APP_CONFIG, AI_CONFIG
    
    # 验证DeepSeek配置
    if AI_CONFIG['USE_DEEPSEEK']:
        logger.info("正在验证DeepSeek API配置")
        
        invalid_key = not AI_CONFIG['DEEPSEEK_API_KEY'] or AI_CONFIG['DEEPSEEK_API_KEY'] == "your_deepseek_api_key_here" or AI_CONFIG['DEEPSEEK_API_KEY'].startswith("sk-if-you-see-this")
        
        if invalid_key:
            logger.warning("⚠️ 未设置有效的DeepSeek API密钥，请设置DEEPSEEK_API_KEY环境变量")
            logger.warning("⚠️ 当前API密钥值不是有效的密钥，API调用将失败")
        else:
            logger.info(f"✓ DeepSeek API密钥已设置 (前4位: {AI_CONFIG['DEEPSEEK_API_KEY'][:4]}***)")
            
        # 检查基础URL是否正确
        base_url = AI_CONFIG['DEEPSEEK_BASE_URL'].rstrip('/')
        logger.info(f"DeepSeek API基础URL: {base_url}")
        
        if '/v1/' in base_url or base_url.endswith('/v1'):
            logger.warning(f"⚠️ 检测到基础URL中包含/v1路径: {base_url}")
            logger.warning("⚠️ 这可能会导致API路径重复，因为代码中会自动添加/v1/chat/completions")
            
        logger.info(f"DeepSeek模型: {AI_CONFIG['DEEPSEEK_MODEL']}")
        
        # 尝试验证 DeepSeek 客户端模块
        try:
            # 尝试导入新的 DeepSeekLLM 类来验证模块是否存在
            from backend.langchainchat.llms.deepseek_client import DeepSeekLLM
            # 之前获取实例的代码不再需要
            # logger.info("✓ DeepSeek客户端服务初始化成功") # 旧日志
            logger.info("✓ DeepSeek客户端模块 (DeepSeekLLM) 导入成功") # 新日志
        except Exception as e:
            # logger.error(f"⚠️ DeepSeek客户端服务初始化失败: {str(e)}") # 旧日志
            logger.error(f"⚠️ DeepSeek客户端模块 (DeepSeekLLM) 导入或验证失败: {str(e)}") # 新日志
    
    # 验证数据库配置
    logger.info(f"数据库URL: {APP_CONFIG['DATABASE_URL'] if 'DATABASE_URL' in APP_CONFIG else '未设置'}")
    
    # 记录调试模式状态
    if APP_CONFIG['DEBUG']:
        logger.info("⚠️ 调试模式已启用")
    else:
        logger.info("✓ 调试模式已禁用")
        
    # 记录API前缀
    logger.info(f"API前缀: {APP_CONFIG['API_PREFIX']}")
    
    # 验证CORS配置
    logger.info(f"CORS允许的源: {', '.join(APP_CONFIG['CORS_ORIGINS'])}")
