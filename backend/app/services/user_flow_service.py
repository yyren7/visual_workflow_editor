from typing import Optional
from sqlalchemy.orm import Session
import logging

from database.models import User

logger = logging.getLogger(__name__)

class UserFlowService:
    """用户流程操作服务，管理用户对流程图的偏好和操作"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_last_selected_flow_id(self, user_id: str) -> Optional[str]:
        """
        获取用户最后选择的流程图ID
        
        Args:
            user_id: 用户ID
            
        Returns:
            最后选择的流程图ID，如果不存在则返回None
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if user and user.last_selected_flow_id:
                logger.info(f"获取用户 {user_id} 最后选择的流程图ID: {user.last_selected_flow_id}")
                return user.last_selected_flow_id
            
            # 如果用户没有选择流程图，返回None
            logger.info(f"用户 {user_id} 没有设置最后选择的流程图")
            return None
        except Exception as e:
            logger.error(f"获取用户流程图偏好失败: {str(e)}")
            return None
    
    def set_last_selected_flow_id(self, user_id: str, flow_id: str) -> bool:
        """
        设置用户最后选择的流程图ID
        
        Args:
            user_id: 用户ID
            flow_id: 流程图ID
            
        Returns:
            是否成功设置
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.error(f"找不到ID为 {user_id} 的用户")
                return False
                
            # 更新用户的last_selected_flow_id字段
            user.last_selected_flow_id = flow_id
            self.db.commit()
            
            logger.info(f"设置用户 {user_id} 最后选择的流程图ID: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"设置用户流程图偏好失败: {str(e)}")
            return False 