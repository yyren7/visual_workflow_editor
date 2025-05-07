"""
测试脚本，用于验证模块导入
"""
import os
import sys

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

print("测试导入...")

# 测试导入主要模块
try:
    from backend.app.services.chat_service import ChatService
    print("✓ 成功导入 ChatService")
except Exception as e:
    print(f"✗ 导入 ChatService 失败: {e}")

# 测试导入 context_collector
try:
    from backend.app.routers.chat import current_flow_id_var
    print("✓ 成功导入 current_flow_id_var")
except Exception as e:
    print(f"✗ 导入 current_flow_id_var 失败: {e}")

# 测试导入 backend.langgraphchat.memory
try:
    from backend.langgraphchat.memory.db_chat_memory import DbChatMemory
    print("✓ 成功导入 DbChatMemory")
except Exception as e:
    print(f"✗ 导入 DbChatMemory 失败: {e}")

# 测试导入 workflow_graph
try:
    from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
    print("✓ 成功导入 compile_workflow_graph")
except Exception as e:
    print(f"✗ 导入 compile_workflow_graph 失败: {e}")

# 测试导入 langgraph
try:
    from langgraph.graph import StateGraph
    print("✓ 成功导入 langgraph.graph.StateGraph")
except Exception as e:
    print(f"✗ 导入 langgraph.graph.StateGraph 失败: {e}")

print("导入测试完成。") 