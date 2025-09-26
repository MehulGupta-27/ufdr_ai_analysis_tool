"""
Vector storage and semantic search service using Qdrant and Azure OpenAI embeddings.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from uuid import uuid4
import numpy as np
from openai import AzureOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from config.settings import settings

logger = logging.getLogger(__name__)


class VectorService:
    """Service for vector embeddings and semantic search."""
    
    def __init__(self):
        """Initialize vector service."""
        self.qdrant_client = None
        self.openai_client = None
        self.collection_name = "forensic_data"
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Qdrant and OpenAI clients."""
        try:
            # Initialize Qdrant client
            if settings.qdrant_url and settings.qdrant_api_key:
                logger.info(f"Initializing Qdrant client with URL: {settings.qdrant_url}")
                self.qdrant_client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key
                )
                # Test connection
                collections = self.qdrant_client.get_collections()
                logger.info(f"✅ Connected to Qdrant vector database - {len(collections.collections)} collections found")
            else:
                logger.warning(f"❌ Qdrant configuration missing - URL: {bool(settings.qdrant_url)}, API Key: {bool(settings.qdrant_api_key)}")
            
            # Initialize Azure OpenAI client
            if settings.embeddings_azure_endpoint and settings.embeddings_api_key:
                logger.info(f"Initializing Azure OpenAI client with endpoint: {settings.embeddings_azure_endpoint}")
                self.openai_client = AzureOpenAI(
                    azure_endpoint=settings.embeddings_azure_endpoint,
                    api_key=settings.embeddings_api_key,
                    api_version=settings.api_version
                )
                logger.info("✅ Connected to Azure OpenAI for embeddings")
            else:
                logger.warning(f"❌ Azure OpenAI configuration missing - Endpoint: {bool(settings.embeddings_azure_endpoint)}, API Key: {bool(settings.embeddings_api_key)}")
        except Exception as e:
            logger.error(f"❌ Error initializing vector service clients: {e}")
            import traceback
            traceback.print_exc()
                
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {str(e)}")
    
    # Removed: initialize_collection() - Collections are now created dynamically per case only
    # This eliminates the generic 'forensic_data' collection
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Azure OpenAI."""
        if not self.openai_client:
            logger.warning("OpenAI client not available")
            return []
        
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model=settings.azure_embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return []
    
    async def store_message_vector(self, message_data: Dict[str, Any]) -> bool:
        """Store message with its vector embedding."""
        if not self.qdrant_client or not message_data.get('content'):
            return False
        
        try:
            # Generate embedding for message content
            embedding = await self.generate_embedding(message_data['content'])
            if not embedding:
                return False
            
            # Create point for Qdrant
            point_id = str(uuid4())
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "message_id": message_data.get('id', ''),
                    "case_id": message_data.get('case_id', ''),
                    "sender": message_data.get('sender', ''),
                    "recipient": message_data.get('recipient', ''),
                    "content": message_data.get('content', ''),
                    "timestamp": message_data.get('message_timestamp', ''),
                    "message_type": message_data.get('message_type', ''),
                    "sentiment_score": message_data.get('sentiment_score', 0.0),
                    "suspicious_score": message_data.get('suspicious_score', 0.0),
                    "keywords": message_data.get('keywords', []),
                    "data_type": "chat_record"
                }
            )
            
            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored message vector: {point_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store message vector: {str(e)}")
            return False
    
    async def store_contact_vector(self, contact_data: Dict[str, Any]) -> bool:
        """Store contact with its vector embedding."""
        if not self.qdrant_client:
            return False
        
        try:
            # Create searchable text from contact data
            contact_text = f"{contact_data.get('name', '')} {' '.join(contact_data.get('phone_numbers', []))} {' '.join(contact_data.get('email_addresses', []))} {contact_data.get('organization', '')} {contact_data.get('notes', '')}"
            
            if not contact_text.strip():
                return False
            
            # Generate embedding
            embedding = await self.generate_embedding(contact_text)
            if not embedding:
                return False
            
            # Create point for Qdrant
            point_id = str(uuid4())
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "contact_id": contact_data.get('id', ''),
                    "case_id": contact_data.get('case_id', ''),
                    "name": contact_data.get('name', ''),
                    "phone_numbers": contact_data.get('phone_numbers', []),
                    "email_addresses": contact_data.get('email_addresses', []),
                    "organization": contact_data.get('organization', ''),
                    "notes": contact_data.get('notes', ''),
                    "searchable_text": contact_text,
                    "data_type": "contact"
                }
            )
            
            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored contact vector: {point_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store contact vector: {str(e)}")
            return False
    
    async def store_finding_vector(self, finding_data: Dict[str, Any]) -> bool:
        """Store finding with its vector embedding."""
        if not self.qdrant_client:
            return False
        
        try:
            # Create searchable text from finding data
            finding_text = f"{finding_data.get('title', '')} {finding_data.get('description', '')} {finding_data.get('category', '')} {' '.join(finding_data.get('recommendations', []))}"
            
            if not finding_text.strip():
                return False
            
            # Generate embedding
            embedding = await self.generate_embedding(finding_text)
            if not embedding:
                return False
            
            # Create point for Qdrant
            point_id = str(uuid4())
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "finding_id": finding_data.get('id', ''),
                    "case_id": finding_data.get('case_id', ''),
                    "title": finding_data.get('title', ''),
                    "description": finding_data.get('description', ''),
                    "category": finding_data.get('category', ''),
                    "severity": finding_data.get('severity', ''),
                    "confidence_score": finding_data.get('confidence_score', 0.0),
                    "recommendations": finding_data.get('recommendations', []),
                    "searchable_text": finding_text,
                    "data_type": "media_file"
                }
            )
            
            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored finding vector: {point_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store finding vector: {str(e)}")
            return False
    
    async def semantic_search(self, query: str, case_id: str = None, 
                            data_types: List[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Perform semantic search across stored vectors."""
        if not self.qdrant_client:
            logger.warning("Qdrant client not available")
            return []
        
        try:
            # Generate embedding for query
            query_embedding = await self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Build filter conditions
            filter_conditions = []
            
            if case_id:
                filter_conditions.append(
                    FieldCondition(key="case_id", match=MatchValue(value=case_id))
                )
            
            if data_types:
                filter_conditions.append(
                    FieldCondition(key="data_type", match=MatchValue(value=data_types[0]))
                )
            
            # Perform search
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=Filter(must=filter_conditions) if filter_conditions else None,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            results = []
            for hit in search_result:
                result = {
                    "score": hit.score,
                    "payload": hit.payload
                }
                results.append(result)
            
            logger.info(f"Semantic search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to perform semantic search: {str(e)}")
            return []
    
    async def find_similar_messages(self, message_content: str, case_id: str = None, 
                                  limit: int = 5) -> List[Dict[str, Any]]:
        """Find messages similar to the given content."""
        return await self.semantic_search(
            query=message_content,
            case_id=case_id,
            data_types=["chat_record"],
            limit=limit
        )
    
    async def find_related_contacts(self, query: str, case_id: str = None, 
                                  limit: int = 5) -> List[Dict[str, Any]]:
        """Find contacts related to the query."""
        return await self.semantic_search(
            query=query,
            case_id=case_id,
            data_types=["contact"],
            limit=limit
        )
    
    async def find_relevant_findings(self, query: str, case_id: str = None, 
                                   limit: int = 5) -> List[Dict[str, Any]]:
        """Find findings relevant to the query."""
        return await self.semantic_search(
            query=query,
            case_id=case_id,
            data_types=["media_file"],
            limit=limit
        )
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        if not self.qdrant_client:
            return {}
        
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            return {
                "total_points": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.value
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {}
    
    async def delete_case_vectors(self, case_id: str) -> bool:
        """Delete all vectors for a specific case."""
        if not self.qdrant_client:
            return False
        
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="case_id", match=MatchValue(value=case_id))]
                )
            )
            logger.info(f"Deleted vectors for case: {case_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete case vectors: {str(e)}")
            return False
    
    async def search_case_collection(
        self,
        query: str,
        collection_name: str,
        data_types: Optional[List[str]] = None,
        limit: int = 20,
        score_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Perform semantic search in a specific case collection."""
        if not self.qdrant_client:
            logger.warning("Qdrant client not available")
            return []
        
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if collection_name not in collection_names:
                logger.warning(f"Collection {collection_name} does not exist")
                return []
            
            # Generate query embedding using AI service
            from app.services.ai_service import ai_service
            query_embeddings = await ai_service.generate_embeddings([query])
            if not query_embeddings:
                logger.warning("Failed to generate query embedding")
                return []
            
            query_embedding = query_embeddings[0]
            logger.info(f"🔍 Generated query embedding with {len(query_embedding)} dimensions")
            
            # Build search filter for data types
            search_filter = None
            if data_types:
                conditions = []
                for data_type in data_types:
                    conditions.append(FieldCondition(key="data_type", match=MatchValue(value=data_type)))
                
                if conditions:
                    search_filter = Filter(should=conditions)
                    logger.info(f"🎯 Filtering by data types: {data_types}")
            
            # Perform search
            search_results = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                })
            
            logger.info(f"✅ Case collection search in {collection_name} returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ Case collection search failed: {str(e)}")
            return []


# Global vector service instance
vector_service = VectorService()