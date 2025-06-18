from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging
import datetime
import uuid

from database.models import Flow
from backend.app.services.flow_variable_service import FlowVariableService
from backend.app.utils import get_default_agent_state

logger = logging.getLogger(__name__)

class FlowService:
    """流程图服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_flows(self, owner_id: Optional[int] = None, limit: int = 100) -> List[Flow]:
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
    
    def get_flow(self, flow_id: int) -> Optional[Dict[str, Any]]:
        """
        获取流程图详情
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            流程图详情，如果不存在则返回None
        """
        flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
        if not flow:
            return None
            
        # 如果flow_data字段为None，初始化为空字典
        flow_data = flow.flow_data or {}
        
        # 添加流程图元数据
        result = {
            "id": flow.id,
            "name": flow.name,
            "owner_id": flow.owner_id,
            "agent_state": flow.agent_state or {},  # 添加agent_state
            "created_at": flow.created_at.isoformat() if flow.created_at else None,
            "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
            **flow_data
        }
        
        return result
    
    def get_flow_instance(self, flow_id: str) -> Optional[Flow]:
        """
        获取 Flow 模型实例

        Args:
            flow_id: 流程图ID

        Returns:
            Flow 模型实例，如果不存在则返回 None
        """
        flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
        return flow
    
    def create_flow(self, owner_id: int, name: str = None, data: dict = None) -> Flow:
        """
        创建新的流程图
        
        Args:
            owner_id: 所有者ID
            name: 流程图名称
            data: 流程图数据
            
        Returns:
            创建的流程图
        """
        try:
            # 如果未提供name，使用默认名称
            if name is None:
                name = f"Untitled Flow {datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                
            # 创建新的流程图
            flow = Flow(
                owner_id=owner_id,
                name=name,
                flow_data=data or {},
                agent_state=get_default_agent_state(),  # 使用默认的agent_state
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            
            self.db.add(flow)
            self.db.commit()
            self.db.refresh(flow)
            
            # 初始化流程图变量
            variable_service = FlowVariableService(self.db)
            variable_service.initialize_flow_variables(flow.id)
            
            return flow
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建流程图失败: {str(e)}")
            raise Exception(f"创建流程图失败: {str(e)}")
    
    def update_flow(self, flow_id: int, data: Dict[str, Any], name: Optional[str] = None) -> bool:
        """
        更新流程图
        
        Args:
            flow_id: 流程图ID
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
                
            # 更新数据
            flow.flow_data = data
            flow.updated_at = datetime.datetime.utcnow()
            
            # 如果提供了名称，也更新名称
            if name is not None:
                flow.name = name
                
            self.db.commit()
            
            logger.info(f"流程图更新成功: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新流程图失败: {str(e)}")
            return False
    
    def delete_flow(self, flow_id: int) -> bool:
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
                
            # 删除流程图关联的变量（流程图删除时，关联的变量会自动删除，因为我们设置了外键的CASCADE删除）
            # variable_service = FlowVariableService(self.db)
            # variable_service.reset_variables(flow_id)
            
            # 删除流程图
            self.db.delete(flow)
            self.db.commit()
            
            logger.info(f"流程图删除成功: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除流程图失败: {str(e)}")
            return False
    
    def ensure_agent_state_fields(self, flow_id: str) -> bool:
        """
        确保流程图的 agent_state 包含所有必需的字段
        如果缺少字段，则添加默认值
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            是否进行了更新
        """
        try:
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"流程图不存在: {flow_id}")
                return False
            
            # 获取默认结构
            default_state = get_default_agent_state()
            
            # 如果 agent_state 为空，直接使用默认值
            if not flow.agent_state:
                flow.agent_state = default_state
                flow.updated_at = datetime.datetime.utcnow()
                self.db.commit()
                logger.info(f"为流程图 {flow_id} 初始化了默认 agent_state")
                return True
            
            # 检查并添加缺失的字段
            updated = False
            current_state = flow.agent_state.copy()
            
            for key, default_value in default_state.items():
                if key not in current_state:
                    current_state[key] = default_value
                    updated = True
            
            if updated:
                flow.agent_state = current_state
                flow.updated_at = datetime.datetime.utcnow()
                self.db.commit()
                logger.info(f"为流程图 {flow_id} 补充了缺失的 agent_state 字段")
                
            return updated
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"确保 agent_state 字段时失败: {str(e)}")
            return False
    
    def update_flow_agent_state(self, flow_id: str, agent_state_data: Dict[str, Any]) -> bool:
        """
        更新流程图的 LangGraph agent 状态
        
        Args:
            flow_id: 流程图ID
            agent_state_data: agent 状态数据
            
        Returns:
            是否成功
        """
        try:
            # 查找流程图
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"要更新agent状态的流程图不存在: {flow_id}")
                return False
                
            # 更新agent状态
            flow.agent_state = agent_state_data
            flow.updated_at = datetime.datetime.utcnow()
                
            self.db.commit()
            
            logger.info(f"流程图agent状态更新成功: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新流程图agent状态失败: {str(e)}")
            return False 