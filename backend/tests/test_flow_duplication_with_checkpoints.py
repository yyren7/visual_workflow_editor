#!/usr/bin/env python3
"""
测试流程图复制时的checkpoint复制功能
"""

import sys
import os
sys.path.append('/workspace')

import asyncio
import logging
from database.connection import get_db_context
from backend.app.services.checkpoint_copy_service import CheckpointCopyService
from sqlalchemy import text

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_checkpoint_copy():
    """测试checkpoint复制功能"""
    
    # 测试用的flow_id
    source_flow_id = "your-source-flow-id-here"  # 替换为实际的flow_id
    target_flow_id = "test-target-flow-id"
    
    try:
        with get_db_context() as db:
            checkpoint_service = CheckpointCopyService(db)
            
            # 1. 检查源flow是否有checkpoints
            logger.info(f"检查源flow {source_flow_id} 的checkpoints...")
            has_source = checkpoint_service.has_checkpoints(source_flow_id)
            logger.info(f"源flow有checkpoints: {has_source}")
            
            if not has_source:
                logger.warning("源flow没有checkpoints，跳过测试")
                return
            
            # 2. 查看源flow的checkpoint详情
            checkpoints = await checkpoint_service._get_checkpoints_by_thread_id(source_flow_id)
            logger.info(f"源flow有 {len(checkpoints)} 个checkpoints")
            
            for i, cp in enumerate(checkpoints):
                logger.info(f"Checkpoint {i+1}: ID={cp['checkpoint_id'][:8]}..., Parent={cp['parent_checkpoint_id'][:8] if cp['parent_checkpoint_id'] else None}...")
            
            # 3. 清理可能存在的目标数据
            logger.info("清理目标flow的数据...")
            await checkpoint_service._cleanup_partial_copy(target_flow_id)
            
            # 4. 执行复制
            logger.info(f"开始复制checkpoints: {source_flow_id} -> {target_flow_id}")
            success = await checkpoint_service.copy_checkpoints(source_flow_id, target_flow_id)
            
            if success:
                logger.info("复制成功！")
                
                # 5. 验证复制结果
                target_has_checkpoints = checkpoint_service.has_checkpoints(target_flow_id)
                logger.info(f"目标flow有checkpoints: {target_has_checkpoints}")
                
                if target_has_checkpoints:
                    target_checkpoints = await checkpoint_service._get_checkpoints_by_thread_id(target_flow_id)
                    logger.info(f"目标flow有 {len(target_checkpoints)} 个checkpoints")
                    
                    # 验证数量是否一致
                    if len(target_checkpoints) == len(checkpoints):
                        logger.info("✅ checkpoint数量匹配")
                    else:
                        logger.error(f"❌ checkpoint数量不匹配: 源={len(checkpoints)}, 目标={len(target_checkpoints)}")
                
                # 6. 清理测试数据
                logger.info("清理测试数据...")
                await checkpoint_service._cleanup_partial_copy(target_flow_id)
                db.commit()
                
            else:
                logger.error("复制失败")
                
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)

async def inspect_checkpoints_table():
    """检查checkpoints表的结构"""
    try:
        with get_db_context() as db:
            # 查看表结构
            result = db.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'checkpoints'
                ORDER BY ordinal_position
            """))
            
            logger.info("Checkpoints表结构:")
            for row in result.fetchall():
                logger.info(f"  {row[0]}: {row[1]}")
            
            # 查看有多少个不同的thread_id
            result = db.execute(text("""
                SELECT thread_id, COUNT(*) as checkpoint_count 
                FROM checkpoints 
                GROUP BY thread_id 
                ORDER BY checkpoint_count DESC 
                LIMIT 10
            """))
            
            logger.info("\n前10个thread_id的checkpoint数量:")
            for row in result.fetchall():
                logger.info(f"  {row[0]}: {row[1]} checkpoints")
                
    except Exception as e:
        logger.error(f"检查表结构失败: {e}", exc_info=True)

if __name__ == "__main__":
    # 如果提供了命令行参数，使用第一个参数作为源flow_id
    if len(sys.argv) > 1:
        source_flow_id = sys.argv[1]
        logger.info(f"使用命令行提供的源flow_id: {source_flow_id}")
    
    # 运行测试
    asyncio.run(inspect_checkpoints_table())
    
    # 如果有源flow_id，运行复制测试
    if len(sys.argv) > 1:
        asyncio.run(test_checkpoint_copy())
    else:
        logger.info("要测试复制功能，请提供源flow_id作为命令行参数:")
        logger.info("python test_flow_duplication_with_checkpoints.py <source_flow_id>") 