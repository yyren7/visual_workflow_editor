import os
import json
import time
import asyncio
import sys
import numpy as np
from typing import List, Tuple
import glob
import random

# 添加当前目录到Python路径，确保可以正确导入app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.embeddings.service import EmbeddingService
from app.embeddings.models import JsonEmbedding
from app.embeddings.utils import calculate_similarity

# 有条件地导入可视化相关的库
try:
    import matplotlib.pyplot as plt
    from sklearn.manifold import TSNE
    from sklearn.metrics import silhouette_score
    visualization_available = True
except ImportError:
    visualization_available = False
    print("警告: matplotlib或sklearn未安装，可视化功能将被禁用")


# 设置数据库连接
DATABASE_URL = "sqlite:///./flow_editor.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 确保表存在
Base.metadata.create_all(bind=engine)

# 创建嵌入服务
embedding_service = EmbeddingService(model_name="BAAI/bge-large-zh-v1.5")


async def benchmark_embedding_creation(
    json_files: List[str], sample_size: int = 10
) -> Tuple[float, List[float]]:
    """测试嵌入向量创建性能"""
    if sample_size > len(json_files):
        sample_size = len(json_files)
        
    # 随机选择文件进行测试
    selected_files = random.sample(json_files, sample_size)
    
    db = SessionLocal()
    times = []
    
    try:
        for json_file in selected_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 测量嵌入向量创建时间
            start_time = time.time()
            await embedding_service.create_embedding(db, json_data)
            end_time = time.time()
            
            times.append(end_time - start_time)
        
        avg_time = sum(times) / len(times)
        return avg_time, times
    finally:
        db.close()


async def test_embedding_quality():
    """测试嵌入向量的质量"""
    db = SessionLocal()
    try:
        # 获取所有嵌入向量
        embeddings = db.query(JsonEmbedding).all()
        if not embeddings:
            print("没有找到嵌入向量，请先运行导入")
            return
        
        # 提取向量和标签
        vectors = [np.array(emb.embedding_vector) for emb in embeddings]
        labels = [emb.id for emb in embeddings]
        
        # 计算所有向量对之间的相似度矩阵
        similarity_matrix = np.zeros((len(vectors), len(vectors)))
        for i in range(len(vectors)):
            for j in range(len(vectors)):
                similarity_matrix[i][j] = calculate_similarity(
                    vectors[i], vectors[j]
                )
        
        # 打印平均相似度
        np.fill_diagonal(similarity_matrix, 0)  # 排除自身相似度
        avg_similarity = np.mean(similarity_matrix)
        print(f"平均文档相似度: {avg_similarity:.4f}")
        
        # 使用t-SNE降维可视化（如果文档数量足够且有可视化库）
        if len(vectors) >= 10 and visualization_available:
            # 转换为numpy数组
            vectors_np = np.array(vectors)
            
            # 应用t-SNE降维
            tsne = TSNE(n_components=2, random_state=42)
            vectors_2d = tsne.fit_transform(vectors_np)
            
            # 计算聚类质量（轮廓系数）
            if len(vectors) >= 3:  # 轮廓系数需要至少3个样本
                silhouette_avg = silhouette_score(
                    vectors_np, labels, metric='cosine'
                )
                print(f"嵌入向量聚类质量（轮廓系数）: {silhouette_avg:.4f}")
            
            # 绘制t-SNE可视化图
            plt.figure(figsize=(10, 8))
            plt.scatter(
                vectors_2d[:, 0], 
                vectors_2d[:, 1], 
                c=range(len(vectors)), 
                cmap='viridis'
            )
            plt.colorbar(label='文档ID')
            plt.title('嵌入向量的t-SNE可视化')
            plt.savefig('embedding_visualization.png')
            print("嵌入向量可视化已保存为 'embedding_visualization.png'")
    except Exception as e:
        print(f"测试嵌入向量质量时出错: {str(e)}")
    finally:
        db.close()


async def test_cross_language_capability():
    """测试跨语言能力"""
    test_queries = [
        "工业机器人如何执行运动控制？",  # 中文
        "How does an industrial robot perform motion control?",  # 英文
        "産業用ロボットはどのように動作制御を行いますか？"  # 日文
    ]
    
    db = SessionLocal()
    try:
        print("测试跨语言检索能力...")
        
        for i, query in enumerate(test_queries):
            print(f"\n查询 {i+1}: {query}")
            
            # 直接使用文本查询
            query_embedding = embedding_service.embeddings.embed_query(query)
            
            # 获取所有嵌入向量
            all_embeddings = db.query(JsonEmbedding).all()
            
            # 计算相似度并排序
            results = []
            for emb in all_embeddings:
                similarity = calculate_similarity(
                    query_embedding, emb.embedding_vector
                )
                results.append((emb, similarity))
            
            results.sort(key=lambda x: x[1], reverse=True)
            
            # 显示前3个结果
            print("前3个相似结果:")
            for j, (emb, score) in enumerate(results[:3]):
                print(f"  {j+1}. 相似度: {score:.4f}, 文档ID: {emb.id}")
                print(f"     内容: "
                      f"{json.dumps(emb.json_data, ensure_ascii=False)[:80]}...")
    except Exception as e:
        print(f"测试跨语言能力时出错: {str(e)}")
    finally:
        db.close()


async def import_mg400_documents():
    """导入MG400文档数据并创建嵌入向量"""
    db = SessionLocal()
    try:
        # 获取JSON文件 - 修正路径
        # 确定项目根目录 (backend的父目录)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mg400_path = os.path.join(project_root, "database", "document_database", "mg400")
        
        json_files = glob.glob(os.path.join(mg400_path, "*.json"))
        print(f"搜索路径: {mg400_path}")
        print(f"发现 {len(json_files)} 个JSON文件")
        
        # 导入所有文件
        for json_file in json_files:
            filename = os.path.basename(json_file)
            print(f"处理文件: {filename}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            await embedding_service.create_embedding(db, json_data)
            
        print("所有文档导入完成")
        return json_files
    except Exception as e:
        print(f"导入文档时出错: {str(e)}")
        return []
    finally:
        db.close()


async def main():
    """主函数"""
    # 清空现有的嵌入向量表
    print("清空现有的嵌入向量表...")
    db = SessionLocal()
    db.query(JsonEmbedding).delete()
    db.commit()
    db.close()
    
    # 导入文档
    print("\n开始导入MG400文档...")
    json_files = await import_mg400_documents()
    
    if not json_files:
        print("没有找到JSON文件，无法继续测试")
        return
        
    # 性能测试
    print("\n测试嵌入向量创建性能...")
    avg_time, times = await benchmark_embedding_creation(
        json_files, sample_size=min(10, len(json_files))
    )
    print(f"平均嵌入向量创建时间: {avg_time:.4f} 秒")
    print(f"最短时间: {min(times):.4f} 秒, 最长时间: {max(times):.4f} 秒")
    
    # 嵌入向量质量测试
    print("\n测试嵌入向量质量...")
    await test_embedding_quality()
    
    # 跨语言能力测试
    print("\n测试跨语言能力...")
    await test_cross_language_capability()


if __name__ == "__main__":
    asyncio.run(main()) 