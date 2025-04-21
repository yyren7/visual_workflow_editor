"""
嵌入向量模块单元测试
"""

# --- 添加 sys.path 修改 --- 
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added {project_root} to sys.path in test_embedding.py")
# --- 结束 sys.path 修改 --- 

import unittest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.embedding import create_embedding, cosine_similarity
from database.embedding.embedding_result import EmbeddingResult
from database.embedding.utils import calculate_similarity
from database.models import JsonEmbedding
from database.embedding.service import EmbeddingService
from database.embedding.config import embedding_config


class TestEmbeddingModule(unittest.TestCase):
    """嵌入向量模块测试用例"""
    
    def setUp(self):
        """测试前初始化"""
        # 创建模拟数据库会话
        self.mock_db = MagicMock(spec=Session)
        
        # 模拟添加和提交方法
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()
        self.mock_db.rollback = MagicMock()
        
        # 重置单例实例和全局缓存
        if '_embedding_service_instance' in globals():
            globals()['_embedding_service_instance'] = None

        # 确保在导入路径下的模块中的_lmstudio_client也被重置
        patch('database.embedding.service._lmstudio_client', None).start()
        self.addCleanup(patch.stopall)
    
    def tearDown(self):
        """测试后清理"""
        pass
    
    @patch('database.embedding.lmstudio_client.LMStudioClient')
    @patch('database.embedding.config.embedding_config.USE_LMSTUDIO', True)
    def test_create_embedding_vector(self, mock_client_class):
        """测试创建嵌入向量"""
        # 模拟LMStudio客户端
        mock_client = mock_client_class.return_value
        mock_client.create_embedding.return_value = [0.1, 0.2, 0.3]
        
        # 使用asyncio运行异步函数
        async def run_test():
            # 模拟EmbeddingService的get_instance方法
            with patch('database.embedding.api.EmbeddingService.get_instance') as mock_get_instance:
                # 使用模拟的服务直接调用方法，确保模拟生效
                service = EmbeddingService()
                # 手动设置模拟客户端
                service.lmstudio_client = mock_client
                # 为get_instance方法设置返回值
                mock_get_instance.return_value = service
                
                # 调用方法
                result = await service.create_embedding_vector("测试文本")
                # 验证结果
                self.assertEqual(len(result), 3)
                self.assertEqual(result, [0.1, 0.2, 0.3])
                # 验证模拟客户端被调用
                mock_client.create_embedding.assert_called_once_with("测试文本")
                
                # 重置模拟对象以便于下一次测试
                mock_client.create_embedding.reset_mock()
                
                # 现在测试通过service测试API功能
                result_api = await create_embedding("测试文本")
                self.assertEqual(result_api, [0.1, 0.2, 0.3])
                # 验证模拟客户端被正确调用
                mock_client.create_embedding.assert_called_once_with("测试文本")
        
        # 运行测试
        asyncio.run(run_test())
        
    @patch('database.embedding.api.EmbeddingService.get_instance')
    def test_get_embedding_model_info(self, mock_get_instance):
        """测试获取嵌入模型信息"""
        # 配置模拟对象
        mock_service = MagicMock()
        mock_service.get_model_info.return_value = {
            "model_name": "test_model",
            "vector_dimension": 768,
            "using_lmstudio": False
        }
        mock_get_instance.return_value = mock_service
        
        # 调用API
        result = get_embedding_model_info()
        
        # 验证结果
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["vector_dimension"], 768)
        self.assertFalse(result["using_lmstudio"])
        
        # 验证mock_get_instance被调用
        mock_get_instance.assert_called_once()


if __name__ == '__main__':
    unittest.main() 