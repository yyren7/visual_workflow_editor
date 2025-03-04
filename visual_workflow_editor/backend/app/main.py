## backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from visual_workflow_editor.backend.app.config import Config
from visual_workflow_editor.backend.app.routers import user, flow, llm
from visual_workflow_editor.backend.app.database import engine
from visual_workflow_editor.backend.app.models import Base

# Create the database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=Config.PROJECT_NAME,
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_CREDENTIALS,
    allow_methods=Config.CORS_METHODS,
    allow_headers=Config.CORS_HEADERS,
)

# Include routers
app.include_router(user.router)
app.include_router(flow.router)
app.include_router(llm.router)

@app.get("/")
async def root():
    return {"message": "Flow Editor API"}
