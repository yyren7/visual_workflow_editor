from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import json
import logging

from backend.app.models import FlowVariable, Flow

logger = logging.getLogger(__name__)

class FlowVariableService:
    """流程图变量服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_variables(self, flow_id: str) -> Dict[str, str]:
        """
        获取流程图的所有变量
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            变量字典 {key: value}
        """
        try:
            # 检查流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"获取变量失败：流程图 {flow_id} 不存在")
                return {}
                
            # 查询所有变量
            variables = self.db.query(FlowVariable).filter(FlowVariable.flow_id == flow_id).all()
            
            # 转换为字典
            result = {var.key: var.value for var in variables}
            logger.info(f"获取流程图 {flow_id} 的变量成功，共 {len(result)} 个")
            return result
            
        except Exception as e:
            logger.error(f"获取流程图 {flow_id} 的变量时出错: {str(e)}")
            return {}
    
    def update_variables(self, flow_id: str, variables: Dict[str, str]) -> bool:
        """
        更新流程图的变量（替换所有现有变量）
        
        Args:
            flow_id: 流程图ID
            variables: 新的变量字典
            
        Returns:
            是否成功
        """
        try:
            # 检查流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"更新变量失败：流程图 {flow_id} 不存在")
                return False
                
            # 删除现有变量
            self.db.query(FlowVariable).filter(FlowVariable.flow_id == flow_id).delete()
            
            # 创建新变量
            for key, value in variables.items():
                var = FlowVariable(flow_id=flow_id, key=key, value=value)
                self.db.add(var)
                
            self.db.commit()
            logger.info(f"更新流程图 {flow_id} 的变量成功，共 {len(variables)} 个")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新流程图 {flow_id} 的变量时出错: {str(e)}")
            return False
    
    def add_variable(self, flow_id: str, key: str, value: str) -> bool:
        """
        添加或更新单个变量
        
        Args:
            flow_id: 流程图ID
            key: 变量名
            value: 变量值
            
        Returns:
            是否成功
        """
        try:
            # 检查流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"添加变量失败：流程图 {flow_id} 不存在")
                return False
                
            # 查找是否已存在该变量
            var = self.db.query(FlowVariable).filter(
                FlowVariable.flow_id == flow_id,
                FlowVariable.key == key
            ).first()
            
            if var:
                # 更新现有变量
                var.value = value
            else:
                # 创建新变量
                var = FlowVariable(flow_id=flow_id, key=key, value=value)
                self.db.add(var)
                
            self.db.commit()
            logger.info(f"添加/更新流程图 {flow_id} 的变量 {key} 成功")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"添加/更新流程图 {flow_id} 的变量 {key} 时出错: {str(e)}")
            return False
    
    def delete_variable(self, flow_id: str, key: str) -> bool:
        """
        删除单个变量
        
        Args:
            flow_id: 流程图ID
            key: 变量名
            
        Returns:
            是否成功
        """
        try:
            # 检查流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"删除变量失败：流程图 {flow_id} 不存在")
                return False
                
            # 删除变量
            result = self.db.query(FlowVariable).filter(
                FlowVariable.flow_id == flow_id,
                FlowVariable.key == key
            ).delete()
            
            self.db.commit()
            
            if result > 0:
                logger.info(f"删除流程图 {flow_id} 的变量 {key} 成功")
                return True
            else:
                logger.warning(f"删除变量失败：流程图 {flow_id} 中不存在变量 {key}")
                return False
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除流程图 {flow_id} 的变量 {key} 时出错: {str(e)}")
            return False
    
    def reset_variables(self, flow_id: str) -> bool:
        """
        重置流程图的所有变量（删除所有变量）
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            是否成功
        """
        try:
            # 检查流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"重置变量失败：流程图 {flow_id} 不存在")
                return False
                
            # 删除所有变量
            result = self.db.query(FlowVariable).filter(FlowVariable.flow_id == flow_id).delete()
            
            self.db.commit()
            logger.info(f"重置流程图 {flow_id} 的变量成功，删除了 {result} 个变量")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"重置流程图 {flow_id} 的变量时出错: {str(e)}")
            return False
    
    def import_variables_from_json(self, flow_id: str, json_data: str) -> bool:
        """
        从JSON字符串导入变量
        
        Args:
            flow_id: 流程图ID
            json_data: JSON字符串
            
        Returns:
            是否成功
        """
        try:
            variables = json.loads(json_data)
            if not isinstance(variables, dict):
                logger.warning(f"导入变量失败：无效的JSON格式，应为对象而不是 {type(variables)}")
                return False
                
            return self.update_variables(flow_id, variables)
            
        except json.JSONDecodeError:
            logger.error("导入变量失败：无效的JSON格式")
            return False
        except Exception as e:
            logger.error(f"从JSON导入变量时出错: {str(e)}")
            return False
    
    def export_variables_to_json(self, flow_id: str) -> str:
        """
        导出变量为JSON字符串
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            JSON字符串
        """
        try:
            variables = self.get_variables(flow_id)
            return json.dumps(variables, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"导出变量到JSON时出错: {str(e)}")
            return "{}"
    
    def initialize_flow_variables(self, flow_id: str) -> bool:
        """
        初始化流程图变量（当创建新流程图时调用）
        
        Args:
            flow_id: 流程图ID
            
        Returns:
            是否成功
        """
        try:
            # 检查流程图是否存在
            flow = self.db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.warning(f"初始化变量失败：流程图 {flow_id} 不存在")
                return False
                
            # 检查是否已有变量
            count = self.db.query(FlowVariable).filter(FlowVariable.flow_id == flow_id).count()
            if count > 0:
                logger.info(f"流程图 {flow_id} 已有 {count} 个变量，跳过初始化")
                return True
                
            # 添加一些默认变量（可选）
            # self.add_variable(flow_id, "example_key", "example_value")
            
            logger.info(f"初始化流程图 {flow_id} 的变量成功")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"初始化流程图 {flow_id} 的变量时出错: {str(e)}")
            return False 