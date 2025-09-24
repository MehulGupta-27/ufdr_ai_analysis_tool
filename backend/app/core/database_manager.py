from typing import List, Dict, Any, Optional
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from neo4j import GraphDatabase
import redis
import json
from sqlalchemy.orm import Session
from config.settings import settings
from app.models.database import get_db

class DatabaseManager:
    def __init__(self):
        self.qdrant_client = None
        self.neo4j_driver = None
        self.redis_client = None
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize all database connections"""
        try:
            # Initialize Qdrant
            self.qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key
            )
            
            # Initialize Neo4j
            self.neo4j_driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            
            # Initialize Redis
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                decode_responses=True
            )
            
            print("All database connections initialized successfully")
            
        except Exception as e:
            print(f"Error initializing database connections: {e}")
    
    def create_qdrant_collections(self):
        """Create Qdrant collections for different data types"""
        collections = [
            ("chat_messages", 3072),  # Azure OpenAI text-embedding-3-large dimension
            ("call_records", 3072),
            ("media_files", 3072),
            ("contacts", 3072)
        ]
        
        for collection_name, vector_size in collections:
            try:
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
                print(f"Created Qdrant collection: {collection_name}")
            except Exception as e:
                print(f"Collection {collection_name} might already exist: {e}")
    
    def store_vector_data(self, collection_name: str, points: List[PointStruct]):
        """Store vector data in Qdrant"""
        try:
            self.qdrant_client.upsert(
                collection_name=collection_name,
                points=points
            )
            return True
        except Exception as e:
            print(f"Error storing vector data: {e}")
            return False
    
    def search_vectors(self, collection_name: str, query_vector: List[float], 
                      limit: int = 10, score_threshold: float = 0.7,
                      filter_conditions: Optional[Filter] = None) -> List[Dict]:
        """Search vectors in Qdrant"""
        try:
            results = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filter_conditions
            )
            return [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                }
                for result in results
            ]
        except Exception as e:
            print(f"Error searching vectors: {e}")
            return []
    
    def create_neo4j_relationships(self, data: Dict[str, Any]):
        """Create relationships in Neo4j"""
        with self.neo4j_driver.session() as session:
            try:
                # Create person nodes
                if "contacts" in data:
                    for contact in data["contacts"]:
                        session.run(
                            """
                            MERGE (p:Person {phone: $phone})
                            SET p.name = $name, p.emails = $emails
                            """,
                            phone=contact.get("phone"),
                            name=contact.get("name"),
                            emails=contact.get("emails", [])
                        )
                
                # Create communication relationships
                if "chat_records" in data:
                    for chat in data["chat_records"]:
                        session.run(
                            """
                            MATCH (sender:Person {phone: $sender})
                            MATCH (receiver:Person {phone: $receiver})
                            CREATE (sender)-[:COMMUNICATED {
                                type: 'chat',
                                app: $app,
                                timestamp: $timestamp,
                                message_id: $message_id
                            }]->(receiver)
                            """,
                            sender=chat.get("sender_number"),
                            receiver=chat.get("receiver_number"),
                            app=chat.get("app_name"),
                            timestamp=chat.get("timestamp"),
                            message_id=str(chat.get("id"))
                        )
                
                if "call_records" in data:
                    for call in data["call_records"]:
                        session.run(
                            """
                            MATCH (caller:Person {phone: $caller})
                            MATCH (receiver:Person {phone: $receiver})
                            CREATE (caller)-[:CALLED {
                                type: $call_type,
                                duration: $duration,
                                timestamp: $timestamp,
                                call_id: $call_id
                            }]->(receiver)
                            """,
                            caller=call.get("caller_number"),
                            receiver=call.get("receiver_number"),
                            call_type=call.get("call_type"),
                            duration=call.get("duration"),
                            timestamp=call.get("timestamp"),
                            call_id=str(call.get("id"))
                        )
                
                return True
            except Exception as e:
                print(f"Error creating Neo4j relationships: {e}")
                return False
    
    def find_connections(self, phone_number: str, depth: int = 2) -> List[Dict]:
        """Find connections for a phone number in Neo4j"""
        with self.neo4j_driver.session() as session:
            try:
                result = session.run(
                    """
                    MATCH path = (p:Person {phone: $phone})-[*1..$depth]-(connected:Person)
                    RETURN path, connected
                    LIMIT 100
                    """,
                    phone=phone_number,
                    depth=depth
                )
                
                connections = []
                for record in result:
                    path = record["path"]
                    connected = record["connected"]
                    connections.append({
                        "connected_person": dict(connected),
                        "path_length": len(path.relationships),
                        "relationships": [dict(rel) for rel in path.relationships]
                    })
                
                return connections
            except Exception as e:
                print(f"Error finding connections: {e}")
                return []
    
    def cache_query_result(self, query_hash: str, result: Dict, ttl: int = 3600):
        """Cache query results in Redis"""
        try:
            self.redis_client.setex(
                f"query_cache:{query_hash}",
                ttl,
                json.dumps(result, default=str)
            )
        except Exception as e:
            print(f"Error caching result: {e}")
    
    def get_cached_result(self, query_hash: str) -> Optional[Dict]:
        """Get cached query result from Redis"""
        try:
            cached = self.redis_client.get(f"query_cache:{query_hash}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"Error getting cached result: {e}")
        return None
    
    def close_connections(self):
        """Close all database connections"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
        if self.redis_client:
            self.redis_client.close()

# Global database manager instance
db_manager = DatabaseManager()