#!/usr/bin/env python3
# backend/db_visualize.py - 数据库表结构可视化工具

import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from sqlalchemy import inspect, MetaData, Table, create_engine
import tempfile
import subprocess

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.app.database import engine, Base
from backend.app.config import Config
from backend.app.models import User, Flow, FlowVariable, VersionInfo

def get_table_info():
    """获取数据库中所有表的信息"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    result = {}
    
    for table_name in tables:
        table_info = {
            "columns": [],
            "primary_key": [],
            "foreign_keys": [],
            "indices": [],
            "constraints": [],
            "row_count": 0
        }
        
        # 获取列信息
        for column in inspector.get_columns(table_name):
            col_info = {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column.get("nullable", True),
                "default": str(column.get("default", "None")),
                "autoincrement": column.get("autoincrement", False),
            }
            table_info["columns"].append(col_info)
        
        # 获取主键信息
        try:
            pk = inspector.get_pk_constraint(table_name)
            if pk and "constrained_columns" in pk:
                table_info["primary_key"] = pk["constrained_columns"]
        except:
            pass
        
        # 获取外键信息
        try:
            for fk in inspector.get_foreign_keys(table_name):
                if "constrained_columns" in fk and "referred_table" in fk:
                    fk_info = {
                        "columns": fk["constrained_columns"],
                        "referred_table": fk["referred_table"],
                        "referred_columns": fk.get("referred_columns", [])
                    }
                    table_info["foreign_keys"].append(fk_info)
        except:
            pass
        
        # 获取索引信息
        try:
            for idx in inspector.get_indexes(table_name):
                if "name" in idx and "column_names" in idx:
                    idx_info = {
                        "name": idx["name"],
                        "columns": idx["column_names"],
                        "unique": idx.get("unique", False)
                    }
                    table_info["indices"].append(idx_info)
        except:
            pass
            
        # 获取唯一约束信息
        try:
            for constraint in inspector.get_unique_constraints(table_name):
                if "name" in constraint and "column_names" in constraint:
                    constraint_info = {
                        "name": constraint["name"],
                        "columns": constraint["column_names"]
                    }
                    table_info["constraints"].append(constraint_info)
        except:
            pass
        
        # 获取表中的行数
        try:
            # 创建表对象
            metadata = MetaData()
            table = Table(table_name, metadata, autoload_with=engine)
            
            # 执行计数查询
            from sqlalchemy.sql import select, func
            count_query = select(func.count()).select_from(table)
            row_count = engine.connect().execute(count_query).scalar()
            table_info["row_count"] = row_count
        except Exception as e:
            print(f"获取表 {table_name} 行数时出错: {e}")
        
        result[table_name] = table_info
    
    return result

def generate_text_report(table_info, file_path):
    """生成文本格式的表结构报告"""
    with open(file_path, 'w') as f:
        f.write("数据库表结构报告\n")
        f.write("=" * 80 + "\n")
        f.write(f"日期: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"数据库URL: {Config.DATABASE_URL}\n")
        f.write("=" * 80 + "\n\n")
        
        for table_name, info in table_info.items():
            f.write(f"表名: {table_name}\n")
            f.write("-" * 50 + "\n")
            
            f.write(f"行数: {info['row_count']}\n\n")
            
            f.write("列:\n")
            for col in info["columns"]:
                default = f", 默认值: {col['default']}" if col['default'] != "None" else ""
                nullable = "可为空" if col["nullable"] else "非空"
                auto_increment = ", 自增" if col["autoincrement"] else ""
                f.write(f"  - {col['name']}: {col['type']} ({nullable}{auto_increment}{default})\n")
            
            if info["primary_key"]:
                f.write("\n主键:\n")
                f.write(f"  {', '.join(info['primary_key'])}\n")
            
            if info["foreign_keys"]:
                f.write("\n外键:\n")
                for fk in info["foreign_keys"]:
                    src_cols = ", ".join(fk["columns"])
                    ref_cols = ", ".join(fk["referred_columns"])
                    f.write(f"  {src_cols} -> {fk['referred_table']}({ref_cols})\n")
            
            if info["indices"]:
                f.write("\n索引:\n")
                for idx in info["indices"]:
                    unique = "唯一" if idx["unique"] else "非唯一"
                    f.write(f"  {idx['name']}: {unique}, 列: {', '.join(idx['columns'])}\n")
            
            if info["constraints"]:
                f.write("\n约束:\n")
                for constraint in info["constraints"]:
                    f.write(f"  {constraint['name']}: 列: {', '.join(constraint['columns'])}\n")
            
            f.write("\n\n")
        
        f.write("\n关系图:\n")
        f.write("(通过外键关联)\n\n")
        
        # 生成一个简单的关系图
        graph = {}
        for table_name, info in table_info.items():
            if table_name not in graph:
                graph[table_name] = []
            
            for fk in info["foreign_keys"]:
                referred_table = fk["referred_table"]
                if referred_table not in graph:
                    graph[referred_table] = []
                
                relation = f"{table_name}.{','.join(fk['columns'])} -> {referred_table}.{','.join(fk['referred_columns'])}"
                graph[table_name].append(relation)
        
        for table, relations in graph.items():
            if relations:
                f.write(f"{table}:\n")
                for relation in relations:
                    f.write(f"  {relation}\n")
                f.write("\n")
        
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("报告生成完毕\n")

def generate_markdown_report(table_info, file_path):
    """生成Markdown格式的表结构报告"""
    with open(file_path, 'w') as f:
        f.write("# 数据库表结构报告\n\n")
        f.write(f"**日期:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**数据库URL:** `{Config.DATABASE_URL}`\n\n")
        
        # 目录
        f.write("## 目录\n\n")
        for table_name in table_info.keys():
            f.write(f"- [{table_name}](#{table_name.lower()})\n")
        f.write("\n")
        
        # 表信息
        for table_name, info in table_info.items():
            f.write(f"## {table_name}\n\n")
            f.write(f"**行数:** {info['row_count']}\n\n")
            
            f.write("### 列\n\n")
            f.write("| 名称 | 类型 | 可空 | 默认值 | 自增 |\n")
            f.write("|------|------|------|--------|------|\n")
            for col in info["columns"]:
                nullable = "是" if col["nullable"] else "否"
                default = col["default"] if col["default"] != "None" else ""
                auto_increment = "是" if col["autoincrement"] else "否"
                f.write(f"| {col['name']} | {col['type']} | {nullable} | {default} | {auto_increment} |\n")
            
            if info["primary_key"]:
                f.write("\n### 主键\n\n")
                f.write(f"`{', '.join(info['primary_key'])}`\n\n")
            
            if info["foreign_keys"]:
                f.write("### 外键\n\n")
                f.write("| 本表列 | 引用表 | 引用列 |\n")
                f.write("|--------|--------|--------|\n")
                for fk in info["foreign_keys"]:
                    src_cols = ", ".join(fk["columns"])
                    ref_cols = ", ".join(fk["referred_columns"])
                    f.write(f"| {src_cols} | {fk['referred_table']} | {ref_cols} |\n")
                f.write("\n")
            
            if info["indices"]:
                f.write("### 索引\n\n")
                f.write("| 名称 | 类型 | 列 |\n")
                f.write("|------|------|----|\n")
                for idx in info["indices"]:
                    unique = "唯一" if idx["unique"] else "非唯一"
                    f.write(f"| {idx['name']} | {unique} | {', '.join(idx['columns'])} |\n")
                f.write("\n")
            
            if info["constraints"]:
                f.write("### 约束\n\n")
                f.write("| 名称 | 列 |\n")
                f.write("|------|----|\n")
                for constraint in info["constraints"]:
                    f.write(f"| {constraint['name']} | {', '.join(constraint['columns'])} |\n")
                f.write("\n")
            
            f.write("\n")
        
        f.write("## 关系图\n\n")
        f.write("```\n")
        # 生成一个简单的关系图
        for table_name, info in table_info.items():
            if info["foreign_keys"]:
                for fk in info["foreign_keys"]:
                    referred_table = fk["referred_table"]
                    src_cols = ", ".join(fk["columns"])
                    ref_cols = ", ".join(fk["referred_columns"])
                    f.write(f"{table_name}({src_cols}) -> {referred_table}({ref_cols})\n")
        f.write("```\n\n")
        
        f.write("---\n")
        f.write("报告生成完毕\n")

def generate_html_report(table_info, file_path):
    """生成HTML格式的表结构报告"""
    with open(file_path, 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据库表结构报告</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #2980b9;
            margin-top: 30px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }
        h3 {
            color: #3498db;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
        }
        th, td {
            text-align: left;
            padding: 8px;
            border: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .table-info {
            margin-bottom: 30px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
        .toc {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 30px;
        }
        .toc ul {
            list-style-type: none;
            padding-left: 0;
        }
        .toc li {
            margin-bottom: 5px;
        }
        .toc a {
            text-decoration: none;
            color: #3498db;
        }
        .toc a:hover {
            text-decoration: underline;
        }
        .relationship {
            font-family: monospace;
            white-space: pre;
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }
        footer {
            margin-top: 40px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            color: #777;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>数据库表结构报告</h1>
    <p><strong>日期:</strong> """)
        
        f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        f.write(f"</p><p><strong>数据库URL:</strong> <code>{Config.DATABASE_URL}</code></p>")
        
        # 目录
        f.write('<div class="toc"><h2>目录</h2><ul>')
        for table_name in table_info.keys():
            f.write(f'<li><a href="#{table_name}">{table_name}</a></li>')
        f.write('</ul></div>')
        
        # 表信息
        for table_name, info in table_info.items():
            f.write(f'<div class="table-info" id="{table_name}">')
            f.write(f'<h2>{table_name}</h2>')
            f.write(f'<p><strong>行数:</strong> {info["row_count"]}</p>')
            
            # 列
            f.write('<h3>列</h3>')
            f.write('<table><tr><th>名称</th><th>类型</th><th>可空</th><th>默认值</th><th>自增</th></tr>')
            for col in info["columns"]:
                nullable = "是" if col["nullable"] else "否"
                default = col["default"] if col["default"] != "None" else ""
                auto_increment = "是" if col["autoincrement"] else "否"
                f.write(f'<tr><td>{col["name"]}</td><td>{col["type"]}</td><td>{nullable}</td><td>{default}</td><td>{auto_increment}</td></tr>')
            f.write('</table>')
            
            # 主键
            if info["primary_key"]:
                f.write('<h3>主键</h3>')
                f.write(f'<p><code>{", ".join(info["primary_key"])}</code></p>')
            
            # 外键
            if info["foreign_keys"]:
                f.write('<h3>外键</h3>')
                f.write('<table><tr><th>本表列</th><th>引用表</th><th>引用列</th></tr>')
                for fk in info["foreign_keys"]:
                    src_cols = ", ".join(fk["columns"])
                    ref_cols = ", ".join(fk["referred_columns"])
                    f.write(f'<tr><td>{src_cols}</td><td>{fk["referred_table"]}</td><td>{ref_cols}</td></tr>')
                f.write('</table>')
            
            # 索引
            if info["indices"]:
                f.write('<h3>索引</h3>')
                f.write('<table><tr><th>名称</th><th>类型</th><th>列</th></tr>')
                for idx in info["indices"]:
                    unique = "唯一" if idx["unique"] else "非唯一"
                    f.write(f'<tr><td>{idx["name"]}</td><td>{unique}</td><td>{", ".join(idx["columns"])}</td></tr>')
                f.write('</table>')
            
            # 约束
            if info["constraints"]:
                f.write('<h3>约束</h3>')
                f.write('<table><tr><th>名称</th><th>列</th></tr>')
                for constraint in info["constraints"]:
                    f.write(f'<tr><td>{constraint["name"]}</td><td>{", ".join(constraint["columns"])}</td></tr>')
                f.write('</table>')
            
            f.write('</div>')
        
        # 关系图
        f.write('<h2>关系图</h2>')
        f.write('<div class="relationship">')
        for table_name, info in table_info.items():
            if info["foreign_keys"]:
                for fk in info["foreign_keys"]:
                    referred_table = fk["referred_table"]
                    src_cols = ", ".join(fk["columns"])
                    ref_cols = ", ".join(fk["referred_columns"])
                    f.write(f'{table_name}({src_cols}) -> {referred_table}({ref_cols})<br>')
        f.write('</div>')
        
        f.write("""
    <footer>
        <p>报告生成于 """)
        f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        f.write("""</p>
    </footer>
</body>
</html>
""")

