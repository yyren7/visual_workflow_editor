import os
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

# Blockly XML 命名空间，根据您的日志，一些文件使用了这个
BLOCKLY_NAMESPACE = "{https://developers.google.com/blockly/xml}"

def get_dynamic_node_types_info(quickfcpr_dir: str = "/workspace/database/node_database/quickfcpr/") -> str:
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

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # This path is relative to where this script would be if it's in backend/langgraphchat/prompts/
    # Adjust if testing from a different location or ensure the structure matches.
    # For robust testing, consider an absolute path or environment variable for the test path.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming this script is in backend/langgraphchat/prompts, 
    # go up three levels for backend/, then down to database/node_database/quickfcpr/
    default_test_path = os.path.abspath(os.path.join(script_dir, "..", "..", "..", "database", "node_database", "quickfcpr"))
    
    info_string = get_dynamic_node_types_info(default_test_path)
    
    print("\n--- 动态生成的节点类型信息 ---")
    print(info_string) 