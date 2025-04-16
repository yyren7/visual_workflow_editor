# export_flow_data_sqlite.py
import os
import json
import re
from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime, ForeignKey, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime

# --- 配置 ---
# 使用用户提供的 SQLite 文件路径
DATABASE_URL = "sqlite:////workspace/database/flow_editor.db" 

# 要导出数据的用户Owner ID
owner_id_to_export = '27c83191-caae-4df4-a217-b6398a62061b' # 修改为正确的用户 ID

# 输出目录
output_base_dir = "/workspace/database"
output_dir = os.path.join(output_base_dir, "flow_database")

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- SQLAlchemy 模型定义 ---
# !!! 重要: 这个模型定义需要与你的 'flow_editor.db' 文件中的 Flow 表结构匹配 !!!
# 如果你的模型定义不同（例如表名、列名、类型），请相应修改。
Base = declarative_base()

class Flow(Base):
    __tablename__ = 'flows' # 确认表名是否正确

    # 假设 id 是字符串类型，根据实际情况修改 (可能是 Integer)
    id = Column(String, primary_key=True, index=True) 
    name = Column(String, index=True)
    owner_id = Column(String, index=True) # 假设 owner_id 是字符串，根据实际情况修改
    flow_data = Column(JSON) # 核心流程图数据
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # 添加其他可能的字段，如果你的模型中有的话
    # last_interacted_chat_id = Column(String, nullable=True) 

# --- 辅助函数：清理文件名 ---
def sanitize_filename(name: str, fallback_id: str) -> str:
    """将流程名称清理为有效的文件名"""
    if not name:
        # 如果名称为空，使用 flow_id
        logger.warning(f"Flow ID '{fallback_id}' 的名称为空，将使用 ID 作为文件名。")
        return f"{fallback_id}.json"
    
    # 替换空格为下划线
    sanitized_name = name.replace(" ", "_")
    # 移除无效字符: / \ : * ? " < > |
    sanitized_name = re.sub(r'[\\/*?:"<>|]', "", sanitized_name)
    # 移除控制字符
    sanitized_name = re.sub(r'[\x00-\x1f\x7f]', '', sanitized_name)
    # 限制长度（可选）
    sanitized_name = sanitized_name[:100] # 限制文件名长度为100个字符
    
    # 如果清理后名称变为空，使用 flow_id
    if not sanitized_name:
         logger.warning(f"Flow ID '{fallback_id}' 的名称 '{name}' 清理后为空，将使用 ID 作为文件名。")
         return f"{fallback_id}.json"
         
    return f"{sanitized_name}.json"

# --- 主逻辑 ---
def export_flows():
    logger.info(f"开始从 SQLite 文件 '{DATABASE_URL}' 导出用户 '{owner_id_to_export}' 的流程图数据...")
    logger.info(f"输出目录: {output_dir}")

    # 创建输出目录（如果不存在）
    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"输出目录已确认或创建: {output_dir}")
    except OSError as e:
        logger.error(f"无法创建输出目录 '{output_dir}': {e}")
        return

    engine = None
    SessionLocal = None
    try:
        # 创建数据库引擎和会话
        # For SQLite, check_same_thread=False might be needed if used in a multithreaded app context, 
        # but likely unnecessary for a simple script like this. Keeping it commented out for now.
        engine = create_engine(DATABASE_URL) # connect_args={"check_same_thread": False} 
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("数据库引擎已创建.")
    except Exception as e:
        logger.error(f"无法创建数据库引擎或会话: {e}")
        return

    db = None
    exported_count = 0
    skipped_count = 0
    try:
        # 获取数据库会话
        db = SessionLocal()
        logger.info("数据库会话已获取.")

        # 查询指定用户的所有流程图
        logger.info(f"正在查询用户 '{owner_id_to_export}' 的流程图...")
        # Ensure the model definition matches the DB schema
        flows_to_export = db.query(Flow).filter(Flow.owner_id == owner_id_to_export).all()
        logger.info(f"找到 {len(flows_to_export)} 个流程图记录.")

        if not flows_to_export:
            logger.info("没有找到该用户的流程图，无需导出。")
            return

        # 遍历并导出每个流程图的 flow_data
        for flow in flows_to_export:
            flow_data = flow.flow_data
            flow_name = flow.name
            # Ensure flow.id is serializable/string for fallback filename
            flow_id_str = str(flow.id) 

            if flow_data is None: # 明确检查 None
                logger.warning(f"流程图 '{flow_name}' (ID: {flow_id_str}) 的 flow_data 为 None，跳过导出。")
                skipped_count += 1
                continue
                
            # SQLite 的 JSON 类型可能直接返回字符串，尝试解析
            if isinstance(flow_data, str):
                try:
                    flow_data = json.loads(flow_data)
                except json.JSONDecodeError:
                     logger.warning(f"流程图 '{flow_name}' (ID: {flow_id_str}) 的 flow_data 是字符串但无法解析为 JSON，跳过导出。内容: {flow_data[:100]}...") # Log first 100 chars
                     skipped_count += 1
                     continue

            # 确保 flow_data 是一个字典 (JSON object)
            if not isinstance(flow_data, dict):
                logger.warning(f"流程图 '{flow_name}' (ID: {flow_id_str}) 的 flow_data 不是有效的字典/JSON格式 (解析后类型: {type(flow_data)})，跳过导出。")
                skipped_count += 1
                continue

            # 生成文件名
            filename = sanitize_filename(flow_name, flow_id_str)
            filepath = os.path.join(output_dir, filename)

            try:
                # 写入 JSON 文件
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(flow_data, f, ensure_ascii=False, indent=4)
                logger.info(f"成功导出流程图 '{flow_name}' (ID: {flow_id_str}) 到: {filepath}")
                exported_count += 1
            except IOError as e:
                logger.error(f"无法写入文件 '{filepath}' (流程图 ID: {flow_id_str}): {e}")
            except TypeError as e:
                 logger.error(f"无法序列化 flow_data 为 JSON (流程图 ID: {flow_id_str}): {e}")
                 skipped_count += 1

    except SQLAlchemyError as e:
        logger.error(f"数据库查询或操作错误: {e}")
    except Exception as e:
        logger.error(f"导出过程中发生未知错误: {e}", exc_info=True) # 添加 exc_info=True 获取更详细的回溯信息
    finally:
        if db:
            db.close()
            logger.info("数据库会话已关闭.")
        # SQLite engine does not need explicit closing in this context typically

    logger.info(f"导出完成。成功导出 {exported_count} 个流程图，跳过 {skipped_count} 个。")

if __name__ == "__main__":
    export_flows() 