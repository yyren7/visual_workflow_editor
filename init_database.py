#!/usr/bin/env python3
"""
Database initialization script
Creates all necessary tables including newly added fields
"""

import sys
import os
sys.path.append('/workspace')

from database.connection import get_db_engine, Base
from database.models import User, Flow, Chat, FlowVariable, VersionInfo, JsonEmbedding
from sqlalchemy import text

def init_database():
    """Initialize the database"""
    print("Starting database initialization...")
    
    try:
        # Get engine
        engine = get_db_engine()
        
        # First check database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ Database connection OK")
        
        # Create all tables
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables creation completed")
        
        # For PostgreSQL, ensure pgvector extension is enabled
        if "postgresql" in str(engine.url):
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                    print("✅ pgvector extension enabled")
            except Exception as e:
                print(f"⚠️ Failed to enable pgvector extension: {e}")
        
        print("🎉 Database initialization completed!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1) 