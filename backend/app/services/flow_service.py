from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging
import datetime
import uuid
import json

from database.models import Flow, Chat
from backend.app.services.flow_variable_service import FlowVariableService
from fastapi import Depends

logger = logging.getLogger(__name__)

class FlowService:
    """流程图服务 - 只负责数据库操作，状态管理由 LangGraph 负责"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_flows(self, owner_id: Optional[str] = None, limit: int = 100) -> List[Flow]:
        """
        获取流程图列表
        
        Args:
            owner_id: 所有者ID，如果提供则只返回该用户的流程图
            limit: 最大返回数量
            
        Returns:
            流程图列表
        """
        query = self.db.query(Flow)
        
        if owner_id is not None:
            query = query.filter(Flow.owner_id == owner_id)
            
        query = query.order_by(Flow.updated_at.desc()).limit(limit)
        return query.all()
    
    async def get_flow(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取流程图详情（只包含数据库信息）
        
        Args:
            flow_id: 流程图ID (string UUID)
            
        Returns:
            流程图详情，如果不存在则返回None
        """
        flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
        if not flow:
            return None
            
        # 如果flow_data字段为None，初始化为空字典
        flow_data = flow.flow_data or {}
        
        # 返回流程图元数据
        result = {
            "id": flow.id,
            "name": flow.name,
            "owner_id": flow.owner_id,
            "flow_data": flow_data,
            "created_at": flow.created_at.isoformat() if flow.created_at is not None else None,
            "updated_at": flow.updated_at.isoformat() if flow.updated_at is not None else None,
            "last_interacted_chat_id": flow.last_interacted_chat_id
        }
        
        return result
    
    async def get_flow_instance(self, flow_id: str) -> Optional[Flow]:
        """
        获取 Flow 模型实例

        Args:
            flow_id: 流程图ID (string UUID)

        Returns:
            Flow 模型实例，如果不存在则返回 None
        """
        flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
        return flow
    
    async def create_flow(self, owner_id: str, name: Optional[str] = None, data: Optional[dict] = None) -> Flow:
        """
        创建新的流程图（只创建数据库记录）
        
        Args:
            owner_id: 所有者ID (UUID字符串)
            name: 流程图名称
            data: 流程图数据
            
        Returns:
            创建的流程图
        """
        try:
            # 如果未提供name，使用默认名称
            if name is None:
                name = f"Untitled Flow {datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # 初始化 flow_data
            flow_data = data or {}
                
            # 创建新的流程图
            flow = Flow(
                owner_id=owner_id,
                name=name,
                flow_data=flow_data,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            
            self.db.add(flow)
            self.db.commit()
            self.db.refresh(flow)
            
            # 初始化流程图变量
            sync_variable_service = FlowVariableService(self.db)
            sync_variable_service.initialize_flow_variables(str(flow.id))
            
            logger.info(f"Created flow {flow.id} for user {owner_id}")
            return flow
            
        except Exception as e:
            logger.error(f"创建流程图时发生未预料的错误: {str(e)}", exc_info=True)
            try:
                self.db.rollback()
                logger.info("数据库事务因创建流程图时发生错误已回滚。")
            except Exception as rb_exc:
                logger.error(f"回滚数据库事务时额外发生错误: {rb_exc}", exc_info=True)
            raise
    
    async def update_flow(self, flow_id: str, data: Dict[str, Any], name: Optional[str] = None) -> bool:
        """
        更新流程图
        
        Args:
            flow_id: 流程图ID (string UUID)
            data: 流程图数据
            name: 流程图名称
            
        Returns:
            是否成功
        """
        try:
            # 查找流程图
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"要更新的流程图不存在: {flow_id}")
                return False
                
            # 更新数据 - 使用setattr避免类型检查问题
            if data is not None:
                setattr(flow, 'flow_data', data)
            setattr(flow, 'updated_at', datetime.datetime.utcnow())
            
            # 如果提供了名称，也更新名称
            if name is not None:
                setattr(flow, 'name', name)
                
            self.db.commit()
            
            logger.info(f"流程图更新成功: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新流程图失败: {str(e)}")
            return False
    
    async def delete_flow(self, flow_id: str) -> bool:
        """
        删除流程图
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            是否成功
        """
        try:
            # 查找流程图
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"要删除的流程图不存在: {flow_id}")
                return False
            
            # 在删除流程图之前，先删除所有关联的聊天记录
            self.db.query(Chat).filter(Chat.flow_id == flow_id).delete(synchronize_session=False)

            # 删除流程图
            self.db.delete(flow)
            self.db.commit()
            
            logger.info(f"流程图删除成功: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除流程图失败: {str(e)}")
            return False 