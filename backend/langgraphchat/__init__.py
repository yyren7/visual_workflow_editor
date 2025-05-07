"""
LangChain聊天模块

此模块提供基于LangChain框架的聊天功能，包括会话管理、上下文收集和工具调用。
"""

# 导出模块版本
__version__ = "0.1.0"

# 注意：为避免循环导入，chat_service实例在导入时不创建
# 用户需要从services.chat_service模块中直接导入
__all__ = []
