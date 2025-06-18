"""
XML 处理工具函数
"""
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

BLOCKLY_NS = "https://developers.google.com/blockly/xml"


def parse_xml_safely(xml_content: str) -> Optional[ET.Element]:
    """
    安全地解析 XML 内容
    
    Args:
        xml_content: XML 字符串内容
        
    Returns:
        解析后的 Element 或 None（如果解析失败）
    """
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error(f"XML 解析错误: {e}")
        logger.debug(f"问题 XML 内容: {xml_content[:200]}...")
        return None
    except Exception as e:
        logger.error(f"解析 XML 时发生意外错误: {e}")
        return None


def create_blockly_xml_root() -> ET.Element:
    """
    创建一个 Blockly XML 根元素
    
    Returns:
        带有正确命名空间的 XML 根元素
    """
    ET.register_namespace("", BLOCKLY_NS)
    return ET.Element(f"{{{BLOCKLY_NS}}}xml")


def extract_block_from_xml(xml_element: ET.Element) -> Optional[ET.Element]:
    """
    从 XML 元素中提取 block 元素
    
    Args:
        xml_element: XML 元素
        
    Returns:
        找到的 block 元素或 None
    """
    # 检查根元素是否就是 block
    if xml_element.tag == f"{{{BLOCKLY_NS}}}block" or xml_element.tag == "block":
        return xml_element
    
    # 在子元素中查找 block
    block = xml_element.find(f"{{{BLOCKLY_NS}}}block")
    if block is None:
        block = xml_element.find("block")
    
    return block


def validate_xml_structure(xml_content: str) -> Tuple[bool, Optional[str]]:
    """
    验证 XML 结构是否有效
    
    Args:
        xml_content: XML 字符串内容
        
    Returns:
        (是否有效, 错误消息)
    """
    if not xml_content or not xml_content.strip():
        return False, "XML 内容为空"
    
    root = parse_xml_safely(xml_content)
    if root is None:
        return False, "XML 解析失败"
    
    # 检查是否有有效的根元素
    if root.tag not in [f"{{{BLOCKLY_NS}}}xml", "xml", f"{{{BLOCKLY_NS}}}block", "block"]:
        return False, f"无效的根元素: {root.tag}"
    
    # 如果是 xml 根元素，检查是否包含 block
    if root.tag in [f"{{{BLOCKLY_NS}}}xml", "xml"]:
        block = extract_block_from_xml(root)
        if block is None:
            return False, "XML 中没有找到 block 元素"
    
    return True, None


def merge_xml_blocks(blocks: List[ET.Element]) -> ET.Element:
    """
    将多个 block 元素合并成一个链式结构
    
    Args:
        blocks: block 元素列表
        
    Returns:
        合并后的第一个 block 元素（其他通过 next 链接）
    """
    if not blocks:
        raise ValueError("没有提供要合并的 blocks")
    
    # 复制第一个 block 作为起点
    first_block = ET.fromstring(ET.tostring(blocks[0]))
    current_block = first_block
    
    # 链接后续的 blocks
    for block in blocks[1:]:
        next_elem = ET.SubElement(current_block, "next")
        block_copy = ET.fromstring(ET.tostring(block))
        next_elem.append(block_copy)
        current_block = block_copy
    
    return first_block


def format_xml_string(element: ET.Element, indent: str = "  ") -> str:
    """
    格式化 XML 元素为字符串
    
    Args:
        element: XML 元素
        indent: 缩进字符串
        
    Returns:
        格式化的 XML 字符串
    """
    if hasattr(ET, 'indent'):
        ET.indent(element, space=indent)
    
    xml_string = ET.tostring(element, encoding='unicode', xml_declaration=False)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}' 