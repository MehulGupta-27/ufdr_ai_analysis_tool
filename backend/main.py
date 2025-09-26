"""
Enhanced UFDR Analysis System with Neo4j, Vector Search, and AI.
"""

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from contextlib import asynccontextmanager

from config.settings import settings
from app.api.routes import router
from app.models.database import create_tables
from app.core.database_manager import db_manager
from app.repositories.neo4j_repository import neo4j_repo
from app.services.vector_service import vector_service

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Enhanced UFDR Analysis System...")
    
    try:
        # Create database tables
        create_tables()
        logger.info("PostgreSQL tables created successfully")
    except Exception as e:
        logger.warning(f"PostgreSQL tables creation failed: {str(e)} - continuing without PostgreSQL")
    
    # Note: Qdrant collections will be created dynamically per case
    # No need to create demo collections at startup
    logger.info("Qdrant will create collections dynamically per case")
    
    try:
        # Test Neo4j connection
        await neo4j_repo.execute_cypher("RETURN 1")
        logger.info("Neo4j connection established successfully")
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {str(e)} - continuing without graph database")
    
    logger.info("Application startup completed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Enhanced UFDR Analysis System...")
    try:
        db_manager.close_connections()
        neo4j_repo.close()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Enhanced UFDR Analysis System",
    description="AI-powered forensic analysis with Neo4j graph database and vector search",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Enhanced UFDR Analysis System API",
        "version": "2.0.0",
        "status": "running",
        "features": {
            "postgresql_storage": True,
            "neo4j_graph_analysis": True,
            "vector_semantic_search": True,
            "ai_enrichment": True,
            "natural_language_queries": True
        }
    }


@app.get("/api/v1/system/info")
async def get_system_info():
    """Get system information and capabilities"""
    return {
        "system": "Enhanced UFDR Analysis System",
        "version": "2.0.0",
        "databases": {
            "postgresql": "Structured data storage",
            "neo4j": "Graph relationships and network analysis",
            "qdrant": "Vector embeddings and semantic search",
            "redis": "Caching and session management"
        },
        "ai_capabilities": {
            "nlp_analysis": "Text analysis, sentiment, entity extraction",
            "semantic_search": "Vector-based similarity search",
            "relationship_mapping": "Communication network analysis",
            "pattern_detection": "Suspicious activity identification"
        }
    }

@app.get("/api/v1/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "message": "UFDR Analysis System is running",
        "port": settings.app_port,
        "version": "2.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )