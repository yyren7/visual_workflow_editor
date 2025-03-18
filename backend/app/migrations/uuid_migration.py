"""
迁移脚本：将User和Flow表的整数ID转换为UUID
运行方法：python -m backend.app.migrations.uuid_migration
"""

import uuid
import sys
import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, ForeignKey, Table, MetaData, text, inspect
# 不再使用PostgreSQL的UUID类型
# from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
from alembic import op
import sqlalchemy as sa

# 导入项目配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from backend.app.config import Config

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建数据库连接
engine = create_engine(Config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 定义元数据
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# 定义原始模型（整数ID）
class OldUser(Base):
    __tablename__ = "users_old"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class OldFlow(Base):
    __tablename__ = "flows_old"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_data = Column(JSON, nullable=False, default={})
    owner_id = Column(Integer, ForeignKey("users_old.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    name = Column(String, nullable=False, default="Untitled Flow")

# 定义新模型（UUID字符串）
class NewUser(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class NewFlow(Base):
    __tablename__ = "flows"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    flow_data = Column(JSON, nullable=False, default={})
    owner_id = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    name = Column(String, nullable=False, default="Untitled Flow")

def table_exists(table_name, engine):
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def migrate_data():
    """迁移数据从整数ID到UUID"""
    logger.info("开始数据迁移...")
    
    session = SessionLocal()
    
    try:
        # 获取当前表状态
        has_users = table_exists("users", engine)
        has_flows = table_exists("flows", engine)
        has_users_old = table_exists("users_old", engine)
        has_flows_old = table_exists("flows_old", engine)
        
        # 如果old表已存在，说明已经部分迁移了，跳过表重命名步骤
        if not has_users_old and has_users:
            # 备份现有表
            logger.info("备份users表...")
            session.execute(text("ALTER TABLE users RENAME TO users_old;"))
            session.commit()
        
        if not has_flows_old and has_flows:
            logger.info("备份flows表...")
            session.execute(text("ALTER TABLE flows RENAME TO flows_old;"))
            session.commit()
        
        # 如果新表不存在，创建新表
        if not table_exists("users", engine) or not table_exists("flows", engine):
            # 创建新表
            logger.info("创建新表...")
            metadata.create_all(bind=engine)
        else:
            logger.info("新表已存在，跳过创建步骤")
        
        # 只有当旧表存在时才迁移数据
        if table_exists("users_old", engine):
            # 获取旧数据
            logger.info("获取旧数据...")
            old_users = session.query(OldUser).all()
            
            # 建立ID映射关系
            user_id_mapping = {}
            
            # 迁移用户数据
            logger.info(f"迁移{len(old_users)}个用户...")
            for old_user in old_users:
                new_uuid = str(uuid.uuid4())  # 使用字符串形式的UUID
                user_id_mapping[old_user.id] = new_uuid
                
                new_user = NewUser(
                    id=new_uuid,
                    username=old_user.username,
                    hashed_password=old_user.hashed_password,
                    created_at=old_user.created_at,
                    updated_at=old_user.updated_at
                )
                session.add(new_user)
            
            session.commit()
            
            # 只有当流程图旧表存在时才迁移流程图数据
            if table_exists("flows_old", engine):
                # 获取旧流程图数据
                old_flows = session.query(OldFlow).all()
                
                # 迁移流程图数据
                logger.info(f"迁移{len(old_flows)}个流程图...")
                for old_flow in old_flows:
                    if old_flow.owner_id in user_id_mapping:
                        new_flow = NewFlow(
                            id=str(uuid.uuid4()),  # 使用字符串形式的UUID
                            flow_data=old_flow.flow_data,
                            owner_id=user_id_mapping[old_flow.owner_id],
                            created_at=old_flow.created_at,
                            updated_at=old_flow.updated_at,
                            name=old_flow.name
                        )
                        session.add(new_flow)
                
                session.commit()
        else:
            logger.info("旧表不存在，跳过数据迁移步骤")
        
        # 确认迁移成功后可以删除旧表
        logger.info("迁移完成，可以删除旧表...")
        # 请手动确认后删除：
        # session.execute(text("DROP TABLE users_old;"))
        # session.execute(text("DROP TABLE flows_old;"))
        # session.commit()
        
        logger.info("迁移完成！")
        
    except Exception as e:
        session.rollback()
        logger.error(f"迁移失败：{str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    migrate_data() 