import logging
from typing import Dict, Any

# 导入工具实现函数
from .flow_tools import (
    create_node_func,
    connect_nodes_func,
    set_properties_func,
    ask_more_info_func,
    generate_text_func
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

    async def execute(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """
        执行指定的工具。
        
        Args:
            tool_name: 要执行的工具名称 (应与 tool_functions 中的键匹配)。
            params: 工具所需的参数字典。
            
        Returns:
            工具执行结果。
        """
        logger.info(f"Attempting to execute tool: {tool_name} with params: {params}")
        
        if tool_name not in self.tool_functions:
            logger.error(f"Unknown tool name: {tool_name}")
            return ToolResult(success=False, message=f"未知的工具: {tool_name}")
        
        # 获取对应的工具函数和参数模型
        tool_func = self.tool_functions[tool_name]
        param_model = self.param_models.get(tool_name)
        
        try:
            # 验证参数
            if param_model:
                validated_params = param_model(**params)
            else:
                # 如果没有定义参数模型，直接使用原始参数 (可能不安全)
                 logger.warning(f"No parameter model defined for tool {tool_name}. Using raw params.")
                 validated_params = params # 或者返回错误
                 # return ToolResult(success=False, message=f"工具 {tool_name} 未定义参数模型")
            
            # 调用工具函数，传入验证后的参数和 LLM 客户端
            # 注意：validated_params 是 Pydantic 模型实例，而工具函数期望接收它
            result = await tool_func(validated_params, self.llm_client)
            
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