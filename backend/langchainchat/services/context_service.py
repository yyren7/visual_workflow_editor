"""
上下文服务
管理聊天上下文数据
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

# 导入必要的组件
from backend.langchainchat.embeddings.semantic_search import search_by_text
from backend.langchainchat.embeddings.node_search import search_nodes

# 设置logger
logger = logging.getLogger(__name__)

class ContextService:
    """上下文服务，负责收集和管理上下文数据"""
    
    def __init__(self):
        """初始化上下文服务"""
        pass
    
    async def collect_all(self, db: Session = None) -> str:
        """
        收集所有可用上下文
        
        Args:
            db: 数据库会话
            
        Returns:
            格式化的上下文字符串
        """
        context_parts = []
        
        # 收集系统状态上下文
        system_context = await self.collect_system_context()
        if system_context:
            context_parts.append("系统状态：")
            context_parts.append(system_context)
        
        # 如果有数据库会话，收集数据库上下文
        if db:
            # 尝试收集最新数据
            db_context = await self.collect_database_context(db)
            if db_context:
                context_parts.append("\n数据库信息：")
                context_parts.append(db_context)
        
        # 收集节点上下文
        node_context = await self.collect_node_context()
        if node_context:
            context_parts.append("\n可用节点：")
            context_parts.append(node_context)
        
        # 合并上下文
        if context_parts:
            return "\n".join(context_parts)
        else:
            return "没有可用的上下文信息。"
    
    async def collect_system_context(self) -> str:
        """
        收集系统状态相关上下文
        
        Returns:
            系统上下文字符串
        """
        try:
            # 这里可以添加系统状态相关信息
            # 例如当前时间、系统负载等
            return "系统正常运行中。"
        except Exception as e:
            logger.error(f"收集系统上下文失败: {str(e)}")
            return ""
    
    async def collect_database_context(self, db: Session) -> str:
        """
        收集数据库相关上下文
        
        Args:
            db: 数据库会话
            
        Returns:
            数据库上下文字符串
        """
        try:
            # 查询一些基本的统计信息
            # 这里只是一个简单示例，实际应用中可以根据需要查询更多信息
            result = db.execute("SELECT COUNT(*) FROM json_embeddings").scalar()
            
            return f"数据库中有 {result} 条嵌入记录。"
        except Exception as e:
            logger.error(f"收集数据库上下文失败: {str(e)}")
            return ""
    
    async def collect_node_context(self) -> str:
        """
        收集节点相关上下文
        
        Returns:
            节点上下文字符串
        """
        try:
            # 获取基本节点信息
            node_results = await search_nodes("type:common", limit=5)
            
            if not node_results:
                return "未找到节点信息。"
            
            context_items = []
            for item in node_results:
                node_data = item.get('data', {})
                node_id = node_data.get('id', 'unknown')
                node_type = node_data.get('type', 'unknown')
                
                context_items.append(f"- {node_id} (类型: {node_type})")
            
            return "\n".join(context_items)
        except Exception as e:
            logger.error(f"收集节点上下文失败: {str(e)}")
            return ""

# 创建单例实例
_context_service_instance = None

def get_context_service() -> ContextService:
    """
    获取上下文服务实例
    
    Returns:
        ContextService实例
    """
    global _context_service_instance
    if _context_service_instance is None:
        _context_service_instance = ContextService()
    return _context_service_instance

# 导出全局实例
context_collector = get_context_service() 