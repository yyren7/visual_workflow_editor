"""
语义搜索和节点搜索单元测试
"""

import unittest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from backend.langchainchat.embeddings.semantic_search import search_by_text
from backend.langchainchat.embeddings.node_search import search_nodes, load_node_database
from backend.langchainchat.embeddings.config import search_config


class TestSearchModules(unittest.TestCase):
    """搜索模块测试用例"""
    
    def setUp(self):
        """测试前初始化"""
        # 创建模拟数据库会话
        self.mock_db = MagicMock(spec=Session)
        
        # 模拟查询结果
        self.mock_query_result = MagicMock()
        self.mock_db.query.return_value.all.return_value = [self.mock_query_result]
        
        # 创建模拟嵌入记录
        self.mock_embedding = MagicMock()
        self.mock_embedding.id = 1
        self.mock_embedding.json_data = {"test": "data"}
        self.mock_embedding.embedding_vector = [0.1, 0.2, 0.3]
        
        # 添加到查询结果
        self.mock_query_result.id = 1
        self.mock_query_result.json_data = {"test": "data"}
        self.mock_query_result.embedding_vector = [0.1, 0.2, 0.3]
    
    def tearDown(self):
        """测试后清理"""
        pass
    
    @patch('backend.langchainchat.embeddings.semantic_search.DatabaseEmbeddingService')
    def test_search_by_text(self, mock_db_service_class):
        """测试文本语义搜索"""
        # 模拟 DatabaseEmbeddingService 实例及其 similarity_search 方法
        mock_service_instance = MagicMock()
        # Configure the return value for the async similarity_search method
        # The return value should be a list of dicts as expected by the test
        async def mock_similarity_search(*args, **kwargs):
            # Simulate finding one result matching the setUp data
            return [{
                "id": 1,
                "data": {"test": "data"},
                "score": 0.8 # Example score
            }]
        mock_service_instance.similarity_search = MagicMock(side_effect=mock_similarity_search)
        mock_db_service_class.return_value = mock_service_instance
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 调用搜索API
            results = await search_by_text(self.mock_db, "测试查询")
            
            # 验证结果
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["id"], 1)
            self.assertEqual(results[0]["data"], {"test": "data"})
            self.assertTrue("score" in results[0])
            # Optionally, verify the similarity_search method was called correctly
            mock_service_instance.similarity_search.assert_called_once_with(
                db=self.mock_db, 
                query="测试查询", 
                threshold=search_config.DEFAULT_SIMILARITY_THRESHOLD, # Use the actual default from config
                k=search_config.DEFAULT_SEARCH_LIMIT # Use the actual default from config
            )
        
        # 运行测试
        asyncio.run(run_test())
    
    @patch('backend.langchainchat.embeddings.node_search.load_node_database')
    def test_node_search(self, mock_load_database):
        """测试节点搜索"""
        # 模拟节点数据库
        mock_node_cache = {
            "test_node.xml": {
                "json_data": {
                    "id": "test_node",
                    "type": "process",
                    "fields": {"name": "Test Node"}
                },
                "file_path": "/path/to/test_node.xml"
            }
        }
        mock_load_database.return_value = mock_node_cache
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 调用搜索API
            results = await search_nodes("process node")
            
            # 验证结果
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["data"]["id"], "test_node")
            self.assertEqual(results[0]["data"]["type"], "process")
        
        # 运行测试
        asyncio.run(run_test())
    
    @patch('backend.langchainchat.embeddings.node_search._get_node_template_service')
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_node_database(self, mock_listdir, mock_exists, mock_get_service):
        """测试加载节点数据库"""
        # 模拟路径存在
        mock_exists.return_value = True
        
        # 模拟目录列表
        mock_listdir.return_value = ["test_node.xml"]
        
        # 模拟模板服务
        mock_get_service.return_value = None
        
        # 模拟ET.parse
        with patch('xml.etree.ElementTree.parse') as mock_parse:
            # 模拟XML解析
            mock_root = MagicMock()
            mock_parse.return_value.getroot.return_value = mock_root
            
            # 模拟block元素
            mock_block = MagicMock()
            mock_block.get.return_value = "process"
            mock_root.findall.return_value = [mock_block]
            
            # 模拟field元素
            mock_field = MagicMock()
            mock_field.get.return_value = "name"
            mock_field.text = "Test Node"
            mock_block.findall.return_value = [mock_field]
            
            # 调用函数
            node_cache = load_node_database()
            
            # 验证结果
            self.assertIn("test_node.xml", node_cache)
            self.assertEqual(node_cache["test_node.xml"]["json_data"]["type"], "process")


if __name__ == '__main__':
    unittest.main() 