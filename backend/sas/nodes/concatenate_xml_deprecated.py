import os
import xml.etree.ElementTree as ET
from pathlib import Path

# 输入目录：包含要连接的XML文件的目录
INPUT_DIR = Path("backend/tests/llm_sas_test/specific_clamp_output/")
# 输出文件路径：连接后的XML文件将保存到这里
OUTPUT_FILE = Path("backend/tests/llm_sas_test/concatenated_output/concatenated_flow.xml")
# Blockly XML 命名空间
BLOCKLY_XMLNS = "https://developers.google.com/blockly/xml"

def concatenate_xml_files(input_dir: Path, output_file: Path):
    """
    连接指定目录下的所有XML文件到一个单独的XML文件中。
    """
    ET.register_namespace("", BLOCKLY_XMLNS) # 注册命名空间

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"错误: 输入目录 {input_dir} 不存在或不是一个目录。")
        return

    xml_files = list(input_dir.glob("*.xml"))
    if not xml_files:
        print(f"在 {input_dir} 中没有找到XML文件。")
        return

    # 创建一个新的根XML元素
    concatenated_root = ET.Element(f"{{{BLOCKLY_XMLNS}}}xml")

    print(f"开始连接 {len(xml_files)} 个XML文件到 {output_file}...")

    for xml_file in sorted(xml_files): # 按文件名排序，以确保一致的连接顺序
        try:
            tree = ET.parse(xml_file)
            root_element = tree.getroot()
            
            # 检查根元素是否是预期的 <xml> 或 <block>
            namespaced_xml_tag = f"{{{BLOCKLY_XMLNS}}}xml"
            namespaced_block_tag = f"{{{BLOCKLY_XMLNS}}}block"

            if root_element.tag == namespaced_xml_tag or root_element.tag == "xml":
                # 如果是 <xml> 根，则将其所有子元素添加到连接后的根中
                for child in root_element:
                    concatenated_root.append(child)
            elif root_element.tag == namespaced_block_tag or root_element.tag == "block":
                # 如果是 <block> 根，则直接将其添加到连接后的根中
                concatenated_root.append(root_element)
            else:
                print(f"警告: 文件 {xml_file} 的根标签为 '{root_element.tag}'，不是预期的 '{namespaced_xml_tag}' 或 '{namespaced_block_tag}'。跳过此文件。")

        except ET.ParseError as e:
            print(f"错误解析XML文件 {xml_file}: {e}")
        except Exception as e:
            print(f"处理文件 {xml_file} 时发生意外错误: {e}")

    try:
        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)
        # 尝试美化输出XML
        ET.indent(concatenated_root) 
    except AttributeError:
        print(f"警告: ET.indent 不可用 (需要Python 3.9+)。XML将不会通过ElementTree的indent方法美化。")
    except OSError as e:
        print(f"错误创建输出目录 {output_file.parent}: {e}")
        return

    tree = ET.ElementTree(concatenated_root)
    try:
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        print(f"成功连接所有XML文件到 {output_file}")
    except IOError as e:
        print(f"写入输出XML文件 {output_file} 时出错: {e}")
    except Exception as e:
        print(f"写入输出XML文件 {output_file} 时发生意外错误: {e}")

if __name__ == "__main__":
    concatenate_xml_files(INPUT_DIR, OUTPUT_FILE) 