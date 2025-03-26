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

from langchainchat.config import settings
from langchainchat.utils.logging import logger
from app.database import get_db

class ContextCollector:
    """
    上下文信息收集器
    
    用于收集工作流系统中的各种上下文信息，包括：
    - 系统信息
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
            
            # 简化版本，只收集系统信息
            system_info = await self.collect_system_info()
            
            # 格式化结果
            result = f"""# 上下文信息

## 系统信息
{system_info}
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

context_collector = ContextCollector() 