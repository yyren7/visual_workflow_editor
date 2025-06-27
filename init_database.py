#!/usr/bin/env python3
"""
数据库初始化脚本
创建所有必要的表，包括新添加的字段
"""

import sys
import os
sys.path.append('/workspace')

from database.connection import get_db_engine, Base
from database.models import User, Flow, Chat, FlowVariable, VersionInfo, JsonEmbedding
from sqlalchemy import text

def init_database():
    """初始化数据库"""
    print("开始初始化数据库...")
    
    try:
        # 获取引擎
        engine = get_db_engine()
        
        # 先检查数据库连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ 数据库连接正常")
        
        # 创建所有表
        print("正在创建数据库表...")
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表创建完成")
        
        # 如果是 PostgreSQL，确保 pgvector 扩展已启用
        if "postgresql" in str(engine.url):
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                    print("✅ pgvector 扩展已启用")
            except Exception as e:
                print(f"⚠️ 启用 pgvector 扩展失败: {e}")
        
        print("🎉 数据库初始化完成！")
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1) 