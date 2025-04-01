"""
迁移脚本：修复flow_variables表的flow_id字段类型
从INTEGER修改为VARCHAR(36)以匹配flows表的id字段类型
"""

import sqlite3
import os
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flow_editor.db")

def migrate_flow_variables():
    """修复flow_variables表的结构"""
    logger.info("开始修复flow_variables表...")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查flow_variables表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flow_variables'")
        if not cursor.fetchone():
            logger.info("flow_variables表不存在，无需修复")
            return True
        
        # 获取表结构
        cursor.execute("PRAGMA table_info(flow_variables)")
        columns = cursor.fetchall()
        flow_id_column = next((col for col in columns if col[1] == 'flow_id'), None)
        
        if not flow_id_column:
            logger.error("flow_variables表中没有flow_id列")
            return False
        
        flow_id_type = flow_id_column[2]
        logger.info(f"当前flow_id列类型: {flow_id_type}")
        
        # 如果flow_id已经是VARCHAR(36)，则无需修复
        if flow_id_type == 'VARCHAR(36)':
            logger.info("flow_id列已经是VARCHAR(36)类型，无需修复")
            return True
        
        # 备份现有数据
        logger.info("备份flow_variables表数据...")
        cursor.execute("CREATE TABLE flow_variables_backup AS SELECT * FROM flow_variables")
        
        # 获取现有数据
        cursor.execute("SELECT id, flow_id, key, value, created_at, updated_at FROM flow_variables_backup")
        variables_data = cursor.fetchall()
        logger.info(f"备份了 {len(variables_data)} 条记录")
        
        # 删除旧表
        logger.info("删除旧的flow_variables表...")
        cursor.execute("DROP TABLE flow_variables")
        
        # 创建新表，使用正确的flow_id类型
        logger.info("创建新的flow_variables表...")
        cursor.execute("""
        CREATE TABLE flow_variables (
            id INTEGER NOT NULL, 
            flow_id VARCHAR(36) NOT NULL, 
            key VARCHAR NOT NULL, 
            value VARCHAR, 
            created_at DATETIME, 
            updated_at DATETIME, 
            PRIMARY KEY (id), 
            CONSTRAINT uix_flow_variable UNIQUE (flow_id, key), 
            FOREIGN KEY(flow_id) REFERENCES flows (id) ON DELETE CASCADE
        )
        """)
        
        # 创建索引
        logger.info("创建flow_variables表索引...")
        cursor.execute("CREATE INDEX ix_flow_variables_id ON flow_variables (id)")
        
        # 恢复数据
        if variables_data:
            logger.info("恢复数据到新表...")
            cursor.executemany(
                "INSERT INTO flow_variables (id, flow_id, key, value, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                variables_data
            )
        
        # 删除备份表
        logger.info("删除备份表...")
        cursor.execute("DROP TABLE flow_variables_backup")
        
        conn.commit()
        logger.info("flow_variables表修复完成")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"修复flow_variables表时出错: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate_flow_variables()
    
    if success:
        logger.info("数据库迁移成功!")
        sys.exit(0)
    else:
        logger.error("数据库迁移失败!")
        sys.exit(1) 