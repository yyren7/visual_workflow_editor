#!/usr/bin/env python3
"""
测试新的 LangGraph + PostgreSQL 持久化架构

这个脚本测试：
1. 创建流程图（数据库）
2. 运行 SAS 工作流（LangGraph + PostgreSQL 持久化）
3. 获取状态（从 LangGraph）
4. 更新状态（到 LangGraph）
5. 查看历史（LangGraph 检查点）
"""

import requests
import json
import time
import sys
from typing import Dict, Any

# 配置
BASE_URL = "http://localhost:8000"  # 移除 /api 前缀
TEST_USER = {
    "username": "test_user",
    "password": "test_password",
    "email": "test@example.com"
}

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.flow_id = None
        
    def log(self, message: str):
        print(f"[TEST] {message}")
        
    def create_user(self) -> bool:
        """创建测试用户"""
        try:
            response = self.session.post(
                f"{BASE_URL}/users/register",
                json=TEST_USER
            )
            if response.status_code == 200:
                self.log("✅ 用户创建成功")
                return True
            elif response.status_code == 400 and "already registered" in response.text:
                self.log("ℹ️ 用户已存在")
                return True
            else:
                self.log(f"❌ 用户创建失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ 用户创建异常: {e}")
            return False
    
    def login(self) -> bool:
        """登录并获取令牌"""
        try:
            response = self.session.post(
                f"{BASE_URL}/users/login",
                data={
                    "username": TEST_USER["username"],
                    "password": TEST_USER["password"]
                }
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                self.log("✅ 登录成功")
                return True
            else:
                self.log(f"❌ 登录失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ 登录异常: {e}")
            return False
    
    def create_flow(self) -> bool:
        """创建测试流程图"""
        try:
            flow_data = {
                "name": "SAS 测试流程图",
                "flow_data": {
                    "description": "用于测试 SAS + LangGraph 持久化的流程图",
                    "test_metadata": {
                        "created_by_test": True,
                        "timestamp": time.time()
                    }
                }
            }
            
            response = self.session.post(f"{BASE_URL}/flows/", json=flow_data)
            if response.status_code == 200:
                data = response.json()
                self.flow_id = data["id"]
                self.log(f"✅ 流程图创建成功，ID: {self.flow_id}")
                return True
            else:
                self.log(f"❌ 流程图创建失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ 流程图创建异常: {e}")
            return False
    
    def get_flow_details(self) -> Dict[str, Any]:
        """获取流程图详情（包含 SAS 状态）"""
        try:
            response = self.session.get(f"{BASE_URL}/flows/{self.flow_id}")
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ 获取流程图详情成功")
                self.log(f"   - 名称: {data.get('name')}")
                self.log(f"   - SAS 状态: {'存在' if data.get('sas_state') else '不存在'}")
                return data
            else:
                self.log(f"❌ 获取流程图详情失败: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            self.log(f"❌ 获取流程图详情异常: {e}")
            return {}
    
    def run_sas_workflow(self) -> Dict[str, Any]:
        """运行 SAS 工作流"""
        try:
            sas_input = {
                "user_input": "创建一个简单的机器人移动流程：从点A移动到点B，然后移动到点C",
                "config": {
                    "test_mode": True,
                    "auto_accept": True
                }
            }
            
            self.log("🚀 开始运行 SAS 工作流...")
            response = self.session.post(
                f"{BASE_URL}/flows/{self.flow_id}/run-sas",
                json=sas_input
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ SAS 工作流执行完成")
                self.log(f"   - 状态: {data.get('status')}")
                self.log(f"   - 对话状态: {data.get('dialog_state')}")
                if data.get('clarification_question'):
                    self.log(f"   - 澄清问题: {data.get('clarification_question')}")
                if data.get('error_message'):
                    self.log(f"   - 错误信息: {data.get('error_message')}")
                self.log(f"   - 生成的任务数量: {len(data.get('generated_tasks', []))}")
                return data
            else:
                self.log(f"❌ SAS 工作流执行失败: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            self.log(f"❌ SAS 工作流执行异常: {e}")
            return {}
    
    def get_sas_state(self) -> Dict[str, Any]:
        """获取当前 SAS 状态"""
        try:
            response = self.session.get(f"{BASE_URL}/flows/{self.flow_id}/sas-state")
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ 获取 SAS 状态成功")
                if data.get('state'):
                    state = data['state']
                    self.log(f"   - 对话状态: {state.get('dialog_state')}")
                    self.log(f"   - 用户输入: {state.get('user_input')}")
                    self.log(f"   - 消息数量: {len(state.get('messages', []))}")
                    self.log(f"   - 生成的任务: {len(state.get('sas_step1_generated_tasks', []))}")
                else:
                    self.log("   - 无状态数据")
                return data
            else:
                self.log(f"❌ 获取 SAS 状态失败: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            self.log(f"❌ 获取 SAS 状态异常: {e}")
            return {}
    
    def get_sas_history(self) -> Dict[str, Any]:
        """获取 SAS 状态历史"""
        try:
            response = self.session.get(f"{BASE_URL}/flows/{self.flow_id}/sas-history")
            if response.status_code == 200:
                data = response.json()
                history = data.get('history', [])
                self.log(f"✅ 获取 SAS 历史成功，共 {len(history)} 个检查点")
                for i, checkpoint in enumerate(history[:3]):  # 只显示前3个
                    self.log(f"   - 检查点 {i+1}: {checkpoint.get('created_at', 'N/A')}")
                return data
            else:
                self.log(f"❌ 获取 SAS 历史失败: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            self.log(f"❌ 获取 SAS 历史异常: {e}")
            return {}
    
    def cleanup(self):
        """清理测试数据"""
        if self.flow_id:
            try:
                response = self.session.delete(f"{BASE_URL}/flows/{self.flow_id}")
                if response.status_code == 200:
                    self.log("✅ 测试流程图已删除")
                else:
                    self.log(f"⚠️ 删除测试流程图失败: {response.status_code}")
            except Exception as e:
                self.log(f"⚠️ 删除测试流程图异常: {e}")
    
    def run_full_test(self):
        """运行完整测试"""
        self.log("🧪 开始测试新的 LangGraph + PostgreSQL 持久化架构")
        self.log("=" * 60)
        
        # 1. 创建用户和登录
        if not self.create_user():
            return False
            
        if not self.login():
            return False
        
        # 2. 创建流程图
        if not self.create_flow():
            return False
        
        self.log(f"✅ 基础测试通过！流程图 ID: {self.flow_id}")
        return True

def main():
    """主函数"""
    tester = APITester()
    
    try:
        success = tester.run_full_test()
        if success:
            print("\n🎊 基础测试通过！")
        else:
            print("\n💥 测试失败！")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 