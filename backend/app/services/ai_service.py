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
        # No Azure OpenAI - embeddings handled by VectorService
        self.openai_client = None
        
        # Setup Gemini for query processing
        try:
            if settings.gemini_api_key:
                print(f"🔧 Setting up Gemini with API key: {settings.gemini_api_key[:8]}...")
                genai.configure(api_key=settings.gemini_api_key)
                # Use the correct model name for Gemini
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
                print(f"✅ Gemini setup successful")
            else:
                print(f"❌ Gemini API key missing")
                self.gemini_model = None
        except Exception as e:
            print(f"❌ Gemini setup failed: {e}")
            self.gemini_model = None
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI"""
        try:
            # Delegate to VectorService local embedder for consistency
            from app.services.vector_service import vector_service
            embeddings = []
            for text in texts:
                vec = await vector_service.generate_embedding(text)
                if not vec:
                    # Fallback: minimal dummy vector of configured size
                    vec = self._generate_dummy_embedding(text, settings.embedding_dimension)
                embeddings.append(vec)
            print(f"✅ Generated {len(embeddings)} embeddings with {len(embeddings[0])} dimensions")
            return embeddings
            
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            return [self._generate_dummy_embedding(text, settings.embedding_dimension) for text in texts]
    
    def _generate_dummy_embedding(self, text: str, dimensions: int = 768) -> List[float]:
        """Generate a dummy embedding based on text content for testing"""
        import hashlib
        import struct
        import numpy as np
        
        # Create a more sophisticated dummy embedding based on text content
        text_hash = hashlib.sha256(text.encode()).digest()
        
        # Use the hash as a seed for reproducible random numbers
        seed = int.from_bytes(text_hash[:4], byteorder='big')
        np.random.seed(seed % (2**32))
        
        # Generate random embedding with normal distribution
        embedding = np.random.normal(0, 0.1, dimensions).tolist()
        
        # Normalize to unit vector (common for embeddings)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        
        print(f"🔧 Generated dummy embedding with {len(embedding)} dimensions for text: '{text[:50]}...'")
        return embedding
    
    async def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user query to determine search strategy using AI"""
        
        # First, get database schema information dynamically
        schema_info = await self._get_dynamic_schema_info()
        
        analysis_prompt = f"""
        You are a forensic data analysis expert. Analyze this query and determine the best search strategy.
        
        Query: "{query}"
        
        Available Data Schema:
        {schema_info}
        
        Based on the actual data available, determine:
        1. What type of information the user is looking for
        2. Which database tables/collections to search
        3. What search approach would be most effective
        4. Any specific filters or conditions needed
        
        Respond in JSON format:
        {{
            "intent": "count|search|analyze|compare|find_relationships",
            "target_data": ["chat_records", "call_records", "contacts", "media_files"],
            "search_approach": "sql_only|vector_only|hybrid|graph_only",
            "specific_filters": {{
                "keywords": ["extracted", "keywords"],
                "phone_numbers": ["if", "mentioned"],
                "apps": ["whatsapp", "telegram", "etc"],
                "time_based": true/false
            }},
            "expected_output": "description of what user expects",
            "confidence": 0.0-1.0
        }}
        """
        
        try:
            if self.gemini_model:
                response = self.gemini_model.generate_content(analysis_prompt)
                if response and response.text and response.text.strip():
                    response_text = response.text.strip()
                    
                    # Clean JSON response
                    if response_text.startswith('```json'):
                        response_text = response_text[7:]
                    if response_text.endswith('```'):
                        response_text = response_text[:-3]
                    
                    response_text = response_text.strip()
                    
                    if response_text:
                        analysis = json.loads(response_text)
                        print(f"🧠 AI Analysis: {analysis}")
                        
                        # Post-process AI analysis to ensure device_info is included for device queries
                        query_lower = query.lower()
                        device_keywords = ["device", "imei", "model", "manufacturer", "serial", "os version", "android", "ios", "phone number", "extraction tool", "case officer", "operating system", "os", "hardware", "specifications"]
                        if any(word in query_lower for word in device_keywords):
                            if "device_info" not in analysis.get("target_data", []):
                                analysis["target_data"].append("device_info")
                                print(f"🔧 Added device_info to AI analysis target_data")
                        
                        return analysis
                        
        except Exception as e:
            print(f"AI analysis failed: {e}")
        
        # Enhanced fallback analysis
        return await self._enhanced_fallback_analysis(query)
    
    async def _get_dynamic_schema_info(self, case_number: Optional[str] = None) -> str:
        """Get actual database schema and data statistics for a specific case or all cases"""
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            from app.services.case_manager import case_manager
            
            db = next(get_db())
            schema_info = "Current Database Contents:\n"
            
            if case_number:
                # Get case-specific data
                case_info = case_manager.get_case_info(case_number)
                if case_info:
                    safe_case_name = case_info["safe_case_name"]
                    schema_name = f"case_{safe_case_name}"
                    
                    schema_info += f"Case: {case_number} (Schema: {schema_name})\n"
                    
                    # Chat records info
                    chat_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.chat_records")).scalar() or 0
                    if chat_count > 0:
                        sample_apps = db.execute(text(f"SELECT DISTINCT app_name FROM {schema_name}.chat_records LIMIT 5")).fetchall()
                        apps = [row[0] for row in sample_apps if row[0]]
                        schema_info += f"- Chat Records: {chat_count} messages from apps: {', '.join(apps)}\n"
                    
                    # Call records info
                    call_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.call_records")).scalar() or 0
                    if call_count > 0:
                        call_types = db.execute(text(f"SELECT DISTINCT call_type FROM {schema_name}.call_records LIMIT 5")).fetchall()
                        types = [row[0] for row in call_types if row[0]]
                        schema_info += f"- Call Records: {call_count} calls of types: {', '.join(types)}\n"
                    
                    # Contacts info
                    contact_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.contacts")).scalar() or 0
                    if contact_count > 0:
                        schema_info += f"- Contacts: {contact_count} contact entries\n"
                    
                    # Media files info
                    media_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.media_files")).scalar() or 0
                    if media_count > 0:
                        media_types = db.execute(text(f"SELECT DISTINCT file_type FROM {schema_name}.media_files LIMIT 5")).fetchall()
                        types = [row[0] for row in media_types if row[0]]
                        schema_info += f"- Media Files: {media_count} files of types: {', '.join(types)}\n"
                else:
                    schema_info += f"Case {case_number} not found or no data available.\n"
            else:
                # Get all cases data
                active_cases = case_manager.list_active_cases()
                if active_cases:
                    schema_info += f"Active Cases: {', '.join(active_cases)}\n"
                    for case in active_cases:
                        case_info = case_manager.get_case_info(case)
                        if case_info:
                            safe_case_name = case_info["safe_case_name"]
                            schema_name = f"case_{safe_case_name}"
                            
                            try:
                                chat_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.chat_records")).scalar() or 0
                                call_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.call_records")).scalar() or 0
                                contact_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.contacts")).scalar() or 0
                                media_count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.media_files")).scalar() or 0
                                
                                schema_info += f"  {case}: {chat_count} chats, {call_count} calls, {contact_count} contacts, {media_count} media\n"
                            except:
                                schema_info += f"  {case}: Schema not accessible\n"
                else:
                    schema_info += "No active cases found.\n"
            
            db.close()
            return schema_info
            
        except Exception as e:
            print(f"Error getting schema info: {e}")
            return "Database schema information unavailable"
    
    async def _enhanced_fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Enhanced fallback analysis with better intent detection"""
        query_lower = query.lower()
        
        # Detect intent patterns
        if any(word in query_lower for word in ["how many", "count", "total", "number of"]):
            intent = "count"
            search_approach = "sql_only"
        elif any(word in query_lower for word in ["show all", "list all", "display", "get all"]):
            intent = "search"
            search_approach = "sql_only"
        elif any(word in query_lower for word in ["find", "search", "look for", "about", "regarding"]):
            intent = "search"
            search_approach = "hybrid"
        elif any(word in query_lower for word in ["connection", "relationship", "between", "linked", "network"]):
            intent = "find_relationships"
            search_approach = "graph_only"
        elif any(word in query_lower for word in ["analyze", "pattern", "suspicious", "risk"]):
            intent = "analyze"
            search_approach = "hybrid"
        else:
            intent = "search"
            search_approach = "hybrid"
        
        # Detect target data types
        target_data = []
        if any(word in query_lower for word in ["message", "chat", "whatsapp", "telegram", "sms", "text"]):
            target_data.append("chat_records")
        if any(word in query_lower for word in ["call", "phone", "dial", "ring"]):
            target_data.append("call_records")
        if any(word in query_lower for word in ["contact", "person", "name"]):
            target_data.append("contacts")
        if any(word in query_lower for word in ["media", "file", "image", "video", "photo"]):
            target_data.append("media_files")
        # Device metadata - detect device-related queries FIRST
        device_keywords = ["device", "imei", "model", "manufacturer", "serial", "os version", "android", "ios", "phone number", "extraction tool", "case officer", "operating system", "os", "hardware", "specifications"]
        if any(word in query_lower for word in device_keywords):
            target_data.append("device_info")
        # Generic artifacts → include all data-bearing tables
        if "artifact" in query_lower or "artifacts" in query_lower:
            target_data = ["chat_records", "call_records", "contacts", "media_files", "device_info"]
        
        # If no specific data types detected, search all
        if not target_data:
            target_data = ["chat_records", "call_records", "contacts", "media_files"]
        
        return {
            "intent": intent,
            "target_data": target_data,
            "search_approach": search_approach,
            "specific_filters": {},
            "expected_output": f"Results for: {query}",
            "confidence": 0.7
        }
    
    async def generate_sql_query(self, natural_query: str, analysis: Dict[str, Any], case_number: Optional[str] = None) -> str:
        """Generate SQL query based on natural language input with dynamic schema info"""
        
        # Get dynamic schema information for the specific case
        schema_info = await self._get_dynamic_schema_info(case_number)
        
        base_schema = """
        Database Schema Structure:
        
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
        You are a forensic data analyst generating SQL queries for PostgreSQL.
        
        {base_schema}
        
        Current Data Available:
        {schema_info}
        
        User Query: "{natural_query}"
        Query Analysis: {json.dumps(analysis, indent=2)}
        
        Generate a PostgreSQL query that:
        1. Uses proper PostgreSQL syntax
        2. Searches the appropriate tables based on the query intent
        3. Uses ILIKE for case-insensitive text search
        4. Uses JSON operators for JSON fields (->>, @>, etc.)
        5. Includes appropriate WHERE clauses for filtering
        6. Uses LIMIT clause (default 50 for performance)
        7. Orders results by relevance (timestamp DESC for time-based data)
        8. Handles phone number variations (+1234567890, +1-234-567-8900, etc.)
        9. NEVER filter by ufdr_report_id - it's a UUID and not the case number
        10. Focus on content-based filtering (message_content, app_name, etc.)
        11. AVOID using CREATE, DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE keywords
        12. Use only SELECT statements
        13. Do not use the word "DELETE" anywhere in the query, even in comments
        14. For simple queries, avoid complex WHERE clauses
        
        For the query intent "{analysis.get('intent', 'search')}" targeting {analysis.get('target_data', [])}, 
        generate the most appropriate SQL query.
        
        CRITICAL RULES:
        - Return ONLY a simple SELECT statement
        - Do NOT use CREATE, DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE
        - Do NOT use complex UNION statements unless absolutely necessary
        - Keep queries simple and focused
        - Use basic WHERE clauses with ILIKE for text search
        - Avoid complex JSON operations that might fail
        """
        
        try:
            if not self.gemini_model:
                print("⚠️ Gemini model not available for SQL generation")
                return ""
                
            response = self.gemini_model.generate_content(sql_prompt)
            if not response or not response.text:
                print("⚠️ Empty response from Gemini for SQL generation")
                return ""
                
            sql_query = response.text.strip()
            
            # Clean up the response to extract just the SQL
            if sql_query.startswith('```sql'):
                sql_query = sql_query[6:]
            elif sql_query.startswith('```'):
                sql_query = sql_query[3:]
            if sql_query.endswith('```'):
                sql_query = sql_query[:-3]
            
            sql_query = sql_query.strip()
            
            # Basic validation
            if not sql_query or len(sql_query) < 10:
                print("⚠️ Generated SQL query too short or empty")
                return ""
            
            # Ensure it's a SELECT query
            if not sql_query.upper().startswith('SELECT'):
                print("⚠️ Generated query is not a SELECT statement")
                return ""
            
            print(f"✅ Generated SQL query: {sql_query[:100]}...")
            return sql_query
            
        except Exception as e:
            print(f"❌ Error generating SQL query: {e}")
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
    
    async def execute_hybrid_search(self, query: str, case_number: Optional[str] = None) -> Dict[str, Any]:
        """Execute intelligent hybrid search with dynamic approach selection"""
        
        print(f"🔍 Starting hybrid search for: {query} (Case: {case_number})")
        
        # Analyze query intent using AI
        analysis = await self.analyze_query_intent(query)
        
        results = {
            "query": query,
            "case_number": case_number,
            "analysis": analysis,
            "vector_results": [],
            "sql_results": [],
            "graph_results": [],
            "combined_score": 0.0
        }
        
        search_approach = analysis.get("search_approach", "hybrid")
        target_data = analysis.get("target_data", [])
        
        print(f"🧠 Search approach: {search_approach}, Target data: {target_data}")
        
        try:
            # Execute SQL search (always for structured data)
            if search_approach in ["sql_only", "hybrid"]:
                # Check if this is a device_info query - handle it specially
                query_lower = query.lower()
                device_keywords = ["device", "imei", "model", "manufacturer", "serial", "os version", "android", "ios", "phone number", "extraction tool", "case officer", "operating system", "os", "hardware", "specifications"]
                is_device_query = any(word in query_lower for word in device_keywords)
                
                if is_device_query and "device_info" in target_data:
                    # Device query - prioritize device_info search
                    print(f"🔧 Detected device query, using device_info search")
                    sql_results = await self._execute_device_info_search(case_number)
                elif "device_info" in target_data:
                    # Mixed query - try LLM first, then fallback
                    if self.gemini_model and analysis.get("intent") != "count":
                        try:
                            generated_sql = await self.generate_sql_query(query, analysis)
                            if generated_sql:
                                print(f"🤖 Generated SQL query: {generated_sql[:100]}...")
                                sql_results = await self._execute_generated_sql(generated_sql, case_number)
                            else:
                                sql_results = await self._execute_sql_search(query, analysis, case_number)
                        except Exception as e:
                            print(f"⚠️ LLM SQL generation failed: {e}, falling back to template search")
                            sql_results = await self._execute_sql_search(query, analysis, case_number)
                    else:
                        sql_results = await self._execute_sql_search(query, analysis, case_number)
                else:
                    # Regular query - use LLM or template
                    if self.gemini_model and analysis.get("intent") != "count":
                        try:
                            generated_sql = await self.generate_sql_query(query, analysis)
                            if generated_sql:
                                print(f"🤖 Generated SQL query: {generated_sql[:100]}...")
                                sql_results = await self._execute_generated_sql(generated_sql, case_number)
                            else:
                                sql_results = await self._execute_sql_search(query, analysis, case_number)
                        except Exception as e:
                            print(f"⚠️ LLM SQL generation failed: {e}, falling back to template search")
                            sql_results = await self._execute_sql_search(query, analysis, case_number)
                    else:
                        sql_results = await self._execute_sql_search(query, analysis, case_number)
                
                if sql_results:
                    results["sql_results"] = sql_results
                    print(f"📊 SQL search found {len(sql_results)} results")
            
            # Execute vector search for semantic queries
            if search_approach in ["vector_only", "hybrid"] and analysis.get("intent") != "count":
                try:
                    from app.services.vector_service import vector_service
                    from app.services.case_manager import case_manager
                    
                    # Check if vector service is available
                    if not vector_service.qdrant_client:
                        print("⚠️ Vector search unavailable - Qdrant client not connected")
                        # Continue without vector search
                    else:
                        # Determine which collection to search
                        collection_name = "forensic_data"  # Default fallback
                        if case_number:
                            case_info = case_manager.get_case_info(case_number)
                            if case_info:
                                safe_case_name = case_info["safe_case_name"]
                                collection_name = f"case_{safe_case_name}"
                                print(f"🎯 Searching in case-specific collection: {collection_name}")
                        
                        # Map target data to vector data types
                        vector_data_types = []
                        for data_type in target_data:
                            if data_type == "chat_records":
                                vector_data_types.append("chat_record")
                            elif data_type == "call_records":
                                vector_data_types.append("call_record")
                            elif data_type == "contacts":
                                vector_data_types.append("contact")
                            elif data_type == "media_files":
                                vector_data_types.append("media_file")
                        
                        # If no specific data types, search all
                        if not vector_data_types:
                            vector_data_types = ["chat_record", "call_record", "contact", "media_file"]
                        
                        # Use the case-specific search method
                        vector_results = await vector_service.search_case_collection(
                            query=query,
                            collection_name=collection_name,
                            data_types=vector_data_types,
                            limit=20,
                            score_threshold=0.3
                        )
                        
                        if vector_results:
                            # Convert vector results to standard format
                            formatted_vector_results = []
                            for result in vector_results:
                                payload = result.get("payload", {})
                                formatted_result = {
                                    "type": payload.get("data_type", "unknown"),
                                    "score": result.get("score", 0.0),
                                    "id": result.get("id", ""),
                                    **payload  # Include all payload data
                                }
                                formatted_vector_results.append(formatted_result)
                            
                            results["vector_results"] = formatted_vector_results
                            print(f"🔍 Vector search found {len(formatted_vector_results)} results in {collection_name}")
                        else:
                            print(f"⚠️ No vector results found in {collection_name}")
                            
                except Exception as e:
                    print(f"❌ Error in vector search: {e}")
                    # Continue without vector search
            
            # Execute graph search for relationship queries
            if search_approach in ["graph_only", "hybrid"] and analysis.get("intent") == "find_relationships":
                try:
                    # This would be implemented when graph queries are needed
                    print("🕸️ Graph search not yet implemented for this query type")
                except Exception as e:
                    print(f"Error in graph search: {e}")
            
            # Calculate combined relevance score
            results["combined_score"] = self._calculate_relevance_score(results)
            
            print(f"✅ Hybrid search completed. SQL: {len(results['sql_results'])}, Vector: {len(results['vector_results'])}")
            
        except Exception as e:
            print(f"❌ Error in hybrid search: {e}")
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
        """Generate intelligent, context-aware response to user query"""
        query = search_results.get('query', 'N/A')
        vector_results = search_results.get('vector_results', [])
        sql_results = search_results.get('sql_results', [])
        analysis = search_results.get('analysis', {})
        
        intent = analysis.get('intent', 'search')
        
        # Handle COUNT queries specifically
        if intent == "count":
            count_results = [r for r in sql_results if r.get('type') == 'count_result']
            if count_results:
                if len(count_results) == 1:
                    result = count_results[0]
                    return f"**{result['description']}**"
                else:
                    answer = f"**Data Summary:**\n\n"
                    for result in count_results:
                        answer += f"• {result['description']}\n"
                    return answer
        
        # Handle regular search results - show actual data, not generic descriptions
        all_results = sql_results + vector_results
        if not all_results:
            return f"**No results found for: {query}**\n\nThe uploaded data doesn't contain information matching your query. Try different keywords or check what data is available."
        
        # For "show/list" queries, use the itemized renderer
        show_words = ["show", "list", "display", "all", "results"]
        if any(w in query.lower() for w in show_words):
            return self.render_itemized_answer(query, search_results)
        
        # For other queries, show actual data with context
        answer = f"**Found {len(all_results)} results for: {query}**\n\n"
        
        # Show actual data from results, not generic descriptions
        for i, result in enumerate(all_results[:10], 1):  # Limit to first 10 for readability
            result_type = result.get('type', 'unknown')
            answer += f"**{i}. {result_type.replace('_', ' ').title()}:**\n"
            
            # Special handling for device_info results
            if result_type == 'device_info':
                device_fields = [
                    ('Manufacturer', result.get('manufacturer')),
                    ('Model', result.get('model')),
                    ('OS Version', result.get('os_version')),
                    ('IMEI', result.get('imei')),
                    ('Serial Number', result.get('serial_number')),
                    ('Phone Number', result.get('phone_number')),
                    ('Extraction Tool', result.get('extraction_tool')),
                    ('Case Officer', result.get('case_officer')),
                    ('Extraction Date', result.get('extraction_date'))
                ]
                
                for field_name, field_value in device_fields:
                    if field_value:
                        answer += f"• {field_name}: {field_value}\n"
            else:
                # Show the most relevant fields dynamically for other types
                relevant_fields = []
                for key, value in result.items():
                    if key not in ['type', 'id', 'ufdr_report_id', 'device_info'] and value is not None:
                        if isinstance(value, (str, int, float)):
                            relevant_fields.append(f"• {key}: {value}")
                        elif isinstance(value, list) and len(value) > 0:
                            relevant_fields.append(f"• {key}: {', '.join(map(str, value[:3]))}")
                
                if relevant_fields:
                    answer += "\n".join(relevant_fields[:5]) + "\n"  # Show top 5 fields
                else:
                    answer += "• No additional details available\n"
            
            answer += "\n"
        
        if len(all_results) > 10:
            answer += f"... and {len(all_results) - 10} more results"
        
        return answer

    def render_itemized_answer(self, query: str, results: Dict[str, Any], max_items: int = 50) -> str:
        """Render dynamic itemized results for 'show/list' style queries without hardcoding fields.
        - Determines requested types from the query if possible; otherwise displays all types.
        - Prints up to max_items entries with their most informative primitive fields.
        """
        all_items: List[Dict[str, Any]] = results.get('sql_results', []) + results.get('vector_results', [])
        if not all_items:
            return "No results found."

        ql = (query or '').lower()
        requested_types = set()
        if any(w in ql for w in ['call', 'calls', 'call records', 'call_record']):
            requested_types.add('call_record')
        if any(w in ql for w in ['chat', 'message', 'messages', 'chats']):
            requested_types.add('chat_record')
        if any(w in ql for w in ['contact', 'contacts', 'people', 'persons']):
            requested_types.add('contact')
        if any(w in ql for w in ['media', 'file', 'files', 'photos', 'images', 'videos']):
            requested_types.add('media_file')

        def pick_fields(item: Dict[str, Any]) -> List[str]:
            # Prefer informative keys; exclude noisy/internal ones
            exclude = { 'id', 'type', 'score', 'payload', 'ufdr_report_id' }
            # Keep primitives only
            kv = [(k, v) for k, v in item.items() if k not in exclude and isinstance(v, (str, int, float, bool)) and v is not None]
            # Heuristic: prefer keys with these hints first
            priority = ['timestamp', 'created_date', 'app_name', 'sender', 'receiver', 'caller', 'call_type', 'duration', 'name', 'phone_numbers', 'email_addresses', 'filename', 'file_type', 'file_size']
            kv.sort(key=lambda t: (0 if t[0] in priority else 1, t[0]))
            lines = []
            for k, v in kv[:6]:
                if isinstance(v, list):
                    v = ', '.join(map(str, v[:3]))
                lines.append(f"{k}: {v}")
            return lines

        filtered = [it for it in all_items if not requested_types or it.get('type') in requested_types]
        header = f"Found {len(filtered)} result(s)" if requested_types else f"Found {len(filtered)} result(s) across all types"
        out = [header]
        for i, item in enumerate(filtered[:max_items], 1):
            out.append(f"{i}. [{item.get('type','unknown')}] ")
            for line in pick_fields(item):
                out.append(f"   - {line}")
        if len(filtered) > max_items:
            out.append(f"… and {len(filtered) - max_items} more")
        return "\n".join(out)
    async def _execute_sql_search(self, query: str, analysis: Dict[str, Any], case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute intelligent SQL-based search on case-specific PostgreSQL data"""
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            from app.services.case_manager import case_manager
            
            db = next(get_db())
            results = []
            
            intent = analysis.get("intent", "search")
            target_data = analysis.get("target_data", [])
            # Normalize query early so it's available to all branches
            query_lower = (query or "").lower()
            
            print(f"🔍 SQL Search - Intent: {intent}, Target: {target_data}, Case: {case_number}")
            
            # Determine which schema to search
            if case_number:
                case_info = case_manager.get_case_info(case_number)
                if case_info:
                    safe_case_name = case_info["safe_case_name"]
                    schema_name = f"case_{safe_case_name}"
                    print(f"🎯 Searching in case-specific schema: {schema_name}")
                else:
                    print(f"⚠️ Case {case_number} not found, searching all available data")
                    schema_name = None
            else:
                # Search all active cases - use the most recent one
                active_cases = case_manager.list_active_cases()
                if active_cases:
                    print(f"🔍 Searching across {len(active_cases)} active cases")
                    # Use the most recent case (last in list)
                    recent_case = active_cases[-1]
                    case_info = case_manager.get_case_info(recent_case)
                    if case_info:
                        safe_case_name = case_info["safe_case_name"]
                        schema_name = f"case_{safe_case_name}"
                        print(f"🎯 Using most recent case: {recent_case} (schema: {schema_name})")
                    else:
                        schema_name = None
                else:
                    print("⚠️ No active cases found")
                    schema_name = None
            
            if not schema_name:
                print("❌ No valid schema found for search")
                return results
            
            # Handle COUNT queries
            if intent == "count":
                if "chat_records" in target_data:
                    count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.chat_records")).scalar() or 0
                    results.append({
                        "type": "count_result",
                        "data_type": "chat_records",
                        "count": count,
                        "description": f"Total chat messages: {count}"
                    })
                
                if "call_records" in target_data:
                    count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.call_records")).scalar() or 0
                    results.append({
                        "type": "count_result",
                        "data_type": "call_records", 
                        "count": count,
                        "description": f"Total call records: {count}"
                    })
                
                if "contacts" in target_data:
                    count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.contacts")).scalar() or 0
                    results.append({
                        "type": "count_result",
                        "data_type": "contacts",
                        "count": count,
                        "description": f"Total contacts: {count}"
                    })
                
                if "media_files" in target_data:
                    count = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.media_files")).scalar() or 0
                    results.append({
                        "type": "count_result",
                        "data_type": "media_files",
                        "count": count,
                        "description": f"Total media files: {count}"
                    })
                # Combined artifact count if user asked about artifacts
                if "artifact" in query_lower or "artifacts" in query_lower:
                    total_count = 0
                    for dt in ["chat_records", "call_records", "contacts", "media_files"]:
                        try:
                            c = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.{dt}")).scalar() or 0
                            total_count += c
                        except Exception:
                            pass
                    results.append({
                        "type": "count_result",
                        "data_type": "artifacts",
                        "count": total_count,
                        "description": f"Total artifacts (all types): {total_count}"
                    })
            
            # Handle SEARCH queries
            elif intent in ["search", "analyze"]:
                
                # Dynamic chat record search
                if "chat_records" in target_data:
                    chat_sql = text(f"""
                        SELECT 'chat_record' as type, app_name, sender_number, receiver_number, 
                               message_content, timestamp, message_type, id
                        FROM {schema_name}.chat_records 
                        WHERE LOWER(message_content) LIKE :query 
                           OR LOWER(app_name) LIKE :query
                           OR LOWER(sender_number) LIKE :query
                           OR LOWER(receiver_number) LIKE :query
                        ORDER BY timestamp DESC
                        LIMIT 20
                    """)
                    
                    chat_results = db.execute(chat_sql, {"query": f"%{query_lower}%"}).fetchall()
                    for row in chat_results:
                        results.append({
                            "type": "chat_record",
                            "id": str(row.id),
                            "app_name": row.app_name,
                            "sender": row.sender_number,
                            "receiver": row.receiver_number,
                            "content": row.message_content,
                            "timestamp": str(row.timestamp),
                            "message_type": row.message_type
                        })
                
                # Dynamic call record search
                if "call_records" in target_data:
                    call_sql = text(f"""
                        SELECT 'call_record' as type, caller_number, receiver_number, 
                               call_type, duration, timestamp, id
                        FROM {schema_name}.call_records 
                        WHERE LOWER(caller_number) LIKE :query 
                           OR LOWER(receiver_number) LIKE :query
                           OR LOWER(call_type) LIKE :query
                        ORDER BY timestamp DESC
                        LIMIT 20
                    """)
                    
                    call_results = db.execute(call_sql, {"query": f"%{query_lower}%"}).fetchall()
                    for row in call_results:
                        results.append({
                            "type": "call_record",
                            "id": str(row.id),
                            "caller": row.caller_number,
                            "receiver": row.receiver_number,
                            "call_type": row.call_type,
                            "duration": row.duration,
                            "timestamp": str(row.timestamp)
                        })
                
                # Dynamic contact search
                if "contacts" in target_data:
                    contact_sql = text(f"""
                        SELECT 'contact' as type, name, phone_numbers, email_addresses, id
                        FROM {schema_name}.contacts 
                        WHERE LOWER(name) LIKE :query
                           OR LOWER(phone_numbers::text) LIKE :query
                           OR LOWER(email_addresses::text) LIKE :query
                        LIMIT 20
                    """)
                    
                    contact_results = db.execute(contact_sql, {"query": f"%{query_lower}%"}).fetchall()
                    for row in contact_results:
                        results.append({
                            "type": "contact",
                            "id": str(row.id),
                            "name": row.name,
                            "phone_numbers": row.phone_numbers,
                            "email_addresses": row.email_addresses
                        })
                
                # Dynamic media file search
                if "media_files" in target_data:
                    media_sql = text(f"""
                        SELECT 'media_file' as type, filename, file_type, file_size, 
                               created_date, file_path, id
                        FROM {schema_name}.media_files 
                        WHERE LOWER(filename) LIKE :query
                           OR LOWER(file_type) LIKE :query
                        ORDER BY created_date DESC
                        LIMIT 20
                    """)
                    
                    media_results = db.execute(media_sql, {"query": f"%{query_lower}%"}).fetchall()
                    for row in media_results:
                        results.append({
                            "type": "media_file",
                            "id": str(row.id),
                            "filename": row.filename,
                            "file_type": row.file_type,
                            "file_size": row.file_size,
                            "created_date": str(row.created_date),
                            "file_path": row.file_path
                        })
                
                # Device info search when requested
                if "device_info" in target_data:
                    try:
                        device_rows = db.execute(text(f"""
                            SELECT id, device_info, extraction_date, investigator, filename
                            FROM {schema_name}.ufdr_reports
                            ORDER BY created_at DESC
                            LIMIT 5
                        """)).fetchall()
                        for row in device_rows:
                            # Parse device_info JSON
                            device_payload = {}
                            if row.device_info:
                                if isinstance(row.device_info, str):
                                    import json
                                    try:
                                        device_payload = json.loads(row.device_info)
                                    except:
                                        device_payload = {}
                                elif isinstance(row.device_info, dict):
                                    device_payload = row.device_info
                            
                            # Create a comprehensive device info result
                            device_result = {
                                "type": "device_info",
                                "id": str(row.id),
                                "extraction_date": str(row.extraction_date) if getattr(row, 'extraction_date', None) else None,
                                "investigator": getattr(row, 'investigator', None),
                                "filename": getattr(row, 'filename', None),
                                "manufacturer": device_payload.get('manufacturer'),
                                "model": device_payload.get('model'),
                                "os_version": device_payload.get('os_version'),
                                "imei": device_payload.get('imei'),
                                "serial_number": device_payload.get('serial_number'),
                                "phone_number": device_payload.get('phone_number'),
                                "extraction_tool": device_payload.get('extraction_tool'),
                                "case_officer": device_payload.get('case_officer'),
                                "device_info": device_payload
                            }
                            results.append(device_result)
                    except Exception as e:
                        print(f"Device info search error: {e}")
            
            # Handle SHOW ALL queries
            elif intent == "search" and any(word in query.lower() for word in ["show all", "list all", "all"]):
                if "chat_records" in target_data:
                    all_chats_sql = text(f"""
                        SELECT 'chat_record' as type, app_name, sender_number, receiver_number, 
                               message_content, timestamp, message_type, id
                        FROM {schema_name}.chat_records 
                        ORDER BY timestamp DESC
                        LIMIT 50
                    """)
                    
                    chat_results = db.execute(all_chats_sql).fetchall()
                    for row in chat_results:
                        results.append({
                            "type": "chat_record",
                            "id": str(row.id),
                            "app_name": row.app_name,
                            "sender": row.sender_number,
                            "receiver": row.receiver_number,
                            "content": row.message_content,
                            "timestamp": str(row.timestamp),
                            "message_type": row.message_type
                        })
                
                if "contacts" in target_data:
                    all_contacts_sql = text(f"""
                        SELECT 'contact' as type, name, phone_numbers, email_addresses, id
                        FROM {schema_name}.contacts 
                        ORDER BY name
                        LIMIT 50
                    """)
                    
                    contact_results = db.execute(all_contacts_sql).fetchall()
                    for row in contact_results:
                        results.append({
                            "type": "contact",
                            "id": str(row.id),
                            "name": row.name,
                            "phone_numbers": row.phone_numbers,
                            "email_addresses": row.email_addresses
                        })
            
            db.close()
            print(f"📊 SQL Search found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"Error in SQL search: {e}")
            return []
    
    async def _execute_device_info_search(self, case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute direct device info search from ufdr_reports table"""
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            from app.services.case_manager import case_manager
            
            db = next(get_db())
            results = []
            
            # Determine schema
            if case_number:
                case_info = case_manager.get_case_info(case_number)
                if case_info:
                    safe_case_name = case_info["safe_case_name"]
                    schema_name = f"case_{safe_case_name}"
                    
                    # Direct query for device info
                    device_rows = db.execute(text(f"""
                        SELECT id, device_info, extraction_date, investigator, filename
                        FROM {schema_name}.ufdr_reports
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)).fetchall()
                    
                    for row in device_rows:
                        # Parse device_info JSON
                        device_payload = {}
                        if row.device_info:
                            if isinstance(row.device_info, str):
                                import json
                                try:
                                    device_payload = json.loads(row.device_info)
                                except:
                                    device_payload = {}
                            elif isinstance(row.device_info, dict):
                                device_payload = row.device_info
                        
                        # Create a comprehensive device info result
                        device_result = {
                            "type": "device_info",
                            "id": str(row.id),
                            "extraction_date": str(row.extraction_date) if getattr(row, 'extraction_date', None) else None,
                            "investigator": getattr(row, 'investigator', None),
                            "filename": getattr(row, 'filename', None),
                            "manufacturer": device_payload.get('manufacturer'),
                            "model": device_payload.get('model'),
                            "os_version": device_payload.get('os_version'),
                            "imei": device_payload.get('imei'),
                            "serial_number": device_payload.get('serial_number'),
                            "phone_number": device_payload.get('phone_number'),
                            "extraction_tool": device_payload.get('extraction_tool'),
                            "case_officer": device_payload.get('case_officer'),
                            "device_info": device_payload
                        }
                        results.append(device_result)
                else:
                    print("❌ Case not found for device info search")
                    return []
            else:
                print("❌ No case specified for device info search")
                return []
            
            db.close()
            print(f"✅ Device info search executed successfully, found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"❌ Error executing device info search: {e}")
            return []
    
    async def _execute_generated_sql(self, sql_query: str, case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute LLM-generated SQL query safely"""
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            from app.services.case_manager import case_manager
            
            db = next(get_db())
            results = []
            
            # Determine schema
            if case_number:
                case_info = case_manager.get_case_info(case_number)
                if case_info:
                    safe_case_name = case_info["safe_case_name"]
                    schema_name = f"case_{safe_case_name}"
                    
                    # Replace generic table names with schema-specific ones
                    sql_query = sql_query.replace("chat_records", f"{schema_name}.chat_records")
                    sql_query = sql_query.replace("call_records", f"{schema_name}.call_records")
                    sql_query = sql_query.replace("contacts", f"{schema_name}.contacts")
                    sql_query = sql_query.replace("media_files", f"{schema_name}.media_files")
                    
                    print(f"🔍 Executing generated SQL on schema: {schema_name}")
                else:
                    print("❌ Case not found for generated SQL")
                    return []
            else:
                print("❌ No case specified for generated SQL")
                return []
            
            # Strict SQL injection protection
            dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE']
            sql_upper = sql_query.upper()
            for keyword in dangerous_keywords:
                if keyword in sql_upper:
                    print(f"🚫 Dangerous SQL keyword detected: {keyword}")
                    return []
            
            # Execute the query
            query_result = db.execute(text(sql_query)).fetchall()
            
            # Convert results to dictionaries
            for row in query_result:
                if hasattr(row, '_mapping'):
                    # SQLAlchemy Row object
                    row_dict = dict(row._mapping)
                else:
                    # Fallback for other row types
                    row_dict = dict(row)
                
                # Convert UUIDs to strings and handle other types
                for key, value in row_dict.items():
                    if hasattr(value, 'hex'):  # UUID
                        row_dict[key] = str(value)
                    elif hasattr(value, 'isoformat'):  # datetime
                        row_dict[key] = value.isoformat()
                
                # Add type information based on table
                if 'chat_records' in sql_query.lower():
                    row_dict['type'] = 'chat_record'
                elif 'call_records' in sql_query.lower():
                    row_dict['type'] = 'call_record'
                elif 'contacts' in sql_query.lower():
                    row_dict['type'] = 'contact'
                elif 'media_files' in sql_query.lower():
                    row_dict['type'] = 'media_file'
                
                results.append(row_dict)
            
            db.close()
            print(f"✅ Generated SQL executed successfully, found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"❌ Error executing generated SQL: {e}")
            return []

# Global AI service instance
ai_service = AIService()