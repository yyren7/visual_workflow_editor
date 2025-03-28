"""
节点类型提示服务

此服务负责动态获取NodeTemplateService中的节点类型，
并将其格式化为LLM可以使用的提示文本。
"""

import logging
from typing import Dict, List, Optional, Any
from backend.app.dependencies import get_node_template_service
from backend.app.services.node_template_service import NodeTemplate, NodeTemplateService

# 配置日志
logger = logging.getLogger("backend.node_type")

class NodeTypePromptService:
    """
    节点类型提示服务
    
    此服务负责从NodeTemplateService中获取节点类型信息，
    并将其格式化为LLM可用的提示文本。
    """
    
    def __init__(self):
        """初始化节点类型提示服务"""
        self._node_template_service = None
        self._node_types_cache = None
        self._formatted_prompt_cache = None
    
    def get_node_template_service(self) -> NodeTemplateService:
        """获取节点模板服务（延迟加载）"""
        if self._node_template_service is None:
            self._node_template_service = get_node_template_service()
            logger.info("节点模板服务已加载")
        return self._node_template_service
    
    def get_node_types(self) -> Dict[str, NodeTemplate]:
        """
        获取所有节点类型
        
        Returns:
            Dict[str, NodeTemplate]: 节点模板字典，键为模板类型
        """
        if self._node_types_cache is None:
            template_service = self.get_node_template_service()
            self._node_types_cache = template_service.templates
            logger.info(f"已加载 {len(self._node_types_cache)} 个节点类型")
        return self._node_types_cache
    
    def get_node_types_enum(self) -> List[str]:
        """
        获取所有节点类型名称列表，用于枚举值
        
        Returns:
            List[str]: 节点类型名称列表
        """
        node_types = self.get_node_types()
        return list(node_types.keys())
    
    def get_node_types_prompt_text(self) -> str:
        """
        获取格式化的节点类型提示文本
        
        Returns:
            str: 格式化的节点类型提示文本，用于LLM提示
        """
        if self._formatted_prompt_cache is not None:
            return self._formatted_prompt_cache
            
        node_types = self.get_node_types()
        
        # 如果没有节点类型，返回默认的标准节点类型
        if not node_types:
            logger.warning("未找到节点类型，使用默认标准类型")
            default_text = """节点类型说明:
- start: 开始节点 (绿色，每个流程图必须有一个)
- end: 结束节点 (红色，每个流程图至少有一个)
- process: 处理节点 (蓝色，表示一个操作或行动)
- decision: 决策节点 (黄色，具有多个输出路径的判断点)
- io: 输入输出节点 (紫色，表示数据输入或输出)
- data: 数据节点 (青色，表示数据存储或检索)"""
            self._formatted_prompt_cache = default_text
            return default_text
        
        # 格式化节点类型提示文本
        prompt_lines = ["节点类型说明:"]
        
        # 必须包含的基本节点类型
        standard_types = {
            "start": "开始节点 (绿色，每个流程图必须有一个)",
            "end": "结束节点 (红色，每个流程图至少有一个)",
            "process": "处理节点 (蓝色，表示一个操作或行动)",
            "decision": "决策节点 (黄色，具有多个输出路径的判断点)"
        }
        
        # 先添加标准节点类型
        for type_name, description in standard_types.items():
            prompt_lines.append(f"- {type_name}: {description}")
        
        # 再添加自定义节点类型
        for type_name, template in node_types.items():
            # 跳过已添加的标准类型
            if type_name in standard_types:
                continue
                
            # 格式化描述
            type_description = template.description if hasattr(template, 'description') and template.description else f"{template.label} 类型节点"
            
            # 添加字段信息(如果有)
            fields_info = ""
            if hasattr(template, 'fields') and template.fields:
                field_names = [field.get('name', '') for field in template.fields if field.get('name')]
                if field_names:
                    fields_info = f"，包含字段: {', '.join(field_names)}"
            
            prompt_lines.append(f"- {type_name}: {type_description}{fields_info}")
        
        # 组合成最终文本
        formatted_text = "\n".join(prompt_lines)
        self._formatted_prompt_cache = formatted_text
        
        logger.info(f"已生成节点类型提示文本，包含 {len(prompt_lines) - 1} 个类型")
        return formatted_text

    def build_node_type_tool_enum(self) -> List[str]:
        """
        构建用于工具定义的节点类型枚举列表
        
        Returns:
            List[str]: 节点类型枚举列表
        """
        # 获取所有模板中的类型
        custom_types = self.get_node_types_enum()
        
        # 确保包含标准节点类型
        standard_types = ["start", "end", "process", "decision", "io", "data"]
        
        # 合并并去重
        all_types = list(set(standard_types + custom_types))
        
        logger.info(f"构建了节点类型枚举列表，包含 {len(all_types)} 个类型")
        return all_types


# 提供一个简单的全局函数用于获取服务实例
def get_node_type_prompt_service():
    """获取NodeTypePromptService的实例"""
    return NodeTypePromptService() 