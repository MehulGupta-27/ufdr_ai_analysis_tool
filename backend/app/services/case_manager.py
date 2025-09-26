"""
Case-based data management service for isolating forensic data by case.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy import text
from qdrant_client.models import Distance, VectorParams, CollectionInfo
from app.models.database import get_db
from app.core.database_manager import db_manager
from app.repositories.neo4j_repository import neo4j_repo
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)


class CaseManager:
    """Manages case-specific data isolation across all databases."""
    
    def __init__(self):
        self.active_cases = {}
    
    async def create_case_environment(self, case_number: str, investigator: str) -> Dict[str, Any]:
        """Create isolated environment for a new case across all databases."""
        
        try:
            logger.info(f"🏗️ Creating case environment for: {case_number}")
            
            # Sanitize case number for database names
            safe_case_name = self._sanitize_case_name(case_number)
            
            result = {
                "case_number": case_number,
                "safe_case_name": safe_case_name,
                "investigator": investigator,
                "created_at": datetime.utcnow().isoformat(),
                "databases": {}
            }
            
            # Create PostgreSQL schema for case
            postgres_result = await self._create_postgres_case_schema(safe_case_name)
            result["databases"]["postgresql"] = postgres_result
            
            # Create Qdrant collection for case
            qdrant_result = await self._create_qdrant_case_collection(safe_case_name)
            result["databases"]["qdrant"] = qdrant_result
            
            # Create Neo4j database/namespace for case
            neo4j_result = await self._create_neo4j_case_namespace(safe_case_name)
            result["databases"]["neo4j"] = neo4j_result
            
            # Store case info
            self.active_cases[case_number] = result
            
            logger.info(f"✅ Case environment created successfully for: {case_number}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to create case environment: {str(e)}")
            raise e
    
    async def delete_all_case_data(self) -> Dict[str, Any]:
        """Delete all data from all databases to start fresh."""
        
        logger.info("🗑️ Starting complete data cleanup...")
        
        result = {
            "postgresql": {"status": "pending"},
            "qdrant": {"status": "pending"},
            "neo4j": {"status": "pending"}
        }
        
        try:
            # Clean PostgreSQL
            postgres_result = await self._clean_postgresql()
            result["postgresql"] = postgres_result
            
            # Clean Qdrant
            qdrant_result = await self._clean_qdrant()
            result["qdrant"] = qdrant_result
            
            # Clean Neo4j
            neo4j_result = await self._clean_neo4j()
            result["neo4j"] = neo4j_result
            
            # Clear active cases
            self.active_cases.clear()
            
            logger.info("✅ Complete data cleanup finished")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error during data cleanup: {str(e)}")
            raise e
    
    def _sanitize_case_name(self, case_number: str) -> str:
        """Sanitize case number for use as database identifier."""
        import re
        # Remove special characters and replace with underscores
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', case_number.lower())
        # Ensure it starts with a letter
        if safe_name[0].isdigit():
            safe_name = f"case_{safe_name}"
        return safe_name
    
    async def _create_postgres_case_schema(self, safe_case_name: str) -> Dict[str, Any]:
        """Create PostgreSQL schema for case-specific data."""
        
        try:
            db = next(get_db())
            
            # Create schema for the case
            schema_name = f"case_{safe_case_name}"
            
            # Drop schema if exists (for fresh start)
            db.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
            
            # Create new schema
            db.execute(text(f"CREATE SCHEMA {schema_name}"))
            
            # Create case-specific tables
            tables_sql = f"""
            -- UFDR Reports table
            CREATE TABLE {schema_name}.ufdr_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255) NOT NULL,
                device_info JSONB,
                extraction_date TIMESTAMP,
                case_number VARCHAR(100) NOT NULL,
                investigator VARCHAR(255) NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Chat Records table
            CREATE TABLE {schema_name}.chat_records (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ufdr_report_id UUID REFERENCES {schema_name}.ufdr_reports(id) ON DELETE CASCADE,
                app_name VARCHAR(100),
                sender_number VARCHAR(50),
                receiver_number VARCHAR(50),
                message_content TEXT,
                timestamp TIMESTAMP,
                message_type VARCHAR(50) DEFAULT 'text',
                is_deleted BOOLEAN DEFAULT FALSE,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Call Records table
            CREATE TABLE {schema_name}.call_records (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ufdr_report_id UUID REFERENCES {schema_name}.ufdr_reports(id) ON DELETE CASCADE,
                caller_number VARCHAR(50),
                receiver_number VARCHAR(50),
                call_type VARCHAR(50),
                duration INTEGER,
                timestamp TIMESTAMP,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Contacts table
            CREATE TABLE {schema_name}.contacts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ufdr_report_id UUID REFERENCES {schema_name}.ufdr_reports(id) ON DELETE CASCADE,
                name VARCHAR(255),
                phone_numbers JSONB,
                email_addresses JSONB,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Media Files table
            CREATE TABLE {schema_name}.media_files (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ufdr_report_id UUID REFERENCES {schema_name}.ufdr_reports(id) ON DELETE CASCADE,
                filename VARCHAR(255),
                file_path TEXT,
                file_type VARCHAR(100),
                file_size BIGINT,
                created_date TIMESTAMP,
                modified_date TIMESTAMP,
                hash_md5 VARCHAR(64),
                hash_sha256 VARCHAR(128),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Create indexes for better performance
            CREATE INDEX idx_{safe_case_name}_chat_timestamp ON {schema_name}.chat_records(timestamp);
            CREATE INDEX idx_{safe_case_name}_chat_app ON {schema_name}.chat_records(app_name);
            CREATE INDEX idx_{safe_case_name}_chat_content ON {schema_name}.chat_records USING gin(to_tsvector('english', message_content));
            CREATE INDEX idx_{safe_case_name}_call_timestamp ON {schema_name}.call_records(timestamp);
            CREATE INDEX idx_{safe_case_name}_contacts_name ON {schema_name}.contacts(name);
            """
            
            db.execute(text(tables_sql))
            db.commit()
            db.close()
            
            return {
                "status": "success",
                "schema_name": schema_name,
                "tables_created": ["ufdr_reports", "chat_records", "call_records", "contacts", "media_files"]
            }
            
        except Exception as e:
            logger.error(f"PostgreSQL case schema creation failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_qdrant_case_collection(self, safe_case_name: str) -> Dict[str, Any]:
        """Create Qdrant collection for case-specific vector data."""
        
        try:
            if not vector_service.qdrant_client:
                return {"status": "skipped", "reason": "Qdrant client not available"}
            
            collection_name = f"case_{safe_case_name}"
            
            # Delete collection if exists
            try:
                vector_service.qdrant_client.delete_collection(collection_name)
                logger.info(f"Deleted existing Qdrant collection: {collection_name}")
            except:
                pass  # Collection might not exist
            
            # Create new collection with proper dimensions and indexing for text-embedding-3-large
            from qdrant_client.models import PayloadSchemaType
            
            vector_service.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=3072,  # text-embedding-3-large dimensions
                    distance=Distance.COSINE
                )
            )
            
            # Create payload index for data_type field to enable filtering
            vector_service.qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="data_type",
                field_schema=PayloadSchemaType.KEYWORD
            )
            
            logger.info(f"Created Qdrant collection: {collection_name}")
            
            return {
                "status": "success",
                "collection_name": collection_name,
                "vector_size": 3072,
                "distance_metric": "cosine"
            }
            
        except Exception as e:
            logger.error(f"Qdrant case collection creation failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_neo4j_case_namespace(self, safe_case_name: str) -> Dict[str, Any]:
        """Create Neo4j namespace for case-specific graph data."""
        
        try:
            if not neo4j_repo.driver:
                return {"status": "skipped", "reason": "Neo4j driver not available"}
            
            # Create case-specific constraints and indexes
            case_label = f"Case_{safe_case_name}"
            
            # Clear any existing data for this case
            await neo4j_repo.execute_cypher(f"""
                MATCH (n:{case_label})
                DETACH DELETE n
            """)
            
            # Create constraints for case-specific nodes
            constraints = [
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person_{safe_case_name}) REQUIRE p.id IS UNIQUE",
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (c:Communication_{safe_case_name}) REQUIRE c.id IS UNIQUE",
                f"CREATE INDEX IF NOT EXISTS FOR (p:Person_{safe_case_name}) ON (p.phone_number)",
                f"CREATE INDEX IF NOT EXISTS FOR (p:Person_{safe_case_name}) ON (p.name)",
                f"CREATE INDEX IF NOT EXISTS FOR (c:Communication_{safe_case_name}) ON (c.timestamp)"
            ]
            
            for constraint in constraints:
                try:
                    await neo4j_repo.execute_cypher(constraint)
                except Exception as e:
                    logger.warning(f"Neo4j constraint creation warning: {str(e)}")
            
            logger.info(f"Created Neo4j namespace for case: {safe_case_name}")
            
            return {
                "status": "success",
                "case_label": case_label,
                "person_label": f"Person_{safe_case_name}",
                "communication_label": f"Communication_{safe_case_name}"
            }
            
        except Exception as e:
            logger.error(f"Neo4j case namespace creation failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _clean_postgresql(self) -> Dict[str, Any]:
        """Clean all PostgreSQL data."""
        
        try:
            db = next(get_db())
            
            # Get all case schemas
            schemas_result = db.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name LIKE 'case_%'
            """)).fetchall()
            
            schemas_dropped = []
            for row in schemas_result:
                schema_name = row[0]
                db.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
                schemas_dropped.append(schema_name)
            
            # Also clean main tables if they exist
            main_tables = ["ufdr_reports", "chat_records", "call_records", "contacts", "media_files"]
            for table in main_tables:
                try:
                    db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                except:
                    pass  # Table might not exist
            
            db.commit()
            db.close()
            
            return {
                "status": "success",
                "schemas_dropped": schemas_dropped,
                "main_tables_truncated": main_tables
            }
            
        except Exception as e:
            logger.error(f"PostgreSQL cleanup failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _clean_qdrant(self) -> Dict[str, Any]:
        """Clean all Qdrant collections."""
        
        try:
            if not vector_service.qdrant_client:
                return {"status": "skipped", "reason": "Qdrant client not available"}
            
            # Get all collections
            collections = vector_service.qdrant_client.get_collections()
            collections_deleted = []
            
            for collection in collections.collections:
                collection_name = collection.name
                vector_service.qdrant_client.delete_collection(collection_name)
                collections_deleted.append(collection_name)
                logger.info(f"Deleted Qdrant collection: {collection_name}")
            
            return {
                "status": "success",
                "collections_deleted": collections_deleted
            }
            
        except Exception as e:
            logger.error(f"Qdrant cleanup failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _clean_neo4j(self) -> Dict[str, Any]:
        """Clean all Neo4j data."""
        
        try:
            if not neo4j_repo.driver:
                return {"status": "skipped", "reason": "Neo4j driver not available"}
            
            # Delete all nodes and relationships
            await neo4j_repo.execute_cypher("MATCH (n) DETACH DELETE n")
            
            # Drop all constraints and indexes (optional, but clean)
            try:
                constraints_result = await neo4j_repo.execute_cypher("SHOW CONSTRAINTS")
                if constraints_result:
                    for constraint in constraints_result:
                        constraint_name = constraint.get('name')
                        if constraint_name:
                            await neo4j_repo.execute_cypher(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
            except:
                pass  # Constraints might not exist or command not supported
            
            logger.info("Cleaned all Neo4j data")
            
            return {
                "status": "success",
                "nodes_deleted": "all",
                "relationships_deleted": "all"
            }
            
        except Exception as e:
            logger.error(f"Neo4j cleanup failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def get_case_info(self, case_number: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific case."""
        return self.active_cases.get(case_number)
    
    def list_active_cases(self) -> List[str]:
        """List all active case numbers."""
        return list(self.active_cases.keys())


# Global case manager instance
case_manager = CaseManager()