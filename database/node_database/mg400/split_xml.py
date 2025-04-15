import re
import os

# 源文件路径 (相对于脚本所在目录)
source_file_path = 'mg400-xml-nodes.txt'
# 输出目录 (脚本所在目录)
output_directory = '.'

# 获取脚本所在的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))
source_abs_path = os.path.join(script_dir, source_file_path)
output_abs_directory = os.path.join(script_dir, output_directory)


# 读取源文件内容
try:
    # 使用绝对路径读取源文件
    with open(source_abs_path, 'r', encoding='utf-8') as f:
        content = f.read()
except FileNotFoundError:
    print(f"错误：找不到源文件 '{source_abs_path}'")
    exit()
except Exception as e:
    print(f"读取文件时出错: {e}")
    exit()

# 使用正则表达式查找所有 XML 块
# 模式匹配注释中的文件名和紧随其后的 XML 内容
# 使用 re.DOTALL 使 '.' 匹配包括换行符在内的任何字符
pattern = re.compile(r'<!--\s*(.*?\.xml)\s*-->\s*(<\?xml.*?<\/xml>)', re.DOTALL | re.IGNORECASE)
matches = pattern.findall(content)

if not matches:
    print(f"错误：在文件 '{source_abs_path}' 中未找到匹配的 XML 块。")
    exit()

# 确保输出目录存在 (使用绝对路径)
os.makedirs(output_abs_directory, exist_ok=True)

print(f"找到了 {len(matches)} 个 XML 节点，正在拆分到目录: {output_abs_directory}")

# 遍历所有匹配项并创建文件
file_count = 0
for filename, xml_content in matches:
    # 清理可能存在的多余空格
    filename = filename.strip()
    xml_content = xml_content.strip()

    # 构建完整输出路径 (使用绝对路径)
    output_file_path = os.path.join(output_abs_directory, filename)

    try:
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            outfile.write(xml_content)
        file_count += 1
        # print(f"已创建文件: {output_file_path}") # 可选：取消注释以查看每个创建的文件
    except Exception as e:
        print(f"写入文件 '{output_file_path}' 时出错: {e}")

print(f"\n处理完成！成功在 '{output_abs_directory}' 创建了 {file_count} 个 XML 文件。")
if len(matches) != file_count:
     print(f"警告：预期创建 {len(matches)} 个文件，但实际创建了 {file_count} 个。可能存在一些问题。") 