#!/usr/bin/env python3
"""
测试checkpoint管理功能（删除和初始化）
"""

import sys
import os
sys.path.append('/workspace')

import asyncio
import logging
from database.connection import get_db_context
from backend.app.services.checkpoint_copy_service import CheckpointCopyService
from sqlalchemy import text
import uuid

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_checkpoint_initialization():
    """测试checkpoint初始化功能"""
    
    test_flow_id = f"test-init-{str(uuid.uuid4())[:8]}"
    
    try:
        with get_db_context() as db:
            checkpoint_service = CheckpointCopyService(db)
            
            # 1. 测试初始化空checkpointer
            logger.info(f"测试初始化空checkpointer: {test_flow_id}")
            
            success = await checkpoint_service.initialize_empty_checkpointer(test_flow_id)
            if success:
                logger.info(f"✅ 成功初始化空checkpointer: {test_flow_id}")
            else:
                logger.error(f"❌ 初始化空checkpointer失败: {test_flow_id}")
                return False
            
            # 2. 验证checkpointer是否被创建
            has_checkpoints = checkpoint_service.has_checkpoints(test_flow_id)
            if has_checkpoints:
                logger.info(f"✅ 验证通过：checkpointer已创建: {test_flow_id}")
            else:
                logger.error(f"❌ 验证失败：checkpointer未创建: {test_flow_id}")
                return False
            
            # 3. 查询创建的checkpoint记录
            query = "SELECT * FROM checkpoints WHERE thread_id = :thread_id"
            result = db.execute(text(query), {"thread_id": test_flow_id})
            records = result.fetchall()
            
            logger.info(f"✅ 找到 {len(records)} 条checkpoint记录")
            for record in records:
                logger.info(f"  - checkpoint_id: {record.checkpoint_id}")
                logger.info(f"  - type: {record.type}")
                logger.info(f"  - created_at: {record.created_at}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ 测试初始化功能失败: {e}", exc_info=True)
        return False

async def test_checkpoint_deletion():
    """测试checkpoint删除功能"""
    
    test_flow_id = f"test-delete-{str(uuid.uuid4())[:8]}"
    
    try:
        with get_db_context() as db:
            checkpoint_service = CheckpointCopyService(db)
            
            # 1. 先创建一些checkpoint记录
            logger.info(f"创建测试数据: {test_flow_id}")
            
            await checkpoint_service.initialize_empty_checkpointer(test_flow_id)
            
            # 验证记录存在
            count_before = db.execute(
                text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :thread_id"),
                {"thread_id": test_flow_id}
            ).scalar()
            
            logger.info(f"删除前记录数: {count_before}")
            
            # 2. 测试删除功能
            logger.info(f"测试删除checkpointer: {test_flow_id}")
            
            success = await checkpoint_service.delete_checkpoints(test_flow_id)
            if success:
                logger.info(f"✅ 成功删除checkpointer: {test_flow_id}")
            else:
                logger.error(f"❌ 删除checkpointer失败: {test_flow_id}")
                return False
            
            # 3. 验证记录是否被删除
            count_after = db.execute(
                text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :thread_id"),
                {"thread_id": test_flow_id}
            ).scalar()
            
            logger.info(f"删除后记录数: {count_after}")
            
            if count_after == 0:
                logger.info(f"✅ 验证通过：所有checkpoint记录已删除")
                return True
            else:
                logger.error(f"❌ 验证失败：仍有 {count_after} 条记录未删除")
                return False
            
    except Exception as e:
        logger.error(f"❌ 测试删除功能失败: {e}", exc_info=True)
        return False

async def test_checkpoint_statistics():
    """显示checkpoint统计信息"""
    
    try:
        with get_db_context() as db:
            # 查询所有checkpoint记录
            result = db.execute(text("SELECT COUNT(*) FROM checkpoints"))
            total_count = result.scalar()
            
            logger.info(f"📊 数据库中总共有 {total_count} 条checkpoint记录")
            
            # 查询不同thread_id的记录数
            result = db.execute(text("""
                SELECT thread_id, COUNT(*) as count 
                FROM checkpoints 
                GROUP BY thread_id 
                ORDER BY count DESC 
                LIMIT 10
            """))
            
            logger.info("📊 最多记录的前10个thread_id:")
            for row in result.fetchall():
                logger.info(f"  - {row.thread_id}: {row.count} 条记录")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ 获取统计信息失败: {e}", exc_info=True)
        return False

async def main():
    """主测试函数"""
    
    logger.info("🚀 开始测试checkpoint管理功能")
    
    try:
        # 1. 显示统计信息
        logger.info("\n" + "="*50)
        logger.info("📊 显示checkpoint统计信息")
        logger.info("="*50)
        await test_checkpoint_statistics()
        
        # 2. 测试初始化功能
        logger.info("\n" + "="*50)
        logger.info("🔧 测试checkpoint初始化功能")
        logger.info("="*50)
        init_success = await test_checkpoint_initialization()
        
        # 3. 测试删除功能
        logger.info("\n" + "="*50)
        logger.info("🗑️  测试checkpoint删除功能")
        logger.info("="*50)
        delete_success = await test_checkpoint_deletion()
        
        # 4. 最终结果
        logger.info("\n" + "="*50)
        logger.info("📝 测试结果汇总")
        logger.info("="*50)
        
        if init_success and delete_success:
            logger.info("🎉 所有测试通过！checkpoint管理功能正常工作")
            return True
        else:
            logger.error("❌ 部分测试失败")
            if not init_success:
                logger.error("  - 初始化功能测试失败")
            if not delete_success:
                logger.error("  - 删除功能测试失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 