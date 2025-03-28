import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path

class NodeTemplate:
    """
    节点模板类，表示一个从XML解析的节点定义
    
    属性:
        id (str): 模板唯一标识符
        type (str): 节点类型
        label (str): 显示标签
        fields (List[Dict]): 字段列表，包含名称和默认值
        inputs (List[Dict]): 输入连接点
        outputs (List[Dict]): 输出连接点
        description (str): 节点描述
        icon (str): 图标标识
    """
    def __init__(self, 
                 id: str, 
                 type: str, 
                 label: str, 
                 fields: List[Dict[str, Any]], 
                 inputs: Optional[List[Dict[str, Any]]] = None, 
                 outputs: Optional[List[Dict[str, Any]]] = None, 
                 description: str = "", 
                 icon: str = ""):
        self.id = id
        self.type = type
        self.label = label
        self.fields = fields
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.description = description
        self.icon = icon

class NodeTemplateService:
    """
    节点模板服务，负责加载和管理XML定义的节点模板
    
    方法:
        load_templates: 加载所有XML模板文件
        get_templates: 获取所有模板用于API响应
    """
    def __init__(self, template_dir: str = None):
        """
        初始化节点模板服务
        
        参数:
            template_dir: XML模板文件所在目录
        """
        if template_dir is None:
            # 使用绝对路径
            BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
            template_dir = os.path.join(BASE_DIR, "database/node_database")
            print(f"使用自动计算的模板目录路径: {template_dir}")
            
        self.template_dir = template_dir
        self.templates = {}
        
    def load_templates(self) -> Dict[str, NodeTemplate]:
        """
        加载所有XML模板文件并解析为NodeTemplate对象
        
        返回:
            Dict[str, NodeTemplate]: 模板字典，键为模板类型
        """
        try:
            if not os.path.exists(self.template_dir):
                print(f"警告: 模板目录不存在: {self.template_dir}")
                os.makedirs(self.template_dir, exist_ok=True)
                print(f"已创建模板目录: {self.template_dir}")
                return {}
                
            files = os.listdir(self.template_dir)
            if not files:
                print(f"警告: 模板目录为空: {self.template_dir}")
                return {}
                
            print(f"发现 {len(files)} 个文件在目录 {self.template_dir}")
            xml_files = [f for f in files if f.endswith('.xml')]
            print(f"其中 {len(xml_files)} 个是XML文件")
            
            for filename in xml_files:
                template_path = os.path.join(self.template_dir, filename)
                try:
                    template = self._parse_template(template_path)
                    if template:
                        self.templates[template.type] = template
                        print(f"成功加载模板: {template.type} 从文件 {filename}")
                    else:
                        print(f"警告: 未能从文件创建模板 {filename}")
                except Exception as e:
                    print(f"错误: 处理模板文件时出错 {filename}: {str(e)}")
            
            print(f"总共加载了 {len(self.templates)} 个模板")
            return self.templates
        except Exception as e:
            print(f"严重错误: 加载模板过程中发生异常: {str(e)}")
            return {}
    
    def _parse_template(self, file_path: str) -> Optional[NodeTemplate]:
        """
        解析单个XML文件为NodeTemplate对象
        
        参数:
            file_path: XML文件路径
            
        返回:
            NodeTemplate或None: 解析成功返回NodeTemplate，失败返回None
        """
        try:
            # 注册命名空间
            namespaces = {
                'blockly': 'https://developers.google.com/blockly/xml'
            }
            
            # 对于ElementTree的命名空间支持
            for prefix, uri in namespaces.items():
                ET.register_namespace(prefix, uri)
                
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 打印XML结构以便调试
            print(f"解析XML文件: {file_path}")
            print(f"XML根元素: {root.tag}")
            
            # 获取block节点，支持命名空间
            # 先尝试直接查找
            block = root.find(".//block")
            
            # 如果没找到，尝试使用命名空间
            if block is None:
                for prefix, uri in namespaces.items():
                    block = root.find(f".//{{{uri}}}block")
                    if block is not None:
                        print(f"使用命名空间 {uri} 找到block元素")
                        break
            
            if block is None:
                print(f"警告: 无法在文件中找到block元素: {file_path}")
                # 打印XML内容以便调试
                print(f"XML内容:\n{ET.tostring(root, encoding='unicode')}")
                return None
                
            node_type = block.get("type")
            if not node_type:
                print(f"警告: block元素缺少type属性: {file_path}")
                return None
                
            node_id = os.path.basename(file_path).replace(".xml", "")
            
            # 解析fields
            fields = []
            for field in block.findall(".//field"):
                field_name = field.get("name")
                field_value = field.text or ""
                fields.append({
                    "name": field_name, 
                    "default_value": field_value,
                    "type": self._infer_field_type(field_value)
                })
            
            # 如果没找到field，尝试使用命名空间
            if not fields:
                for prefix, uri in namespaces.items():
                    for field in block.findall(f".//{{{uri}}}field"):
                        field_name = field.get("name")
                        field_value = field.text or ""
                        fields.append({
                            "name": field_name, 
                            "default_value": field_value,
                            "type": self._infer_field_type(field_value)
                        })
                    if fields:
                        print(f"使用命名空间 {uri} 找到field元素")
                        break
            
            # 解析statement (可用于确定输入槽)
            statements = block.findall(".//statement")
            # 如果没找到statement，尝试使用命名空间
            if not statements:
                for prefix, uri in namespaces.items():
                    ns_statements = block.findall(f".//{{{uri}}}statement")
                    if ns_statements:
                        statements = ns_statements
                        print(f"使用命名空间 {uri} 找到statement元素")
                        break
                        
            has_statements = len(statements) > 0
            
            # 解析next (用于确定输出连接)
            has_next = block.find(".//next") is not None
            # 如果没找到next，尝试使用命名空间
            if not has_next:
                for prefix, uri in namespaces.items():
                    if block.find(f".//{{{uri}}}next") is not None:
                        has_next = True
                        print(f"使用命名空间 {uri} 找到next元素")
                        break
            
            # 确定输入输出
            inputs = []
            # 基本输入点（所有节点都有）
            inputs.append({"id": "input", "label": "Input", "position": 0})
            
            # 从statement添加额外输入点
            if has_statements:
                for i, stmt in enumerate(statements):
                    stmt_name = stmt.get("name")
                    inputs.append({
                        "id": f"input_{stmt_name}", 
                        "label": self._format_label(stmt_name),
                        "position": i + 1
                    })
            
            outputs = []
            # 基本输出点（大多数节点都有）
            outputs.append({"id": "output", "label": "Output", "position": 0})
            
            # 根据节点类型调整输入输出
            if node_type == "return":
                # return节点没有输出
                outputs = []
            elif node_type == "condition":
                # 条件节点有两个输出：真和假
                outputs = [
                    {"id": "true", "label": "True", "position": 0},
                    {"id": "false", "label": "False", "position": 1}
                ]
                
            # 添加描述信息
            description = f"{self._format_label(node_type)}"
            
            return NodeTemplate(
                id=node_id,
                type=node_type,
                label=self._format_label(node_type),
                fields=fields,
                inputs=inputs,
                outputs=outputs,
                description=description,
            )
            
        except Exception as e:
            print(f"Error parsing template {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _infer_field_type(self, value: str) -> str:
        """
        推断字段类型
        
        参数:
            value: 字段值
            
        返回:
            str: 推断的类型名称
        """
        if value.lower() in ['true', 'false', 'enable', 'disable', 'on', 'off']:
            return 'boolean'
        try:
            int(value)
            return 'integer'
        except ValueError:
            try:
                float(value)
                return 'number'
            except ValueError:
                if value.lower() in ['none']:
                    return 'none'
                return 'string'
    
    def _format_label(self, type_name: str) -> str:
        """
        将类型名格式化为友好标签
        
        参数:
            type_name: 类型名
            
        返回:
            str: 格式化后的标签
        """
        words = type_name.split('_')
        return ' '.join(word.capitalize() for word in words)
    
    def get_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        返回模板列表，用于API响应
        
        返回:
            Dict[str, Dict[str, Any]]: 模板数据字典
        """
        result = {}
        for template_id, template in self.templates.items():
            result[template_id] = {
                "id": template.id,
                "type": template.type,
                "label": template.label,
                "fields": template.fields,
                "inputs": template.inputs,
                "outputs": template.outputs,
                "description": template.description,
                "icon": template.icon
            }
        return result

# 如果直接运行这个文件，则加载模板并测试
if __name__ == "__main__":
    service = NodeTemplateService()
    templates = service.load_templates()
    print(f"加载了 {len(templates)} 个模板:")
    for template_type, template in templates.items():
        print(f"- {template_type}: {template.label}")
        print(f"  字段: {len(template.fields)}")
        print(f"  输入: {len(template.inputs)}")
        print(f"  输出: {len(template.outputs)}") 