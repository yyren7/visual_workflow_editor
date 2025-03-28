from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Any

from database.connection import get_db
from backend.app.embeddings.service import EmbeddingService
from backend.app.embeddings.models import JsonEmbedding
from backend.app.embeddings.config import embedding_config

router = APIRouter(
    prefix="/api/embeddings",
    tags=["embeddings"],
    responses={404: {"description": "Not found"}},
)

@router.post("/create")
async def create_embedding(
    json_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """创建JSON数据的embedding"""
    service = EmbeddingService.get_instance()
    try:
        embedding = await service.create_embedding(db, json_data)
        return {
            "status": "success",
            "embedding_id": embedding.id,
            "message": "Successfully created embedding"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/find-similar")
async def find_similar(
    query_json: Dict[str, Any],
    threshold: float = embedding_config.DEFAULT_SIMILARITY_THRESHOLD,
    limit: int = embedding_config.DEFAULT_SEARCH_LIMIT,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """查找相似的JSON数据"""
    service = EmbeddingService.get_instance()
    try:
        similar_embeddings = await service.find_similar(
            db, 
            query_json,
            threshold=threshold,
            limit=limit
        )
        return [
            {
                "id": emb.id,
                "json_data": emb.json_data,
                "created_at": emb.created_at
            }
            for emb in similar_embeddings
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query")
async def query_with_llm(
    question: str,
    context_limit: int = 1,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """使用LLM回答基于相似文档的问题"""
    service = EmbeddingService.get_instance()
    try:
        response = await service.query_with_llm(
            db,
            question,
            context_limit=context_limit
        )
        return {
            "status": "success",
            "answer": response
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 