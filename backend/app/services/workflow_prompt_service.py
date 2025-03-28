from typing import Dict, Any, List, Optional, Tuple
import logging
import json
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.app.services.prompt_service import BasePromptService
from backend.app.config import Config
from backend.app.services.deepseek_client_service import DeepSeekClientService

# 使用专门的workflow日志记录器
logger = logging.getLogger("backend.workflow")

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
    expanded_prompt: Optional[str] = Field(default=None, description="扩展后的提示")
    llm_interactions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="与LLM的交互记录")

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
        
        # 初始化对话历史
        self._conversation_history = []
        
        # 工作流JSON输出模板 - 使用基本模板，不再动态获取节点类型
        self.workflow_json_template = """
你是一个专业的流程图解析助手。请根据用户输入，识别需要创建的节点和连接关系，并输出JSON格式的结果。

用户输入: {user_input}

请生成符合以下结构的JSON输出:
{
  "nodes": [
    {
      "id": "唯一ID，如node1, node2...",
      "type": "节点类型，根据系统支持的节点类型选择",
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

请确保输出的JSON格式完全正确，不要添加额外的说明文本。只需返回符合上述结构的有效JSON。
"""
        
        # 工作流工具调用定义 - 使用基本列表，不再动态获取节点类型
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
                                "description": "节点类型，请从可用节点类型中选择",
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
        处理用户输入，生成工作流的节点和连接
        
        Args:
            user_input: 用户输入
            db: 数据库会话
            
        Returns:
            工作流处理结果
        """
        try:
            # 记录处理开始
            logger.info(f"开始处理用户输入: {user_input}")
            print(f"\n======== 工作流处理开始 ========")
            print(f"用户输入: {user_input}")
            
            # 获取最近的对话历史上下文
            context = ""
            if self._conversation_history:
                # 获取最近的5轮对话
                recent_history = self._conversation_history[-5:] if len(self._conversation_history) > 5 else self._conversation_history
                context = "\n".join([f"用户: {item['user']}\n助手: {item['assistant']}" for item in recent_history])
                print(f"对话历史上下文: {context[:200]}..." if len(context) > 200 else context)
            
            # 获取所有上下文信息（流程图、全局变量、系统信息等）
            all_context_info = await self._gather_all_context_info(db)
            
            # 添加当前流程图信息到用户输入
            enriched_user_input = user_input
            if all_context_info:
                logger.info("添加上下文信息到用户输入")
                print("添加上下文信息到用户输入")
                enriched_user_input = f"{all_context_info}\n用户输入: {user_input}"
            
            # 扩展用户提示
            expanded_input = await self.expansion_service.expand_prompt(enriched_user_input, context)
            logger.info(f"扩展后的提示: {expanded_input}")
            print(f"扩展后的提示: {expanded_input}")
            
            # 检查是否是工具调用请求
            is_tool_request, tool_name, tool_params = self.expansion_service.check_direct_tool_request(user_input)
            
            # 首先尝试直接运行工具（如果是直接工具请求）
            if is_tool_request:
                logger.info(f"检测到直接工具请求: {tool_name}, 参数: {tool_params}")
                print(f"检测到直接工具请求: {tool_name}, 参数: {tool_params}")
                
                # 执行工具调用
                tool_result = await self.tool_service.execute_tool(tool_name, tool_params)
                logger.info(f"直接工具调用结果: {tool_result}")
                print(f"直接工具调用结果: {json.dumps(tool_result, ensure_ascii=False, indent=2)}")
                
                # 保存对话历史
                self._conversation_history.append({
                    "user": user_input,
                    "assistant": f"执行了{tool_name}工具: {tool_result.get('message', '')}" 
                })
                
                # 转换为响应格式
                return self._convert_tool_result_to_response(tool_result, user_input, expanded_input)
            
            # 检查是否需要工具请求来执行任务
            needs_tool_calling, tool_request = self.expansion_service.check_needs_tool_request(expanded_input)
            
            if needs_tool_calling:
                logger.info(f"需要进行工具调用: {tool_request}")
                print(f"需要进行工具调用: {tool_request}")
                
                # 首先检查是否缺少信息
                missing_info = await self.tool_service.check_missing_info(tool_request)
                
                if missing_info:
                    logger.info(f"缺少信息: {missing_info}")
                    print(f"缺少信息: {json.dumps(missing_info, ensure_ascii=False, indent=2)}")
                    
                    # 添加到对话历史
                    questions = ""
                    if "data" in missing_info and "questions" in missing_info["data"]:
                        questions = "\n".join(missing_info["data"]["questions"])
                    
                    self._conversation_history.append({
                        "user": user_input,
                        "assistant": f"我需要更多信息:\n{questions}"
                    })
                    
                    # 返回缺少的信息
                    return {
                        "user_input": user_input,
                        "expanded_input": expanded_input,
                        "step_results": [],
                        "missing_info": missing_info,
                        "expanded_prompt": expanded_input,
                        "llm_interactions": [{
                            "stage": "missing_info_check",
                            "input": tool_request,
                            "output": missing_info
                        }]
                    }
                
                # 执行工具调用
                steps_results = []
                created_nodes = {}
                interactions = []
                
                # 解析步骤
                steps = self.expansion_service.extract_steps(expanded_input)
                
                for i, step in enumerate(steps):
                    logger.info(f"处理步骤 {i+1}: {step}")
                    print(f"处理步骤 {i+1}: {step}")
                    
                    enriched_step = await self.tool_service.enrich_step_with_context(step, steps_results)
                    logger.info(f"添加上下文后的步骤: {enriched_step}")
                    
                    # 使用结构化输出获取工具定义
                    tool_action = await self.tool_service.get_tool_action(enriched_step)
                    logger.info(f"工具动作: {tool_action['tool_type'] if tool_action else 'None'}")
                    
                    # 记录工具参数
                    if tool_action:
                        print(f"工具类型: {tool_action['tool_type']}")
                        print(f"工具参数: {json.dumps(tool_action.get('tool_params', {}), ensure_ascii=False, indent=2)}")
                    
                    # 执行工具
                    if tool_action:
                        tool_result = await self.tool_service.execute_tool(
                            tool_action["tool_type"],
                            tool_action.get("tool_params", {})
                        )
                        
                        logger.info(f"工具执行结果: {tool_result}")
                        print(f"工具执行结果: {json.dumps(tool_result, ensure_ascii=False, indent=2) if isinstance(tool_result, dict) else tool_result}")
                        
                        # 保存创建的节点
                        if (tool_action["tool_type"] == "node_creation" and 
                            tool_result.get("success", False) and 
                            tool_result.get("data")):
                            
                            node_data = tool_result["data"]
                            node_id = node_data.get("node_id")
                            if node_id:
                                created_nodes[node_id] = node_data
                        
                        # 添加到步骤结果
                        step_result = {
                            "step": step,
                            "enriched_step": enriched_step,
                            "tool_action": {
                                "tool_type": tool_action["tool_type"],
                                "result": tool_result
                            }
                        }
                        steps_results.append(step_result)
                        
                        # 添加到交互记录
                        interactions.append({
                            "stage": f"step_{i+1}",
                            "input": enriched_step,
                            "output": tool_result,
                            "tool_type": tool_action["tool_type"],
                            "tool_params": tool_action.get("tool_params", {})
                        })
                    else:
                        # 没有找到合适的工具
                        logger.warning(f"步骤 '{enriched_step}' 没有找到合适的工具")
                        print(f"步骤 '{enriched_step}' 没有找到合适的工具")
                        
                        step_result = {
                            "step": step,
                            "enriched_step": enriched_step,
                            "error": "没有找到合适的工具"
                        }
                        steps_results.append(step_result)
                        
                        # 添加到交互记录
                        interactions.append({
                            "stage": f"step_{i+1}_error",
                            "input": enriched_step,
                            "output": {"error": "没有找到合适的工具"}
                        })
                
                # 生成响应摘要
                summary = await self.generate_summary(user_input, expanded_input, steps_results)
                logger.info(f"生成摘要: {summary}")
                print(f"生成摘要: {summary}")
                
                # 添加到对话历史
                self._conversation_history.append({
                    "user": user_input,
                    "assistant": summary 
                })
                
                # 构建最终响应
                result = {
                    "user_input": user_input,
                    "expanded_input": expanded_input,
                    "step_results": steps_results,
                    "created_nodes": created_nodes,
                    "summary": summary,
                    "expanded_prompt": expanded_input,
                    "llm_interactions": interactions
                }
                
                print(f"======== 工作流处理完成 ========\n")
                return result
            else:
                # 使用DeepSeek生成自然语言回复
                logger.info("生成自然语言回复")
                print("生成自然语言回复")
                
                # 系统提示
                system_prompt = """你是一个专业的流程图设计助手，帮助用户设计和创建工作流流程图。
