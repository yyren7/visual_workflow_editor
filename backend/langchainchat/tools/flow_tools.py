from typing import Dict, Any, List, Optional, Type, Union
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import logging
import uuid

from langchainchat.utils.logging import logger

# 提供一个简单的工具列表
def get_flow_tools() -> List[BaseTool]:
    """
    获取流程工具列表
    
    Returns:
        工具列表
    """
    logger.info("获取流程工具列表 - 暂时返回空列表")
    return [] 