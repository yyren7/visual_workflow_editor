"""
文件操作工具函数
"""
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


def ensure_directory_exists(directory: Union[str, Path]) -> Path:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        directory: 目录路径
        
    Returns:
        Path 对象
    """
    dir_path = Path(directory)
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"确保目录存在: {dir_path}")
        return dir_path
    except Exception as e:
        logger.error(f"创建目录失败 {dir_path}: {e}")
        raise


def save_xml_file(content: str, file_path: Union[str, Path]) -> Path:
    """
    保存 XML 内容到文件
    
    Args:
        content: XML 内容
        file_path: 文件路径
        
    Returns:
        保存的文件路径
    """
    file_path = Path(file_path)
    
    # 确保目录存在
    ensure_directory_exists(file_path.parent)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"成功保存 XML 文件: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"保存 XML 文件失败 {file_path}: {e}")
        raise


def load_xml_file(file_path: Union[str, Path]) -> Optional[str]:
    """
    从文件加载 XML 内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        XML 内容或 None（如果加载失败）
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.debug(f"成功加载 XML 文件: {file_path}")
        return content
    except Exception as e:
        logger.error(f"加载 XML 文件失败 {file_path}: {e}")
        return None


def get_timestamped_filename(base_name: str, extension: str = ".xml") -> str:
    """
    生成带时间戳的文件名
    
    Args:
        base_name: 基础文件名
        extension: 文件扩展名
        
    Returns:
        带时间戳的文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}{extension}"


def copy_file(source: Union[str, Path], destination: Union[str, Path]) -> Path:
    """
    复制文件
    
    Args:
        source: 源文件路径
        destination: 目标文件路径
        
    Returns:
        目标文件路径
    """
    import shutil
    
    source_path = Path(source)
    dest_path = Path(destination)
    
    if not source_path.exists():
        raise FileNotFoundError(f"源文件不存在: {source_path}")
    
    # 确保目标目录存在
    ensure_directory_exists(dest_path.parent)
    
    try:
        shutil.copy2(source_path, dest_path)
        logger.info(f"成功复制文件: {source_path} -> {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"复制文件失败: {e}")
        raise


def list_xml_files(directory: Union[str, Path]) -> list[Path]:
    """
    列出目录中的所有 XML 文件
    
    Args:
        directory: 目录路径
        
    Returns:
        XML 文件路径列表
    """
    dir_path = Path(directory)
    
    if not dir_path.exists() or not dir_path.is_dir():
        logger.warning(f"目录不存在或不是目录: {dir_path}")
        return []
    
    xml_files = list(dir_path.glob("*.xml"))
    logger.debug(f"在 {dir_path} 中找到 {len(xml_files)} 个 XML 文件")
    return xml_files 