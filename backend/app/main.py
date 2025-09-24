"""
Main FastAPI application for UFDR AI Analyzer.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import asyncio
from contextlib import asynccontextmanager

from app.api.routes import router
from config.settings import settings
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
    logger.info("Starting UFDR AI Analyzer...")
    
    try:
        # Initialize vector collection
        await vector_service.initialize_collection()
        logger.info("Vector service initialized")
    except Exception as e:
        logger.warning(f"Vector service initialization failed: {str(e)}")
    
    try:
        # Test Neo4j connection
        await neo4j_repo.execute_cypher("RETURN 1")
        logger.info("Neo4j connection established")
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down UFDR AI Analyzer...")
    neo4j_repo.close()


# Create FastAPI application
app = FastAPI(
    title="UFDR AI Analyzer",
    description="AI-powered forensic analysis tool for UFDR data",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "UFDR AI Analyzer API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/v1/status")
async def get_status():
    """Get application status."""
    return {
        "application": "UFDR AI Analyzer",
        "version": "1.0.0",
        "status": "healthy",
        "features": {
            "ufdr_parsing": True,
            "ai_enrichment": True,
            "vector_search": True,
            "graph_analysis": True,
            "natural_language_queries": True
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )