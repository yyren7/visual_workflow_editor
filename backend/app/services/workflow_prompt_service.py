from typing import Dict, Any, List, Optional, Tuple
import logging
import json
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.app.services.prompt_service import BasePromptService
from backend.app.config import Config
from backend.app.services.deepseek_client_service import DeepSeekClientService

logger = logging.getLogger(__name__)

# 添加一个全局变量存储单例实例
_workflow_prompt_service_instance = None

# 定义工作流处理响应模型
class WorkflowProcessResponse(BaseModel):
    """工作流处理响应"""
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="创建的节点列表")
    connections: List[Dict[str, Any]] = Field(default_factory=list, description="创建的连接列表") 
    steps: List[str] = Field(default_factory=list, description="处理步骤")
    missing_info: Optional[List[str]] = Field(default=None, description="缺少的信息")
    error: Optional[str] = Field(default=None, description="错误信息")
    summary: Optional[str] = Field(default=None, description="处理结果摘要，用于聊天机器人响应")

class WorkflowPromptService(BasePromptService):
    """
    工作流Prompt服务
    集成四个特化组件，处理用户输入到流程图的全过程
    """
    
    def __init__(
        self,
        expansion_service=None,
        embedding_service=None,
        tool_service=None,
        structured_output_service=None
    ):
        super().__init__()
        # 延迟导入服务，避免循环引用
        if expansion_service is None:
            from backend.app.services.prompt_expansion_service import PromptExpansionService
            expansion_service = PromptExpansionService()
        
        if embedding_service is None:
            from backend.app.services.prompt_embedding_service import PromptEmbeddingService
            # 使用单例实例
            embedding_service = PromptEmbeddingService.get_instance()
        
        if tool_service is None:
            from backend.app.services.tool_calling_service import ToolCallingService
            tool_service = ToolCallingService()
        
        if structured_output_service is None:
            from backend.app.services.structured_output_service import StructuredOutputService
            structured_output_service = StructuredOutputService()
        
        self.expansion_service = expansion_service
        self.embedding_service = embedding_service
        self.tool_service = tool_service
        self.structured_output_service = structured_output_service
        
        # 初始化DeepSeek客户端服务
        self.deepseek_service = DeepSeekClientService.get_instance()
        
        # 工作流会话ID - 用于保持对话上下文
        self.workflow_conversation_id = None
        
        # 工作流JSON输出模板
        self.workflow_json_template = """
你是一个专业的流程图解析助手。请根据用户输入，识别需要创建的节点和连接关系，并输出JSON格式的结果。

用户输入: {user_input}

请生成符合以下结构的JSON输出:
{
  "nodes": [
    {
      "id": "唯一ID，如node1, node2...",
      "type": "节点类型，如process, decision, start, end等",
      "label": "节点标签/名称",
      "properties": {
        "属性名称": "属性值"
      }
    }
  ],
  "connections": [
    {
      "source": "源节点ID",
      "target": "目标节点ID",
      "label": "连接标签/说明"
    }
  ],
  "steps": [
    "处理步骤1",
    "处理步骤2"
  ],
  "missing_info": [
    "缺少的信息1",
    "缺少的信息2"
  ]
}

节点类型说明:
- start: 开始节点
- end: 结束节点 
- process: 处理节点
- decision: 决策节点
- io: 输入输出节点
- data: 数据节点

请确保输出的JSON格式完全正确，不要添加额外的说明文本。只需返回符合上述结构的有效JSON。
"""
    
        # 工作流工具调用定义
        self.workflow_tool_definition = [
            {
                "type": "function",
                "function": {
                    "name": "create_node",
                    "description": "创建一个流程图节点",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "node_type": {
                                "type": "string", 
                                "description": "节点类型，如process, decision, start, end等",
                                "enum": ["start", "end", "process", "decision", "io", "data"]
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
            },
            {
                "type": "function",
                "function": {
                    "name": "connect_nodes",
                    "description": "连接两个节点",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_id": {
                                "type": "string",
                                "description": "源节点ID"
                            },
                            "target_id": {
                                "type": "string",
                                "description": "目标节点ID"  
                            },
                            "label": {
                                "type": "string",
                                "description": "连接标签/说明"
                            }
                        },
                        "required": ["source_id", "target_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_missing_info",
                    "description": "请求用户提供缺少的信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "需要向用户询问的问题列表"
                            }
                        },
                        "required": ["questions"]
                    }
                }
            }
        ]
    
    @classmethod
    def get_instance(cls):
        """获取WorkflowPromptService的单例实例"""
        global _workflow_prompt_service_instance
        if _workflow_prompt_service_instance is None:
            logger.debug("创建WorkflowPromptService单例实例")
            _workflow_prompt_service_instance = cls()
        return _workflow_prompt_service_instance
    
    async def process_user_input(self, user_input: str, db: Session) -> Dict[str, Any]:
        """
        处理用户输入，创建或修改工作流程图
        
        Args:
            user_input: 用户输入
            db: 数据库会话
            
        Returns:
            处理结果
        """
        try:
            logger.info(f"开始处理用户输入: {user_input}")
            
            # 步骤1: 扩展和修正用户输入为专业步骤
            expanded_prompt = await self.expansion_service.expand_prompt(user_input)
            logger.info(f"扩展后的提示: {expanded_prompt}")
            
            # 解析扩展后的步骤
            steps = self._parse_steps(expanded_prompt)
            
            # 收集处理结果
            results = []
            missing_info = []
            created_nodes = {}  # 存储创建的节点，用于后续连接
            
            for i, step in enumerate(steps):
                step_result = {"step": step}
                
                # 如果是询问缺少的信息
                if step.startswith("缺少信息:"):
                    missing_info.append(step.replace("缺少信息:", "").strip())
                    continue
                
                # 步骤2: 根据需要使用embedding丰富上下文
                enriched_step = await self.embedding_service.enrich_with_context(step, db)
                step_result["enriched_step"] = enriched_step
                
                # 步骤3: 判断是否需要工具调用
                tool_request = await self.tool_service.determine_tool_needs(enriched_step)
                
                if tool_request:
                    # 导入所需类型
                    from backend.app.services.tool_calling_service import ToolCallRequest, ToolResult
                    
                    # 执行工具调用
                    tool_result = await self.tool_service.execute_tool(tool_request)
                    step_result["tool_action"] = {
                        "tool_type": tool_request.tool_type,
                        "result": tool_result.dict()
                    }
                    
                    # 保存创建的节点信息
                    if tool_request.tool_type == "node_creation" and tool_result.success:
                        node_id = tool_result.data.get("node_id")
                        if node_id:
                            created_nodes[node_id] = tool_result.data
                
                results.append(step_result)
            
            # 处理缺少的信息
            ask_more_info_result = None
            if missing_info:
                questions_params = {
                    "questions": missing_info,
                    "context": "根据您的描述，我需要以下额外信息来完成流程图"
                }
                ask_more_info_result = await self.tool_service.ask_more_info(questions_params)
            
            return {
                "user_input": user_input,
                "expanded_input": expanded_prompt,
                "step_results": results,
                "missing_info": ask_more_info_result.dict() if ask_more_info_result else None,
                "created_nodes": created_nodes
            }
        except Exception as e:
            logger.error(f"处理用户输入时出错: {str(e)}")
            return {
                "user_input": user_input,
                "error": str(e)
            }
            
    async def process_workflow(self, user_input: str, db: Session, use_history: bool = True) -> WorkflowProcessResponse:
        """
        使用DeepSeek模型处理工作流，支持JSON结构化输出或函数调用
        
        Args:
            user_input: 用户输入描述的工作流
            db: 数据库会话
            use_history: 是否使用会话历史
            
        Returns:
            工作流处理响应
        """
        try:
            logger.info(f"开始处理工作流: {user_input}")
            
            # 初始化会话ID（如果需要使用历史）
            if use_history and self.workflow_conversation_id is None:
                system_message = "你是一个专业的流程图设计助手，能够将用户需求转换为结构化的流程图定义。"
                self.workflow_conversation_id = self.deepseek_service.create_conversation(
                    system_message=system_message
                )
                logger.info(f"创建新的工作流会话: {self.workflow_conversation_id}")
            elif not use_history and self.workflow_conversation_id:
                # 如果不使用历史但有现有会话，则清除
                self.deepseek_service.clear_conversation(self.workflow_conversation_id)
                self.workflow_conversation_id = None
            
            # 直接使用JSON结构化输出生成完整的流程图
            return await self.generate_complete_workflow(user_input, db)
        except Exception as e:
            logger.error(f"处理工作流时出错: {str(e)}")
            return WorkflowProcessResponse(
                error=f"处理工作流失败: {str(e)}"
            )
    
    async def generate_complete_workflow(self, user_input: str, db: Session) -> WorkflowProcessResponse:
        """
        直接生成完整的流程图（包括节点和连接）
        
        Args:
            user_input: 用户输入描述的工作流
            db: 数据库会话
            
        Returns:
            包含节点和连接的工作流处理响应
        """
        try:
            logger.info(f"直接生成完整流程图: {user_input}")
            
            # 准备简化的提示模板
            simplified_template = """
你是一个专业的流程图生成专家。请根据用户输入，直接生成一个完整的流程图，包括所有必要的节点和节点之间的连接关系。

用户输入: {user_input}

请生成符合以下结构的JSON输出:
{
  "nodes": [
    {
      "id": "唯一ID，如node1, node2...",
      "type": "节点类型，如process, decision, start, end等",
      "label": "节点标签/名称",
      "properties": {
        "描述": "节点详细信息"
      },
      "position": {
        "x": 节点X坐标(整数),
        "y": 节点Y坐标(整数)
      }
    }
  ],
  "connections": [
    {
      "source": "源节点ID",
      "target": "目标节点ID",
      "label": "连接标签/说明"
    }
  ],
  "summary": "流程图整体描述"
}

节点类型说明:
- start: 开始节点 (绿色，每个流程图必须有一个)
- end: 结束节点 (红色，每个流程图至少有一个)
- process: 处理节点 (蓝色，表示一个操作或行动)
- decision: 决策节点 (黄色，具有多个输出路径的判断点)
- io: 输入输出节点 (紫色，表示数据输入或输出)
- data: 数据节点 (青色，表示数据存储或检索)

注意事项:
1. 必须包含一个start节点和至少一个end节点
2. 所有节点必须通过connections连接成一个完整流程
3. 决策节点(decision)应该有多个输出连接，表示不同的决策路径
4. 节点ID必须唯一，建议使用node1, node2等格式
5. 节点位置应该合理排布，避免重叠，从上到下或从左到右布局
6. 给节点添加合适的位置坐标，确保布局合理

请确保输出的JSON格式完全正确，不要添加额外的说明文本。只需返回符合上述结构的有效JSON。
"""
            
            # 准备提示
            workflow_prompt = self.process_template(
                simplified_template,
                {"user_input": user_input}
            )
            
            # 系统提示
            system_prompt = "你是一个专业的流程图设计助手，能够将用户需求直接转换为完整的流程图，包括节点和连接。"
            
            # 定义结构化输出的schema
            workflow_schema = {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "label": {"type": "string"},
                                "properties": {"type": "object"},
                                "position": {
                                    "type": "object", 
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "target": {"type": "string"},
                                "label": {"type": "string"}
                            }
                        }
                    },
                    "summary": {"type": "string"}
                }
            }
            
            # 调用结构化输出方法
            result, success = await self.deepseek_service.structured_output(
                prompt=workflow_prompt,
                system_prompt=system_prompt,
                schema=workflow_schema
            )
            
            if not success:
                logger.error("流程图生成失败")
                return WorkflowProcessResponse(
                    error="无法生成流程图：AI服务暂时不可用"
                )
            
            logger.info(f"流程图生成成功: {len(result.get('nodes', []))}个节点, {len(result.get('connections', []))}个连接")
            
            # 设置步骤说明
            steps = [
                f"根据输入'{user_input}'生成流程图",
                f"创建了{len(result.get('nodes', []))}个节点",
                f"建立了{len(result.get('connections', []))}个连接",
                "流程图生成完成"
            ]
            
            # 确保所有节点都有position属性
            for node in result.get("nodes", []):
                if "position" not in node:
                    # 为缺少位置信息的节点添加默认位置
                    node["position"] = {"x": 100, "y": 100}
                    
                # 确保节点有properties属性
                if "properties" not in node:
                    node["properties"] = {}
                    
                # 添加节点描述（如果有总结信息）
                if "summary" in result and not node["properties"].get("描述"):
                    node["properties"]["描述"] = f"作为{result['summary']}的一部分"
            
            # 转换结果为WorkflowProcessResponse
            return WorkflowProcessResponse(
                nodes=result.get("nodes", []),
                connections=result.get("connections", []),
                steps=steps,
                missing_info=None,  # 直接生成不需要缺失信息
                summary=result.get("summary", f"根据'{user_input}'生成了完整流程图，包含{len(result.get('nodes', []))}个节点和{len(result.get('connections', []))}个连接。")
            )
                
        except Exception as e:
            logger.error(f"生成完整流程图出错: {str(e)}")
            return WorkflowProcessResponse(
                error=f"流程图生成失败: {str(e)}"
            )
            
    async def _process_with_json_mode(self, user_input: str, db: Session, use_history: bool = True) -> WorkflowProcessResponse:
        """使用JSON结构化输出模式处理工作流"""
        try:
            # 先检查是否能从嵌入式数据库中找到类似的工作流
            # 避免每次都重新初始化embedding服务
            enriched_input = await self.embedding_service.enrich_with_context(user_input, db)
            
            # 准备提示
            workflow_prompt = self.process_template(
                self.workflow_json_template,
                {"user_input": enriched_input if enriched_input else user_input}
            )
            
            # 使用DeepSeek客户端服务进行JSON结构化输出调用
            conversation_id = self.workflow_conversation_id if use_history else None
            
            # 系统提示
            system_prompt = "你是一个专业的流程图设计助手，能够将用户需求转换为结构化的流程图定义。"
            
            # 定义结构化输出的schema
            workflow_schema = {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "label": {"type": "string"},
                                "properties": {"type": "object"}
                            }
                        }
                    },
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "target": {"type": "string"},
                                "label": {"type": "string"}
                            }
                        }
                    },
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "missing_info": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
            
            # 调用结构化输出方法
            result, success = await self.deepseek_service.structured_output(
                prompt=workflow_prompt,
                system_prompt=system_prompt,
                conversation_id=conversation_id,
                schema=workflow_schema
            )
            
            if not success:
                logger.error("DeepSeek API结构化输出调用失败")
                return WorkflowProcessResponse(
                    error="无法处理工作流：AI服务暂时不可用"
                )
            
            logger.info("DeepSeek API结构化输出调用成功")
            
            # 转换结果为WorkflowProcessResponse
            return WorkflowProcessResponse(
                nodes=result.get("nodes", []),
                connections=result.get("connections", []),
                steps=result.get("steps", []),
                missing_info=result.get("missing_info")
            )
                
        except Exception as e:
            logger.error(f"JSON模式处理工作流出错: {str(e)}")
            return WorkflowProcessResponse(
                error=f"JSON模式处理失败: {str(e)}"
            )
            
    async def _process_with_function_calling(self, user_input: str, db: Session, use_history: bool = True) -> WorkflowProcessResponse:
        """使用函数调用模式处理工作流"""
        try:
            # 先检查是否能从嵌入式数据库中找到类似的工作流
            # 避免每次都重新初始化embedding服务
            enriched_input = await self.embedding_service.enrich_with_context(user_input, db)
            enriched_input = enriched_input if enriched_input else user_input
            
            # 系统提示
            system_prompt = "你是一个专业的流程图设计助手，能够将用户需求转换为流程图节点和连接。"
            
            # 创建会话ID（如果使用历史但没有现有会话）
            conversation_id = None
            if use_history:
                if self.workflow_conversation_id is None:
                    self.workflow_conversation_id = self.deepseek_service.create_conversation(
                        system_message=system_prompt
                    )
                conversation_id = self.workflow_conversation_id
            
            # 创建函数调用响应
            nodes = []
            connections = []
            steps = []
            missing_info = []
            
            # 调用函数调用方法
            result, success = await self.deepseek_service.function_calling(
                prompt=enriched_input,
                tools=self.workflow_tool_definition,
                system_prompt=system_prompt,
                conversation_id=conversation_id
            )
            
            if not success:
                logger.error("DeepSeek API函数调用失败")
                return WorkflowProcessResponse(
                    error="无法处理工作流：AI服务暂时不可用"
                )
            
            # 处理函数调用结果
            if "tool_calls" in result:
                # 解析工具调用结果，创建节点和连接
                # 注意: 这里需要根据DeepSeek的具体函数调用格式进行调整
                tool_calls_text = result["tool_calls"]
                # 这里需要实现解析逻辑
                # 暂时返回空结果
                pass
            else:
                # 没有工具调用，保存处理步骤
                steps.append(result.get("content", "处理完成，但没有识别到具体操作"))
            
            # 构建响应
            return WorkflowProcessResponse(
                nodes=nodes,
                connections=connections,
                steps=steps,
                missing_info=missing_info if missing_info else None
            )
                
        except Exception as e:
            logger.error(f"函数调用模式处理工作流出错: {str(e)}")
            return WorkflowProcessResponse(
                error=f"函数调用模式处理失败: {str(e)}"
            )
            
    def _convert_old_result_to_response(self, old_result: Dict[str, Any]) -> WorkflowProcessResponse:
        """将旧的处理结果转换为新的响应格式"""
        nodes = []
        connections = []
        steps = []
        missing_info = None
        error = old_result.get("error")
        
        # 提取节点
        created_nodes = old_result.get("created_nodes", {})
        for node_id, node_data in created_nodes.items():
            nodes.append({
                "id": node_id,
                "type": node_data.get("node_type"),
                "label": node_data.get("node_label"),
                "properties": node_data.get("properties", {})
            })
        
        # 提取步骤
        step_results = old_result.get("step_results", [])
        for step_result in step_results:
            steps.append(step_result.get("step", ""))
        
        # 提取缺少的信息
        missing_info_data = old_result.get("missing_info")
        if missing_info_data:
            missing_info = missing_info_data.get("data", {}).get("questions", [])
        
        return WorkflowProcessResponse(
            nodes=nodes,
            connections=connections,
            steps=steps,
            missing_info=missing_info,
            error=error
        )
    
    def _parse_steps(self, expanded_prompt: str) -> List[str]:
        """解析扩展后的提示中的步骤"""
        steps = []
        for line in expanded_prompt.split('\n'):
            line = line.strip()
            if line and (line.startswith("步骤") or line.startswith("缺少信息:")):
                # 移除步骤数字前缀，但保留"缺少信息:"前缀
                if line.startswith("步骤"):
                    # 查找第一个冒号
                    colon_index = line.find(":")
                    if colon_index != -1:
                        line = line[colon_index + 1:].strip()
                steps.append(line)
        
        return steps 