def generate_json_report(table_info, file_path):
    """生成JSON格式的表结构报告"""
    report = {
        "generated_at": datetime.datetime.now().isoformat(),
        "database_url": Config.DATABASE_URL,
        "tables": table_info
    }
    
    with open(file_path, 'w') as f:
        json.dump(report, f, indent=2)

def generate_er_diagram(table_info, file_path):
    """生成ER图（使用Graphviz DOT格式）"""
    dot_file = tempfile.NamedTemporaryFile(suffix='.dot', delete=False)
    
    with open(dot_file.name, 'w') as f:
        f.write('digraph ER {\n')
        f.write('  graph [rankdir=LR, overlap=false, splines=true];\n')
        f.write('  node [shape=record, fontsize=10, margin="0.25,0.125"];\n')
        f.write('  edge [arrowhead=none, dir=both, arrowtail=crow, arrowsize=0.8];\n\n')
        
        # 定义节点（表）
        for table_name, info in table_info.items():
            # 创建表节点标签
            label = f"{{{table_name}|"
            
            # 添加列
            cols = []
            for col in info["columns"]:
                pk_marker = " <PK>" if col["name"] in info["primary_key"] else ""
                fk_marker = " <FK>" if any(col["name"] in fk["columns"] for fk in info["foreign_keys"]) else ""
                
                col_type = str(col["type"])
                if len(col_type) > 15:  # 如果类型名称太长，缩短它
                    col_type = col_type[:12] + "..."
                
                cols.append(f"{col['name']}{pk_marker}{fk_marker}: {col_type}")
            
            label += "\\l".join(cols) + "\\l"  # 左对齐
            label += "}"
            
            # 定义节点
            f.write(f'  "{table_name}" [label="{label}"];\n')
        
        f.write('\n')
        
        # 定义边（关系）
        for table_name, info in table_info.items():
            for fk in info["foreign_keys"]:
                referred_table = fk["referred_table"]
                # 创建关系边
                f.write(f'  "{table_name}" -> "{referred_table}" [label="{", ".join(fk["columns"])}", arrowhead=normal, arrowtail=none];\n')
        
        f.write('}\n')
    
    # 调用dot命令生成图片
    try:
        output_format = file_path.split('.')[-1]  # 从文件扩展名获取输出格式
        if output_format not in ['png', 'svg', 'pdf']:
            output_format = 'png'  # 默认格式
            file_path = f"{file_path}.{output_format}"
        
        subprocess.run(['dot', '-T'+output_format, dot_file.name, '-o', file_path], check=True)
        print(f"ER图已生成: {file_path}")
        
        # 删除临时dot文件
        os.unlink(dot_file.name)
        return True
    except Exception as e:
        print(f"生成ER图失败: {e}")
        print(f"DOT文件已保存: {dot_file.name}")
        return False

