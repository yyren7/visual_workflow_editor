from typing import Dict, Any, List, Optional, Tuple
import json
import os
import platform
from pathlib import Path
import logging
from datetime import datetime
from sqlalchemy.orm import Session
import traceback
import asyncio
import sys

from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate

from backend.langgraphchat.config import settings
logger = logging.getLogger(__name__)
from backend.database.connection import get_db
from backend.langgraphchat.tools.flow_tools import get_active_flow_id

class ContextCollector:
    """
    上下文信息收集器
    
    用于收集工作流系统中的各种上下文信息，包括：
    - 系统信息
    - 流程图信息
    """
    
    def __init__(self, db: Session = None):
        """
        初始化上下文收集器
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def collect_all(self, db: Optional[Session] = None) -> str:
        """
        收集所有上下文信息
        
        Args:
            db: 数据库会话，如果不提供则创建新的会话
            
        Returns:
            格式化的上下文信息
        """
        try:
            logger.info("开始收集上下文信息")
            
            # 收集系统信息
            system_info = await self.collect_system_info()
            
            # 收集流程图信息
            flow_info = await self.collect_flow_info(db)
            
            # 格式化结果
            result = f"""# 上下文信息

## 系统信息
{system_info}

## 当前流程图信息
{flow_info}
"""
            logger.info("上下文信息收集完成")
            return result
            
        except Exception as e:
            logger.error(f"收集上下文信息时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return f"上下文收集失败: {str(e)}"
    
    async def collect_system_info(self) -> str:
        """
        收集系统信息
        
        Returns:
            格式化的系统信息
        """
        try:
            logger.info("收集系统信息")
            
            # 获取Python版本
            python_version = platform.python_version()
            
            # 获取操作系统信息
            os_info = platform.platform()
            
            # 获取当前时间
            current_time = datetime.now().isoformat()
            
            # 获取工作目录
            work_dir = os.getcwd()
            
            # 构建结果
            result = f"""Python版本: {python_version}
操作系统: {os_info}
当前时间: {current_time}
工作目录: {work_dir}
"""
            
            logger.info("系统信息收集完成")
            return result
            
        except Exception as e:
            logger.error(f"收集系统信息时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return f"系统信息收集失败: {str(e)}"
    
    async def collect_flow_info(self, db: Optional[Session] = None) -> str:
        """
        收集当前流程图信息
        
        Args:
            db: 数据库会话，如果不提供则创建新的会话
            
        Returns:
            格式化的流程图信息
        """
        try:
            logger.info("收集当前流程图信息")
            
            # 如果未提供数据库会话，则创建新的会话
            internal_db = False
            if db is None:
                internal_db = True
                db = next(get_db())
            
            try:
                # 从flow_tools获取当前活动的流程图ID
                flow_id = get_active_flow_id(db)
                
                if not flow_id:
                    logger.warning("没有找到当前活动的流程图")
                    return "当前没有活动的流程图"
                
                logger.info(f"获取流程图ID: {flow_id}")
                
                # 获取流程图服务
                from backend.app.services.flow_service import FlowService
                flow_service = FlowService(db)
                
                # 获取流程图详情
                flow_data = flow_service.get_flow(flow_id)
                
                if not flow_data:
                    logger.warning(f"无法获取流程图 {flow_id} 的详情")
                    return f"无法获取流程图 {flow_id} 的详情"
                
                # 提取流程图基本信息
                flow_name = flow_data.get("name", "未命名流程图")
                flow_id = flow_data.get("id", "未知ID")
                nodes = flow_data.get("nodes", [])
                connections = flow_data.get("connections", [])
                
                # 构建基本流程图信息
                result = f"""流程图名称: {flow_name}
流程图ID: {flow_id}
创建时间: {flow_data.get("created_at", "未知")}
更新时间: {flow_data.get("updated_at", "未知")}
节点数量: {len(nodes)}
连接数量: {len(connections)}
"""
                
                # 如果有节点，添加节点概要
                if nodes:
                    result += "\n节点概要:\n"
                    for node in nodes[:5]:  # 仅显示前5个节点，避免上下文过长
                        node_id = node.get("id", "未知")
                        node_type = node.get("type", "未知")
                        node_label = node.get("data", {}).get("label", "未命名")
                        result += f"- 节点: {node_label} (类型: {node_type}, ID: {node_id})\n"
                    
                    if len(nodes) > 5:
                        result += f"... 等共计 {len(nodes)} 个节点\n"
                
                logger.info(f"成功收集流程图信息: {flow_name}")
                return result
                
            finally:
                # 如果是内部创建的会话，则关闭
                if internal_db:
                    db.close()
            
        except Exception as e:
            logger.error(f"收集流程图信息时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return f"收集流程图信息失败: {str(e)}"

def get_active_flow_context(data: Dict[str, Any]) -> str:
    """
    获取当前激活流程的上下文信息，并以字符串形式返回。
    """
    # Implementation of get_active_flow_context function
    pass

context_collector = ContextCollector() 