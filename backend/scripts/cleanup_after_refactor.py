#!/usr/bin/env python3
"""
重构后清理冗余文件

此脚本用于删除在重构嵌入向量和语义搜索功能后不再需要的冗余文件。
在运行此脚本前，请确保已经完成测试并验证新功能正常工作。
"""

import os
import shutil
import sys
from pathlib import Path


# 待删除的文件夹
DIRECTORIES_TO_DELETE = [
    'database/embeddings'
]

# 待删除的单个文件 (相对于项目根目录的路径)
FILES_TO_DELETE = [
    # 在此添加单个文件路径
]


def confirm_action():
    """确认是否执行删除操作"""
    print("警告：此操作将删除以下目录和文件：")
    
    print("\n目录：")
    for directory in DIRECTORIES_TO_DELETE:
        print(f"  - {directory}")
    
    if FILES_TO_DELETE:
        print("\n文件：")
        for file_path in FILES_TO_DELETE:
            print(f"  - {file_path}")
    
    print("\n这些文件可能包含重要数据。删除前请确保：")
    print("1. 所有功能已经迁移到新的模块")
    print("2. 单元测试已经通过")
    print("3. 集成测试已经通过")
    print("4. 已经创建代码备份或使用版本控制系统")
    
    response = input("\n是否继续删除？(yes/no): ")
    return response.lower() == 'yes'


def delete_directories(base_path):
    """删除指定目录"""
    for directory in DIRECTORIES_TO_DELETE:
        dir_path = os.path.join(base_path, directory)
        if os.path.exists(dir_path):
            try:
                print(f"删除目录: {dir_path}")
                shutil.rmtree(dir_path)
                print(f"✓ 目录已删除: {dir_path}")
            except Exception as e:
                print(f"× 删除目录失败 {dir_path}: {str(e)}")
        else:
            print(f"! 目录不存在: {dir_path}")


def delete_files(base_path):
    """删除指定文件"""
    for file_path in FILES_TO_DELETE:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            try:
                print(f"删除文件: {full_path}")
                os.remove(full_path)
                print(f"✓ 文件已删除: {full_path}")
            except Exception as e:
                print(f"× 删除文件失败 {full_path}: {str(e)}")
        else:
            print(f"! 文件不存在: {full_path}")


def get_project_root():
    """获取项目根目录"""
    # 假设此脚本位于 backend/scripts 目录
    current_path = os.path.dirname(os.path.abspath(__file__))
    # 向上两级找到项目根目录
    return os.path.abspath(os.path.join(current_path, '..', '..'))


def main():
    """主函数"""
    print("嵌入向量与语义搜索重构后清理工具")
    print("==================================")
    
    # 获取项目根目录
    project_root = get_project_root()
    print(f"项目根目录: {project_root}")
    
    # 确认操作
    if not confirm_action():
        print("操作已取消")
        return
    
    # 执行删除
    print("\n开始删除...")
    delete_directories(project_root)
    delete_files(project_root)
    
    print("\n清理完成。如有错误，请检查输出信息。")


if __name__ == "__main__":
    main() 