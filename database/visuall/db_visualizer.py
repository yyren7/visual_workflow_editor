#!/usr/bin/env python3
# 数据库可视化工具 - 将数据库内容输出为可视化文件

import os
import sys
import json
import sqlite3
import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 添加项目根目录到路径
current_dir = Path(__file__).parent.parent.parent
sys.path.append(str(current_dir))

# 设置输出目录
OUTPUT_DIR = Path(__file__).parent
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据库路径
DB_PATH = current_dir / "database" / "flow_editor.db"

def json_serialize(obj):
    """处理JSON序列化中的特殊类型"""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return str(obj)

def get_db_connection():
    """连接到SQLite数据库"""
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件不存在: {DB_PATH}")
        sys.exit(1)
    
    return sqlite3.connect(DB_PATH)

def get_all_tables(conn):
    """获取数据库中的所有表"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    return [table[0] for table in tables]

def export_table_to_json(conn, table_name):
    """将表数据导出为JSON格式"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    
    # 获取列名
    columns = [description[0] for description in cursor.description]
    
    # 获取所有行
    rows = cursor.fetchall()
    
    # 将行数据转换为字典列表
    data = []
    for row in rows:
        row_dict = {}
        for i, column in enumerate(columns):
            row_dict[column] = row[i]
        data.append(row_dict)
    
    # 写入JSON文件
    output_file = OUTPUT_DIR / f"{table_name}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=json_serialize, ensure_ascii=False)
    
    print(f"已导出表 {table_name} 到 {output_file}")
    return data

def create_table_summary(conn, tables):
    """创建数据库表摘要"""
    summary = {}
    
    for table_name in tables:
        cursor = conn.cursor()
        # 获取表结构
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        # 获取行数
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        summary[table_name] = {
            "columns": [col[1] for col in columns],
            "column_types": [col[2] for col in columns],
            "row_count": row_count
        }
    
    # 写入摘要文件
    summary_file = OUTPUT_DIR / "db_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"已创建数据库摘要: {summary_file}")
    return summary

def generate_table_visualizations(conn, tables):
    """为表生成可视化"""
    for table_name in tables:
        try:
            # 读取表数据到DataFrame
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            
            if len(df) == 0:
                print(f"表 {table_name} 没有数据，跳过可视化")
                continue
            
            # 创建表结构可视化
            plt.figure(figsize=(10, 6))
            plt.title(f"{table_name} - 列数据类型")
            df.dtypes.value_counts().plot(kind='bar')
            plt.tight_layout()
            plt.savefig(OUTPUT_DIR / f"{table_name}_column_types.png")
            plt.close()
            
            # 如果表有足够的行，创建行计数可视化
            if len(df) > 0 and 'created_at' in df.columns:
                plt.figure(figsize=(12, 6))
                plt.title(f"{table_name} - 创建时间分布")
                
                # 转换created_at为日期时间
                if df['created_at'].dtype == 'object':
                    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                
                # 按日期分组并计数
                if not df['created_at'].isna().all():
                    df.set_index('created_at').resample('D').size().plot(kind='line')
                    plt.tight_layout()
                    plt.savefig(OUTPUT_DIR / f"{table_name}_creation_timeline.png")
                
                plt.close()
            
            print(f"已为表 {table_name} 创建可视化")
        except Exception as e:
            print(f"为表 {table_name} 创建可视化时出错: {e}")

def create_relationships_visualization(tables_summary):
    """创建表关系可视化"""
    import networkx as nx
    
    G = nx.DiGraph()
    
    # 添加节点（表）
    for table in tables_summary:
        G.add_node(table, size=tables_summary[table]["row_count"])
    
    # 查找外键关系并添加边
    for table, info in tables_summary.items():
        for i, col in enumerate(info["columns"]):
            if "id" in col.lower() and col != "id":
                # 可能的外键
                related_table = col.replace("_id", "")
                if related_table in tables_summary:
                    G.add_edge(table, related_table)
    
    # 创建图形可视化
    plt.figure(figsize=(12, 10))
    pos = nx.spring_layout(G)
    
    # 绘制节点，大小基于行数
    node_sizes = [100 + tables_summary[node]["row_count"] * 20 for node in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, alpha=0.7)
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5)
    nx.draw_networkx_labels(G, pos, font_size=10)
    
    plt.title("数据库表关系图")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "db_relationships.png")
    plt.close()
    print("已创建数据库关系图")

