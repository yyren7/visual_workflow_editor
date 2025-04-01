"""
重构后的功能集成测试
"""

import unittest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

# 导入所有相关模块
from database.embedding import create_embedding, create_json_embedding
from backend.langchainchat.embeddings.semantic_search import search_by_text
from backend.langchainchat.embeddings.node_search import search_nodes
from backend.langchainchat.services.qa_service import get_qa_service
from backend.langchainchat.services.context_service import get_context_service


class TestIntegration(unittest.TestCase):
    """集成测试用例"""
    
    def setUp(self):
        """测试前初始化"""
        # 创建模拟数据库会话
        self.mock_db = MagicMock(spec=Session)
        
        # 重置全局缓存变量
        self._reset_globals()
    
    def tearDown(self):
        """测试后清理"""
        self._reset_globals()
    
    def _reset_globals(self):
        """重置全局缓存变量"""
        # 嵌入服务
        if '_embedding_service_instance' in globals():
            globals()['_embedding_service_instance'] = None
        # LMStudio客户端
        if '_lmstudio_client' in globals():
            globals()['_lmstudio_client'] = None
        # QA服务
        if '_qa_service_instance' in globals():
            globals()['_qa_service_instance'] = None
        # LLM客户端
        if '_llm_client' in globals():
            globals()['_llm_client'] = None
        # 上下文服务
        if '_context_service_instance' in globals():
            globals()['_context_service_instance'] = None
        # 节点缓存
        if '_node_cache' in globals():
            globals()['_node_cache'] = {}
    
    @patch('database.embedding.service.LMStudioClient')
    @patch('backend.langchainchat.embeddings.semantic_search.calculate_similarity')
    @patch('backend.langchainchat.services.qa_service.OpenAI')
    def test_full_workflow(self, mock_openai, mock_similarity, mock_lmstudio_client):
        """测试完整的工作流程"""
        # 模拟LMStudio客户端
        mock_client = MagicMock()
        mock_client.create_embedding.return_value = [0.1, 0.2, 0.3]
        mock_lmstudio_client.return_value = mock_client
        
        # 模拟相似度计算
        mock_similarity.return_value = 0.8
        
        # 模拟OpenAI响应
        mock_openai_client = MagicMock()
        mock_openai.return_value = mock_openai_client
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "这是集成测试回答"
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 步骤1: 创建嵌入向量
            embedding = await create_embedding("测试文本")
            self.assertEqual(len(embedding), 3)
            
            # 模拟嵌入查询结果
            self.mock_db.query.return_value.all.return_value = [MagicMock(
                id=1,
                json_data={"content": "测试内容"},
                embedding_vector=embedding,
                score=0.8
            )]
            
            # 步骤2: 语义搜索
            search_results = await search_by_text(self.mock_db, "测试查询")
            self.assertEqual(len(search_results), 1)
            
            # 步骤3: 节点搜索
            with patch('backend.langchainchat.embeddings.node_search.load_node_database') as mock_load:
                mock_load.return_value = {
                    "test_node.xml": {
                        "json_data": {
                            "id": "test_node",
                            "type": "process",
                            "fields": {"name": "Test Node"}
                        },
                        "file_path": "/path/to/test_node.xml"
                    }
                }
                
                node_results = await search_nodes("process")
                self.assertEqual(len(node_results), 1)
            
            # 步骤4: QA服务
            # 模拟搜索结果
            with patch('backend.langchainchat.services.qa_service.search_by_text') as mock_search_text:
                with patch('backend.langchainchat.services.qa_service.search_nodes') as mock_search_nodes:
                    mock_search_text.return_value = search_results
                    mock_search_nodes.return_value = node_results
                    
                    # 获取QA服务
                    qa_service = get_qa_service()
                    
                    # 使用上下文回答问题
                    answer = await qa_service.query_with_context(self.mock_db, "测试问题")
                    self.assertEqual(answer, "这是集成测试回答")
            
            # 步骤5: 上下文服务
            with patch('backend.langchainchat.services.context_service.search_nodes') as mock_search:
                mock_search.return_value = node_results
                
                # 获取上下文服务
                context_service = get_context_service()
                
                # 收集上下文
                context = await context_service.collect_all(self.mock_db)
                self.assertIsInstance(context, str)
                self.assertTrue(len(context) > 0)
        
        # 运行测试
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main() 