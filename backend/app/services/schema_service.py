"""
Schema-aware service for dynamic schema extraction and management.
This service implements the TODO improvements for better LLM query accuracy.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.services.case_manager import case_manager

logger = logging.getLogger(__name__)


class SchemaService:
    """Service for dynamic schema extraction and management."""
    
    def __init__(self):
        self._schema_cache = {}  # Cache schema summaries per case
        self._max_tokens = 4000  # Token limit for schema summaries
        self._field_abbreviations = {
            'varchar': 'str',
            'text': 'txt',
            'integer': 'int',
            'bigint': 'bigint',
            'timestamp': 'ts',
            'boolean': 'bool',
            'json': 'json',
            'uuid': 'uuid'
        }
    
    async def extract_case_schema(self, case_number: str) -> Dict[str, Any]:
        """Extract comprehensive schema details for a specific case."""
        try:
            case_info = case_manager.get_case_info(case_number)
            if not case_info:
                logger.warning(f"Case {case_number} not found for schema extraction")
                return {}
            
            safe_case_name = case_info["safe_case_name"]
            schema_name = f"case_{safe_case_name}"
            
            db = next(get_db())
            schema_details = {
                "case_number": case_number,
                "schema_name": schema_name,
                "extraction_timestamp": datetime.utcnow().isoformat(),
                "tables": {},
                "relationships": [],
                "sample_data": {},
                "statistics": {}
            }
            
            # Get table information
            tables = await self._get_table_schemas(db, schema_name)
            schema_details["tables"] = tables
            
            # Get relationships
            relationships = await self._get_table_relationships(db, schema_name)
            schema_details["relationships"] = relationships
            
            # Get sample data for key fields
            sample_data = await self._get_sample_data(db, schema_name, tables)
            schema_details["sample_data"] = sample_data
            
            # Get statistics
            statistics = await self._get_table_statistics(db, schema_name, tables)
            schema_details["statistics"] = statistics
            
            db.close()
            
            # Cache the schema
            self._schema_cache[case_number] = schema_details
            
            logger.info(f"Schema extracted for case {case_number}: {len(tables)} tables")
            return schema_details
            
        except Exception as e:
            logger.error(f"Error extracting schema for case {case_number}: {e}")
            return {}
    
    async def _get_table_schemas(self, db: Session, schema_name: str) -> Dict[str, Any]:
        """Get detailed table schemas."""
        tables = {}
        
        # Get list of tables in the schema
        table_query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = :schema_name
            ORDER BY table_name
        """)
        
        table_results = db.execute(table_query, {"schema_name": schema_name}).fetchall()
        table_names = [row[0] for row in table_results]
        
        for table_name in table_names:
            # Get column information
            column_query = text("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                AND table_name = :table_name
                ORDER BY ordinal_position
            """)
            
            column_results = db.execute(column_query, {
                "schema_name": schema_name,
                "table_name": table_name
            }).fetchall()
            
            columns = {}
            for col in column_results:
                column_info = {
                    "type": self._abbreviate_type(col.data_type),
                    "nullable": col.is_nullable == 'YES',
                    "default": col.column_default,
                    "max_length": col.character_maximum_length,
                    "precision": col.numeric_precision,
                    "scale": col.numeric_scale
                }
                columns[col.column_name] = column_info
            
            tables[table_name] = {
                "columns": columns,
                "column_count": len(columns)
            }
        
        return tables
    
    async def _get_table_relationships(self, db: Session, schema_name: str) -> List[Dict[str, Any]]:
        """Get foreign key relationships between tables."""
        relationships = []
        
        fk_query = text("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_schema = :schema_name
        """)
        
        fk_results = db.execute(fk_query, {"schema_name": schema_name}).fetchall()
        
        for fk in fk_results:
            relationships.append({
                "from_table": fk.table_name,
                "from_column": fk.column_name,
                "to_table": fk.foreign_table_name,
                "to_column": fk.foreign_column_name
            })
        
        return relationships
    
    async def _get_sample_data(self, db: Session, schema_name: str, tables: Dict[str, Any]) -> Dict[str, Any]:
        """Get sample data for key fields to help LLM understand data patterns."""
        sample_data = {}
        
        for table_name, table_info in tables.items():
            if table_name in ['chat_records', 'call_records', 'contacts', 'media_files']:
                try:
                    # Get sample records (limit to 3 for token efficiency)
                    sample_query = text(f"SELECT * FROM {schema_name}.{table_name} LIMIT 3")
                    sample_results = db.execute(sample_query).fetchall()
                    
                    if sample_results:
                        # Convert to dict format
                        sample_records = []
                        for row in sample_results:
                            if hasattr(row, '_mapping'):
                                record = dict(row._mapping)
                                # Convert non-serializable types
                                for key, value in record.items():
                                    if hasattr(value, 'isoformat'):  # datetime
                                        record[key] = value.isoformat()
                                    elif hasattr(value, 'hex'):  # UUID
                                        record[key] = str(value)
                                sample_records.append(record)
                        
                        sample_data[table_name] = sample_records
                        
                except Exception as e:
                    logger.warning(f"Could not get sample data for {table_name}: {e}")
        
        return sample_data
    
    async def _get_table_statistics(self, db: Session, schema_name: str, tables: Dict[str, Any]) -> Dict[str, Any]:
        """Get table statistics for better query planning."""
        statistics = {}
        
        for table_name in tables.keys():
            try:
                count_query = text(f"SELECT COUNT(*) FROM {schema_name}.{table_name}")
                count_result = db.execute(count_query).scalar()
                statistics[table_name] = {"row_count": count_result}
            except Exception as e:
                logger.warning(f"Could not get statistics for {table_name}: {e}")
                statistics[table_name] = {"row_count": 0}
        
        return statistics
    
    def _abbreviate_type(self, data_type: str) -> str:
        """Abbreviate data types to save tokens."""
        return self._field_abbreviations.get(data_type.lower(), data_type.lower())
    
    def generate_schema_summary(self, case_number: str) -> str:
        """Generate concise, human-readable schema summary for LLM prompts."""
        if case_number not in self._schema_cache:
            logger.warning(f"No cached schema for case {case_number}")
            return "Schema information not available."
        
        schema = self._schema_cache[case_number]
        summary_parts = []
        
        # Header
        summary_parts.append(f"Schema for Case: {case_number}")
        summary_parts.append(f"Database: {schema['schema_name']}")
        summary_parts.append("")
        
        # Tables section
        summary_parts.append("TABLES:")
        for table_name, table_info in schema["tables"].items():
            summary_parts.append(f"  {table_name} ({table_info['column_count']} cols):")
            
            # List columns with types
            for col_name, col_info in table_info["columns"].items():
                nullable = "?" if col_info["nullable"] else ""
                summary_parts.append(f"    {col_name}: {col_info['type']}{nullable}")
        
        # Relationships section
        if schema["relationships"]:
            summary_parts.append("")
            summary_parts.append("RELATIONSHIPS:")
            for rel in schema["relationships"]:
                summary_parts.append(f"  {rel['from_table']}.{rel['from_column']} -> {rel['to_table']}.{rel['to_column']}")
        
        # Statistics section
        summary_parts.append("")
        summary_parts.append("STATISTICS:")
        for table_name, stats in schema["statistics"].items():
            summary_parts.append(f"  {table_name}: {stats['row_count']} records")
        
        # Sample data section (limited for token efficiency)
        if schema["sample_data"]:
            summary_parts.append("")
            summary_parts.append("SAMPLE DATA:")
            for table_name, samples in schema["sample_data"].items():
                if samples:
                    summary_parts.append(f"  {table_name}:")
                    # Show only first sample, key fields only
                    sample = samples[0]
                    key_fields = ['id', 'name', 'content', 'timestamp', 'app_name', 'sender_number']
                    for field in key_fields:
                        if field in sample and sample[field] is not None:
                            value = str(sample[field])[:50]  # Truncate long values
                            summary_parts.append(f"    {field}: {value}")
        
        summary_text = "\n".join(summary_parts)
        
        # Token optimization: truncate if too long
        if len(summary_text) > self._max_tokens * 4:  # Rough token estimation
            summary_text = self._truncate_summary(summary_text)
        
        return summary_text
    
    def _truncate_summary(self, summary: str) -> str:
        """Truncate summary to fit token limits using map-reduce approach."""
        lines = summary.split('\n')
        
        # Keep essential parts
        essential_lines = []
        current_section = None
        
        for line in lines:
            if line.startswith("Schema for Case:") or line.startswith("Database:"):
                essential_lines.append(line)
            elif line.startswith("TABLES:"):
                essential_lines.append(line)
                current_section = "tables"
            elif line.startswith("RELATIONSHIPS:"):
                essential_lines.append(line)
                current_section = "relationships"
            elif line.startswith("STATISTICS:"):
                essential_lines.append(line)
                current_section = "statistics"
            elif line.startswith("SAMPLE DATA:"):
                essential_lines.append(line)
                current_section = "samples"
            elif current_section == "tables" and line.strip().startswith(("chat_records", "call_records", "contacts", "media_files")):
                essential_lines.append(line)
            elif current_section == "statistics" and line.strip():
                essential_lines.append(line)
            elif current_section == "samples" and line.strip().startswith(("chat_records:", "call_records:", "contacts:", "media_files:")):
                essential_lines.append(line)
        
        return "\n".join(essential_lines)
    
    def get_cached_schema(self, case_number: str) -> Optional[Dict[str, Any]]:
        """Get cached schema for a case."""
        return self._schema_cache.get(case_number)
    
    def clear_schema_cache(self, case_number: Optional[str] = None):
        """Clear schema cache for a specific case or all cases."""
        if case_number:
            self._schema_cache.pop(case_number, None)
        else:
            self._schema_cache.clear()
    
    def is_schema_cached(self, case_number: str) -> bool:
        """Check if schema is cached for a case."""
        return case_number in self._schema_cache


# Global schema service instance
schema_service = SchemaService()
