"""
Database initialization script
用于初始化数据库结构和执行必要的迁移操作
"""

import os
import logging
import argparse

from sqlalchemy.exc import SQLAlchemyError

from database.connection import engine, Base, get_db_context
from database.models import User, Flow, FlowVariable, VersionInfo, Chat
# 导入迁移脚本
from database.migrations.fix_flow_variables import migrate_flow_variables
from database.migrations.migrate_user_preference import migrate_user_preferences

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    """创建所有数据库表"""
    try:
        logger.info("创建数据库表...")
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建成功")
        return True
    except SQLAlchemyError as e:
        logger.error(f"创建数据库表时出错: {str(e)}")
        return False

def init_database():
    """初始化数据库结构并执行必要的迁移"""
    # 确保database目录存在
    os.makedirs(os.path.dirname(engine.url.database.replace('sqlite:///', '')), exist_ok=True)
    
    # 创建数据库表
    success = create_tables()
    if not success:
        return False
        
    # 修复flow_variables表
    logger.info("修复flow_variables表...")
    success = migrate_flow_variables()
    if not success:
        logger.error("修复flow_variables表失败")
    
    # 迁移用户偏好数据
    logger.info("迁移用户流程图偏好数据...")
    success = migrate_user_preferences()
    if not success:
        logger.error("迁移用户流程图偏好数据失败")
    
    # 初始化版本信息如果需要
    with get_db_context() as db:
        version_info = db.query(VersionInfo).first()
        if not version_info:
            logger.info("初始化版本信息...")
            version_info = VersionInfo(version="0.1.0", last_updated="2024-06-01")
            db.add(version_info)
            db.commit()
            
    logger.info("数据库初始化完成")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="数据库初始化脚本")
    parser.add_argument("--force", action="store_true", help="强制重新创建表")
    args = parser.parse_args()
    
    if args.force:
        # 备份当前数据库
        logger.warning("强制重新创建表，将删除所有数据！")
        # TODO: 添加备份逻辑
        
        # 删除现有表并重新创建
        Base.metadata.drop_all(bind=engine)
        
    # 初始化数据库
    init_database() 