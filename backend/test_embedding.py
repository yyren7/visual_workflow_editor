import os
import json
import asyncio
import sys

# 添加当前目录到Python路径，确保可以正确导入app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.embeddings.service import EmbeddingService
from app.embeddings.models import JsonEmbedding
import glob

# 设置数据库连接
DATABASE_URL = "sqlite:///./flow_editor.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 确保表存在
Base.metadata.create_all(bind=engine)

# 创建嵌入服务
embedding_service = EmbeddingService(model_name="BAAI/bge-large-zh-v1.5")

async def import_mg400_documents():
    """从mg400目录导入文档并创建嵌入向量"""
    db = SessionLocal()
    try:
        # 获取数据目录中的所有JSON文件 - 修正路径，使用绝对路径
        # 确定项目根目录 (backend的父目录)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mg400_path = os.path.join(project_root, "database", "document_database", "mg400")
        
        json_files = glob.glob(os.path.join(mg400_path, "*.json"))
        print(f"搜索路径: {mg400_path}")
        print(f"发现 {len(json_files)} 个JSON文件")
        
        # 逐个处理JSON文件
        for json_file in json_files:
            filename = os.path.basename(json_file)
            print(f"处理文件: {filename}")
            
            # 读取JSON文件
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 创建嵌入向量
            embedding = await embedding_service.create_embedding(db, json_data)
            print(f"成功为 {filename} 创建嵌入向量 (ID: {embedding.id})")
        
        print("所有文档导入完成")
    except Exception as e:
        print(f"导入过程中出错: {str(e)}")
    finally:
        db.close()

async def test_similarity_search():
    """测试相似度搜索功能"""
    db = SessionLocal()
    try:
        # 选择一个示例JSON进行测试
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mg400_path = os.path.join(project_root, "database", "document_database", "mg400")
        
        json_files = glob.glob(os.path.join(mg400_path, "*.json"))
        if not json_files:
            print("没有找到测试文件")
            return
            
        test_file = json_files[0]
        print(f"使用 {os.path.basename(test_file)} 进行相似度测试")
        
        # 读取测试文件
        with open(test_file, 'r', encoding='utf-8') as f:
            test_json = json.load(f)
        
        # 查找相似的文档
        similar_docs = await embedding_service.find_similar(
            db, 
            test_json, 
            threshold=0.7,  # 设置较低的阈值以获取更多结果
            limit=5
        )
        
        print(f"找到 {len(similar_docs)} 个相似文档:")
        for i, doc in enumerate(similar_docs):
            print(f"{i+1}. ID: {doc.id}, 文档: "
                  f"{json.dumps(doc.json_data, ensure_ascii=False)[:100]}...")
    except Exception as e:
        print(f"相似度搜索测试中出错: {str(e)}")
    finally:
        db.close()

async def main():
    """主函数"""
    # 在测试之前清空表
    print("清空现有的嵌入向量表...")
    db = SessionLocal()
    db.query(JsonEmbedding).delete()
    db.commit()
    db.close()
    
    # 导入文档并创建嵌入向量
    print("开始导入文档...")
    await import_mg400_documents()
    
    # 测试相似度搜索
    print("\n测试相似度搜索...")
    await test_similarity_search()

if __name__ == "__main__":
    asyncio.run(main()) 