请根据用户的需求，提供专业、简洁的回复。只回答关于流程图设计的问题，避免讨论无关话题。"""
                
                # 准备上下文
                conversation_id = self.deepseek_service.create_conversation(system_message=system_prompt)
                
                # 确保在自然语言回复中也使用增强后的输入
                # 生成自然语言回复
                response_text, success = await self.deepseek_service.chat_completion(
                    conversation_id=conversation_id,
                    user_message=expanded_input  # 使用包含全局上下文信息的扩展输入
                )
                
                if not success:
                    logger.error("生成自然语言回复失败")
                    response_text = "抱歉，我无法处理您的请求。请尝试更具体地描述您需要的流程图。"
                
                logger.info(f"自然语言回复: {response_text}")
                print(f"自然语言回复: {response_text}")
                
                # 添加到对话历史
                self._conversation_history.append({
                    "user": user_input,
                    "assistant": response_text 
                })
                
                # 返回自然语言回复
                return {
                    "user_input": user_input,
                    "expanded_input": expanded_input,
                    "step_results": [],
                    "summary": response_text,
                    "expanded_prompt": expanded_input,
                    "llm_interactions": [{
                        "stage": "natural_language_response",
                        "input": expanded_input,
                        "output": response_text
                    }]
                }
            
        except Exception as e:
            # 记录详细错误
            logger.error(f"处理用户输入时出错: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"错误详情: {error_trace}")
            print(f"处理用户输入时出错: {str(e)}")
            print(f"错误详情: {error_trace}")
            
            # 如果是空错误消息，添加更多上下文
            error_msg = str(e)
            if not error_msg:
                error_msg = "发生未知错误 (空错误消息)"
                logger.error(f"检测到空错误消息，已替换为: {error_msg}")
            
            # 添加到对话历史
            if hasattr(self, '_conversation_history'):
                self._conversation_history.append({
                    "user": user_input,
                    "assistant": f"处理请求时出错: {error_msg}"
                })
            
            # 返回错误响应
            return {
                "user_input": user_input,
                "error": error_msg,
                "expanded_prompt": user_input,
                "llm_interactions": [{
                    "stage": "error",
                    "input": user_input,
                    "output": {"error": error_msg}
                }]
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
        生成完整的工作流，包括所有节点和连接
        
        此方法直接使用结构化输出，尝试一次性生成一个完整的工作流
        
        Args:
            user_input: 用户输入
            db: 数据库会话
            
        Returns:
            WorkflowProcessResponse: 工作流处理响应
        """
        try:
            # 获取扩展后的用户输入
            enriched_user_input = await self.expansion_service.expand_prompt(user_input)
            logger.info("扩展后的用户输入准备完成")
            
            # 准备简化的提示模板 - 使用基本节点类型，不再动态获取
            simplified_template = """
你是一个专业的流程图生成专家。请根据用户输入，直接生成一个完整的流程图，包括所有必要的节点和节点之间的连接关系。

用户输入: {user_input}

请生成符合以下结构的JSON输出:
{
  "nodes": [
    {
      "id": "唯一ID，如node1, node2...",
      "type": "节点类型，根据系统支持的节点类型选择",
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

注意事项:
1. 必须包含合适的开始节点和至少一个结束节点
2. 所有节点必须通过connections连接成一个完整流程
3. 决策节点应该有多个输出连接，表示不同的决策路径
4. 节点ID必须唯一，建议使用node1, node2等格式
5. 节点位置应该合理排布，避免重叠，从上到下或从左到右布局
6. 给节点添加合适的位置坐标，确保布局合理

请确保输出的JSON格式完全正确，不要添加额外的说明文本。只需返回符合上述结构的有效JSON。
"""
            
            # 准备提示
            workflow_prompt = self.process_template(
                simplified_template,
                {"user_input": enriched_user_input}
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
            
            # 获取所有上下文信息（流程图、全局变量、系统信息等）
            all_context_info = await self._gather_all_context_info(db)
            
            # 添加上下文信息到用户输入
            if all_context_info:
                logger.info("添加上下文信息到用户输入")
                enriched_input = f"{all_context_info}\n{enriched_input if enriched_input else user_input}"
            
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
            
            # 获取所有上下文信息（流程图、全局变量、系统信息等）
            all_context_info = await self._gather_all_context_info(db)
            
            # 添加上下文信息到用户输入
            if all_context_info:
                logger.info("添加上下文信息到用户输入")
                enriched_input = f"{all_context_info}\n{enriched_input if enriched_input else user_input}"
            
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
        expanded_prompt = old_result.get("expanded_input") or old_result.get("expanded_prompt")
        llm_interactions = old_result.get("llm_interactions", [])
        
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
            error=error,
            expanded_prompt=expanded_prompt,
            llm_interactions=llm_interactions
        )
    
    def _parse_steps(self, expanded_prompt: str) -> List[str]:
        """解析扩展后的提示中的步骤"""
        steps = []
        missing_info = []
        contains_node_creation = False
        
        for line in expanded_prompt.split('\n'):
            line = line.strip()
            if line:
                # 检查是否包含节点创建指令
                if "创建" in line and any(keyword in line for keyword in ["节点", "node"]):
                    contains_node_creation = True
                
                if line.startswith("步骤"):
                    # 查找第一个冒号
                    colon_index = line.find(":")
                    if colon_index != -1:
                        step_content = line[colon_index + 1:].strip()
                        steps.append(step_content)
                elif line.startswith("缺少信息:"):
                    missing_info_item = line.replace("缺少信息:", "").strip()
                    if missing_info_item:  # 只添加非空的缺少信息
                        missing_info.append(missing_info_item)
        
        # 当存在节点创建指令时，忽略不必要的缺少信息
        if contains_node_creation and len(steps) > 0:
            return steps
            
        # 合并步骤和必要的缺少信息
        if missing_info:
            steps.extend(["缺少信息:" + item for item in missing_info])
            
        return steps 

    async def _get_current_flow_info(self, db: Session) -> str:
        """
        获取当前流程图的信息
        
        Args:
            db: 数据库会话
            
        Returns:
            流程图信息的字符串表示
        """
        try:
            # 从数据库获取当前流程图数据
            from backend.app.models import Flow
            from backend.app.services.flow_service import FlowService
            from backend.app.services.user_flow_preference_service import UserFlowPreferenceService
            
            flow_service = FlowService(db)
            
            # 尝试从全局变量获取当前活动的流程图ID
            from langchainchat.tools.flow_tools import get_active_flow_id
            flow_id = get_active_flow_id()
            
            if not flow_id:
                # 如果没有当前活动的流程图ID，尝试从用户偏好中获取
                # 获取所有流程图
                flows = flow_service.get_flows()
                
                if not flows or len(flows) == 0:
                    logger.info("没有找到现有流程图")
                    return ""
                
                # 获取最后一个流程图的所有者
                owner_id = flows[0].owner_id
                
                if owner_id:
                    # 获取用户最后选择的流程图
                    preference_service = UserFlowPreferenceService(db)
                    last_selected_flow_id = preference_service.get_last_selected_flow_id(owner_id)
                    
                    if last_selected_flow_id:
                        # 检查流程图是否存在
                        flow_exists = db.query(Flow).filter(Flow.id == last_selected_flow_id).first() is not None
                        if flow_exists:
                            flow_id = last_selected_flow_id
                            logger.info(f"使用用户 {owner_id} 最后选择的流程图: {flow_id}")
                        else:
                            # 如果流程图不存在，使用最新的流程图
                            flow_id = flows[0].id
                            logger.info(f"用户选择的流程图已不存在，使用最新的流程图: {flow_id}")
                    else:
                        # 如果用户没有选择过流程图，使用最新的流程图
                        flow_id = flows[0].id
                        logger.info(f"用户没有选择过流程图，使用最新的流程图: {flow_id}")
                else:
                    # 如果流程图没有所有者，使用最新的流程图
                    flow_id = flows[0].id
                    logger.info(f"使用最新的流程图: {flow_id}")
            
            # 获取流程图详情
            flow_data = flow_service.get_flow(flow_id)
            
            if not flow_data:
                logger.info(f"无法获取流程图 {flow_id} 的详情")
                return ""
                
            # 获取流程图基本信息
            flow = db.query(Flow).filter(Flow.id == flow_id).first()
            if not flow:
                logger.info(f"流程图 {flow_id} 不存在")
                return ""
            
            # 提取节点和连接信息
            nodes = flow_data.get("nodes", [])
            connections = flow_data.get("connections", [])
            
            # 格式化节点信息
            nodes_info = []
            for node in nodes:
                node_info = f"节点ID: {node.get('id')}, 类型: {node.get('type')}, 标签: {node.get('label')}"
                properties = node.get("properties", {})
                if properties:
                    props_str = ", ".join([f"{k}: {v}" for k, v in properties.items()])
                    node_info += f", 属性: {{{props_str}}}"
                nodes_info.append(node_info)
                
            # 格式化连接信息
            connections_info = []
            for conn in connections:
                conn_info = f"从 {conn.get('source')} 到 {conn.get('target')}"
                if conn.get('label'):
                    conn_info += f", 标签: {conn.get('label')}"
                connections_info.append(conn_info)
                
            # 组合流程图信息
            flow_info = f"流程图名称: {flow.name}\n"
            flow_info += f"流程图ID: {flow.id}\n"
            flow_info += f"所有者ID: {flow.owner_id}\n"
            flow_info += f"创建时间: {flow.created_at}\n"
            flow_info += f"更新时间: {flow.updated_at}\n"
            flow_info += f"节点数量: {len(nodes)}\n"
            if nodes_info:
                flow_info += "节点详情:\n"
                flow_info += "\n".join([f"- {info}" for info in nodes_info])
                flow_info += "\n"
            
            if connections_info:
                flow_info += f"\n连接数量: {len(connections)}\n"
                flow_info += "连接详情:\n"
                flow_info += "\n".join([f"- {info}" for info in connections_info])
            
            logger.info(f"成功获取流程图信息，节点数量: {len(nodes)}, 连接数量: {len(connections)}")
            return flow_info
            
        except Exception as e:
            logger.error(f"获取当前流程图信息时出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return ""
            
    async def _get_global_variables(self, db: Session) -> str:
        """
        获取当前流程图的变量信息
        
        Args:
            db: 数据库会话
            
        Returns:
            变量信息的字符串表示
        """
        try:
            import json
            from backend.app.services.flow_service import FlowService
            from backend.app.services.flow_variable_service import FlowVariableService
            from backend.app.services.user_flow_preference_service import UserFlowPreferenceService
            
            # 获取当前活动的流程图
            flow_service = FlowService(db)
            
            # 尝试从全局变量获取当前活动的流程图ID
            from langchainchat.tools.flow_tools import get_active_flow_id
            flow_id = get_active_flow_id()
            
            if not flow_id:
                # 如果没有当前活动的流程图ID，尝试从用户偏好中获取
                # 为了简化，我们这里使用系统中最后操作流程图的用户
                flows = flow_service.get_flows()
                if not flows or len(flows) == 0:
                    logger.info("没有找到现有流程图，无法获取变量")
                    return "当前没有活动的流程图，无法获取变量"
                
                # 获取最后一个流程图的所有者
                owner_id = flows[0].owner_id
                
                if owner_id:
                    # 获取用户最后选择的流程图
                    preference_service = UserFlowPreferenceService(db)
                    last_selected_flow_id = preference_service.get_last_selected_flow_id(owner_id)
                    
                    if last_selected_flow_id:
                        flow_id = last_selected_flow_id
                        logger.info(f"使用用户 {owner_id} 最后选择的流程图: {flow_id}")
                    else:
                        # 如果用户没有选择过流程图，使用最新的流程图
                        flow_id = flows[0].id
                        logger.info(f"用户没有选择过流程图，使用最新的流程图: {flow_id}")
                else:
                    # 如果流程图没有所有者，使用最新的流程图
                    flow_id = flows[0].id
                    logger.info(f"使用最新的流程图: {flow_id}")
            
            # 使用FlowVariableService获取变量
            variable_service = FlowVariableService(db)
            variables = variable_service.get_variables(flow_id)
            
            # 如果没有变量
            if not variables:
                logger.info(f"流程图 {flow_id} 没有变量")
                return "当前流程图没有设置变量"
            
            # 格式化变量信息
            vars_info = "流程图变量信息:\n"
            for key, value in variables.items():
                var_str = f"{key}: {json.dumps(value, ensure_ascii=False)}"
                vars_info += f"- {var_str}\n"
            
            logger.info(f"成功获取流程图 {flow_id} 的变量，共 {len(variables)} 个")
            return vars_info
            
        except Exception as e:
            logger.error(f"获取流程图变量时出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return "获取流程图变量时出错"
            
    async def _get_system_info(self) -> str:
        """
        获取系统信息
        
        Returns:
            系统信息的字符串表示
        """
        try:
            import platform
            from backend.app.config import Config
            
            system_info = "系统信息:\n"
            system_info += f"- 项目名称: {Config.PROJECT_NAME}\n"
            system_info += f"- 操作系统: {platform.system()} {platform.release()}\n"
            system_info += f"- Python版本: {platform.python_version()}\n"
            system_info += f"- 调试模式: {'启用' if Config.DEBUG else '禁用'}\n"
            
            # 尝试获取版本信息
            try:
                from backend.app.utils import get_version_info
                version_data = get_version_info()
                system_info += f"- 系统版本: {version_data.get('version', '未知')}\n"
                system_info += f"- 最后更新: {version_data.get('lastUpdated', '未知')}\n"
            except:
                system_info += "- 版本信息: 无法获取\n"
                
            logger.info("成功获取系统信息")
            return system_info
            
        except Exception as e:
            logger.error(f"获取系统信息时出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return "获取系统信息时出错"
            
    async def _get_current_user_info(self, db: Session) -> str:
        """
        获取当前用户信息
        
        Args:
            db: 数据库会话
            
        Returns:
            用户信息的字符串表示
        """
        try:
            # 注意：这里只是获取基本用户信息，不包含敏感信息如密码
            from backend.app.models import User, Flow
            
            # 尝试从最新流程图获取所有者ID
            flow_service = None
            from backend.app.services.flow_service import FlowService
            flow_service = FlowService(db)
            flows = flow_service.get_flows()
            
            if not flows or len(flows) == 0:
                logger.info("没有找到现有流程图，无法获取用户信息")
                return "未找到用户信息"
            
            owner_id = flows[0].owner_id
            if not owner_id:
                return "流程图没有关联用户"
                
            # 根据所有者ID查询用户信息
            user = db.query(User).filter(User.id == owner_id).first()
            if not user:
                return f"未找到ID为 {owner_id} 的用户"
                
            user_info = "用户信息:\n"
            user_info += f"- 用户ID: {user.id}\n"
            user_info += f"- 用户名: {user.username}\n"
            user_info += f"- 创建时间: {user.created_at}\n"
            
            # 获取用户拥有的流程图数量
            flow_count = db.query(Flow).filter(Flow.owner_id == user.id).count()
            user_info += f"- 拥有流程图数量: {flow_count}\n"
            
            logger.info(f"成功获取用户信息: {user.username}")
            return user_info
            
        except Exception as e:
            logger.error(f"获取当前用户信息时出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return "获取用户信息时出错"

    async def _gather_all_context_info(self, db: Session) -> str:
        """
        收集所有上下文信息用于DeepSeek交互
        
        Args:
            db: 数据库会话
            
        Returns:
            包含所有上下文信息的字符串
        """
        logger.info("收集所有上下文信息用于DeepSeek交互")
        
        # 收集流程图信息
        flow_info = await self._get_current_flow_info(db)
        
        # 收集用户信息
        user_info = await self._get_current_user_info(db)
        
        # 收集全局变量信息
        global_vars_info = await self._get_global_variables(db)
        
        # 收集系统信息
        system_info = await self._get_system_info()
        
        # 组合所有信息
        context_info = "===== 环境上下文信息 =====\n\n"
        
        if user_info:
            context_info += f"【用户信息】\n{user_info}\n\n"
            
        if flow_info:
            context_info += f"【流程图信息】\n{flow_info}\n\n"
            
        if global_vars_info:
            context_info += f"【全局变量】\n{global_vars_info}\n\n"
            
        if system_info:
            context_info += f"【系统信息】\n{system_info}\n\n"
            
        context_info += "===== 环境上下文信息结束 =====\n\n"
        
        logger.info("成功收集所有上下文信息")
        return context_info 