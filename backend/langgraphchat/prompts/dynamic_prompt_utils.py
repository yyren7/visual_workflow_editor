import os
import xml.etree.ElementTree as ET
import logging
from dotenv import load_dotenv

load_dotenv() # 加载 .env 文件中的环境变量

logger = logging.getLogger(__name__)

# Blockly XML 命名空间，根据您的日志，一些文件使用了这个
BLOCKLY_NAMESPACE = "{https://developers.google.com/blockly/xml}"

# 尝试从环境变量读取路径，如果未设置，则使用默认值
DEFAULT_QUICKFCPR_DIR = "/workspace/database/node_database/quick-fcpr-new/"
NODE_TEMPLATE_DIR = os.getenv("NODE_TEMPLATE_DIR_PATH", DEFAULT_QUICKFCPR_DIR)

def get_dynamic_node_types_info(quickfcpr_dir: str = NODE_TEMPLATE_DIR) -> str:
    """
    遍历指定目录下的XML文件，提取Blockly节点类型及其标签，
    并格式化为供Prompt使用的字符串。
    """
    node_types = []
    if not os.path.isdir(quickfcpr_dir):
        logger.error(f"指定的目录不存在: {quickfcpr_dir}")
        return "错误：无法加载节点类型信息，指定目录不存在。"

    for filename in os.listdir(quickfcpr_dir):
        if filename.endswith(".xml"):
            file_path = os.path.join(quickfcpr_dir, filename)
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                block_element = None
                
                if root.tag == f"{BLOCKLY_NAMESPACE}xml" or root.tag == "xml":
                    block_element = root.find(f"{BLOCKLY_NAMESPACE}block")
                    if block_element is None:
                        block_element = root.find("block")
                elif root.tag == f"{BLOCKLY_NAMESPACE}block" or root.tag == "block":
                    block_element = root
                
                if block_element is not None:
                    node_type = block_element.get("type")
                    if node_type:
                        label = None
                        possible_label_field_names = ["TEXT", "text", "NAME", "name", "label", "LABEL"]
                        
                        for field_name_to_check in possible_label_field_names:
                            field_element = block_element.find(f".//{BLOCKLY_NAMESPACE}field[@name='{field_name_to_check}']")
                            if field_element is None: # Try without namespace
                                field_element = block_element.find(f".//field[@name='{field_name_to_check}']")
                            
                            if field_element is not None and field_element.text:
                                label = field_element.text.strip()
                                break
                        
                        if not label:
                            label = f"{node_type} (从 {filename} 加载)" 
                            
                        node_types.append(f"- {node_type}: {label if label else '暂无描述'}")
                    else:
                        logger.warning(f"文件 {filename} 中的 <block> 元素缺少 'type' 属性。")
                else:
                    logger.warning(f"在文件 {filename} 中未找到 <block> 元素。根元素: {root.tag}")

            except ET.ParseError as e:
                # Skip files that are not valid XML, like .DS_Store or empty/corrupt files
                if "no element found" not in str(e) and "syntax error" not in str(e).lower():
                    logger.error(f"解析XML文件失败 {file_path}: {e}")
            except Exception as e:
                logger.error(f"处理文件 {file_path} 时发生未知错误: {e}")
    
    if not node_types:
        return "未能从指定目录加载任何节点类型信息。"
        
    node_types.sort()
    
    return "当前可用的主要节点类型包括 (具体参数和行为请以实际节点定义为准):\n" + "\n".join(node_types)

def get_node_params_from_xml(xml_path: str) -> dict:
    """
    解析单个XML节点文件，提取所有参数名、类型、范围和默认值。
    返回格式：
    {
        'node_type': str,
        'params': [
            {'name': str, 'type': str, 'default': Any}
        ]
    }
    """
    result = {'node_type': None, 'params': []}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        block_element = None
        if root.tag == f"{BLOCKLY_NAMESPACE}xml" or root.tag == "xml":
            block_element = root.find(f"{BLOCKLY_NAMESPACE}block")
            if block_element is None:
                block_element = root.find("block")
        elif root.tag == f"{BLOCKLY_NAMESPACE}block" or root.tag == "block":
            block_element = root
        if block_element is not None:
            node_type = block_element.get("type")
            result['node_type'] = node_type
            # 解析所有 <field> 参数
            for field in block_element.findall(f".//{BLOCKLY_NAMESPACE}field") + block_element.findall(f".//field"):
                param_name = field.get("name")
                param_type = "str"  # Blockly field一般为字符串，可扩展
                default_value = field.text if field.text is not None else ""
                if param_name:
                    result['params'].append({
                        'name': param_name,
                        'type': param_type,
                        'default': default_value
                    })
            # 解析 <value> 参数（如有）
            for value in block_element.findall(f".//{BLOCKLY_NAMESPACE}value") + block_element.findall(f".//value"):
                param_name = value.get("name")
                param_type = "block"  # 可能是嵌套block
                default_value = None
                if param_name:
                    result['params'].append({
                        'name': param_name,
                        'type': param_type,
                        'default': default_value
                    })
            # 解析 <statement> 参数（如有）
            for statement in block_element.findall(f".//{BLOCKLY_NAMESPACE}statement") + block_element.findall(f".//statement"):
                param_name = statement.get("name")
                param_type = "statement"  # 语句块
                default_value = None
                if param_name:
                    result['params'].append({
                        'name': param_name,
                        'type': param_type,
                        'default': default_value
                    })
        else:
            result['error'] = '未找到block元素'
    except Exception as e:
        result['error'] = str(e)
    return result

if __name__ == '__main__':
    # This path is relative to where this script would be if it's in backend/langgraphchat/prompts/
    # Adjust if testing from a different location or ensure the structure matches.
    # For robust testing, consider an absolute path or environment variable for the test path.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming this script is in backend/langgraphchat/prompts, 
    # go up three levels for backend/, then down to database/node_database/quick-fcpr-new/
    default_test_path = os.path.abspath(os.path.join(script_dir, "..", "..", "..", "database", "node_database", "quick-fcpr-new"))
    
    info_string = get_dynamic_node_types_info() # 测试时将使用环境变量或默认值
    
    print("\n--- 动态生成的节点类型信息 ---")
    print(info_string)

    # 新增：演示解析单个xml节点文件参数
    print("\n--- 单节点参数解析演示 (if.xml) ---")
    if_xml_path = os.path.join(default_test_path, "if.xml")
    params_info = get_node_params_from_xml(if_xml_path)
    print(params_info) 