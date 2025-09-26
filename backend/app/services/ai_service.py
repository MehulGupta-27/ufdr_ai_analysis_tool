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
            if settings.embeddings_azure_endpoint and settings.embeddings_api_key:
                print(f"🔧 Setting up Azure OpenAI client with endpoint: {settings.embeddings_azure_endpoint}")
                self.openai_client = AzureOpenAI(
                    azure_endpoint=settings.embeddings_azure_endpoint,
                    api_key=settings.embeddings_api_key,
                    api_version=settings.api_version
                )
                print(f"✅ Azure OpenAI client setup successful")
            else:
                print(f"❌ Azure OpenAI configuration missing - Endpoint: {bool(settings.embeddings_azure_endpoint)}, API Key: {bool(settings.embeddings_api_key)}")
                self.openai_client = None
        except Exception as e:
            print(f"❌ Azure OpenAI setup failed: {e}")
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
            if not self.openai_client:
                print("⚠️ Azure OpenAI client not available, using dummy embeddings")
                # Return dummy embeddings with correct dimensions (3072 for text-embedding-3-large)
                return [self._generate_dummy_embedding(text, 3072) for text in texts]
            
            embeddings = []
            for text in texts:
                response = self.openai_client.embeddings.create(
                    model=settings.azure_embedding_model,
                    input=text
                )
                embeddings.append(response.data[0].embedding)
                
            print(f"✅ Generated {len(embeddings)} embeddings with {len(embeddings[0])} dimensions")
            return embeddings
            
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            # Return dummy embeddings with correct dimensions (3072 for text-embedding-3-large)
            return [self._generate_dummy_embedding(text, 3072) for text in texts]
    
    def _generate_dummy_embedding(self, text: str, dimensions: int = 3072) -> List[float]:
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
                # First try to generate SQL using LLM
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
        
        # Handle regular search results
        all_results = sql_results + vector_results
        if not all_results:
            return f"**No results found for: {query}**\n\nThe uploaded data doesn't contain information matching your query. Try different keywords or check what data is available."
        
        # Group results by type for better presentation
        chat_results = [r for r in all_results if r.get('type') == 'chat_record']
        call_results = [r for r in all_results if r.get('type') == 'call_record']
        contact_results = [r for r in all_results if r.get('type') == 'contact']
        media_results = [r for r in all_results if r.get('type') == 'media_file']
        
        answer = f"**Found {len(all_results)} results for: {query}**\n\n"
        
        # Show chat messages
        if chat_results:
            answer += f"**💬 Chat Messages ({len(chat_results)}):**\n"
            for i, result in enumerate(chat_results[:5], 1):
                app = result.get('app_name', 'Unknown')
                sender = result.get('sender', 'Unknown')
                content = result.get('content', 'N/A')
                timestamp = result.get('timestamp', 'Unknown')
                
                # Truncate long messages
                if len(content) > 100:
                    content = content[:100] + "..."
                
                answer += f"{i}. **{app}** ({timestamp})\n"
                answer += f"   From: {sender}\n"
                answer += f"   Message: {content}\n\n"
            
            if len(chat_results) > 5:
                answer += f"   ... and {len(chat_results) - 5} more messages\n\n"
        
        # Show call records
        if call_results:
            answer += f"**📞 Call Records ({len(call_results)}):**\n"
            for i, result in enumerate(call_results[:5], 1):
                caller = result.get('caller', 'Unknown')
                receiver = result.get('receiver', 'Unknown')
                call_type = result.get('call_type', 'Unknown')
                duration = result.get('duration', 0)
                timestamp = result.get('timestamp', 'Unknown')
                
                answer += f"{i}. **{call_type.title()} Call** ({timestamp})\n"
                answer += f"   {caller} → {receiver} ({duration}s)\n\n"
            
            if len(call_results) > 5:
                answer += f"   ... and {len(call_results) - 5} more calls\n\n"
        
        # Show contacts
        if contact_results:
            answer += f"**👥 Contacts ({len(contact_results)}):**\n"
            for i, result in enumerate(contact_results[:5], 1):
                name = result.get('name', 'Unknown')
                phones = result.get('phone_numbers', [])
                emails = result.get('email_addresses', [])
                
                answer += f"{i}. **{name}**\n"
                if phones:
                    answer += f"   Phone: {', '.join(phones[:2])}\n"
                if emails:
                    answer += f"   Email: {', '.join(emails[:2])}\n"
                answer += "\n"
            
            if len(contact_results) > 5:
                answer += f"   ... and {len(contact_results) - 5} more contacts\n\n"
        
        # Show media files
        if media_results:
            answer += f"**📁 Media Files ({len(media_results)}):**\n"
            for i, result in enumerate(media_results[:5], 1):
                filename = result.get('filename', 'Unknown')
                file_type = result.get('file_type', 'unknown')
                file_size = result.get('file_size', 0)
                created = result.get('created_date', 'Unknown')
                
                # Format file size
                if file_size:
                    if file_size > 1024*1024:
                        size_str = f"{file_size/(1024*1024):.1f}MB"
                    elif file_size > 1024:
                        size_str = f"{file_size/1024:.1f}KB"
                    else:
                        size_str = f"{file_size}B"
                else:
                    size_str = "Unknown size"
                
                answer += f"{i}. **{filename}** ({file_type})\n"
                answer += f"   Size: {size_str}, Created: {created}\n\n"
            
            if len(media_results) > 5:
                answer += f"   ... and {len(media_results) - 5} more files\n\n"
        
        # Add helpful suggestions
        if len(all_results) > 10:
            answer += "💡 **Tip**: Use more specific keywords to narrow down results."
        
        return answer
        
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
            
            # Handle SEARCH queries
            elif intent in ["search", "analyze"]:
                query_lower = query.lower()
                
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