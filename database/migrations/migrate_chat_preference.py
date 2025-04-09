"""
迁移脚本：向 flows 表添加 last_interacted_chat_id 字段
"""

import sqlite3
import os
import sys
import logging
import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库路径 (假设脚本在 database/migrations/ 下，数据库在 database/ 下)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flow_editor.db")
# DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "flow_editor.db") # 另一种相对路径写法

def add_last_interacted_chat_id_column():
    """
    向 flows 表添加 last_interacted_chat_id 字段

    步骤:
    1. 检查 flows 表是否存在
    2. 检查 last_interacted_chat_id 字段是否已存在
    3. 如果字段不存在，则添加该字段
    """
    logger.info(f"开始向 flows 表添加 last_interacted_chat_id 字段...")
    logger.info(f"数据库路径: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        return False

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. 检查 flows 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flows'")
        if not cursor.fetchone():
            logger.error("flows 表不存在")
            return False
        logger.info("flows 表存在")

        # 2. 检查 flows 表中是否已有 last_interacted_chat_id 字段
        cursor.execute("PRAGMA table_info(flows)")
        columns = cursor.fetchall()
        has_field = any(col[1] == 'last_interacted_chat_id' for col in columns)

        if not has_field:
            logger.info("flows 表中不存在 last_interacted_chat_id 字段，准备添加...")

            # 3. 添加新字段到 flows 表
            # 注意：SQLite 对 ALTER TABLE 添加外键约束的支持有限，这里只添加列
            # 真实的外键约束是在 SQLAlchemy 模型层面定义的
            # ON DELETE SET NULL 行为也需要应用逻辑来保证或在支持的数据库中使用
            alter_query = """
            ALTER TABLE flows
            ADD COLUMN last_interacted_chat_id VARCHAR(36) DEFAULT NULL
            """
            # 如果需要显式引用 chats(id) 并设置 ON DELETE SET NULL (如果数据库支持)
            # alter_query = """
            # ALTER TABLE flows
            # ADD COLUMN last_interacted_chat_id VARCHAR(36)
            # REFERENCES chats(id) ON DELETE SET NULL DEFAULT NULL
            # """
            logger.info(f"执行 SQL: {alter_query.strip()}")
            cursor.execute(alter_query)

            # 再次检查确认字段已添加
            cursor.execute("PRAGMA table_info(flows)")
            columns_after = cursor.fetchall()
            has_field_after = any(col[1] == 'last_interacted_chat_id' for col in columns_after)
            if has_field_after:
                 logger.info("字段 last_interacted_chat_id 添加成功")
            else:
                 logger.error("字段添加失败，请检查 SQL 或数据库状态")
                 return False # 添加失败，返回 False

        else:
            logger.info("flows 表已有 last_interacted_chat_id 字段，无需操作")

        conn.commit()
        logger.info("向 flows 表添加 last_interacted_chat_id 字段的操作完成")
        return True

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        # 捕获更具体的 SQLite 错误
        logger.error(f"操作 flows 表时发生 SQLite 错误: {e}")
        # 打印详细错误信息，例如重复添加列的错误
        if "duplicate column name" in str(e):
             logger.warning("字段可能已存在，虽然初始检查未发现。")
             # 可以在这里决定是否算作成功
        return False
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"添加字段时发生意外错误: {e}", exc_info=True) # 使用 exc_info=True 记录堆栈跟踪
        return False
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")

if __name__ == "__main__":
    logger.info("="*20 + " 开始执行数据库迁移脚本 " + "="*20)
    success = add_last_interacted_chat_id_column()

    if success:
        logger.info("数据库迁移脚本执行成功!")
        sys.exit(0)
    else:
        logger.error("数据库迁移脚本执行失败!")
        sys.exit(1)