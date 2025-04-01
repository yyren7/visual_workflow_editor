"""
问答服务和上下文服务单元测试
"""

import unittest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from backend.langchainchat.services.qa_service import QAService, get_qa_service
from backend.langchainchat.services.context_service import ContextService, get_context_service


class TestServices(unittest.TestCase):
    """服务模块测试用例"""
    
    def setUp(self):
        """测试前初始化"""
        # 创建模拟数据库会话
        self.mock_db = MagicMock(spec=Session)
        
        # 全局客户端重置
        if '_llm_client' in globals():
            globals()['_llm_client'] = None
        if '_qa_service_instance' in globals():
            globals()['_qa_service_instance'] = None
        if '_context_service_instance' in globals():
            globals()['_context_service_instance'] = None
    
    def tearDown(self):
        """测试后清理"""
        pass
    
    @patch('backend.langchainchat.services.qa_service.search_by_text')
    @patch('backend.langchainchat.services.qa_service.search_nodes')
    @patch('backend.langchainchat.services.qa_service.OpenAI')
    def test_query_with_context(self, mock_openai, mock_search_nodes, mock_search_text):
        """测试使用上下文回答问题"""
        # 模拟语义搜索结果
        mock_search_text.return_value = [
            {"id": 1, "data": {"content": "测试内容1"}, "score": 0.8}
        ]
        
        # 模拟节点搜索结果
        mock_search_nodes.return_value = [
            {"id": 2, "data": {"id": "node1", "type": "process", "fields": {"name": "Test Node"}}}
        ]
        
        # 模拟OpenAI客户端
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 模拟聊天完成响应
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "这是测试回答"
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_response
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 创建QA服务
            qa_service = QAService()
            
            # 调用问答API
            response = await qa_service.query_with_context(self.mock_db, "测试问题")
            
            # 验证结果
            self.assertEqual(response, "这是测试回答")
            mock_search_text.assert_called_once()
            mock_search_nodes.assert_called_once()
            mock_client.chat.completions.create.assert_called_once()
        
        # 运行测试
        asyncio.run(run_test())
    
    @patch('backend.langchainchat.services.qa_service.QAService')
    def test_get_qa_service(self, mock_service_class):
        """测试获取QA服务实例"""
        # 模拟服务类
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        # 调用函数
        service1 = get_qa_service()
        service2 = get_qa_service()
        
        # 验证单例模式
        self.assertEqual(service1, service2)
        # 验证只创建一次
        mock_service_class.assert_called_once()
    
    @patch('backend.langchainchat.services.context_service.search_nodes')
    def test_collect_node_context(self, mock_search_nodes):
        """测试收集节点上下文"""
        # 模拟节点搜索结果
        mock_search_nodes.return_value = [
            {"id": 1, "data": {"id": "node1", "type": "process"}},
            {"id": 2, "data": {"id": "node2", "type": "decision"}}
        ]
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 创建上下文服务
            context_service = ContextService()
            
            # 调用上下文收集API
            context = await context_service.collect_node_context()
            
            # 验证结果
            self.assertIn("node1", context)
            self.assertIn("node2", context)
            self.assertIn("process", context)
            self.assertIn("decision", context)
        
        # 运行测试
        asyncio.run(run_test())
    
    @patch('backend.langchainchat.services.context_service.ContextService.collect_system_context')
    @patch('backend.langchainchat.services.context_service.ContextService.collect_database_context')
    @patch('backend.langchainchat.services.context_service.ContextService.collect_node_context')
    def test_collect_all_context(self, mock_node_context, mock_db_context, mock_system_context):
        """测试收集所有上下文"""
        # 模拟各部分上下文
        mock_system_context.return_value = "系统正常运行中"
        mock_db_context.return_value = "数据库中有 10 条嵌入记录"
        mock_node_context.return_value = "- node1 (类型: process)\n- node2 (类型: decision)"
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 创建上下文服务
            context_service = ContextService()
            
            # 调用上下文收集API
            context = await context_service.collect_all(self.mock_db)
            
            # 验证结果
            self.assertIn("系统正常运行中", context)
            self.assertIn("数据库中有 10 条嵌入记录", context)
            self.assertIn("node1", context)
            self.assertIn("node2", context)
            
            # 验证调用
            mock_system_context.assert_called_once()
            mock_db_context.assert_called_once()
            mock_node_context.assert_called_once()
        
        # 运行测试
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main() 