#!/usr/bin/env python3
"""
测试动态路径生成功能
"""

import sys
import os
sys.path.append('/workspace')

from backend.sas.prompt_loader import get_dynamic_output_path

def test_dynamic_path_generation():
    """测试动态路径生成功能"""
    print("=== 测试动态路径生成功能 ===")
    
    # 测试用例
    test_cases = [
        ("flow_123", "user1"),
        ("flow_abc-def", "用户测试"),
        ("flow@special#chars", "user@email.com"),
        ("flow_456", "admin"),
    ]
    
    for flow_id, username in test_cases:
        try:
            path = get_dynamic_output_path(flow_id, username)
            print(f"流程图ID: {flow_id}")
            print(f"用户名: {username}")
            print(f"生成路径: {path}")
            print("-" * 50)
        except Exception as e:
            print(f"生成路径失败: {e}")
            print(f"流程图ID: {flow_id}, 用户名: {username}")
            print("-" * 50)

def test_directory_creation():
    """测试目录创建功能"""
    print("=== 测试目录创建功能 ===")
    
    test_flow_id = "test_flow_001"
    test_username = "test_user"
    
    try:
        path = get_dynamic_output_path(test_flow_id, test_username)
        print(f"测试路径: {path}")
        
        # 创建目录
        os.makedirs(path, exist_ok=True)
        
        if os.path.exists(path):
            print("✅ 目录创建成功")
            
            # 创建一个子目录来模拟任务目录
            task_dir = os.path.join(path, "00_test_task")
            os.makedirs(task_dir, exist_ok=True)
            
            if os.path.exists(task_dir):
                print("✅ 任务子目录创建成功")
                
                # 创建一个测试XML文件
                test_xml_path = os.path.join(task_dir, "test_block.xml")
                with open(test_xml_path, 'w', encoding='utf-8') as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<xml><block id="test">Test Block</block></xml>')
                
                if os.path.exists(test_xml_path):
                    print("✅ 测试XML文件创建成功")
                    print(f"文件路径: {test_xml_path}")
                else:
                    print("❌ 测试XML文件创建失败")
            else:
                print("❌ 任务子目录创建失败")
        else:
            print("❌ 目录创建失败")
            
    except Exception as e:
        print(f"❌ 目录创建测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dynamic_path_generation()
    print()
    test_directory_creation()
    print("\n=== 测试完成 ===") 