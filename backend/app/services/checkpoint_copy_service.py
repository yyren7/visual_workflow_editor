# backend/app/services/checkpoint_copy_service.py
import logging
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import asyncio

logger = logging.getLogger(__name__)

class CheckpointCopyService:
    """处理LangGraph checkpoints复制的服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def copy_checkpoints(
        self, 
        source_thread_id: str, 
        target_thread_id: str
    ) -> bool:
        """
        复制checkpoints从源thread_id到目标thread_id
        
        Args:
            source_thread_id: 源flow_id
            target_thread_id: 目标flow_id
            
        Returns:
            bool: 是否成功复制
        """
        try:
            logger.info(f"开始复制checkpoints: {source_thread_id} -> {target_thread_id}")
            
            # 1. 获取源thread_id的所有checkpoints
            source_checkpoints = await self._get_checkpoints_by_thread_id(source_thread_id)
            
            if not source_checkpoints:
                logger.warning(f"源thread_id {source_thread_id} 没有checkpoints")
                return True  # 没有数据也算成功
            
            logger.info(f"找到 {len(source_checkpoints)} 个checkpoint记录")
            
            # 2. 创建checkpoint_id映射表
            checkpoint_id_mapping = {}
            
            # 3. 复制checkpoints（保持顺序）
            for checkpoint_row in source_checkpoints:
                await self._copy_single_checkpoint(
                    checkpoint_row, 
                    target_thread_id, 
                    checkpoint_id_mapping
                )
            
            logger.info(f"成功复制所有checkpoints到 {target_thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"复制checkpoints失败: {e}", exc_info=True)
            # 清理可能已创建的部分数据
            await self._cleanup_partial_copy(target_thread_id)
            return False
    
    async def _get_checkpoints_by_thread_id(self, thread_id: str) -> List[Dict[str, Any]]:
        """获取指定thread_id的所有checkpoints，按创建时间排序"""
        query = """
        SELECT 
            checkpoint_id,
            parent_checkpoint_id,
            type,
            checkpoint,
            metadata,
            created_at
        FROM checkpoints 
        WHERE thread_id = :thread_id
        ORDER BY created_at ASC
        """
        
        result = self.db.execute(
            text(query), 
            {"thread_id": thread_id}
        )
        
        return [dict(row._mapping) for row in result.fetchall()]
    
    async def _copy_single_checkpoint(
        self, 
        source_checkpoint: Dict[str, Any], 
        target_thread_id: str,
        checkpoint_id_mapping: Dict[str, str]
    ) -> None:
        """复制单个checkpoint记录"""
        
        # 生成新的checkpoint_id
        old_checkpoint_id = source_checkpoint['checkpoint_id']
        new_checkpoint_id = str(uuid.uuid4())
        checkpoint_id_mapping[old_checkpoint_id] = new_checkpoint_id
        
        # 处理parent_checkpoint_id映射
        old_parent_id = source_checkpoint['parent_checkpoint_id']
        new_parent_id = None
        if old_parent_id and old_parent_id in checkpoint_id_mapping:
            new_parent_id = checkpoint_id_mapping[old_parent_id]
        
        # 复制并修改checkpoint数据中的thread_id引用
        checkpoint_data = source_checkpoint['checkpoint']
        if checkpoint_data and isinstance(checkpoint_data, dict):
            # 更新checkpoint中的thread_id引用
            checkpoint_data = self._update_thread_id_in_checkpoint(
                checkpoint_data, 
                target_thread_id
            )
        
        # 插入新的checkpoint记录
        insert_query = """
        INSERT INTO checkpoints (
            checkpoint_id,
            thread_id,
            parent_checkpoint_id,
            type,
            checkpoint,
            metadata,
            created_at
        ) VALUES (
            :checkpoint_id,
            :thread_id,
            :parent_checkpoint_id,
            :type,
            :checkpoint,
            :metadata,
            :created_at
        )
        """
        
        self.db.execute(text(insert_query), {
            "checkpoint_id": new_checkpoint_id,
            "thread_id": target_thread_id,
            "parent_checkpoint_id": new_parent_id,
            "type": source_checkpoint['type'],
            "checkpoint": json.dumps(checkpoint_data) if checkpoint_data else None,
            "metadata": json.dumps(source_checkpoint['metadata']) if source_checkpoint['metadata'] else None,
            "created_at": source_checkpoint['created_at']
        })
        
        logger.debug(f"复制checkpoint: {old_checkpoint_id} -> {new_checkpoint_id}")
    
    def _update_thread_id_in_checkpoint(
        self, 
        checkpoint_data: Dict[str, Any], 
        new_thread_id: str
    ) -> Dict[str, Any]:
        """更新checkpoint数据中的thread_id引用"""
        
        # 深度复制避免修改原数据
        updated_data = json.loads(json.dumps(checkpoint_data))
        
        # 递归更新所有thread_id字段
        def update_thread_ids(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ['thread_id', 'current_chat_id'] and isinstance(value, str):
                        obj[key] = new_thread_id
                    elif isinstance(value, (dict, list)):
                        update_thread_ids(value)
            elif isinstance(obj, list):
                for item in obj:
                    update_thread_ids(item)
        
        update_thread_ids(updated_data)
        return updated_data
    
    async def _cleanup_partial_copy(self, target_thread_id: str) -> None:
        """清理部分复制的数据"""
        try:
            cleanup_query = "DELETE FROM checkpoints WHERE thread_id = :thread_id"
            self.db.execute(text(cleanup_query), {"thread_id": target_thread_id})
            self.db.commit()
            logger.info(f"清理了thread_id {target_thread_id} 的部分复制数据")
        except Exception as e:
            logger.error(f"清理部分复制数据失败: {e}")
    
    def has_checkpoints(self, thread_id: str) -> bool:
        """检查指定thread_id是否有checkpoints"""
        query = "SELECT COUNT(*) FROM checkpoints WHERE thread_id = :thread_id"
        result = self.db.execute(text(query), {"thread_id": thread_id})
        count = result.scalar()
        return count is not None and count > 0
    
    async def delete_checkpoints(self, thread_id: str) -> bool:
        """
        删除指定thread_id的所有checkpoints
        
        Args:
            thread_id: 要删除的flow_id
            
        Returns:
            bool: 是否成功删除
        """
        try:
            logger.info(f"开始删除thread_id {thread_id} 的所有checkpoints")
            
            # 先查询有多少条记录
            count_query = "SELECT COUNT(*) FROM checkpoints WHERE thread_id = :thread_id"
            result = self.db.execute(text(count_query), {"thread_id": thread_id})
            count = result.scalar()
            
            if count == 0:
                logger.info(f"Thread_id {thread_id} 没有checkpoints，无需删除")
                return True
            
            # 删除所有相关checkpoints
            delete_query = "DELETE FROM checkpoints WHERE thread_id = :thread_id"
            self.db.execute(text(delete_query), {"thread_id": thread_id})
            self.db.commit()
            
            logger.info(f"成功删除thread_id {thread_id} 的 {count} 条checkpoint记录")
            return True
            
        except Exception as e:
            logger.error(f"删除checkpoints失败: {e}", exc_info=True)
            self.db.rollback()
            return False
    
    async def initialize_empty_checkpointer(self, thread_id: str) -> bool:
        """
        为新的flow初始化一个空的checkpointer状态
        
        Args:
            thread_id: 新flow的flow_id
            
        Returns:
            bool: 是否成功初始化
        """
        try:
            logger.info(f"开始为thread_id {thread_id} 初始化空checkpointer")
            
            # 检查是否已经有checkpoints
            if self.has_checkpoints(thread_id):
                logger.warning(f"Thread_id {thread_id} 已有checkpoints，跳过初始化")
                return True
            
            # 创建初始状态的checkpoint
            initial_checkpoint_id = str(uuid.uuid4())
            
            # 创建空的初始状态
            initial_state = {
                "thread_id": thread_id,
                "flow_id": thread_id,
                "current_step": "initial",
                "initialized": True,
                "created_at": "now"
            }
            
            # 插入初始checkpoint
            insert_query = """
            INSERT INTO checkpoints (
                checkpoint_id,
                thread_id,
                parent_checkpoint_id,
                type,
                checkpoint,
                metadata,
                created_at
            ) VALUES (
                :checkpoint_id,
                :thread_id,
                :parent_checkpoint_id,
                :type,
                :checkpoint,
                :metadata,
                NOW()
            )
            """
            
            self.db.execute(text(insert_query), {
                "checkpoint_id": initial_checkpoint_id,
                "thread_id": thread_id,
                "parent_checkpoint_id": None,  # 初始状态没有parent
                "type": "initial",
                "checkpoint": json.dumps(initial_state),
                "metadata": json.dumps({"initialized": True, "flow_id": thread_id})
            })
            
            self.db.commit()
            logger.info(f"成功为thread_id {thread_id} 初始化空checkpointer")
            return True
            
        except Exception as e:
            logger.error(f"初始化空checkpointer失败: {e}", exc_info=True)
            self.db.rollback()
            return False 