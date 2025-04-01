from typing import Dict, Any, List, Optional, Union
import asyncio
import json
from datetime import datetime
from sqlalchemy.orm import Session
from langchain.agents import initialize_agent, AgentType
from langchain.chains import ConversationChain, LLMChain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import re

from langchainchat.config import settings
from langchainchat.utils.logging import logger
from langchainchat.models.llm import get_chat_model
from langchainchat.memory.conversation_memory import create_memory, EnhancedConversationMemory
from langchainchat.tools.flow_tools import get_flow_tools, set_active_flow_id
from langchainchat.utils.context_collector import context_collector
from langchainchat.models.response import ChatResponse  # 导入ChatResponse类
from langchainchat.utils.translator import translator
from langchainchat.prompts.chat_prompts import (
    ENHANCED_CHAT_PROMPT_TEMPLATE,
    CHAT_PROMPT_TEMPLATE,
    CONTEXT_PROCESSING_TEMPLATE,
    TOOL_CALLING_TEMPLATE,
    ERROR_HANDLING_TEMPLATE
)

# 添加导入
try:
    from backend.app.dependencies import get_node_template_service
except ImportError:
    logger.warning("无法导入节点模板服务，将使用默认节点类型")
    get_node_template_service = None

class ChatService:
    """
    LangChain聊天服务
    
    集成LangChain的各个组件实现聊天功能
    """
    
    def __init__(self):
        """初始化聊天服务"""
        logger.info("初始化聊天服务")
        
        # 创建基础聊天模型
        self.llm = get_chat_model()
        logger.info(f"创建聊天模型: {settings.CHAT_MODEL_NAME}")
        
        # 创建基础聊天链
        self.chat_chain = CHAT_PROMPT_TEMPLATE | self.llm | StrOutputParser()
        
        # 创建上下文增强聊天链
        self.enhanced_chat_chain = ENHANCED_CHAT_PROMPT_TEMPLATE | self.llm | StrOutputParser()
        
        # 创建上下文处理链
        self.context_processing_chain = CONTEXT_PROCESSING_TEMPLATE | self.llm | StrOutputParser()
        
        # 错误处理链
        self.error_handling_chain = ERROR_HANDLING_TEMPLATE | self.llm | StrOutputParser()
        
        # 存储会话缓存
        self._memory_cache = {}
        
        # 缓存节点模板
        self._node_templates_cache = None
        
        logger.info("聊天服务初始化完成")
    
    def _get_node_templates(self) -> Dict[str, Any]:
        """
        获取节点模板，与前端NodeSelector组件保持一致
        
        Returns:
            Dict[str, Any]: 节点模板字典，键为模板类型
        """
        # 如果已缓存，直接返回
        if self._node_templates_cache is not None:
            return self._node_templates_cache
            
        # 尝试从节点模板服务获取模板
        try:
            if get_node_template_service:
                template_service = get_node_template_service()
                templates = template_service.get_templates()
                if templates:
                    logger.info(f"成功从节点模板服务获取 {len(templates)} 个模板")
                    self._node_templates_cache = templates
                    return templates
        except Exception as e:
            logger.error(f"获取节点模板失败: {str(e)}")
            
        # 提供默认节点类型作为后备方案
        default_templates = {
            "moveL": {
                "id": "moveL",
                "type": "moveL",
                "label": "机器人直线移动",
                "description": "控制机器人执行直线移动操作",
                "fields": [
                    {"name": "control_x", "default_value": "enable", "type": "boolean"},
                    {"name": "control_y", "default_value": "enable", "type": "boolean"},
                    {"name": "point_name_list", "default_value": "[]", "type": "array"}
                ],
                "inputs": [{"id": "input", "label": "输入"}],
                "outputs": [{"id": "output", "label": "输出"}]
            },
            "process": {
                "id": "process",
                "type": "process",
                "label": "处理节点",
                "description": "表示一个处理过程或操作",
                "fields": [],
                "inputs": [{"id": "input", "label": "输入"}],
                "outputs": [{"id": "output", "label": "输出"}]
            },
            "decision": {
                "id": "decision",
                "type": "decision",
                "label": "决策节点",
                "description": "根据条件创建分支流程",
                "fields": [],
                "inputs": [{"id": "input", "label": "输入"}],
                "outputs": [
                    {"id": "true", "label": "是"},
                    {"id": "false", "label": "否"}
                ]
            }
        }
        
        logger.warning("使用默认节点模板")
        self._node_templates_cache = default_templates
        return default_templates
    
    async def _process_with_tools(
        self,
        user_input: str,
        session_id: str = None,
        context: str = "",
        flow_id: str = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        使用工具调用处理用户输入
        
        Args:
            user_input: 用户输入
            session_id: 会话ID
            context: 上下文信息
            flow_id: 流程图ID
            metadata: 附加元数据，包含language等信息
            
        Returns:
            处理结果文本
        """
        try:
            logger.info(f"使用工具处理用户输入")
            
            # 获取流程图工具
            tools = get_flow_tools()
            if not tools:
                logger.warning("没有可用的流程图工具")
                return ChatResponse(
                    conversation_id=session_id,
                    message=f"无法使用工具处理您的请求: 没有可用的流程图工具。您请求的是: {user_input}",
                    created_at=datetime.now().isoformat()
                )
            
            # 记录流程图ID
            logger.info(f"当前流程图ID: {flow_id}")
            
            # 如果提供了flow_id，设置为当前活动流程图ID
            if flow_id:
                from langchainchat.tools.flow_tools import set_active_flow_id
                set_active_flow_id(flow_id)
                logger.info(f"设置当前活动流程图ID: {flow_id}")
            
            # 获取节点模板 - 与前端NodeSelector组件保持一致
            node_templates = self._get_node_templates()
            logger.info(f"可用节点模板: {list(node_templates.keys())}")
            
            # 直接检查用户输入中是否包含创建请求和节点类型
            is_node_creation_request = False
            detected_node_type = None
            
            # 添加直接的节点创建短语匹配 - 强化日语检测
            direct_node_phrases = {
                "ムーブノードを作成": "moveL",
                "ムーブノード作成": "moveL",
                "移動ノードを作成": "moveL",
                "移動ノード作成": "moveL",
                "ノードを作成": None,  # 表示需要创建节点，但类型未明确
                "ノード作成": None,    # 表示需要创建节点，但类型未明确
            }
            
            # 先检查完整短语匹配
            for phrase, node_type in direct_node_phrases.items():
                if phrase in user_input:
                    is_node_creation_request = True
                    detected_node_type = node_type
                    logger.info(f"完整短语匹配成功: '{phrase}' -> {node_type or '未指定类型'}")
                    break
            
            # 如果完整短语未匹配成功，再进行分词匹配
            if not is_node_creation_request:
                # 检查是否有日语创建请求
                japanese_creation_words = ["作成", "作る", "追加", "生成", "ノード作成", "ノード追加", "ノード生成", "追加する", "作成する"]
                for word in japanese_creation_words:
                    if word in user_input:
                        is_node_creation_request = True
                        logger.info(f"日语创建关键词匹配成功: '{word}'")
                        break
                    
                # 如果没有日语创建请求，检查中文和英文
                if not is_node_creation_request:
                    chinese_creation_words = ["创建", "生成", "添加", "新建", "构建"]
                    for word in chinese_creation_words:
                        if word in user_input:
                            is_node_creation_request = True
                            logger.info(f"中文创建关键词匹配成功: '{word}'")
                            break
                    
                # 如果仍然没有，检查英文
                if not is_node_creation_request:
                    english_creation_words = ["create", "generate", "add", "new", "make", "build"]
                    for word in english_creation_words:
                        if word.lower() in user_input.lower():
                            is_node_creation_request = True
                            logger.info(f"英文创建关键词匹配成功: '{word}'")
                            break
            
            # 如果只确认了是创建请求但没有确定节点类型，则检查节点类型
            if is_node_creation_request and not detected_node_type:
                # 日语节点类型关键词
                japanese_node_types = {
                    "moveL": ["ムーブ", "移動", "動き", "モーブエル", "ムーブノード", "移動ノード"],
                    "process": ["プロセス", "処理", "工程", "プロセスノード", "処理ノード"],
                    "decision": ["判断", "決定", "分岐", "条件分岐", "判断ノード", "決定ノード"]
                }
                
                # 检查日语节点类型
                for node_type, keywords in japanese_node_types.items():
                    for keyword in keywords:
                        if keyword in user_input:
                            detected_node_type = node_type
                            logger.info(f"日语节点类型匹配成功: '{keyword}' -> {node_type}")
                            break
                    if detected_node_type:
                        break
            
            # 添加调试日志
            logger.info(f"用户输入: '{user_input}'")
            logger.info(f"是否识别为节点创建请求: {is_node_creation_request}")
            logger.info(f"检测到的节点类型: {detected_node_type}")
            logger.info(f"语言设置: {metadata.get('language') if metadata else 'None'}")
            
            # 如果是节点创建请求，直接创建节点
            if is_node_creation_request:
                # 从用户输入中提取可能的节点类型 - 优先匹配节点模板
                node_type = detected_node_type
                node_template = None
                
                # 首先尝试直接匹配节点模板ID
                for template_id, template in node_templates.items():
                    if template_id.lower() in user_input.lower():
                        node_type = template_id
                        node_template = template
                        break
                
                # 如果没找到匹配的模板ID，尝试使用别名和描述词匹配
                if not node_type:
                    # 定义节点类型及其可能的别名
                    node_type_mapping = {
                        "moveL": ["movel", "move l", "移动", "移动节点", "机器人移动", "move", "動き", "移動", "ムーブ", "ロボット移動", "モーブエル"],
                        "process": ["处理", "处理节点", "process node", "处理过程", "流程", "过程", "プロセス", "処理", "処理ノード", "工程", "手順"],
                        "decision": ["决策", "判断", "条件", "decision node", "条件判断", "if", "分支", "判断", "決定", "分岐", "条件分岐", "イフ", "デシジョン"],
                        "start": ["开始", "起点", "start node", "开始节点", "入口", "スタート", "始点", "開始", "開始ノード", "入り口"],
                        "end": ["结束", "终点", "end node", "结束节点", "出口", "エンド", "終点", "終了", "終了ノード", "出口"]
                    }
                    
                    # 遍历映射尝试匹配
                    for type_key, aliases in node_type_mapping.items():
                        # 检查此类型是否在模板中
                        if type_key in node_templates:
                            # 检查别名
                            for alias in aliases:
                                if alias.lower() in user_input.lower():
                                    node_type = type_key
                                    node_template = node_templates[type_key]
                                    break
                        if node_type:
                            break
                
                # 如果仍未找到匹配的节点类型，使用默认类型
                if not node_type:
                    # 使用默认的moveL类型作为回退
                    if "moveL" in node_templates:
                        node_type = "moveL"
                        node_template = node_templates["moveL"]
                    else:
                        # 如果moveL不可用，使用第一个可用的模板
                        template_keys = list(node_templates.keys())
                        if template_keys:
                            node_type = template_keys[0]
                            node_template = node_templates[node_type]
                        else:
                            # 如果没有可用的模板，使用generic类型
                            node_type = "generic"
                            node_template = None
                
                # 尝试从用户输入中提取节点标签
                node_label = None
                
                # 使用简单的启发式方法：寻找引号内的内容作为可能的标签
                import re
                label_matches = re.findall(r'["\'](.+?)["\']', user_input)
                if label_matches:
                    node_label = label_matches[0]
                else:
                    # 尝试提取"名为XXX"、"叫做XXX"等模式
                    label_patterns = [
                        r'名为\s*([^\s,\.，。]+)',
                        r'叫做\s*([^\s,\.，。]+)',
                        r'标签为\s*([^\s,\.，。]+)',
                        r'名称为\s*([^\s,\.，。]+)',
                        r'名称是\s*([^\s,\.，。]+)',
                        r'名为\s*([^\s,\.，。]+)',
                        r'called\s+([^\s,\.]+)',
                        r'named\s+([^\s,\.]+)',
                        r'labeled\s+([^\s,\.]+)',
                        # 添加日语匹配模式
                        r'名前は\s*([^\s,\.、。]+)',
                        r'名前が\s*([^\s,\.、。]+)',
                        r'ラベルは\s*([^\s,\.、。]+)',
                        r'ラベルが\s*([^\s,\.、。]+)',
                        r'という名前の\s*([^\s,\.、。]+)',
                        r'という\s*([^\s,\.、。]+)',
                        r'名付けた\s*([^\s,\.、。]+)'
                    ]
                    for pattern in label_patterns:
                        matches = re.search(pattern, user_input)
                        if matches:
                            node_label = matches.group(1)
                            break
                
                # 如果标签仍为空且有模板，使用模板标签
                if not node_label and node_template:
                    node_label = node_template.get("label", node_type)
                elif not node_label:
                    # 如果没有模板也没有标签，使用节点类型作为标签
                    node_label = node_type.capitalize()
                
                # 找到create_node工具
                create_tool = None
                for tool in tools:
                    if tool.name == "create_node":
                        create_tool = tool
                        break
                
                if create_tool:
                    try:
                        # 准备节点属性 - 基于模板定义
                        properties = {
                            "description": f"{node_label} - 由AI助手创建",
                        }
                        
                        # 如果有模板，使用模板中的字段定义
                        if node_template:
                            # 从模板中提取字段默认值
                            for field in node_template.get("fields", []):
                                field_name = field.get("name")
                                default_value = field.get("default_value")
                                if field_name and default_value is not None:
                                    properties[field_name] = default_value
                            
                            # 添加输入和输出定义
                            properties["inputs"] = node_template.get("inputs", [])
                            properties["outputs"] = node_template.get("outputs", [])
                            properties["nodeType"] = node_template.get("type", node_type)
                        else:
                            # 对moveL节点提供特殊处理
                            if node_type.lower() == "movel":
                                properties.update({
                                    "control_x": "enable",
                                    "control_y": "enable",
                                    "point_name_list": [],
                                    "pallet_list": [],
                                    "camera_list": []
                                })
                        
                        # 调用工具函数创建节点，提供更多参数增加成功率
                        logger.info(f"创建节点类型: {node_type}, 标签: {node_label}")
                        tool_result = create_tool.func(
                            node_type=node_type,
                            node_label=node_label,
                            properties=properties,
                            flow_id=flow_id  # 传递流程图ID
                        )
                        
                        if tool_result and tool_result.get("success", False):
                            node_id = tool_result.get("node_data", {}).get("id", "未知ID")
                            position = tool_result.get("node_data", {}).get("position", {})
                            
                            # 构建更详细、更友好的响应
                            response_parts = {}
                            
                            # 中文响应
                            response_parts["zh"] = [
                                f"我已为您创建了一个{node_type}类型的节点：",
                                f"- 节点ID: {node_id}",
                                f"- 节点标签: {node_label}",
                                f"- 节点位置: x={position.get('x', 0):.0f}, y={position.get('y', 0):.0f}"
                            ]
                            
                            # 英文响应
                            response_parts["en"] = [
                                f"I have created a {node_type} type node for you:",
                                f"- Node ID: {node_id}",
                                f"- Node Label: {node_label}",
                                f"- Node Position: x={position.get('x', 0):.0f}, y={position.get('y', 0):.0f}"
                            ]
                            
                            # 日文响应
                            response_parts["ja"] = [
                                f"{node_type}タイプのノードを作成しました：",
                                f"- ノードID: {node_id}",
                                f"- ノードラベル: {node_label}",
                                f"- ノード位置: x={position.get('x', 0):.0f}, y={position.get('y', 0):.0f}"
                            ]
                            
                            # 根据模板类型添加描述
                            if node_template and "description" in node_template:
                                response_parts["zh"].append(f"- 节点描述: {node_template['description']}")
                                response_parts["en"].append(f"- Node Description: {node_template['description']}")
                                response_parts["ja"].append(f"- ノード説明: {node_template['description']}")
                            # 否则对不同类型节点提供不同的提示
                            elif node_type.lower() == "movel":
                                response_parts["zh"].append("这是一个机器人移动节点，用于控制机器人执行直线移动。")
                                response_parts["en"].append("This is a robot movement node used to control the robot to perform linear movement.")
                                response_parts["ja"].append("これはロボットの直線移動を制御するためのロボット移動ノードです。")
                            elif node_type.lower() == "process":
                                response_parts["zh"].append("这是一个处理节点，用于表示一个处理过程或操作。")
                                response_parts["en"].append("This is a process node used to represent a processing procedure or operation.")
                                response_parts["ja"].append("これは処理手順や操作を表すプロセスノードです。")
                            elif node_type.lower() == "decision":
                                response_parts["zh"].append("这是一个决策节点，用于根据条件创建分支流程。")
                                response_parts["en"].append("This is a decision node used to create branching processes based on conditions.")
                                response_parts["ja"].append("これは条件に基づいて分岐プロセスを作成する決定ノードです。")
                            
                            response_parts["zh"].append("节点已添加到流程图中，您可以在流程图编辑器中看到它。")
                            response_parts["en"].append("The node has been added to the flowchart and can be viewed in the flowchart editor.")
                            response_parts["ja"].append("ノードはフローチャートに追加され、フローチャートエディターで確認できます。")
                            
                            # 选择语言 - 默认为中文
                            language = "zh"  # 默认语言
                            # 从metadata中获取language参数，或从请求参数获取
                            if metadata and "language" in metadata:
                                language = metadata.get("language").lower()
                            # 语言代码标准化
                            if language == "jp" or language == "japanese":
                                language = "ja"
                            elif language == "en" or language == "english":
                                language = "en"
                            elif language == "zh" or language == "chinese":
                                language = "zh"
                                
                            # 确保语言代码有效，否则使用默认中文
                            if language not in response_parts:
                                language = "zh"
                                
                            # 返回带有刷新标记的元数据
                            metadata = {
                                "refresh_flow": True,  # 通知前端刷新流程图
                                "node_id": node_id,
                                "node_type": node_type,
                                "node_label": node_label,
                                "position": position
                            }
                            
                            return ChatResponse(
                                conversation_id=session_id,
                                message="\n".join(response_parts[language]),
                                created_at=datetime.now().isoformat(),
                                metadata=metadata  # 包含刷新指令的元数据
                            )
                        else:
                            error_msg = tool_result.get("error", "未知错误") if tool_result else "创建失败"
                            logger.error(f"创建节点失败: {error_msg}")
                            return ChatResponse(
                                conversation_id=session_id,
                                message=f"创建节点失败: {error_msg}",
                                created_at=datetime.now().isoformat()
                            )
                    except Exception as e:
                        logger.error(f"创建节点失败: {str(e)}")
                        import traceback
                        logger.error(f"错误详情: {traceback.format_exc()}")
                        return ChatResponse(
                            conversation_id=session_id,
                            message=f"创建节点时出错: {str(e)}。请尝试重新表述您的请求，或提供更明确的节点类型。",
                            created_at=datetime.now().isoformat()
                        )
            
            # 其他情况，如获取流程图信息
            # 检查是否是获取流程图信息的请求
            is_info_request = False
            info_patterns = ["信息", "详情", "查看", "显示", "info", "details", "show", "display"]
            is_info_request = any(pattern in user_input.lower() for pattern in info_patterns)
            
            if is_info_request:
                # 找到get_flow_info工具
                info_tool = None
                for tool in tools:
                    if tool.name == "get_flow_info":
                        info_tool = tool
                        break
                
                if info_tool:
                    try:
                        # 直接调用工具函数
                        logger.info("获取流程图信息")
                        tool_result = info_tool.func(flow_id=flow_id)  # 传递流程图ID
                        
                        if isinstance(tool_result, dict) and "flow_info" in tool_result:
                            flow_info = tool_result["flow_info"]
                            nodes = flow_info.get("nodes", [])
                            
                            # 构建更详细的响应
                            response_parts = [
                                f"当前流程图信息:",
                                f"- 名称: {flow_info.get('name', '未命名')}",
                                f"- ID: {flow_info.get('id', '无ID')}",
                                f"- 节点数量: {flow_info.get('node_count', 0)}",
                                f"- 连接数量: {flow_info.get('connection_count', 0)}"
                            ]
                            
                            # 添加节点列表
                            if nodes:
                                response_parts.append("\n节点列表:")
                                for i, node in enumerate(nodes[:5]):  # 只显示前5个节点
                                    node_type = node.get("type", "未知")
                                    node_label = node.get("label", "未命名")
                                    response_parts.append(f"  {i+1}. {node_label} (类型: {node_type})")
                                
                                if len(nodes) > 5:
                                    response_parts.append(f"  ... 以及其他 {len(nodes) - 5} 个节点")
                            
                            return ChatResponse(
                                conversation_id=session_id,
                                message="\n".join(response_parts),
                                created_at=datetime.now().isoformat(),
                                metadata={
                                    "refresh_flow": True,  # 通知前端刷新流程图
                                    "flow_info": flow_info
                                }  # 包含刷新指令的元数据
                            )
                        else:
                            return ChatResponse(
                                conversation_id=session_id,
                                message=f"获取流程图信息: {tool_result}",
                                created_at=datetime.now().isoformat()
                            )
                    except Exception as e:
                        logger.error(f"获取流程图信息失败: {str(e)}")
                        return ChatResponse(
                            conversation_id=session_id,
                            message=f"获取流程图信息时出错: {str(e)}。请稍后再试。",
                            created_at=datetime.now().isoformat()
                        )
            
            # 如果以上特定匹配都失败，使用LLM生成一般性回复
            return await self._generate_general_response(user_input, session_id, context)
        
        except Exception as e:
            logger.error(f"工具处理出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return ChatResponse(
                conversation_id=session_id,
                message=f"处理工具请求时出错: {str(e)}。请尝试重新表述您的请求或联系系统管理员。",
                created_at=datetime.now().isoformat()
            )
    
    async def _generate_general_response(self, user_input: str, session_id: str = None, context: str = "") -> ChatResponse:
        """生成一般性回复，当无法使用工具时使用"""
        try:
            # 避免使用format方法，直接拼接字符串
            prompt = "你是流程图设计助手。"
            prompt += f"\n\n用户的请求是: '{user_input}'"
            if context:
                prompt += f"\n\n上下文信息:\n{context}"
            prompt += "\n\n请生成一个有帮助的回复，不要尝试执行任何工具调用，只提供信息或建议。"
            
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            return ChatResponse(
                conversation_id=session_id,
                message=content,
                created_at=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"生成一般性回复失败: {str(e)}")
            return ChatResponse(
                conversation_id=session_id,
                message=f"我无法理解您的请求。请尝试更清晰地表述您需要什么帮助。",
                created_at=datetime.now().isoformat()
            )

    def translate_response(self, text: str, language: str) -> str:
        """
        翻译响应文本到指定语言
        
        Args:
            text: 要翻译的文本
            language: 目标语言代码 (如 'en', 'zh', 'ja')
            
        Returns:
            翻译后的文本
        """
        # 如果没有文本或没有指定语言，直接返回原文
        if not language or not text:
            return text
            
        try:
            logger.info(f"处理响应翻译，目标语言: {language}")
            translated_text = translator.translate(text, target_language=language)
            return translated_text
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            # 如果翻译失败，返回原文
            return text
    
    async def process_message(
        self,
        user_input: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None,
        use_tools: bool = True,
        use_context: bool = True,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            user_input: 用户输入消息
            conversation_id: 会话ID，如果不提供则创建新会话
            user_id: 用户ID
            metadata: 附加元数据，可以包含flow_id字段指定当前流程图ID
            db: 数据库会话
            use_tools: 是否使用工具
            use_context: 是否使用上下文
            language: 期望的响应语言 (en, zh, ja)
            
        Returns:
            处理结果
        """
        try:
            logger.info(f"处理聊天消息: 会话={conversation_id}, 使用上下文={use_context}, 使用工具={use_tools}, 语言={language}")
            
            # 创建或获取记忆组件
            memory = await self._get_memory(conversation_id, user_id, metadata)
            conversation_id = memory.conversation_id
            
            # 检查是否为节点创建请求
            node_creation_patterns = [
                "创建", "生成", "添加", "创建节点", "生成节点", "添加节点", 
                "create", "generate", "add", "create node", "generate node", "add node"
            ]
            is_node_creation_request = any(pattern in user_input.lower() for pattern in node_creation_patterns)
            
            # 如果是节点创建请求，优先使用工具调用
            if is_node_creation_request and use_tools:
                logger.info("检测到节点创建请求，使用工具调用")
                
                try:
                    # 从元数据中获取当前流程图ID
                    current_flow_id = None
                    if metadata and "flow_id" in metadata:
                        current_flow_id = metadata["flow_id"]
                        logger.info(f"从元数据中获取流程图ID: {current_flow_id}")
                        # 设置当前活动流程图ID - 但最好直接传递给_process_with_tools方法
                        set_active_flow_id(current_flow_id)
                    else:
                        logger.warning("元数据中未找到flow_id，将使用默认流程图")
                    
                    # 使用工具调用模板处理请求
                    context = await context_collector.collect_all(db)
                    
                    # 使用TOOL_CALLING_TEMPLATE，传递flow_id和metadata
                    tool_response = await self._process_with_tools(user_input, conversation_id, context, current_flow_id, metadata)
                    
                    # 将工具调用响应添加到记忆
                    memory.chat_memory.add_user_message(user_input)
                    memory.chat_memory.add_ai_message(tool_response.message)
                    memory.save()
                    
                    # 构建结果
                    result = {
                        "conversation_id": conversation_id,
                        "message": tool_response.message,
                        "created_at": datetime.now().isoformat(),
                        "metadata": tool_response.metadata or {},
                        "tool_used": True  # 标记使用了工具
                    }
                    
                    logger.info(f"成功处理节点创建请求: 会话={conversation_id}")
                    return result
                except Exception as e:
                    logger.error(f"工具调用处理失败，回退到普通处理: {str(e)}")
                    # 回退到普通处理
            
            # 是否为简短响应
            is_short_response = len(user_input.strip()) < 10
            context_text = None
            
            # 如果是简短响应且有上下文，使用上下文处理链
            if is_short_response and memory.chat_memory.messages and len(memory.chat_memory.messages) > 1:
                logger.info("检测到简短响应，使用上下文处理")
                
                # 从内存中收集上下文
                context_messages = memory.chat_memory.messages[-4:]  # 获取最近的4条消息
                context_text = "\n".join([f"{msg.__class__.__name__}: {msg.content}" for msg in context_messages])
                
                try:
                    # 使用上下文处理链处理简短响应
                    original_response = await self.context_processing_chain.ainvoke({
                        "context": context_text,
                        "input": user_input
                    })
                except Exception as e:
                    logger.error(f"上下文处理链执行失败: {str(e)}")
                    # 失败时回退到普通处理
                    original_response = await self._process_with_context(user_input, db, language) if use_context else await self._process_without_context(user_input, language)
            else:
                # 使用适当的处理方式
                if use_context:
                    original_response = await self._process_with_context(user_input, db, language)
                else:
                    original_response = await self._process_without_context(user_input, language)
            
            # 进行翻译
            response = self.translate_response(original_response, language)
            
            # 将用户消息和响应添加到记忆
            memory.chat_memory.add_user_message(user_input)
            memory.chat_memory.add_ai_message(original_response)  # 存储未翻译的原始响应
            
            # 保存记忆
            memory.save()
            
            # 创建结果
            result = {
                "conversation_id": conversation_id,
                "message": response,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # 如果使用了上下文，添加到结果中
            if context_text:
                result["context_used"] = context_text
                
            logger.info(f"成功处理消息: 会话={conversation_id}, 响应长度={len(response)}")
            return result
            
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            
            # 尝试处理错误
            try:
                error_message = f"处理消息时出错: {str(e)}"
                error_response = await self.error_handling_chain.ainvoke({
                    "input": user_input[:100] + "..." if len(user_input) > 100 else user_input,
                    "error": str(e)
                })
                
                # 翻译错误消息
                error_response = self.translate_response(error_response, language)
            except:
                error_response = f"处理消息时出错: {str(e)}"
                # 翻译基本错误消息
                if language and language != "en":
                    try:
                        error_response = self.translate_response(error_response, language)
                    except:
                        pass
            
            return {
                "conversation_id": conversation_id or "error_session",
                "message": error_response,
                "created_at": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def _process_with_context(self, user_input: str, db: Session = None, language: str = "en") -> str:
        """
        使用上下文处理用户输入
        
        Args:
            user_input: 用户输入
            db: 数据库会话
            language: 目标语言代码
            
        Returns:
            处理结果
        """
        logger.info("使用上下文处理用户输入")
        
        # 尝试使用QA服务处理
        try:
            from .qa_service import get_qa_service
            qa_service = get_qa_service()
            
            # 使用QA服务进行问答
            response = await qa_service.query_with_context(db, user_input, context_limit=3)
            logger.info("使用QA服务生成回答")
            return response
        except Exception as e:
            logger.error(f"使用QA服务失败，回退到基本上下文处理: {str(e)}")
            
            # 回退到基本处理
            # 收集上下文信息
            context = await context_collector.collect_all(db)
            
            # 使用增强聊天链
            response = await self.enhanced_chat_chain.ainvoke({
                "context": context,
                "input": user_input
            })
            
            return response
    
    async def _process_without_context(self, user_input: str, language: str = "en") -> str:
        """
        不使用上下文处理用户输入
        
        Args:
            user_input: 用户输入
            language: 目标语言代码
            
        Returns:
            处理结果
        """
        logger.info("不使用上下文处理用户输入")
        
        # 使用基础聊天链
        response = await self.chat_chain.ainvoke({
            "input": user_input
        })
        
        return response
    
    async def _get_memory(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EnhancedConversationMemory:
        """
        获取会话记忆组件
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
            metadata: 附加元数据
            
        Returns:
            记忆组件
        """
        # 如果有会话ID且已缓存，直接返回
        if conversation_id and conversation_id in self._memory_cache:
            logger.debug(f"使用缓存的会话记忆: {conversation_id}")
            return self._memory_cache[conversation_id]
            
        # 创建系统消息
        system_message = """你是一个专业的流程图设计助手，帮助用户设计和创建工作流流程图。

作为流程图助手，你应该:
1. 提供专业、简洁的流程图设计建议
2. 帮助解释不同节点类型的用途
3. 提出合理的流程优化建议
4. 协助用户解决流程图设计中遇到的问题
5. 只回答与流程图和工作流相关的问题

可用的节点类型:
- moveL: 机器人直线移动节点，控制机器人执行直线运动
- process: 处理节点，表示一个处理过程或操作
- decision: 决策节点，根据条件创建分支流程
- start: 开始节点，表示流程的起点
- end: 结束节点，表示流程的终点

如何创建节点:
当用户请求创建节点时，你可以使用如下格式：
- "创建一个moveL节点"
- "添加一个名为'数据处理'的process节点"
- "生成决策节点"

当用户询问流程图信息时：
1. 优先从上下文中的"当前流程图信息"部分获取流程图名称、ID、节点数量等信息
2. 如果上下文信息不足，使用get_flow_info工具获取最新的流程图信息
3. 始终告知用户当前正在处理的流程图名称和基本信息

保持你的回答专业、清晰且符合流程图设计的最佳实践。当用户请求创建节点时，无需解释工具调用过程，直接响应节点创建的结果即可。"""
        
        # 创建新的记忆组件
        memory = create_memory(
            conversation_id=conversation_id,
            user_id=user_id,
            system_message=system_message,
            metadata=metadata,
            max_token_limit=settings.DEFAULT_CONTEXT_WINDOW
        )
        
        # 缓存记忆组件
        self._memory_cache[memory.conversation_id] = memory
        
        return memory
    
    def list_conversations(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取会话列表
        
        Args:
            user_id: 用户ID，如果提供则只返回该用户的会话
            
        Returns:
            会话列表
        """
        return EnhancedConversationMemory.list_conversations(user_id)
    
    def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> bool:
        """
        删除会话
        
        Args:
            conversation_id: 会话ID
            user_id: 用户ID
            
        Returns:
            是否成功删除
        """
        # 如果会话存在于缓存中，先清除
        if conversation_id in self._memory_cache:
            del self._memory_cache[conversation_id]
            
        # 构建会话路径
        import os
        from pathlib import Path
        
        sessions_dir = Path(settings.SESSIONS_DB_PATH)
        
        # 用户特定目录
        if user_id:
            file_path = sessions_dir / user_id / f"{conversation_id}.json"
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"删除会话: {conversation_id}, 用户: {user_id}")
                return True
                
        # 公共目录
        file_path = sessions_dir / f"{conversation_id}.json"
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"删除会话: {conversation_id}")
            return True
            
        logger.warning(f"未找到要删除的会话: {conversation_id}")
        return False 