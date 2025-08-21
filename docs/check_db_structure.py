#!/usr/bin/env python3
"""
查看数据库表结构
"""

import sys
import os
sys.path.append('/workspace')

import json
from database.connection import get_db_context
from sqlalchemy import text

def check_db_structure():
    print("🔍 检查数据库表结构")
    print("="*60)
    
    try:
        with get_db_context() as db:
            # 查看所有表
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
            
            result = db.execute(text(tables_query))
            tables = [row[0] for row in result.fetchall()]
            
            print(f"📋 找到的表: {tables}")
            
            # 重点查看checkpoint相关表
            checkpoint_tables = [t for t in tables if 'checkpoint' in t.lower()]
            
            if checkpoint_tables:
                print(f"\n🎯 Checkpoint相关表: {checkpoint_tables}")
                
                for table_name in checkpoint_tables:
                    print(f"\n{'='*40}")
                    print(f"📊 表结构: {table_name}")
                    print(f"{'='*40}")
                    
                    # 查看表结构
                    structure_query = f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position;
                    """
                    
                    result = db.execute(text(structure_query))
                    columns = result.fetchall()
                    
                    for col in columns:
                        nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                        default = f"DEFAULT {col[3]}" if col[3] else ""
                        print(f"  {col[0]:<25} {col[1]:<20} {nullable:<10} {default}")
                    
                    # 查看数据条数
                    count_query = f"SELECT COUNT(*) FROM {table_name}"
                    count = db.execute(text(count_query)).scalar()
                    print(f"\n📊 记录总数: {count}")
                    
                    # 如果是主要的checkpoints表，查看一些样本数据
                    if table_name == 'checkpoints' and count and count > 0:
                        sample_query = f"""
                        SELECT thread_id, checkpoint_id, type
                        FROM {table_name}
                        ORDER BY checkpoint_id
                        LIMIT 5
                        """
                        
                        sample_result = db.execute(text(sample_query))
                        samples = sample_result.fetchall()
                        
                        print(f"\n📝 样本数据:")
                        for sample in samples:
                            print(f"  Thread: {sample[0]}")
                            print(f"  Checkpoint: {sample[1]}")
                            print(f"  Type: {sample[2]}")
                            print(f"  ---")
            else:
                print("\n❌ 没有找到checkpoint相关的表")
                print(f"所有表: {tables}")
    
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db_structure() 