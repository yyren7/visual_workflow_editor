import logging
from typing import Dict, Any, Optional, List
import asyncio
from langchain_core.tools import StructuredTool

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
        # Map *synchronous* tool functions intended for the Agent
        self.agent_tool_functions = {
            "create_node": create_node_tool_func,
            "connect_nodes": connect_nodes_tool_func,
            "get_flow_info": get_flow_info_tool_func,
            # Add other sync functions if available and needed by agent
            # "set_properties": set_properties_func, # Needs a sync wrapper or agent shouldn't use directly?
            # "ask_more_info": ask_more_info_func, # Likely requires LLM call, better within agent logic?
            # "generate_text": generate_text_func # Requires LLM, better within agent?
        }
        # Map Pydantic models for argument validation for *synchronous* tools
        self.agent_param_models = {
            "create_node": NodeParams,
            "connect_nodes": ConnectionParams,
            "get_flow_info": None, # No Pydantic model for this one
            # "set_properties": PropertyParams,
            # "ask_more_info": QuestionsParams,
            # "generate_text": TextGenerationParams,
        }
        # Add descriptions for the Agent tools
        self.agent_tool_descriptions = {
             "create_node": "Creates a new node in the workflow diagram. Specify node type, label, position, etc.",
             "connect_nodes": "Connects two nodes in the workflow diagram using their source and target handles.",
             "get_flow_info": "Retrieves information about the current workflow, such as nodes, connections, and variables.",
             # Add descriptions for other agent tools
        }

    def get_langchain_tools(self) -> List[StructuredTool]:
        """Creates and returns a list of Langchain StructuredTool objects for the agent."""
        langchain_tools = []
        for name, func in self.agent_tool_functions.items():
            description = self.agent_tool_descriptions.get(name, f"Executes the {name} tool.") # Default description
            args_schema = self.agent_param_models.get(name)

            # Ensure the function is actually callable (it should be)
            if not callable(func):
                 logger.warning(f"Tool function for '{name}' is not callable. Skipping.")
                 continue

            try:
                 tool = StructuredTool.from_function(
                     func=func,
                     name=name,
                     description=description,
                     args_schema=args_schema,
                     # handle_tool_error=True, # Consider adding error handling
                 )
                 langchain_tools.append(tool)
                 logger.debug(f"Successfully created StructuredTool for: {name}")
            except Exception as e:
                 logger.error(f"Failed to create StructuredTool for '{name}': {e}", exc_info=True)

        logger.info(f"Generated {len(langchain_tools)} Langchain tools.")
        return langchain_tools

    async def execute(self, tool_name: str, parameters: Dict[str, Any], db_session=None, flow_id: Optional[str] = None) -> ToolResult:
        """Executes the specified tool (used internally or potentially by custom logic)."""
        logger.info(f"Attempting to execute tool: {tool_name} with params: {parameters} for flow_id: {flow_id}")

        # Use the agent_tool_functions map for execution consistency
        if tool_name not in self.agent_tool_functions:
            # Maybe check other internal function maps if needed, or just error out
            logger.error(f"Unknown or non-agent tool name provided to execute: {tool_name}")
            return ToolResult(success=False, message=f"未知或非代理可用工具: {tool_name}")

        tool_func = self.agent_tool_functions[tool_name]
        param_model = self.agent_param_models.get(tool_name)

        try:
            # Prepare parameters, including flow_id needed by sync funcs
            call_params = {**parameters, "flow_id": flow_id}

            # Validate parameters using Pydantic model IF one exists
            if param_model:
                try:
                    # Create model instance ONLY with keys defined in the model
                    # Pydantic v2 automatically ignores extra fields by default
                    # For Pydantic v1, might need: validated_params = param_model.parse_obj(parameters)
                    validated_params_dict = param_model(**parameters).dict()
                    # Re-add flow_id if it's not part of the Pydantic model but needed by the function
                    call_params_for_func = {**validated_params_dict, "flow_id": flow_id}
                    logger.debug(f"Validated params for {tool_name}: {validated_params_dict}")
                except Exception as pydantic_err:
                     logger.error(f"Parameter validation failed for tool {tool_name} using {param_model.__name__}: {pydantic_err}")
                     raise pydantic_err # Re-raise validation error
            else:
                 # No Pydantic model, pass parameters directly (including flow_id)
                 call_params_for_func = call_params
                 logger.debug(f"No Pydantic model for {tool_name}, using raw params: {call_params_for_func}")


            # Execute the synchronous tool function in a separate thread
            tool_result_dict = await asyncio.to_thread(
                tool_func,
                **call_params_for_func # Pass validated & prepared args
            )

            # Convert dict result to ToolResult object
            result = ToolResult(
                success=tool_result_dict.get("success", False),
                message=tool_result_dict.get("message", ""),
                data=tool_result_dict.get("node_data") or tool_result_dict.get("connection_data") or tool_result_dict.get("flow_info"), # Adapt based on tool output keys
                error_message=tool_result_dict.get("error")
            )

            logger.info(f"Tool {tool_name} executed. Success: {result.success}")
            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
            return ToolResult(success=False, message=f"执行工具 {tool_name} 时出错: {str(e)}")

# 注意：
# 1. determine_tool_needs 的逻辑（判断是否需要工具以及需要哪个工具）
#    通常由 LangChain Agent 或特定的链来处理，它会调用 LLM 并解析其输出来决定
#    调用哪个工具以及使用什么参数。这个 Executor 只负责执行已经被决定的工具调用。
# 2. LangChain Agent 通常会直接调用注册的 Tool 对象（例如使用 @tool 装饰器或 StructuredTool 定义的函数），
#    这个 Executor 类提供了一种替代的、更手动的执行方式，或者可以被 Agent 内部使用。 