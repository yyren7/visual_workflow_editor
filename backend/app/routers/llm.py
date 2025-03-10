## Code: backend/app/routers/llm.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app import database, schemas
from backend.app.config import Config
from backend.app.utils import get_current_user
import httpx  # For making HTTP requests to the LLM API
import json

router = APIRouter(
    prefix="/llm",
    tags=["llm"],
    responses={404: {"description": "Not found"}},
)

LLM_API_URL = Config.LLM_API_URL
LLM_API_KEY = Config.LLM_API_KEY  # Retrieve LLM API key from config


async def call_llm_api(endpoint: str, data: dict):
    """
    Helper function to call the LLM API.
    """
    url = f"{LLM_API_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"  # Add API key to header if available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to LLM API: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Error decoding LLM API response: {str(e)}")


@router.post("/generate_node", response_model=schemas.NodeData, description="Generate a new node using LLM")
async def generate_node(prompt: str, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Generates a new node using the LLM based on the provided prompt.
    """
    try:
        llm_response = await call_llm_api("/generate", {"prompt": prompt})  # Adjust endpoint as needed
        node_data = llm_response.get("node_data")

        if not node_data:
             raise HTTPException(status_code=500, detail="LLM API did not return node data")

        # Basic validation of node_data structure (can be expanded)
        if not isinstance(node_data, dict) or "type" not in node_data or "data" not in node_data:
            raise HTTPException(status_code=500, detail="Invalid node data format from LLM API")

        return schemas.NodeData(**node_data)  # Ensure it matches the schema
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating node: {str(e)}")


@router.post("/update_node/{node_id}", description="Update a node using LLM")
async def update_node_by_llm(node_id: str, prompt: str, db: Session = Depends(database.get_db), current_user: schemas.User = Depends(get_current_user)):
    """
    Updates an existing node using the LLM based on the provided prompt and node ID.
    """
    try:
        llm_response = await call_llm_api(f"/update/{node_id}", {"prompt": prompt})  # Adjust endpoint as needed
        updated_node_data = llm_response.get("node_data")

        if not updated_node_data:
            raise HTTPException(status_code=500, detail="LLM API did not return updated node data")

         # Basic validation of updated_node_data structure (can be expanded)
        if not isinstance(updated_node_data, dict) or "data" not in updated_node_data:
            raise HTTPException(status_code=500, detail="Invalid updated node data format from LLM API")

        return updated_node_data  # Return the updated node data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating node: {str(e)}")
