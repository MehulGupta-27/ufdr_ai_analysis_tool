"""
Neo4j repository implementation for graph database operations.
"""

import logging
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase, Driver
from config.settings import settings

logger = logging.getLogger(__name__)


class Neo4jRepository:
    """Repository for Neo4j graph database operations."""
    
    def __init__(self):
        """Initialize Neo4j repository."""
        self.driver: Optional[Driver] = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            self.driver = None
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
    
    async def create_node(self, label: str, properties: Dict[str, Any]) -> str:
        """Create a node in the graph."""
        if not self.driver:
            raise Exception("Neo4j connection not available")
        
        try:
            with self.driver.session() as session:
                query = f"""
                CREATE (n:{label} $properties)
                RETURN n.id as node_id
                """
                result = session.run(query, properties=properties)
                record = result.single()
                return record["node_id"] if record else None
        except Exception as e:
            logger.error(f"Failed to create node: {str(e)}")
            raise
    
    async def create_relationship(self, source_id: str, target_id: str, 
                                relationship_type: str, properties: Dict[str, Any] = None) -> str:
        """Create a relationship between two nodes."""
        if not self.driver:
            raise Exception("Neo4j connection not available")
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (a {id: $source_id}), (b {id: $target_id})
                CREATE (a)-[r:%s $properties]->(b)
                RETURN r.id as rel_id
                """ % relationship_type
                
                result = session.run(query, 
                                   source_id=source_id, 
                                   target_id=target_id, 
                                   properties=properties or {})
                record = result.single()
                return record["rel_id"] if record else None
        except Exception as e:
            logger.error(f"Failed to create relationship: {str(e)}")
            raise
    
    async def find_nodes(self, label: str, properties: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Find nodes by label and properties."""
        if not self.driver:
            raise Exception("Neo4j connection not available")
        
        try:
            with self.driver.session() as session:
                if properties:
                    query = f"MATCH (n:{label}) WHERE "
                    conditions = [f"n.{key} = ${key}" for key in properties.keys()]
                    query += " AND ".join(conditions)
                    query += " RETURN n"
                    result = session.run(query, **properties)
                else:
                    query = f"MATCH (n:{label}) RETURN n"
                    result = session.run(query)
                
                return [dict(record["n"]) for record in result]
        except Exception as e:
            logger.error(f"Failed to find nodes: {str(e)}")
            raise
    
    async def execute_cypher(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""
        if not self.driver:
            raise Exception("Neo4j connection not available")
        
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Failed to execute Cypher query: {str(e)}")
            raise
    
    async def create_person_node(self, person_data: Dict[str, Any]) -> str:
        """Create a Person node."""
        return await self.create_node("Person", person_data)
    
    async def create_device_node(self, device_data: Dict[str, Any]) -> str:
        """Create a Device node."""
        return await self.create_node("Device", device_data)
    
    async def create_communication_relationship(self, person1_id: str, person2_id: str, 
                                              comm_data: Dict[str, Any]) -> str:
        """Create a COMMUNICATES_WITH relationship."""
        return await self.create_relationship(
            person1_id, person2_id, "COMMUNICATES_WITH", comm_data
        )
    
    async def find_communication_network(self, person_ids: List[str]) -> List[Dict[str, Any]]:
        """Find communication network for given persons."""
        query = """
        MATCH (p1:Person)-[r:COMMUNICATES_WITH]-(p2:Person)
        WHERE p1.id IN $person_ids OR p2.id IN $person_ids
        RETURN p1, r, p2
        ORDER BY r.frequency DESC
        """
        return await self.execute_cypher(query, {"person_ids": person_ids})
    
    async def find_shortest_path(self, source_id: str, target_id: str) -> List[Dict[str, Any]]:
        """Find shortest path between two persons."""
        query = """
        MATCH path = shortestPath((p1:Person {id: $source_id})-[*]-(p2:Person {id: $target_id}))
        RETURN path
        """
        return await self.execute_cypher(query, {"source_id": source_id, "target_id": target_id})
    
    async def get_centrality_analysis(self) -> List[Dict[str, Any]]:
        """Get centrality analysis for the communication network."""
        query = """
        MATCH (p:Person)-[r:COMMUNICATES_WITH]-(other:Person)
        WITH p, COUNT(r) as degree, SUM(r.frequency) as total_frequency
        RETURN p.id as person_id, p.name as name, degree, total_frequency
        ORDER BY degree DESC, total_frequency DESC
        """
        return await self.execute_cypher(query)
    
    async def clear_all_data(self):
        """Clear all data from the graph (for testing)."""
        if not self.driver:
            raise Exception("Neo4j connection not available")
        
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared all Neo4j data")
        except Exception as e:
            logger.error(f"Failed to clear Neo4j data: {str(e)}")
            raise


# Global repository instance
neo4j_repo = Neo4jRepository()