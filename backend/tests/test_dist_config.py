#!/usr/bin/env python
"""
分布式配置系统测试脚本

使用此脚本验证新的分布式配置系统是否正常工作。
"""

def test_config():
    """测试配置系统"""
    # 导入配置字典和辅助函数
    from backend.config import (
        APP_CONFIG, 
        DB_CONFIG, 
        AI_CONFIG, 
        LANGCHAIN_CONFIG,
        get_env_bool,
        get_log_file_path
    )
    
    print("===== 分布式配置系统测试 =====")
    
    # 测试应用配置
    print(f"应用名称: {APP_CONFIG['PROJECT_NAME']}")
    print(f"调试模式: {APP_CONFIG['DEBUG']}")
    print(f"CORS源: {APP_CONFIG['CORS_ORIGINS']}")
    
    # 测试数据库配置
    print(f"数据库URL: {DB_CONFIG['DATABASE_URL']}")
    print(f"连接池大小: {DB_CONFIG['DB_POOL_SIZE']}")
    
    # 测试AI提供商配置
    print(f"使用DeepSeek: {AI_CONFIG['USE_DEEPSEEK']}")
    print(f"DeepSeek模型: {AI_CONFIG['DEEPSEEK_MODEL']}")
    print(f"当前LLM API URL: {AI_CONFIG['LLM_API_URL']}")
    
    # 测试LangChain配置
    print(f"LangChain模块名称: {LANGCHAIN_CONFIG['PROJECT_NAME']}")
    print(f"向量存储类型: {LANGCHAIN_CONFIG['VECTOR_STORE_TYPE']}")
    print(f"向量存储路径: {LANGCHAIN_CONFIG['VECTOR_STORE_PATH']}")
    print(f"LangChain日志文件: {LANGCHAIN_CONFIG['LANGCHAIN_LOG_FILE']}")
    
    # 测试辅助函数
    test_bool = get_env_bool("DEBUG", "1")
    print(f"DEBUG环境变量解析结果: {test_bool}")
    
    log_path = get_log_file_path("test.log")
    print(f"测试日志文件路径: {log_path}")
    
    print("===== 测试完成 =====")

if __name__ == "__main__":
    test_config() 