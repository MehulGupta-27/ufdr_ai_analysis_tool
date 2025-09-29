"""
Vector storage and semantic search service using Qdrant and Azure OpenAI embeddings.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from uuid import uuid4
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from config.settings import settings
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


class VectorService:
    """Service for vector embeddings and semantic search."""
    
    def __init__(self):
        """Initialize vector service."""
        self.qdrant_client = None
        self.embedder: Optional[TextEmbedding] = None
        self.collection_name = "forensic_data"
        self._embedding_dimension: Optional[int] = None
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
            
            # Initialize local embedder
            try:
                self.embedder = TextEmbedding(model_name=settings.embedding_model_name)
                logger.info(f"✅ Local embedder ready: {settings.embedding_model_name}")
                # Detect and cache the embedding dimension dynamically
                try:
                    self._embedding_dimension = self._determine_embedding_dimension()
                    if self._embedding_dimension:
                        logger.info(f"🔎 Detected embedding dimension: {self._embedding_dimension}")
                except Exception as dim_err:
                    logger.warning(f"Unable to detect embedding dimension: {dim_err}")
            except Exception as e:
                logger.error(f"❌ Failed to init local embedder: {e}")
        except Exception as e:
            logger.error(f"❌ Error initializing vector service clients: {e}")
            import traceback
            traceback.print_exc()
                
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {str(e)}")
    
    # Removed: initialize_collection() - Collections are now created dynamically per case only
    # This eliminates the generic 'forensic_data' collection
    
    def _determine_embedding_dimension(self) -> Optional[int]:
        """Determine embedding dimension locally from the embedder."""
        if not self.embedder:
            return None
        vectors = list(self.embedder.embed(["dimension_check"]))
        if not vectors:
            return None
        return len(vectors[0])

    def get_embedding_dimension(self) -> Optional[int]:
        """Return cached embedding dimension, or detect it if unknown."""
        if self._embedding_dimension is None:
            try:
                self._embedding_dimension = self._determine_embedding_dimension()
            except Exception:
                self._embedding_dimension = None
        return self._embedding_dimension

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using local model."""
        if not self.embedder:
            logger.warning("Local embedder not available")
            return []
        try:
            # fastembed returns numpy arrays
            vectors = list(self.embedder.embed([text]))
            return vectors[0].tolist() if vectors else []
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
    
    async def find_suspicious_conversations(self, case_id: str = None, 
                                          limit: int = 20) -> List[Dict[str, Any]]:
        """Find suspicious conversations using enhanced semantic search."""
        if not self.qdrant_client:
            logger.warning("Qdrant client not available")
            return []
        
        try:
            # Get case-specific collection name
            if not case_id:
                logger.warning("No case_id provided for suspicious conversation search")
                return []
            
            from app.services.case_manager import case_manager
            case_info = case_manager.get_case_info(case_id)
            if not case_info:
                logger.warning(f"Case {case_id} not found")
                return []
            
            safe_case_name = case_info["safe_case_name"]
            collection_name = f"case_{safe_case_name}"
            
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if collection_name not in collection_names:
                logger.warning(f"Collection {collection_name} does not exist")
                return []
            
            # Enhanced suspicious conversation queries
            suspicious_queries = [
                "suspicious conversations criminal activity illegal",
                "threats violence dangerous behavior",
                "drug dealing trafficking illegal substances",
                "fraud scam money laundering financial crime",
                "terrorism extremist activity radical",
                "weapons guns explosives dangerous materials",
                "human trafficking exploitation abuse",
                "cybercrime hacking data breach security",
                "blackmail extortion threats intimidation",
                "organized crime gang activity conspiracy",
                "money transfer payment suspicious financial",
                "meeting location secret hidden private",
                "code words encrypted messages secret communication",
                "urgent emergency immediate action required",
                "police law enforcement investigation avoid",
                "evidence destroy delete remove traces",
                "confidential secret classified information",
                "planning preparation execution criminal act"
            ]
            
            all_results = []
            
            for query in suspicious_queries:
                # Generate embedding for each suspicious query
                query_embedding = await self.generate_embedding(query)
                if not query_embedding:
                    continue
                
                # Build filter conditions
                filter_conditions = []
                
                # Focus on chat records for suspicious conversations
                filter_conditions.append(
                    FieldCondition(key="data_type", match=MatchValue(value="chat_record"))
                )
                
                # Perform search with lower threshold to get some results
                search_result = self.qdrant_client.search(
                    collection_name=collection_name,  # Use case-specific collection
                    query_vector=query_embedding,
                    query_filter=Filter(must=filter_conditions) if filter_conditions else None,
                    limit=limit // len(suspicious_queries) + 1,  # Distribute limit across queries
                    score_threshold=0.1,  # Lower threshold to get some results
                    with_payload=True,
                    with_vectors=False
                )
                
                # Add results with enhanced scoring
                for hit in search_result:
                    # Boost score for suspicious indicators
                    enhanced_score = self._calculate_suspicious_score(hit.payload, hit.score)
                    
                    result = {
                        "score": enhanced_score,
                        "original_score": hit.score,
                        "payload": hit.payload,
                        "suspicious_indicators": self._extract_suspicious_indicators(hit.payload)
                    }
                    all_results.append(result)
            
            # Sort by enhanced score and remove duplicates
            all_results = self._deduplicate_and_rank_results(all_results)
            
            logger.info(f"✅ Found {len(all_results)} suspicious conversations in {collection_name}")
            if all_results:
                logger.info(f"Top result score: {all_results[0]['score']:.3f}")
                logger.info(f"Top result content: {all_results[0]['payload'].get('message_content', '')[:100]}...")
            return all_results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to find suspicious conversations: {str(e)}")
            return []
    
    def _calculate_suspicious_score(self, payload: Dict[str, Any], base_score: float) -> float:
        """Calculate enhanced suspicious score based on content analysis."""
        content = payload.get("message_content", "").lower()
        if not content:
            return base_score
        
        # Suspicious keywords and their weights
        suspicious_patterns = {
            # High weight patterns
            "kill": 0.3, "murder": 0.3, "death": 0.2, "die": 0.2,
            "bomb": 0.4, "explosive": 0.4, "weapon": 0.3, "gun": 0.3,
            "drug": 0.3, "cocaine": 0.4, "heroin": 0.4, "marijuana": 0.2,
            "fraud": 0.3, "scam": 0.3, "steal": 0.2, "rob": 0.2,
            "threat": 0.3, "blackmail": 0.4, "extort": 0.4,
            "terror": 0.4, "bomb": 0.4, "attack": 0.3,
            "traffic": 0.3, "exploit": 0.3, "abuse": 0.3,
            "hack": 0.3, "breach": 0.3, "steal data": 0.3,
            "money": 0.1, "payment": 0.1, "transfer": 0.1,
            "secret": 0.2, "confidential": 0.2, "private": 0.1,
            "urgent": 0.1, "immediate": 0.1, "asap": 0.1,
            "police": 0.2, "cop": 0.2, "fbi": 0.3, "investigation": 0.2,
            "evidence": 0.2, "destroy": 0.2, "delete": 0.1,
            "meet": 0.1, "location": 0.1, "address": 0.1,
            "code": 0.2, "encrypted": 0.2, "password": 0.1
        }
        
        # Calculate suspicious score
        suspicious_score = 0.0
        for pattern, weight in suspicious_patterns.items():
            if pattern in content:
                suspicious_score += weight
        
        # Normalize and combine with base score
        max_possible_score = sum(suspicious_patterns.values())
        normalized_suspicious = min(suspicious_score / max_possible_score, 1.0)
        
        # Combine base semantic score with suspicious score
        enhanced_score = (base_score * 0.6) + (normalized_suspicious * 0.4)
        
        return min(enhanced_score, 1.0)
    
    def _extract_suspicious_indicators(self, payload: Dict[str, Any]) -> List[str]:
        """Extract suspicious indicators from message content."""
        content = payload.get("message_content", "").lower()
        if not content:
            return []
        
        indicators = []
        suspicious_keywords = [
            "kill", "murder", "death", "bomb", "weapon", "gun",
            "drug", "cocaine", "heroin", "fraud", "scam", "steal",
            "threat", "blackmail", "extort", "terror", "attack",
            "traffic", "exploit", "abuse", "hack", "breach",
            "secret", "confidential", "urgent", "police", "evidence"
        ]
        
        for keyword in suspicious_keywords:
            if keyword in content:
                indicators.append(keyword)
        
        return indicators
    
    def _deduplicate_and_rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and rank results by suspicious score."""
        seen_ids = set()
        unique_results = []
        
        for result in results:
            result_id = result["payload"].get("id", result["payload"].get("message_id", ""))
            if result_id and result_id not in seen_ids:
                seen_ids.add(result_id)
                unique_results.append(result)
            elif not result_id:
                # If no ID, use content hash
                content = result["payload"].get("message_content", "")
                content_hash = hash(content)
                if content_hash not in seen_ids:
                    seen_ids.add(content_hash)
                    unique_results.append(result)
        
        # Sort by enhanced suspicious score
        unique_results.sort(key=lambda x: x["score"], reverse=True)
        
        return unique_results
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collections."""
        if not self.qdrant_client:
            return {"status": "disconnected", "reason": "Qdrant client not available"}
        
        try:
            # Get all collections instead of looking for a specific one
            collections = self.qdrant_client.get_collections()
            total_collections = len(collections.collections)
            total_points = 0
            
            # Calculate total points across all collections
            for collection in collections.collections:
                try:
                    collection_info = self.qdrant_client.get_collection(collection.name)
                    total_points += collection_info.points_count
                except Exception:
                    continue
            
            return {
                "status": "connected",
                "total_collections": total_collections,
                "total_points": total_points,
                "collections": [col.name for col in collections.collections]
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {"status": "error", "reason": str(e)}
    
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
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Perform semantic search in a specific case collection."""
        if not self.qdrant_client:
            logger.warning("Qdrant client not available")
            return []
        
        try:
            # Quick compatibility check: log if collection vector size mismatches the embedder
            try:
                info = self.qdrant_client.get_collection(collection_name)
                size_in_collection = getattr(getattr(info.config, 'params', None), 'vectors', None)
                size_val = getattr(size_in_collection, 'size', None)
                dim = self.get_embedding_dimension() or settings.embedding_dimension
                if size_val is not None and dim is not None and size_val != dim:
                    logger.error(
                        f"❌ Vector size mismatch for collection '{collection_name}': collection={size_val}, embedder={dim}. Searches may fail."
                    )
            except Exception:
                pass
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

    async def search_case_data(
        self,
        query: str,
        collection_name: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search case data - wrapper for search_case_collection for compatibility"""
        return await self.search_case_collection(
            query=query,
            collection_name=collection_name,
            limit=limit
        )


# Global vector service instance
vector_service = VectorService()