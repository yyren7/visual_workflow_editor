#!/usr/bin/env python3
# backend/create_flow_variables.py - 创建多个测试全局变量用于测试

import sys
import os

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from database.connection import Base, engine, get_db, SessionLocal
from database.models import User, Flow, FlowVariable
from backend.app.config import Config
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey, UniqueConstraint
import datetime

# 打印当前使用的数据库URL
print(f"使用数据库: {Config.DATABASE_URL}")

# 使用元数据方式创建表，确保即使不依赖ORM模型也能创建表
metadata = MetaData()

# 定义flow_variables表
flow_variables = Table(
    'flow_variables', 
    metadata,
    Column('id', Integer, primary_key=True, index=True),
    Column('flow_id', String(36), ForeignKey('flows.id', ondelete='CASCADE'), nullable=False),
    Column('key', String, nullable=False),
    Column('value', String, nullable=True),
    Column('created_at', String, default=str(datetime.datetime.utcnow())),
    Column('updated_at', String, default=str(datetime.datetime.utcnow())),
    UniqueConstraint('flow_id', 'key', name='uix_flow_variable')
)

try:
    # 使用ORM方式创建表
    print("尝试使用ORM创建表...")
    Base.metadata.create_all(bind=engine)
    print("ORM表创建完成")
    
    # 使用元数据方式创建表
    print("尝试使用元数据创建表...")
    metadata.create_all(engine)
    print("元数据表创建完成")
    
    print("数据库表结构创建成功！")
except Exception as e:
    print(f"创建数据库表结构时出错: {str(e)}")

# 打印数据库表结构
print("数据库表结构:")
from sqlalchemy import inspect
inspector = inspect(engine)
for table_name in inspector.get_table_names():
    print(f"表: {table_name}")
    for column in inspector.get_columns(table_name):
        print(f"  - {column['name']}: {column['type']}") 