def main():
    parser = argparse.ArgumentParser(description="数据库表结构可视化工具")
    
    parser.add_argument('--output', '-o', type=str, default='db_structure_report',
                      help='输出文件路径（不包括扩展名）')
    
    parser.add_argument('--format', '-f', type=str, choices=['text', 'markdown', 'html', 'json', 'er', 'all'],
                      default='text', help='输出格式')
    
    args = parser.parse_args()
    
    # 获取表信息
    print("正在获取数据库表结构信息...")
    table_info = get_table_info()
    print(f"找到 {len(table_info)} 个表")
    
    # 根据格式生成报告
    base_path = args.output
    
    if args.format == 'text' or args.format == 'all':
        file_path = f"{base_path}.txt"
        print(f"生成文本报告: {file_path}")
        generate_text_report(table_info, file_path)
    
    if args.format == 'markdown' or args.format == 'all':
        file_path = f"{base_path}.md"
        print(f"生成Markdown报告: {file_path}")
        generate_markdown_report(table_info, file_path)
    
    if args.format == 'html' or args.format == 'all':
        file_path = f"{base_path}.html"
        print(f"生成HTML报告: {file_path}")
        generate_html_report(table_info, file_path)
    
    if args.format == 'json' or args.format == 'all':
        file_path = f"{base_path}.json"
        print(f"生成JSON报告: {file_path}")
        generate_json_report(table_info, file_path)
    
    if args.format == 'er' or args.format == 'all':
        file_path = f"{base_path}.png"
        print(f"生成ER图: {file_path}")
        try:
            generate_er_diagram(table_info, file_path)
        except Exception as e:
            print(f"生成ER图失败: {e}")
            print("ER图生成需要安装Graphviz。请运行: apt-get install graphviz")

    print("完成！")

if __name__ == "__main__":
    main() 