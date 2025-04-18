import logging
from typing import Dict, Any, Optional
import asyncio

# 导入工具实现函数
from .flow_tools import (
    create_node_func,
    connect_nodes_func,
    set_properties_func,
    ask_more_info_func,
    generate_text_func,
    create_node_tool_func,
    connect_nodes_tool_func,
    get_flow_info_tool_func
)
# 导入参数模型和结果模型
from .definitions import (
    NodeParams, ConnectionParams, PropertyParams, QuestionsParams, TextGenerationParams, 
    ToolResult,
    ToolType # 如果需要根据类型分发
)
# 导入 LLM 客户端 (如果需要在这里注入)
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM

logger = logging.getLogger(__name__)

class ToolExecutor:
    """
    负责根据工具名称和参数调用相应的工具实现函数。
    """
    
    def __init__(self, llm_client: DeepSeekLLM):
        """
        初始化 ToolExecutor。
        
        Args:
            llm_client: LLM 客户端实例，用于传递给需要调用 LLM 的工具。
        """
        self.llm_client = llm_client
        # 将工具函数映射到名称
        self.tool_functions = {
            "create_node": create_node_func,
            "connect_nodes": connect_nodes_func,
            "set_properties": set_properties_func,
            "ask_more_info": ask_more_info_func,
            "generate_text": generate_text_func,
            # 也可以使用 ToolType 枚举作为键
            # ToolType.NODE_CREATION: create_node_func,
            # ...
        }
        # 将参数模型映射到名称 (用于验证)
        self.param_models = {
            "create_node": NodeParams,
            "connect_nodes": ConnectionParams,
            "set_properties": PropertyParams,
            "ask_more_info": QuestionsParams,
            "generate_text": TextGenerationParams,
        }

    async def execute(self, tool_name: str, parameters: Dict[str, Any], db_session=None, flow_id: Optional[str] = None) -> ToolResult:
        """
        执行指定的工具。
        
        Args:
            tool_name: 要执行的工具名称 (应与 tool_functions 中的键匹配)。
            parameters: 工具所需的参数字典。
            db_session: 数据库会话 (可选, 传递给需要的工具)。
            flow_id: 当前流程图 ID (可选, 传递给需要的工具)。
            
        Returns:
            工具执行结果。
        """
        logger.info(f"Attempting to execute tool: {tool_name} with params: {parameters} for flow_id: {flow_id}")
        
        if tool_name not in self.tool_functions:
            logger.error(f"Unknown tool name: {tool_name}")
            return ToolResult(success=False, message=f"未知的工具: {tool_name}")
        
        # 获取对应的工具函数和参数模型
        tool_func = self.tool_functions[tool_name]
        param_model = self.param_models.get(tool_name)
        
        try:
            # 验证参数
            if param_model:
                # 将 flow_id 添加到参数字典中，以便 Pydantic 模型可以接收它 (如果定义了)
                # 或者，如果工具函数直接接收 flow_id，则不需要在这里添加
                # 当前 flow_tools.py 中的异步工具函数不直接接收 flow_id，而是 ToolResult 模型
                # 而同步的 *_tool_func 接收 flow_id
                # 为了兼容性，我们先尝试验证 Pydantic 模型，然后将 flow_id 传递给函数
                validated_params = param_model(**parameters)
            else:
                # 如果没有定义参数模型，直接使用原始参数 (可能不安全)
                 logger.warning(f"No parameter model defined for tool {tool_name}. Using raw params.")
                 validated_params = parameters # 或者返回错误
                 # return ToolResult(success=False, message=f"工具 {tool_name} 未定义参数模型")
            
            # 调用工具函数，传入验证后的参数和 LLM 客户端
            # 注意：validated_params 是 Pydantic 模型实例
            # 检查工具函数签名是否需要 db_session 或 flow_id
            # 当前异步函数 (create_node_func 等) 的签名是 (params: Model, llm_client: LLM)
            # 同步函数 (create_node_tool_func 等) 的签名包含 flow_id
            # 这里执行的是异步函数，它们不直接接收 flow_id。 flow_id 应该在异步函数内部需要时获取。
            # 但是，WorkflowChain 现在调用的是这里的 execute 方法，所以我们需要决定如何处理 flow_id
            
            # 方案1 (当前选择): 异步工具函数内部不使用 flow_id，依赖于之前的设置或默认行为 (需要修改工具函数)
            # 方案2: 修改异步工具函数签名以接收 flow_id
            # 方案3: 在这里根据 tool_name 调用不同的实现 (同步/异步)
            
            # --- 采用方案1的思路，异步工具函数签名不变 --- 
            # 如果需要，LLM 客户端可以传递给需要它的工具
            # result = await tool_func(validated_params, self.llm_client)
            
            # --- 尝试修改以适配新的调用方式 --- 
            # 这里需要确定 tool_func 指向的是哪个函数
            # 假设 tool_functions 映射的是异步函数 (如 create_node_func)
            # 这些异步函数签名是 (params: Model, llm_client: LLM)
            # 它们不直接接收 flow_id。 flow_id 需要在这些函数内部处理，
            # 或者我们应该在这里调用能处理 flow_id 的同步函数 ( *_tool_func)。
            
            # --- 修正：让 ToolExecutor 调用能处理 flow_id 的同步函数 --- 
            sync_tool_functions = {
                "create_node": create_node_tool_func,
                "connect_nodes": connect_nodes_tool_func,
                "get_flow_info": get_flow_info_tool_func,
                # 其他工具可能没有同步版本或不需要 flow_id
            }
            sync_param_models = {
                "create_node": NodeParams, # 使用 Pydantic 模型验证
                "connect_nodes": ConnectionParams,
                "get_flow_info": None # get_flow_info 不使用 Pydantic 模型
            }
            
            if tool_name in sync_tool_functions:
                sync_tool_func = sync_tool_functions[tool_name]
                sync_param_model = sync_param_models.get(tool_name)
                
                # 准备参数，合并 flow_id
                call_params = {**parameters, "flow_id": flow_id} 
                
                # 验证参数 (如果模型存在)
                if sync_param_model:
                     try:
                         # Pydantic 模型不一定有 flow_id，直接传递原始参数给函数
                         # validated_call_params = sync_param_model(**call_params)
                         pass # 跳过 Pydantic 验证，让函数自己处理
                     except Exception as pydantic_err:
                          logger.error(f"Parameter validation failed for sync tool {tool_name}: {pydantic_err}")
                          raise pydantic_err # 重新抛出错误
                
                # 调用同步工具函数
                # 注意：同步函数在异步方法中调用，需要使用 asyncio.to_thread
                tool_result_dict = await asyncio.to_thread(
                    sync_tool_func, 
                    **call_params # 解包参数字典
                )
                # 将字典结果转换为 ToolResult 对象
                result = ToolResult(
                    success=tool_result_dict.get("success", False),
                    message=tool_result_dict.get("message", ""),
                    data=tool_result_dict.get("node_data") or tool_result_dict.get("connection_data") or tool_result_dict.get("flow_info"),
                    error_message=tool_result_dict.get("error")
                )
                
            elif tool_name in self.tool_functions: # 回退到原来的异步工具调用
                 tool_func = self.tool_functions[tool_name]
                 param_model = self.param_models.get(tool_name)
                 if param_model:
                      validated_params = param_model(**parameters)
                 else:
                      validated_params = parameters
                 # 异步函数不接收 flow_id 或 db_session
                 result = await tool_func(validated_params, self.llm_client)
            else:
                 # 不应该到达这里，因为前面已经检查过 tool_name
                  raise ValueError(f"Tool function mapping error for {tool_name}")

            logger.info(f"Tool {tool_name} executed successfully.")
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # 返回 Pydantic 验证错误或其他执行错误
            return ToolResult(success=False, message=f"执行工具 {tool_name} 时出错: {str(e)}")

# 注意：
# 1. determine_tool_needs 的逻辑（判断是否需要工具以及需要哪个工具）
#    通常由 LangChain Agent 或特定的链来处理，它会调用 LLM 并解析其输出来决定
#    调用哪个工具以及使用什么参数。这个 Executor 只负责执行已经被决定的工具调用。
# 2. LangChain Agent 通常会直接调用注册的 Tool 对象（例如使用 @tool 装饰器或 StructuredTool 定义的函数），
#    这个 Executor 类提供了一种替代的、更手动的执行方式，或者可以被 Agent 内部使用。 