from typing import Optional
from sqlalchemy.orm import Session
import logging

from backend.app import models

logger = logging.getLogger(__name__)

class UserFlowPreferenceService:
    """用户流程图偏好服务"""
    
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
            preference = self.db.query(models.UserFlowPreference).filter(
                models.UserFlowPreference.user_id == user_id
            ).first()
            
            if preference and preference.last_selected_flow_id:
                logger.info(f"获取用户 {user_id} 最后选择的流程图ID: {preference.last_selected_flow_id}")
                return preference.last_selected_flow_id
            
            # 如果用户没有偏好记录，返回None
            logger.info(f"用户 {user_id} 没有流程图偏好记录")
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
            # 查找现有的偏好记录
            preference = self.db.query(models.UserFlowPreference).filter(
                models.UserFlowPreference.user_id == user_id
            ).first()
            
            if preference:
                # 更新现有记录
                preference.last_selected_flow_id = flow_id
            else:
                # 创建新记录
                preference = models.UserFlowPreference(
                    user_id=user_id,
                    last_selected_flow_id=flow_id
                )
                self.db.add(preference)
            
            self.db.commit()
            logger.info(f"设置用户 {user_id} 最后选择的流程图ID: {flow_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"设置用户流程图偏好失败: {str(e)}")
            return False 