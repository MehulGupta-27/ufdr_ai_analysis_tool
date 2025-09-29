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
from app.services.ufdr_report_generator import ufdr_report_generator
from app.services.pdf_generator import pdf_generator
from app.services.case_manager import case_manager
from app.services.schema_service import schema_service
from app.models.database import get_db
from sqlalchemy import text

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
        
        # Validate file type - accept ONLY .ufdr as per new strict parser
        allowed_extensions = ('.ufdr',)
        if not file.filename.lower().endswith(allowed_extensions):
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Please upload a .ufdr file"
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
        # Get case number from request or use most recent active case
        case_number = getattr(request, 'case_number', None)
        if not case_number:
            active_cases = case_manager.list_active_cases()
            if active_cases:
                case_number = active_cases[-1]  # Get the most recent case
                print(f"🎯 Using most recent case: {case_number}")
        
        # Execute hybrid search with case context - now returns processed response
        results = await ai_service.execute_hybrid_search(request.query, case_number)
        
        return JSONResponse(content={
            "query": request.query,
            "case_number": case_number,
            "answer": results.get("answer", "No response generated"),
            "success": results.get("success", False),
            "data_sources": results.get("data_sources", {})
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
        # Dynamic overall statistics across active cases
        summary = {
            "total_cases": 0,
            "total_chat_records": 0,
            "total_call_records": 0,
            "total_contacts": 0,
            "total_media_files": 0,
            "recent_activity": []
        }
        db = next(get_db())
        active_cases = case_manager.list_active_cases()
        summary["total_cases"] = len(active_cases)
        for case in active_cases:
            info = case_manager.get_case_info(case)
            if not info:
                continue
            schema = f"case_{info['safe_case_name']}"
            try:
                summary["total_chat_records"] += db.execute(text(f"SELECT COUNT(*) FROM {schema}.chat_records")).scalar() or 0
                summary["total_call_records"] += db.execute(text(f"SELECT COUNT(*) FROM {schema}.call_records")).scalar() or 0
                summary["total_contacts"] += db.execute(text(f"SELECT COUNT(*) FROM {schema}.contacts")).scalar() or 0
                summary["total_media_files"] += db.execute(text(f"SELECT COUNT(*) FROM {schema}.media_files")).scalar() or 0
            except Exception:
                continue
        db.close()
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

@router.post("/generate-comprehensive-report")
async def generate_comprehensive_report(case_number: str = Form(...)):
    """Generate comprehensive UFDR analysis report with criminal risk assessment"""
    
    try:
        print(f"📊 Generating comprehensive report for case: {case_number}")
        
        # Generate comprehensive report
        report_result = await ufdr_report_generator.generate_comprehensive_report(case_number)
        
        if not report_result.get("success"):
            raise HTTPException(
                status_code=404, 
                detail=report_result.get("error", "Failed to generate report")
            )
        
        return JSONResponse(content={
            "success": True,
            "message": "Comprehensive report generated successfully",
            "case_number": case_number,
            "report": report_result
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating comprehensive report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@router.post("/generate-pdf-report")
async def generate_pdf_report(case_number: str = Form(...)):
    """Generate PDF report for download"""
    
    try:
        print(f"📄 Generating PDF report for case: {case_number}")
        
        # First generate comprehensive report
        report_result = await ufdr_report_generator.generate_comprehensive_report(case_number)
        
        if not report_result.get("success"):
            raise HTTPException(
                status_code=404, 
                detail=report_result.get("error", "Failed to generate report data")
            )
        
        # Generate PDF
        pdf_result = pdf_generator.generate_pdf_report(report_result)
        
        if not pdf_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=pdf_result.get("error", "Failed to generate PDF")
            )
        
        return JSONResponse(content={
            "success": True,
            "message": "PDF report generated successfully",
            "case_number": case_number,
            "pdf_data": pdf_result["pdf_data"],
            "filename": pdf_result["filename"],
            "size": pdf_result["size"]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating PDF report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@router.get("/quick-query")
async def quick_query(q: str, case_number: Optional[str] = None):
    """Quick query endpoint that returns concise, relevant answers for a specific case"""
    
    try:
        print(f"🔍 Quick query: '{q}' (Case: {case_number})")
        
        # If no case specified, try to get the most recent active case
        if not case_number:
            active_cases = case_manager.list_active_cases()
            if active_cases:
                case_number = active_cases[-1]  # Get the most recent case
                print(f"🎯 Using most recent case: {case_number}")
            else:
                print("⚠️ No case number provided and no active cases found")
                return JSONResponse(content={
                    "query": q,
                    "case_number": None,
                    "answer": "No active cases found. Please upload a UFDR file first to analyze forensic data.",
                    "success": False
                })
        
        # Execute search with case context - now returns processed response
        results = await ai_service.execute_hybrid_search(q, case_number)
        
        return JSONResponse(content={
            "query": q,
            "case_number": case_number,
            "answer": results.get("answer", "No response generated"),
            "success": results.get("success", False),
            "data_sources": results.get("data_sources", {})
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.post("/case/cleanup")
async def cleanup_all_data():
    """Clean all data from all databases"""
    
    try:
        print("🗑️ Starting complete data cleanup...")
        
        cleanup_result = await case_manager.delete_all_case_data()
        
        return JSONResponse(content={
            "success": True,
            "message": "All data cleaned successfully",
            "cleanup_result": cleanup_result
        })
        
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}")

@router.delete("/case/{case_number}/data")
async def clear_case_data(case_number: str):
    """Clear all data for a specific case"""
    
    try:
        print(f"🗑️ Clearing data for case: {case_number}")
        
        success = await data_processor.clear_case_data(case_number)
        
        if success:
            return JSONResponse(content={
                "success": True,
                "message": f"Data cleared successfully for case {case_number}",
                "case_number": case_number
            })
        else:
            raise HTTPException(status_code=404, detail=f"Case {case_number} not found or could not be cleared")
        
    except Exception as e:
        print(f"❌ Error clearing case data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing case data: {str(e)}")

@router.get("/case/list")
async def list_active_cases():
    """List all active cases"""
    
    try:
        cases = case_manager.list_active_cases()
        
        return JSONResponse(content={
            "success": True,
            "active_cases": cases,
            "total_cases": len(cases)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing cases: {str(e)}")

@router.get("/case/{case_number}/info")
async def get_case_info(case_number: str):
    """Get information about a specific case"""
    
    try:
        case_info = case_manager.get_case_info(case_number)
        
        if not case_info:
            raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
        
        return JSONResponse(content={
            "success": True,
            "case_info": case_info
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting case info: {str(e)}")

@router.get("/case/{case_number}/counts")
async def get_case_counts(case_number: str):
    """Dynamic per-case counts using SQL only."""
    try:
        info = case_manager.get_case_info(case_number)
        if not info:
            raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
        schema = f"case_{info['safe_case_name']}"
        db = next(get_db())
        counts = {
            "chat_records": 0,
            "call_records": 0,
            "contacts": 0,
            "media_files": 0
        }
        try:
            counts["chat_records"] = db.execute(text(f"SELECT COUNT(*) FROM {schema}.chat_records")).scalar() or 0
            counts["call_records"] = db.execute(text(f"SELECT COUNT(*) FROM {schema}.call_records")).scalar() or 0
            counts["contacts"] = db.execute(text(f"SELECT COUNT(*) FROM {schema}.contacts")).scalar() or 0
            counts["media_files"] = db.execute(text(f"SELECT COUNT(*) FROM {schema}.media_files")).scalar() or 0
        finally:
            db.close()
        return JSONResponse(content={"success": True, "case_number": case_number, "counts": counts})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting case counts: {str(e)}")

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

@router.post("/admin/cleanup-all")
async def admin_cleanup_all():
    """Delete all case data from Postgres, Qdrant, Neo4j and clear Redis cache."""
    try:
        cleanup_result = await case_manager.delete_all_case_data()
        from app.core.database_manager import db_manager
        cache_cleared = db_manager.clear_cache()
        return JSONResponse(content={
            "success": True,
            "cleanup": cleanup_result,
            "cache_cleared": cache_cleared
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/admin/cache-status")
async def admin_cache_status():
    """Check Redis caching availability."""
    from app.core.database_manager import db_manager
    return JSONResponse(content={
        "redis_alive": db_manager.ping_redis()
    })

@router.post("/schema/extract/{case_number}")
async def extract_case_schema(case_number: str):
    """Manually extract schema for a specific case to improve AI accuracy."""
    try:
        print(f"🔄 Manually extracting schema for case: {case_number}")
        
        schema_details = await schema_service.extract_case_schema(case_number)
        
        if schema_details:
            return JSONResponse(content={
                "success": True,
                "message": f"Schema extracted successfully for case {case_number}",
                "case_number": case_number,
                "tables": list(schema_details.get("tables", {}).keys()),
                "relationships": len(schema_details.get("relationships", [])),
                "statistics": schema_details.get("statistics", {})
            })
        else:
            raise HTTPException(status_code=404, detail=f"Could not extract schema for case {case_number}")
        
    except Exception as e:
        print(f"❌ Error extracting schema: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting schema: {str(e)}")

@router.get("/schema/summary/{case_number}")
async def get_schema_summary(case_number: str):
    """Get human-readable schema summary for a case."""
    try:
        # Ensure schema is extracted
        if not schema_service.is_schema_cached(case_number):
            await schema_service.extract_case_schema(case_number)
        
        schema_summary = schema_service.generate_schema_summary(case_number)
        
        return JSONResponse(content={
            "success": True,
            "case_number": case_number,
            "schema_summary": schema_summary
        })
        
    except Exception as e:
        print(f"❌ Error getting schema summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting schema summary: {str(e)}")

@router.get("/schema/details/{case_number}")
async def get_schema_details(case_number: str):
    """Get detailed schema information for a case."""
    try:
        schema_details = schema_service.get_cached_schema(case_number)
        
        if not schema_details:
            # Extract schema if not cached
            schema_details = await schema_service.extract_case_schema(case_number)
        
        if schema_details:
            return JSONResponse(content={
                "success": True,
                "case_number": case_number,
                "schema_details": schema_details
            })
        else:
            raise HTTPException(status_code=404, detail=f"Schema not found for case {case_number}")
        
    except Exception as e:
        print(f"❌ Error getting schema details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting schema details: {str(e)}")

@router.delete("/schema/cache/{case_number}")
async def clear_schema_cache(case_number: str):
    """Clear schema cache for a specific case."""
    try:
        schema_service.clear_schema_cache(case_number)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Schema cache cleared for case {case_number}"
        })
        
    except Exception as e:
        print(f"❌ Error clearing schema cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing schema cache: {str(e)}")

@router.post("/schema/refresh-all")
async def refresh_all_schemas():
    """Refresh schema cache for all active cases."""
    try:
        active_cases = case_manager.list_active_cases()
        refreshed_cases = []
        
        for case_number in active_cases:
            try:
                await schema_service.extract_case_schema(case_number)
                refreshed_cases.append(case_number)
            except Exception as e:
                print(f"⚠️ Failed to refresh schema for case {case_number}: {e}")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Schema refresh completed for {len(refreshed_cases)} cases",
            "refreshed_cases": refreshed_cases,
            "total_cases": len(active_cases)
        })
        
    except Exception as e:
        print(f"❌ Error refreshing all schemas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error refreshing all schemas: {str(e)}")

@router.post("/data/remove-duplicates/{case_number}")
async def remove_duplicate_data(case_number: str):
    """Remove duplicate records from a case."""
    try:
        result = await data_processor.remove_duplicate_data(case_number)
        
        if result["success"]:
            return JSONResponse(content={
                "success": True,
                "case_number": case_number,
                "duplicates_removed": result["duplicates_removed"],
                "total_removed": result["total_removed"],
                "message": f"Removed {result['total_removed']} duplicate records"
            })
        else:
            raise HTTPException(status_code=400, detail=result["error"])
        
    except Exception as e:
        print(f"❌ Error removing duplicates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing duplicates: {str(e)}")

@router.delete("/data/clear-case/{case_number}")
async def clear_case_data(case_number: str):
    """Clear all data for a specific case."""
    try:
        success = await data_processor.clear_case_data(case_number)
        
        if success:
            return JSONResponse(content={
                "success": True,
                "case_number": case_number,
                "message": f"All data cleared for case {case_number}"
            })
        else:
            raise HTTPException(status_code=400, detail=f"Failed to clear data for case {case_number}")
        
    except Exception as e:
        print(f"❌ Error clearing case data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing case data: {str(e)}")