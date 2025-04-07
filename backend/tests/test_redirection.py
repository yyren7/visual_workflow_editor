#!/usr/bin/env python
"""
配置系统验证脚本

此脚本确保所有配置模块能够正确加载。
"""

def test_config():
    """测试配置系统"""
    
    print("===== 配置系统测试 =====")
    
    # 测试 backend/config 模块
    print("1. 测试 backend/config 模块:")
    from backend.config import APP_CONFIG
    print(f"  导入成功，APP_CONFIG存在")
    
    # 测试 Config 类替代方案
    print("\n2. 测试 APP_CONFIG 字典配置:")
    from backend.config import APP_CONFIG
    print(f"  APP_CONFIG字典可正常使用")
    print(f"  APP_CONFIG['PROJECT_NAME']: {APP_CONFIG['PROJECT_NAME']}")
    print(f"  APP_CONFIG['DEBUG']: {APP_CONFIG['DEBUG']}")
    
    # 测试 settings 替代方案
    print("\n3. 测试 LANGCHAIN_CONFIG 字典配置:")
    from backend.config import LANGCHAIN_CONFIG, AI_CONFIG
    print(f"  LANGCHAIN_CONFIG字典可正常使用")
    print(f"  LANGCHAIN_CONFIG['PROJECT_NAME']: {LANGCHAIN_CONFIG['PROJECT_NAME']}")
    print(f"  LANGCHAIN_CONFIG['VECTOR_STORE_TYPE']: {LANGCHAIN_CONFIG['VECTOR_STORE_TYPE']}")
    print(f"  AI_CONFIG['DEEPSEEK_MODEL']: {AI_CONFIG['DEEPSEEK_MODEL']}")
    
    print("\n===== 测试完成 =====")

if __name__ == "__main__":
    test_config() 