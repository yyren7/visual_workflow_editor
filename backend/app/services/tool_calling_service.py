from typing import Dict, Any, List, Optional, Union, Tuple
import json
import logging
import httpx
import os
from openai import OpenAI
from enum import Enum
from pydantic import BaseModel, Field
from backend.app.config import Config
from backend.app.services.prompt_service import BasePromptService
from backend.app.services.deepseek_client_service import DeepSeekClientService

logger = logging.getLogger(__name__)

# 单例管理
_tool_calling_service_instance = None

class ToolType(str, Enum):
    """工具类型"""
    NODE_CREATION = "node_creation"
    CONNECTION_CREATION = "connection_creation"
    PROPERTY_SETTING = "property_setting"
    ASK_MORE_INFO = "ask_more_info"
    TEXT_GENERATION = "text_generation"

class NodeParams(BaseModel):
    """节点创建参数"""
    node_type: str
    node_label: str
    position: Optional[Dict[str, float]] = None
    properties: Optional[Dict[str, Any]] = None

class ConnectionParams(BaseModel):
    """节点连接参数"""
    source_id: str
    target_id: str
    label: Optional[str] = None
    
class QuestionsParams(BaseModel):
    """追加问题参数"""
    questions: List[str]
    context: Optional[str] = None

class ToolCallRequest(BaseModel):
    """工具调用请求"""
    tool_type: ToolType
    params: Dict[str, Any]
    description: Optional[str] = None

class ToolResult(BaseModel):
    """工具调用结果"""
    success: bool
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)