def create_html_report(tables_summary, tables):
    """创建HTML摘要报告"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>数据库内容摘要</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #333; }
            .table-info { margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .visualization { margin-top: 10px; }
            img { max-width: 100%; border: 1px solid #ddd; }
            .data-section { margin-top: 20px; }
            .json-data { background-color: #f8f8f8; padding: 10px; border: 1px solid #ddd; border-radius: 5px; overflow: auto; max-height: 300px; }
            pre { margin: 0; white-space: pre-wrap; }
            .toggle-btn { padding: 5px 10px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; }
        </style>
        <script>
            function toggleDataDisplay(tableId) {
                var dataDiv = document.getElementById(tableId);
                if (dataDiv.style.display === "none") {
                    dataDiv.style.display = "block";
                } else {
                    dataDiv.style.display = "none";
                }
            }
        </script>
    </head>
    <body>
        <h1>数据库内容摘要</h1>
    """
    
    # 添加数据库整体信息
    html_content += f"""
        <div class="table-info">
            <h2>数据库概览</h2>
            <p>表数量: {len(tables)}</p>
            <p>生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="table-info">
            <h2>表关系图</h2>
            <div class="visualization">
                <img src="db_relationships.png" alt="数据库关系图">
            </div>
        </div>
    """
    
    # 添加每个表的信息
    for table in tables:
        html_content += f"""
        <div class="table-info">
            <h2>表: {table}</h2>
            <p>行数: {tables_summary[table]['row_count']}</p>
            
            <h3>列信息</h3>
            <table>
                <tr>
                    <th>列名</th>
                    <th>数据类型</th>
                </tr>
        """
        
        for i, col in enumerate(tables_summary[table]['columns']):
            col_type = tables_summary[table]['column_types'][i]
            html_content += f"""
                <tr>
                    <td>{col}</td>
                    <td>{col_type}</td>
                </tr>
            """
        
        html_content += """
            </table>
        """
        
        # 添加表可视化
        html_content += """
            <h3>可视化</h3>
            <div class="visualization">
        """
        
        column_types_img = f"{table}_column_types.png"
        if os.path.exists(OUTPUT_DIR / column_types_img):
            html_content += f"""
                <div>
                    <h4>列数据类型分布</h4>
                    <img src="{column_types_img}" alt="{table} 列类型">
                </div>
            """
        
        timeline_img = f"{table}_creation_timeline.png"
        if os.path.exists(OUTPUT_DIR / timeline_img):
            html_content += f"""
                <div>
                    <h4>创建时间分布</h4>
                    <img src="{timeline_img}" alt="{table} 创建时间">
                </div>
            """
        
        html_content += """
            </div>
        """
        
        # 添加表数据内容
        html_content += f"""
            <div class="data-section">
                <h3>表数据 <button class="toggle-btn" onclick="toggleDataDisplay('{table}_data')">显示/隐藏数据</button></h3>
                <div class="json-data" id="{table}_data" style="display: none;">
        """
        
        # 读取表的JSON数据
        json_file = OUTPUT_DIR / f"{table}.json"
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                try:
                    table_data = json.load(f)
                    if table_data:
                        # 如果有数据，创建表格显示
                        if table == "flows" and len(table_data) > 0 and "flow_data" in table_data[0]:
                            # 对于flows表，flow_data列内容可能很大，用压缩显示
                            html_content += "<table><tr>"
                            columns = list(table_data[0].keys())
                            for col in columns:
                                html_content += f"<th>{col}</th>"
                            html_content += "</tr>"
                            
                            for row in table_data:
                                html_content += "<tr>"
                                for col in columns:
                                    if col == "flow_data" and row[col]:
                                        # 显示摘要信息
                                        if isinstance(row[col], dict) and row[col]:
                                            html_content += f"<td>{{复杂JSON数据 (包含 {len(row[col])} 个键)}}</td>"
                                        else:
                                            html_content += f"<td>{{JSON数据}}</td>"
                                    else:
                                        value = str(row[col]).replace("<", "&lt;").replace(">", "&gt;")
                                        if len(value) > 100:
                                            value = value[:100] + "..."
                                        html_content += f"<td>{value}</td>"
                                html_content += "</tr>"
                            html_content += "</table>"
                        else:
                            # 其他表正常显示
                            html_content += "<table><tr>"
                            if table_data:
                                columns = list(table_data[0].keys())
                                for col in columns:
                                    html_content += f"<th>{col}</th>"
                                html_content += "</tr>"
                                
                                for row in table_data:
                                    html_content += "<tr>"
                                    for col in columns:
                                        value = str(row[col]).replace("<", "&lt;").replace(">", "&gt;")
                                        if len(value) > 100:
                                            value = value[:100] + "..."
                                        html_content += f"<td>{value}</td>"
                                    html_content += "</tr>"
                            html_content += "</table>"
                        
                        # 添加完整JSON数据
                        html_content += f"""
                            <h4>原始JSON数据</h4>
                            <pre>{json.dumps(table_data, indent=2, ensure_ascii=False)}</pre>
                        """
                    else:
                        html_content += "<p>表中没有数据</p>"
                except Exception as e:
                    html_content += f"<p>读取数据出错: {str(e)}</p>"
        else:
            html_content += f"<p>找不到表 {table} 的JSON数据文件</p>"
        
        html_content += """
                </div>
            </div>
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    # 写入HTML文件
    html_file = OUTPUT_DIR / "db_report.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"已创建HTML报告: {html_file}")

def main():
    """主函数"""
    try:
        print(f"开始生成数据库可视化报告...")
        print(f"数据库路径: {DB_PATH}")
        print(f"输出目录: {OUTPUT_DIR}")
        
        # 连接数据库
        conn = get_db_connection()
        
        # 获取所有表
        tables = get_all_tables(conn)
        print(f"找到 {len(tables)} 个表: {', '.join(tables)}")
        
        # 创建表摘要
        tables_summary = create_table_summary(conn, tables)
        
        # 导出表数据到JSON
        for table in tables:
            export_table_to_json(conn, table)
        
        # 生成可视化
        generate_table_visualizations(conn, tables)
        
        # 创建关系图
        create_relationships_visualization(tables_summary)
        
        # 创建HTML报告
        create_html_report(tables_summary, tables)
        
        print(f"数据库可视化报告已生成到: {OUTPUT_DIR}")
    
    except Exception as e:
        print(f"生成报告时出错: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main() 