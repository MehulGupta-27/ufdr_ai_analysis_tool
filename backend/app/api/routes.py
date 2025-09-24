from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import os
import tempfile
from pydantic import BaseModel

from app.services.data_processor import data_processor
from app.services.ai_service import ai_service
from app.core.database_manager import db_manager
from app.repositories.neo4j_repository import neo4j_repo
from app.services.vector_service import vector_service

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    case_number: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class InvestigationRequest(BaseModel):
    case_number: str
    title: str
    description: Optional[str] = None
    investigator: str

@router.post("/upload-ufdr")
async def upload_ufdr_file(
    file: UploadFile = File(...),
    case_number: str = Form(...),
    investigator: str = Form(...)
):
    """Upload and process UFDR file"""
    
    try:
        print(f"📁 Received file: {file.filename}")
        print(f"📋 Case number: {case_number}")
        print(f"👤 Investigator: {investigator}")
        
        # Validate file type - accept more formats for UFDR
        allowed_extensions = ('.xml', '.json', '.csv', '.xlsx', '.ufdr', '.zip', '.txt')
        if not file.filename.lower().endswith(allowed_extensions):
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Please upload one of: {', '.join(allowed_extensions)}"
            )
        
        # Get file size
        content = await file.read()
        file_size = len(content)
        print(f"📊 File size: {file_size} bytes")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            print(f"💾 Saved to temporary file: {temp_file_path}")
            
            # Process the UFDR file
            print("🔄 Starting UFDR file processing...")
            result = await data_processor.process_ufdr_file(
                temp_file_path, case_number, investigator
            )
            
            print("✅ UFDR file processing completed")
            
            return JSONResponse(content={
                "success": True,
                "message": "UFDR file processed successfully",
                "filename": file.filename,
                "file_size": file_size,
                "case_number": case_number,
                "investigator": investigator,
                "result": result
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"🗑️  Cleaned up temporary file")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing UFDR file: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing UFDR file: {str(e)}")

@router.post("/query")
async def execute_query(request: QueryRequest):
    """Execute natural language query on forensic data"""
    
    try:
        # Execute hybrid search
        results = await ai_service.execute_hybrid_search(request.query)
        
        # Generate investigation report
        report = await ai_service.generate_investigation_report(results)
        
        return JSONResponse(content={
            "query": request.query,
            "results": results,
            "report": report,
            "success": True
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")

@router.get("/connections/{phone_number}")
async def find_connections(phone_number: str, depth: int = 2):
    """Find connections for a specific phone number"""
    
    try:
        connections = db_manager.find_connections(phone_number, depth)
        
        return JSONResponse(content={
            "phone_number": phone_number,
            "connections": connections,
            "total_connections": len(connections)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding connections: {str(e)}")

@router.post("/investigations")
async def create_investigation(request: InvestigationRequest):
    """Create a new investigation case"""
    
    try:
        # This would typically create a new investigation record
        # For now, return success response
        return JSONResponse(content={
            "message": "Investigation created successfully",
            "case_number": request.case_number,
            "investigator": request.investigator
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating investigation: {str(e)}")

@router.get("/investigations/{case_number}")
async def get_investigation(case_number: str):
    """Get investigation details and associated data"""
    
    try:
        # This would fetch investigation details from database
        # For now, return placeholder response
        return JSONResponse(content={
            "case_number": case_number,
            "status": "active",
            "message": "Investigation details retrieved successfully"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving investigation: {str(e)}")

@router.get("/search/semantic")
async def semantic_search(
    query: str,
    collection: str = "chat_messages",
    limit: int = 10,
    threshold: float = 0.7
):
    """Perform semantic search in vector database"""
    
    try:
        # Generate query embedding
        query_embeddings = await ai_service.generate_embeddings([query])
        
        if not query_embeddings:
            raise HTTPException(status_code=500, detail="Failed to generate query embedding")
        
        # Search in Qdrant
        results = db_manager.search_vectors(
            collection_name=collection,
            query_vector=query_embeddings[0],
            limit=limit,
            score_threshold=threshold
        )
        
        return JSONResponse(content={
            "query": query,
            "collection": collection,
            "results": results,
            "total_results": len(results)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in semantic search: {str(e)}")

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Get analytics summary of processed data"""
    
    try:
        # This would typically query the database for statistics
        # For now, return placeholder data
        summary = {
            "total_cases": 0,
            "total_chat_records": 0,
            "total_call_records": 0,
            "total_contacts": 0,
            "total_media_files": 0,
            "recent_activity": []
        }
        
        return JSONResponse(content=summary)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting analytics summary: {str(e)}")

@router.get("/graph/network/{case_id}")
async def get_communication_network(case_id: str):
    """Get communication network from Neo4j for a case"""
    
    try:
        # Get all persons for this case
        persons = await neo4j_repo.find_nodes('Person', {'case_id': case_id})
        person_ids = [p['id'] for p in persons]
        
        # Get communication network
        network = await neo4j_repo.find_communication_network(person_ids)
        
        return JSONResponse(content={
            "case_id": case_id,
            "network": network,
            "total_nodes": len(persons),
            "total_relationships": len(network)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting communication network: {str(e)}")

@router.get("/graph/centrality")
async def get_centrality_analysis():
    """Get centrality analysis from Neo4j"""
    
    try:
        centrality_data = await neo4j_repo.get_centrality_analysis()
        
        return JSONResponse(content={
            "centrality_analysis": centrality_data,
            "total_persons": len(centrality_data)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting centrality analysis: {str(e)}")

@router.get("/graph/path/{source_id}/{target_id}")
async def find_shortest_path(source_id: str, target_id: str):
    """Find shortest path between two persons"""
    
    try:
        path = await neo4j_repo.find_shortest_path(source_id, target_id)
        
        return JSONResponse(content={
            "source_id": source_id,
            "target_id": target_id,
            "path": path
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding shortest path: {str(e)}")

@router.post("/search/semantic/advanced")
async def advanced_semantic_search(request: QueryRequest):
    """Advanced semantic search with filters"""
    
    try:
        case_id = request.case_number
        data_types = request.filters.get('data_types', []) if request.filters else []
        limit = request.filters.get('limit', 10) if request.filters else 10
        
        results = await vector_service.semantic_search(
            query=request.query,
            case_id=case_id,
            data_types=data_types,
            limit=limit
        )
        
        return JSONResponse(content={
            "query": request.query,
            "case_id": case_id,
            "results": results,
            "total_results": len(results)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in advanced semantic search: {str(e)}")

@router.get("/search/similar-messages")
async def find_similar_messages(
    content: str,
    case_id: Optional[str] = None,
    limit: int = 5
):
    """Find messages similar to given content"""
    
    try:
        results = await vector_service.find_similar_messages(content, case_id, limit)
        
        return JSONResponse(content={
            "content": content,
            "case_id": case_id,
            "similar_messages": results,
            "total_results": len(results)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding similar messages: {str(e)}")

@router.get("/vector/stats")
async def get_vector_stats():
    """Get vector database statistics"""
    
    try:
        stats = await vector_service.get_collection_stats()
        
        return JSONResponse(content={
            "vector_database_stats": stats
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting vector stats: {str(e)}")

@router.post("/vector/initialize")
async def initialize_vector_collection():
    """Initialize vector collection"""
    
    try:
        await vector_service.initialize_collection()
        
        return JSONResponse(content={
            "message": "Vector collection initialized successfully"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing vector collection: {str(e)}")

@router.delete("/case/{case_id}/vectors")
async def delete_case_vectors(case_id: str):
    """Delete all vectors for a specific case"""
    
    try:
        success = await vector_service.delete_case_vectors(case_id)
        
        if success:
            return JSONResponse(content={
                "message": f"Vectors for case {case_id} deleted successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to delete case vectors")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting case vectors: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    
    try:
        # Check database connections
        status = {
            "status": "healthy",
            "databases": {
                "postgres": "connected",
                "qdrant": "connected",
                "neo4j": "connected",
                "redis": "connected"
            }
        }
        
        # Test vector service
        try:
            vector_stats = await vector_service.get_collection_stats()
            status["databases"]["qdrant"] = "connected"
        except:
            status["databases"]["qdrant"] = "disconnected"
        
        # Test Neo4j
        try:
            await neo4j_repo.execute_cypher("RETURN 1")
            status["databases"]["neo4j"] = "connected"
        except:
            status["databases"]["neo4j"] = "disconnected"
        
        return JSONResponse(content=status)
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )