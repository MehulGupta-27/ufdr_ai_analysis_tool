import openai
import google.generativeai as genai
from typing import List, Dict, Any, Optional, Tuple
import json
import hashlib
from config.settings import settings
from app.core.database_manager import db_manager

class AIService:
    def __init__(self):
        self._setup_clients()
        
    def _setup_clients(self):
        """Setup AI service clients"""
        # Setup Azure OpenAI for embeddings (using new client)
        try:
            from openai import AzureOpenAI
            self.openai_client = AzureOpenAI(
                azure_endpoint=settings.embeddings_azure_endpoint,
                api_key=settings.embeddings_api_key,
                api_version=settings.api_version
            )
        except Exception as e:
            print(f"Warning: Azure OpenAI setup failed: {e}")
            self.openai_client = None
        
        # Setup Gemini for query processing
        try:
            genai.configure(api_key=settings.gemini_api_key)
            # Use the correct model name for Gemini
            self.gemini_model = genai.GenerativeModel('gemini-2.5-pro')
        except Exception as e:
            print(f"Warning: Gemini setup failed: {e}")
            self.gemini_model = None
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI"""
        try:
            if not self.openai_client:
                print("Azure OpenAI client not available, using dummy embeddings")
                # Return dummy embeddings for testing (384 dimensions to match existing collections)
                return [self._generate_dummy_embedding(text, 384) for text in texts]
            
            embeddings = []
            for text in texts:
                response = self.openai_client.embeddings.create(
                    model=settings.azure_embedding_model,
                    input=text
                )
                embeddings.append(response.data[0].embedding)
            return embeddings
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            # Return dummy embeddings for testing (384 dimensions to match existing collections)
            return [self._generate_dummy_embedding(text, 384) for text in texts]
    
    def _generate_dummy_embedding(self, text: str, dimensions: int = 384) -> List[float]:
        """Generate a dummy embedding based on text content for testing"""
        import hashlib
        import struct
        
        # Create a hash of the text
        text_hash = hashlib.md5(text.encode()).digest()
        
        # Convert hash to floats
        embedding = []
        for i in range(0, len(text_hash), 4):
            chunk = text_hash[i:i+4]
            if len(chunk) == 4:
                # Convert 4 bytes to float
                float_val = struct.unpack('f', chunk)[0]
                # Normalize to [-1, 1] range
                embedding.append(max(-1.0, min(1.0, float_val / 1000000)))
        
        # Pad or truncate to desired dimensions
        while len(embedding) < dimensions:
            embedding.extend(embedding[:min(len(embedding), dimensions - len(embedding))])
        
        return embedding[:dimensions]
    
    async def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user query to determine search strategy"""
        
        analysis_prompt = f"""
        Analyze the following forensic investigation query and determine the best search strategy.
        
        Query: "{query}"
        
        Determine:
        1. Query type: semantic_search, structured_query, relationship_analysis, or hybrid
        2. Data types needed: chat_records, call_records, contacts, media_files
        3. Filters needed: date_range, phone_numbers, keywords, file_types
        4. Search approach: vector_only, sql_only, neo4j_only, or hybrid
        
        Respond in JSON format:
        {{
            "query_type": "semantic_search|structured_query|relationship_analysis|hybrid",
            "data_types": ["chat_records", "call_records", "contacts", "media_files"],
            "filters": {{
                "date_range": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}},
                "phone_numbers": ["phone1", "phone2"],
                "keywords": ["keyword1", "keyword2"],
                "file_types": ["image", "video"],
                "apps": ["whatsapp", "telegram"]
            }},
            "search_approach": "vector_only|sql_only|neo4j_only|hybrid",
            "confidence": 0.0-1.0
        }}
        """
        
        try:
            if self.gemini_model:
                response = self.gemini_model.generate_content(analysis_prompt)
                if response and response.text:
                    analysis = json.loads(response.text)
                    return analysis
        except Exception as e:
            print(f"Error analyzing query intent: {e}")
        
        # Smart fallback analysis based on keywords
        query_lower = query.lower()
        
        # Determine data types based on keywords
        data_types = []
        if any(word in query_lower for word in ["message", "chat", "whatsapp", "telegram", "sms", "text"]):
            data_types.append("chat_records")
        if any(word in query_lower for word in ["call", "phone", "dial", "ring"]):
            data_types.append("call_records")
        if any(word in query_lower for word in ["contact", "person", "name", "number"]):
            data_types.append("contacts")
        if any(word in query_lower for word in ["media", "file", "image", "video", "photo"]):
            data_types.append("media_files")
        
        # If no specific data types, include all
        if not data_types:
            data_types = ["chat_records", "call_records", "contacts", "media_files"]
        
        # Determine search approach
        if any(word in query_lower for word in ["about", "regarding", "similar", "like", "related"]):
            search_approach = "vector_only"
            confidence = 0.8
        elif any(word in query_lower for word in ["all", "show", "list", "count", "how many"]):
            search_approach = "sql_only"
            confidence = 0.9
        elif any(word in query_lower for word in ["connection", "relationship", "between", "linked"]):
            search_approach = "neo4j_only"
            confidence = 0.7
        else:
            search_approach = "hybrid"
            confidence = 0.6
        
        return {
            "query_type": "hybrid",
            "data_types": data_types,
            "filters": {},
            "search_approach": search_approach,
            "confidence": confidence
        }
    
    async def generate_sql_query(self, natural_query: str, analysis: Dict[str, Any]) -> str:
        """Generate SQL query based on natural language input"""
        
        schema_info = """
        Database Schema:
        
        Table: chat_records
        - id (UUID), ufdr_report_id (UUID), app_name (String), sender_number (String)
        - receiver_number (String), message_content (Text), timestamp (DateTime)
        - message_type (String), is_deleted (Boolean), metadata (JSON)
        
        Table: call_records  
        - id (UUID), ufdr_report_id (UUID), caller_number (String), receiver_number (String)
        - call_type (String), duration (Integer), timestamp (DateTime), metadata (JSON)
        
        Table: contacts
        - id (UUID), ufdr_report_id (UUID), name (String), phone_numbers (JSON)
        - email_addresses (JSON), metadata (JSON)
        
        Table: media_files
        - id (UUID), ufdr_report_id (UUID), filename (String), file_path (String)
        - file_type (String), file_size (Integer), created_date (DateTime)
        - modified_date (DateTime), hash_md5 (String), hash_sha256 (String), metadata (JSON)
        """
        
        sql_prompt = f"""
        {schema_info}
        
        Generate a PostgreSQL query for: "{natural_query}"
        
        Analysis context: {json.dumps(analysis)}
        
        Rules:
        1. Use proper PostgreSQL syntax
        2. Include appropriate JOINs when needed
        3. Use ILIKE for case-insensitive text search
        4. Use JSON operators for JSON fields (->>, @>, etc.)
        5. Include LIMIT clause (default 100)
        6. Use proper date filtering with timestamp fields
        
        Return only the SQL query, no explanations.
        """
        
        try:
            response = self.gemini_model.generate_content(sql_prompt)
            sql_query = response.text.strip()
            
            # Clean up the response to extract just the SQL
            if sql_query.startswith('```sql'):
                sql_query = sql_query[6:]
            if sql_query.endswith('```'):
                sql_query = sql_query[:-3]
            
            return sql_query.strip()
        except Exception as e:
            print(f"Error generating SQL query: {e}")
            return ""
    
    async def generate_cypher_query(self, natural_query: str, analysis: Dict[str, Any]) -> str:
        """Generate Cypher query for Neo4j relationship analysis"""
        
        cypher_prompt = f"""
        Generate a Cypher query for Neo4j to analyze relationships in forensic data.
        
        Query: "{natural_query}"
        Analysis: {json.dumps(analysis)}
        
        Graph Schema:
        - Person nodes: phone, name, emails
        - COMMUNICATED relationships: type, app, timestamp, message_id
        - CALLED relationships: type, duration, timestamp, call_id
        
        Common patterns:
        - Find connections: MATCH (p:Person)-[*1..3]-(connected:Person)
        - Communication frequency: COUNT(relationships)
        - Time-based analysis: WHERE r.timestamp >= datetime()
        
        Return only the Cypher query, no explanations.
        """
        
        try:
            response = self.gemini_model.generate_content(cypher_prompt)
            cypher_query = response.text.strip()
            
            # Clean up the response
            if cypher_query.startswith('```cypher'):
                cypher_query = cypher_query[9:]
            elif cypher_query.startswith('```'):
                cypher_query = cypher_query[3:]
            if cypher_query.endswith('```'):
                cypher_query = cypher_query[:-3]
            
            return cypher_query.strip()
        except Exception as e:
            print(f"Error generating Cypher query: {e}")
            return ""
    
    async def execute_hybrid_search(self, query: str) -> Dict[str, Any]:
        """Execute hybrid search combining vector, SQL, and graph queries"""
        
        # Generate query hash for caching
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        # Check cache first
        try:
            cached_result = db_manager.get_cached_result(query_hash)
            if cached_result:
                return cached_result
        except Exception as e:
            print(f"Cache check failed: {e}")
            # Continue without cache
        
        # Analyze query intent
        analysis = await self.analyze_query_intent(query)
        
        results = {
            "query": query,
            "analysis": analysis,
            "vector_results": [],
            "sql_results": [],
            "graph_results": [],
            "combined_score": 0.0
        }
        
        try:
            # Vector search if semantic analysis is needed
            if analysis["search_approach"] in ["vector_only", "hybrid"]:
                try:
                    from app.services.vector_service import vector_service
                    
                    # Determine data types to search based on query analysis
                    data_types_to_search = []
                    for data_type in analysis["data_types"]:
                        if data_type == "chat_records":
                            data_types_to_search.append("message")
                        elif data_type == "call_records":
                            data_types_to_search.append("message")  # Call records are stored as messages
                        elif data_type == "contacts":
                            data_types_to_search.append("contact")
                        elif data_type == "media_files":
                            data_types_to_search.append("finding")
                    
                    # If no specific data types, search all
                    if not data_types_to_search:
                        data_types_to_search = ["message", "contact", "finding"]
                    
                    # Perform semantic search for each data type
                    for data_type in data_types_to_search:
                        try:
                            vector_results = await vector_service.semantic_search(
                                query=query,
                                case_id=None,  # Search all cases
                                data_types=[data_type],
                                limit=10
                            )
                            if vector_results:
                                results["vector_results"].extend(vector_results)
                        except Exception as e:
                            print(f"Error searching vectors for {data_type}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error in vector search: {e}")
            
            # SQL search for structured queries
            sql_results = await self._execute_sql_search(query, analysis)
            if sql_results:
                results["sql_results"] = sql_results
                print(f"Found {len(sql_results)} SQL results")
            
            # Graph search for relationship analysis
            if analysis["search_approach"] in ["neo4j_only", "hybrid"]:
                cypher_query = await self.generate_cypher_query(query, analysis)
                if cypher_query:
                    # Execute Cypher query (implementation needed in database_manager)
                    results["cypher_query"] = cypher_query
                    # results["graph_results"] = db_manager.execute_cypher_query(cypher_query)
            
            # Calculate combined relevance score
            results["combined_score"] = self._calculate_relevance_score(results)
            
            # Cache results
            db_manager.cache_query_result(query_hash, results)
            
        except Exception as e:
            print(f"Error in hybrid search: {e}")
            results["error"] = str(e)
        
        return results
    
    def _calculate_relevance_score(self, results: Dict[str, Any]) -> float:
        """Calculate combined relevance score from different search results"""
        vector_score = sum(r.get("score", 0) for r in results["vector_results"]) / max(len(results["vector_results"]), 1)
        
        # Simple scoring - can be enhanced with more sophisticated algorithms
        combined_score = vector_score * 0.6  # Weight vector search more for semantic queries
        
        if results["sql_results"]:
            combined_score += 0.3  # Add weight for structured results
        
        if results["graph_results"]:
            combined_score += 0.1  # Add weight for relationship results
        
        return min(combined_score, 1.0)
    
    async def generate_investigation_report(self, search_results: Dict[str, Any]) -> str:
        """Generate human-readable investigation report from search results"""
        
        # If no AI model available, generate a basic report
        if not self.gemini_model:
            return self._generate_basic_report(search_results)
        
        report_prompt = f"""
        Generate a comprehensive forensic investigation report based on the following search results:
        
        Query: {search_results.get('query', 'N/A')}
        
        Search Results:
        {json.dumps(search_results, indent=2, default=str)}
        
        Generate a professional forensic report that includes:
        1. Executive Summary
        2. Key Findings
        3. Evidence Details
        4. Connections and Relationships
        5. Recommendations for Further Investigation
        
        Format the report in a clear, professional manner suitable for law enforcement.
        Highlight important evidence and potential leads.
        """
        
        try:
            response = self.gemini_model.generate_content(report_prompt)
            return response.text
        except Exception as e:
            print(f"Error generating report: {e}")
            return self._generate_basic_report(search_results)
    
    def _generate_basic_report(self, search_results: Dict[str, Any]) -> str:
        """Generate a basic report when AI services are not available"""
        query = search_results.get('query', 'N/A')
        vector_results = search_results.get('vector_results', [])
        sql_results = search_results.get('sql_results', [])
        
        report = f"""
📊 **Investigation Report**

**Query:** {query}

**Search Results Summary:**
- SQL search results: {len(sql_results)} items found
- Vector search results: {len(vector_results)} items found
- Analysis approach: {search_results.get('analysis', {}).get('search_approach', 'hybrid')}
- Combined relevance score: {search_results.get('combined_score', 0.0):.2f}

**Key Findings:**
"""
        
        # Show SQL results first (more reliable)
        if sql_results:
            report += "\n**Evidence Found in Database:**\n"
            for i, result in enumerate(sql_results[:5], 1):
                if result.get('type') == 'chat_record':
                    content = result.get('content', 'N/A')
                    app = result.get('app_name', 'Unknown')
                    sender = result.get('sender', 'Unknown')
                    receiver = result.get('receiver', 'Unknown')
                    report += f"{i}. **{app} Message**: {sender} → {receiver}\n"
                    report += f"   Content: \"{content[:80]}...\"\n"
                elif result.get('type') == 'call_record':
                    caller = result.get('caller', 'Unknown')
                    receiver = result.get('receiver', 'Unknown')
                    call_type = result.get('call_type', 'Unknown')
                    duration = result.get('duration', 0)
                    report += f"{i}. **{call_type.title()} Call**: {caller} → {receiver} ({duration}s)\n"
                elif result.get('type') == 'contact':
                    name = result.get('name', 'Unknown')
                    phones = result.get('phone_numbers', [])
                    report += f"{i}. **Contact**: {name} - {', '.join(phones[:2])}\n"
        
        # Show vector results if available
        if vector_results:
            report += "\n**Additional Vector Search Results:**\n"
            for i, result in enumerate(vector_results[:3], 1):
                payload = result.get('payload', {})
                content = payload.get('message_content', payload.get('filename', 'N/A'))
                score = result.get('score', 0.0)
                report += f"{i}. {content[:80]}... (Relevance: {score:.2f})\n"
        
        # If no results found
        if not sql_results and not vector_results:
            report += "\n- No specific evidence found matching the query criteria"
            report += "\n- This could indicate:"
            report += "\n  • The query terms don't match available data"
            report += "\n  • Try more specific search terms"
            report += "\n  • Use keywords like 'WhatsApp', 'call', 'message', 'contact'"
        
        # Add data summary
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            
            db = next(get_db())
            
            # Get total counts
            total_chats = db.execute(text("SELECT COUNT(*) FROM chat_records")).scalar()
            total_calls = db.execute(text("SELECT COUNT(*) FROM call_records")).scalar()
            total_contacts = db.execute(text("SELECT COUNT(*) FROM contacts")).scalar()
            total_media = db.execute(text("SELECT COUNT(*) FROM media_files")).scalar()
            
            report += f"""

**Database Summary:**
- Total Chat Records: {total_chats}
- Total Call Records: {total_calls}
- Total Contacts: {total_contacts}
- Total Media Files: {total_media}

**Recommendations:**
- Try specific queries like: "WhatsApp messages", "outgoing calls", "John Smith"
- Search for phone numbers: "+1234567890"
- Look for specific apps: "Telegram", "SMS"
"""
            
            db.close()
            
        except Exception as e:
            print(f"Error getting database summary: {e}")
            report += f"""

**Recommendations:**
- Try specific queries like: "WhatsApp messages", "outgoing calls", "contacts"
- Search for phone numbers or contact names
- Use keywords related to communication data
"""
        
        return report
    async def _execute_sql_search(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute SQL-based search on PostgreSQL data"""
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            
            db = next(get_db())
            
            # Simple keyword-based search
            query_lower = query.lower()
            results = []
            
            # Search in chat records for message-related queries
            if "message" in query_lower or "chat" in query_lower or "whatsapp" in query_lower or "telegram" in query_lower or "sms" in query_lower:
                chat_sql = text("""
                    SELECT 'chat_record' as type, app_name, sender_number, receiver_number, 
                           message_content, timestamp, message_type
                    FROM chat_records 
                    WHERE LOWER(message_content) LIKE :query 
                       OR LOWER(app_name) LIKE :query
                    ORDER BY timestamp DESC
                    LIMIT 10
                """)
                
                chat_results = db.execute(chat_sql, {"query": f"%{query_lower}%"}).fetchall()
                for row in chat_results:
                    results.append({
                        "type": row.type,
                        "app_name": row.app_name,
                        "sender": row.sender_number,
                        "receiver": row.receiver_number,
                        "content": row.message_content,
                        "timestamp": str(row.timestamp),
                        "message_type": row.message_type
                    })
            
            # Search in call records for call-related queries
            if "call" in query_lower or "phone" in query_lower:
                call_sql = text("""
                    SELECT 'call_record' as type, caller_number, receiver_number, 
                           call_type, duration, timestamp
                    FROM call_records 
                    WHERE LOWER(caller_number) LIKE :query 
                       OR LOWER(receiver_number) LIKE :query
                       OR LOWER(call_type) LIKE :query
                    ORDER BY timestamp DESC
                    LIMIT 10
                """)
                
                call_results = db.execute(call_sql, {"query": f"%{query_lower}%"}).fetchall()
                for row in call_results:
                    results.append({
                        "type": row.type,
                        "caller": row.caller_number,
                        "receiver": row.receiver_number,
                        "call_type": row.call_type,
                        "duration": row.duration,
                        "timestamp": str(row.timestamp)
                    })
            
            # Search in contacts for contact-related queries
            if "contact" in query_lower or "name" in query_lower:
                contact_sql = text("""
                    SELECT 'contact' as type, name, phone_numbers, email_addresses
                    FROM contacts 
                    WHERE LOWER(name) LIKE :query
                    LIMIT 10
                """)
                
                contact_results = db.execute(contact_sql, {"query": f"%{query_lower}%"}).fetchall()
                for row in contact_results:
                    results.append({
                        "type": row.type,
                        "name": row.name,
                        "phone_numbers": row.phone_numbers,
                        "email_addresses": row.email_addresses
                    })
            
            # For general queries like "show all", "how many", "evidence", show summary
            if any(word in query_lower for word in ["all", "show", "find", "how many", "evidence", "summary", "data"]):
                # Get all chat records
                all_chats_sql = text("""
                    SELECT 'chat_record' as type, app_name, sender_number, receiver_number, 
                           message_content, timestamp, message_type
                    FROM chat_records 
                    ORDER BY timestamp DESC
                    LIMIT 10
                """)
                
                all_chat_results = db.execute(all_chats_sql).fetchall()
                for row in all_chat_results:
                    results.append({
                        "type": row.type,
                        "app_name": row.app_name,
                        "sender": row.sender_number,
                        "receiver": row.receiver_number,
                        "content": row.message_content,
                        "timestamp": str(row.timestamp),
                        "message_type": row.message_type
                    })
                
                # Get all call records
                all_calls_sql = text("""
                    SELECT 'call_record' as type, caller_number, receiver_number, 
                           call_type, duration, timestamp
                    FROM call_records 
                    ORDER BY timestamp DESC
                    LIMIT 5
                """)
                
                all_call_results = db.execute(all_calls_sql).fetchall()
                for row in all_call_results:
                    results.append({
                        "type": row.type,
                        "caller": row.caller_number,
                        "receiver": row.receiver_number,
                        "call_type": row.call_type,
                        "duration": row.duration,
                        "timestamp": str(row.timestamp)
                    })
            
            db.close()
            return results
            
        except Exception as e:
            print(f"Error in SQL search: {e}")
            return []
# Global AI service instance
ai_service = AIService()