class ToolCallingService(BasePromptService):
    """
    工具调用服务
    负责确定是否需要使用工具以及调用相应的工具
    """
    
    def __init__(self):
        """初始化工具调用服务"""
        super().__init__()
        
        # 使用DeepSeekClientService
        self.deepseek_service = DeepSeekClientService.get_instance()
        
        # 工具调用会话映射：用于维护不同会话的工具调用历史
        self.tool_conversation_mapping = {}
        
        # 需求分析提示模板
        self.needs_analysis_template = """
你是一个专业的流程图设计分析助手。请分析用户的需求，判断是否需要使用特定的工具。

用户输入: {input_prompt}

请判断用户的输入是否需要使用以下工具之一:
1. 节点创建工具: 创建流程图中的节点
2. 连接创建工具: 创建节点间的连接
3. 属性设置工具: 设置节点或连接的属性
4. 信息询问工具: 向用户询问更多信息
5. 文本生成工具: 生成描述性文本

如果需要使用工具，请输出以下JSON格式:
{
  "need_tool": true,
  "tool_type": "工具类型",
  "params": {
    "参数名": "参数值"
  },
  "description": "为什么需要使用这个工具的简短说明"
}

工具类型应为以下之一: "node_creation", "connection_creation", "property_setting", "ask_more_info", "text_generation"

如果不需要使用工具，请输出:
{
  "need_tool": false
}

请确保输出的JSON格式完全正确，不要添加额外的说明文本。
"""

        # 节点创建工具定义
        self.node_creation_tool_definition = {
            "type": "function",
            "function": {
                "name": "create_node",
                "description": "创建流程图节点",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_type": {
                            "type": "string",
                            "enum": ["process", "decision", "start", "end", "data", "io"],
                            "description": "节点类型"
                        },
                        "node_label": {
                            "type": "string",
                            "description": "节点标签/名称"
                        },
                        "properties": {
                            "type": "object",
                            "description": "节点属性"
                        }
                    },
                    "required": ["node_type", "node_label"]
                }
            }
        }
    
    @classmethod
    def get_instance(cls):
        """获取ToolCallingService的单例实例"""
        global _tool_calling_service_instance
        if _tool_calling_service_instance is None:
            logger.info("创建ToolCallingService单例")
            _tool_calling_service_instance = cls()
        return _tool_calling_service_instance
    
    async def determine_tool_needs(self, input_prompt: str) -> Optional[ToolCallRequest]:
        """
        确定是否需要调用工具
        
        Args:
            input_prompt: 用户输入
            
        Returns:
            工具调用请求(如果需要)或None(如果不需要)
        """
        try:
            logger.info("分析用户输入以确定是否需要工具")
            
            # 准备需求分析提示
            analysis_prompt = self.process_template(
                self.needs_analysis_template,
                {"input_prompt": input_prompt}
            )
            
            # 系统提示
            system_prompt = "你是一个专业的流程图设计分析助手，擅长分析用户需求并确定是否需要使用特定工具。"
            
            # 定义分析结果结构
            analysis_schema = {
                "type": "object",
                "properties": {
                    "need_tool": {"type": "boolean"},
                    "tool_type": {"type": "string"},
                    "params": {"type": "object"},
                    "description": {"type": "string"}
                },
                "required": ["need_tool"]
            }
            
            # 使用DeepSeek客户端进行结构化输出调用
            result, success = await self.deepseek_service.structured_output(
                prompt=analysis_prompt,
                system_prompt=system_prompt,
                schema=analysis_schema
            )
            
            if not success:
                logger.error("工具需求分析失败")
                return None
            
            # 解析结果
            need_tool = result.get("need_tool", False)
            
            if not need_tool:
                logger.info("不需要使用工具")
                return None
            
            # 创建工具调用请求
            tool_type = result.get("tool_type")
            params = result.get("params", {})
            description = result.get("description", "")
            
            if not tool_type:
                logger.warning("需要工具但未指定工具类型")
                return None
            
            try:
                return ToolCallRequest(
                    tool_type=tool_type,
                    params=params,
                    description=description
                )
            except Exception as e:
                logger.error(f"创建工具调用请求时出错: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"确定工具需求时出错: {str(e)}")
            return None
    
    async def execute_tool(self, tool_request: ToolCallRequest) -> ToolResult:
        """
        执行工具调用
        
        Args:
            tool_request: 工具调用请求
            
        Returns:
            工具执行结果
        """
        try:
            tool_type = tool_request.tool_type
            params = tool_request.params
            
            logger.info(f"执行工具调用: {tool_type}")
            
            # 根据工具类型执行不同操作
            if tool_type == ToolType.NODE_CREATION:
                return await self._execute_node_creation(params)
            elif tool_type == ToolType.CONNECTION_CREATION:
                return await self._execute_connection_creation(params)
            elif tool_type == ToolType.PROPERTY_SETTING:
                return await self._execute_property_setting(params)
            elif tool_type == ToolType.ASK_MORE_INFO:
                return await self._execute_ask_more_info(params)
            elif tool_type == ToolType.TEXT_GENERATION:
                return await self._execute_text_generation(params)
            else:
                logger.warning(f"未知的工具类型: {tool_type}")
                return ToolResult(
                    success=False,
                    message=f"不支持的工具类型: {tool_type}"
                )
                
        except Exception as e:
            logger.error(f"执行工具调用时出错: {str(e)}")
            return ToolResult(
                success=False,
                message=f"工具执行失败: {str(e)}"
            )
    
    async def process_user_prompt(self, prompt: str) -> str:
        """
        处理用户提示并生成回复
        
        Args:
            prompt: 用户提示
            
        Returns:
            AI回复
        """
        try:
            # 判断是否使用DeepSeek API
            system_prompt = "你是一个专业的流程图设计助手，能够帮助用户设计和理解流程图。"
            
            # 使用DeepSeek客户端服务进行聊天完成
            response_text, success = await self.deepseek_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            
            if not success:
                logger.error("处理用户提示失败")
                return "抱歉，AI服务暂时不可用，请稍后再试。"
                
            return response_text
            
        except Exception as e:
            logger.error(f"处理用户提示时出错: {str(e)}")
            return f"处理失败: {str(e)}"
    
    def create_new_tool_conversation(self, system_message: str = None) -> str:
        """
        创建新的工具调用对话
        
        Args:
            system_message: 可选的系统消息
            
        Returns:
            对话ID
        """
        # 使用DeepSeek客户端服务创建对话
        default_system_message = "你是一个专业的流程图设计工具助手，能够处理各种工具调用需求。"
        conversation_id = self.deepseek_service.create_conversation(
            system_message=system_message or default_system_message
        )
        
        logger.info(f"创建新的工具调用对话: {conversation_id}")
        return conversation_id
    
    async def generate_node_properties(self, node_type: str, node_label: str) -> Tuple[Dict[str, Any], bool]:
        """
        根据节点类型和标签生成推荐的节点属性
        
        Args:
            node_type: 节点类型
            node_label: 节点标签
            
        Returns:
            (推荐的属性, 是否成功)
        """
        try:
            prompt = f"""请为以下流程图节点生成合适的属性：
            
节点类型: {node_type}
节点标签: {node_label}

请生成一个属性对象，属性名应该反映该类型节点的常见特性。
"""
            
            # 使用DeepSeek客户端服务进行结构化输出
            properties_schema = {
                "type": "object",
                "properties": {
                    "properties": {
                        "type": "object",
                        "description": "节点的属性键值对"
                    }
                },
                "required": ["properties"]
            }
            
            result, success = await self.deepseek_service.structured_output(
                prompt=prompt,
                system_prompt="你是一个流程图节点属性专家，擅长为不同类型的节点推荐合适的属性。",
                schema=properties_schema
            )
            
            if not success or "properties" not in result:
                logger.error("生成节点属性失败")
                return {}, False
                
            return result["properties"], True
            
        except Exception as e:
            logger.error(f"生成节点属性时出错: {str(e)}")
            return {}, False
    
    async def ask_more_info(self, params: Dict[str, Any]) -> ToolResult:
        """询问更多信息工具实现"""
        try:
            questions = params.get("questions", [])
            context = params.get("context", "")
            
            if not questions:
                return ToolResult(
                    success=False,
                    message="未提供问题"
                )
            
            result = {
                "questions": questions,
                "context": context
            }
            
            return ToolResult(
                success=True,
                message="成功生成问题",
                data=result
            )
        except Exception as e:
            logger.error(f"生成问题时出错: {str(e)}")
            return ToolResult(
                success=False,
                message=f"生成问题失败: {str(e)}"
            )
    
    # 工具实现方法
    async def _execute_node_creation(self, params: Dict[str, Any]) -> ToolResult:
        """节点创建工具实现"""
        try:
            node_type = params.get("node_type")
            node_label = params.get("node_label")
            properties = params.get("properties", {})
            
            if not node_type or not node_label:
                return ToolResult(
                    success=False,
                    message="缺少必要的节点参数"
                )
            
            # 生成节点ID
            node_id = f"node_{str(uuid.uuid4())[:8]}"
            
            # 如果没有提供属性，尝试生成
            if not properties:
                properties, _ = await self.generate_node_properties(node_type, node_label)
            
            result = {
                "node_id": node_id,
                "node_type": node_type,
                "node_label": node_label,
                "properties": properties
            }
            
            return ToolResult(
                success=True,
                message=f"成功创建节点: {node_label}",
                data=result
            )
        except Exception as e:
            logger.error(f"创建节点时出错: {str(e)}")
            return ToolResult(
                success=False,
                message=f"创建节点失败: {str(e)}"
            )
    
    async def _execute_connection_creation(self, params: Dict[str, Any]) -> ToolResult:
        """连接创建工具实现"""
        try:
            source_id = params.get("source_id")
            target_id = params.get("target_id")
            label = params.get("label", "")
            
            if not source_id or not target_id:
                return ToolResult(
                    success=False,
                    message="缺少必要的连接参数"
                )
            
            # 生成连接ID
            connection_id = f"conn_{str(uuid.uuid4())[:8]}"
            
            result = {
                "connection_id": connection_id,
                "source_id": source_id,
                "target_id": target_id,
                "label": label
            }
            
            return ToolResult(
                success=True,
                message=f"成功创建连接: {source_id} -> {target_id}",
                data=result
            )
        except Exception as e:
            logger.error(f"创建连接时出错: {str(e)}")
            return ToolResult(
                success=False,
                message=f"创建连接失败: {str(e)}"
            )
    
    async def _execute_property_setting(self, params: Dict[str, Any]) -> ToolResult:
        """属性设置工具实现"""
        try:
            element_id = params.get("element_id")
            properties = params.get("properties", {})
            
            if not element_id or not properties:
                return ToolResult(
                    success=False,
                    message="缺少必要的属性参数"
                )
            
            result = {
                "element_id": element_id,
                "properties": properties
            }
            
            return ToolResult(
                success=True,
                message=f"成功设置属性: {element_id}",
                data=result
            )
        except Exception as e:
            logger.error(f"设置属性时出错: {str(e)}")
            return ToolResult(
                success=False,
                message=f"设置属性失败: {str(e)}"
            )
    
    async def _execute_ask_more_info(self, params: Dict[str, Any]) -> ToolResult:
        """询问更多信息工具实现"""
        return await self.ask_more_info(params)
    
    async def _execute_text_generation(self, params: Dict[str, Any]) -> ToolResult:
        """文本生成工具实现"""
        try:
            prompt = params.get("prompt")
            max_length = params.get("max_length", 500)
            
            if not prompt:
                return ToolResult(
                    success=False,
                    message="缺少必要的文本生成参数"
                )
            
            # 使用DeepSeek客户端服务生成文本
            response_text, success = await self.deepseek_service.chat_completion(
                messages=[
                    {"role": "system", "content": "你是一个专业的文本生成助手，擅长根据提示生成高质量的文本内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_length
            )
            
            if not success:
                return ToolResult(
                    success=False,
                    message="文本生成失败"
                )
            
            return ToolResult(
                success=True,
                message="成功生成文本",
                data={"text": response_text}
            )
        except Exception as e:
            logger.error(f"生成文本时出错: {str(e)}")
            return ToolResult(
                success=False,
                message=f"生成文本失败: {str(e)}"
            ) 