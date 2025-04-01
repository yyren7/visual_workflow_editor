"""
迁移脚本：将user_flow_preferences表的数据合并到users表中
添加last_selected_flow_id字段到users表，并迁移现有数据
"""

import sqlite3
import os
import sys
import logging
import datetime

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flow_editor.db")

def migrate_user_preferences():
    """
    将用户流程图偏好数据从user_flow_preferences表合并到users表
    
    步骤:
    1. 向users表添加last_selected_flow_id字段
    2. 将user_flow_preferences表中的数据迁移到users表
    3. 删除user_flow_preferences表
    """
    logger.info("开始迁移用户流程图偏好数据...")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查users表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.error("users表不存在")
            return False
        
        # 检查user_flow_preferences表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_flow_preferences'")
        has_preferences_table = cursor.fetchone() is not None
        
        # 检查users表中是否已有last_selected_flow_id字段
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        has_last_selected_field = any(col[1] == 'last_selected_flow_id' for col in columns)
        
        if not has_last_selected_field:
            logger.info("向users表添加last_selected_flow_id字段...")
            
            # 添加新字段到users表
            cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN last_selected_flow_id VARCHAR(36) 
            REFERENCES flows(id) ON DELETE SET NULL
            """)
            logger.info("字段添加成功")
        else:
            logger.info("users表已有last_selected_flow_id字段")
        
        # 如果user_flow_preferences表存在，迁移数据
        if has_preferences_table:
            logger.info("从user_flow_preferences表迁移数据...")
            
            # 获取所有用户偏好
            cursor.execute("""
            SELECT user_id, last_selected_flow_id FROM user_flow_preferences
            """)
            preferences = cursor.fetchall()
            
            # 更新users表
            for user_id, flow_id in preferences:
                if flow_id:  # 只在flow_id非空时更新
                    cursor.execute("""
                    UPDATE users SET last_selected_flow_id = ? WHERE id = ?
                    """, (flow_id, user_id))
                    logger.info(f"已更新用户 {user_id} 的最后选择流程: {flow_id}")
            
            # 验证迁移
            cursor.execute("""
            SELECT COUNT(*) FROM users WHERE last_selected_flow_id IS NOT NULL
            """)
            users_with_preference = cursor.fetchone()[0]
            
            logger.info(f"共有 {len(preferences)} 条偏好记录，已迁移 {users_with_preference} 条到users表")
            
            # 删除旧表
            logger.info("删除user_flow_preferences表...")
            cursor.execute("DROP TABLE user_flow_preferences")
        
        conn.commit()
        logger.info("用户流程图偏好数据迁移完成")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"迁移用户流程图偏好数据时出错: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate_user_preferences()
    
    if success:
        logger.info("数据库迁移成功!")
        sys.exit(0)
    else:
        logger.error("数据库迁移失败!")
        sys.exit(1) 