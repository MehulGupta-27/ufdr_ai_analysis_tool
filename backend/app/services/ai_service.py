"""
AI Service for UFDR AI Analyzer - LLM-Driven Approach
Handles natural language query processing and SQL generation using LLM with full context
"""

import logging
import json
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from app.services.schema_service import schema_service

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self._setup_clients()
    
    def _setup_clients(self):
        """Initialize AI clients"""
        try:
            # Setup Gemini with proper API key from settings
            from config.settings import settings
            
            if settings.gemini_api_key and settings.gemini_api_key != "":
                genai.configure(api_key=settings.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('models/gemini-2.5-pro')
                print("✅ Gemini AI client initialized")
            else:
                print("⚠️ Gemini API key not configured - AI features will be limited")
                self.gemini_model = None
        except Exception as e:
            print(f"⚠️ Failed to initialize Gemini: {e}")
            self.gemini_model = None
    
    async def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user query to determine search strategy using AI"""
        try:
            if not self.gemini_model:
                return await self._enhanced_fallback_analysis(query)
            
            prompt = f"""
            You are a forensic data analysis expert. Analyze this query and determine the best search approach.

            QUERY: "{query}"

            CLASSIFICATION RULES:
            
            **SQL-ONLY QUERIES** (Simple, direct data retrieval):
            - "How many [records] are there?" → Count queries
            - "Show me all [specific table] of [app]" → Direct table queries
            - "Show all [data_type]" → Simple listing queries
            - "List all [specific items]" → Direct enumeration
            - "Find [specific field] = [value]" → Exact match queries
            - "Show [data_type] from [app]" → App-specific queries
            - "Display all [foreign/international] contacts" → Filtered queries
            
            **SEMANTIC-ONLY QUERIES** (Complex, contextual analysis):
            - "Show suspicious conversations" → Contextual analysis needed
            - "Find criminal activities" → Pattern recognition required
            - "Show relationships between people" → Network analysis
            - "Find evidence of [complex behavior]" → Behavioral analysis
            - "Analyze communication patterns" → Pattern analysis
            - "Show people he is related with" → Relationship mapping
            - "Find conversations about [complex topic]" → Semantic understanding
            
            **HYBRID QUERIES** (Need both approaches):
            - "Find WhatsApp messages about meetings" → SQL for WhatsApp + semantic for meetings
            - "Show suspicious calls from yesterday" → SQL for calls + semantic for suspicious
            
            DECISION PROCESS:
            1. Can this be answered with a simple SQL query? → SQL_ONLY
            2. Does this require understanding context/meaning? → SEMANTIC_ONLY  
            3. Does this need both direct data + context? → HYBRID
            
            Return JSON format:
            {{
                "search_approach": "sql_only|semantic_only|hybrid",
                "reasoning": "Brief explanation of why this approach was chosen",
                "target_data": ["chat_records", "call_records", "contacts", "media_files", "device_info"],
                "query_type": "count|list|search|analyze|relationship",
                "complexity": "simple|moderate|complex",
                "confidence": 0.9
            }}
            """
            
            response = self.gemini_model.generate_content(prompt)
            if response and response.text:
                try:
                    analysis = json.loads(response.text.strip())
                    print(f"🧠 AI Query Analysis: {analysis}")
                    return analysis
                except json.JSONDecodeError:
                    print("⚠️ Failed to parse AI response, using fallback")
                    return await self._enhanced_fallback_analysis(query)
            else:
                return await self._enhanced_fallback_analysis(query)
                
        except Exception as e:
            print(f"❌ Error in AI query analysis: {e}")
            return await self._enhanced_fallback_analysis(query)
    
    async def _enhanced_fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Enhanced fallback analysis with better intent detection"""
        query_lower = query.lower()
        
        # Simple pattern-based classification
        if any(word in query_lower for word in ["how many", "count", "total", "number of", "evidence", "evidences"]):
            return {
                "search_approach": "sql_only",
                "reasoning": "Count query - can be answered with SQL",
                "target_data": ["chat_records", "call_records", "contacts", "media_files"],
                "query_type": "count",
                "complexity": "simple",
                "confidence": 0.8
            }
        elif any(word in query_lower for word in ["show all", "list all", "display all", "all chats", "all messages", "all contacts", "all calls", "all media", "all files"]):
            return {
                "search_approach": "sql_only",
                "reasoning": "Simple listing query - can be answered with SQL",
                "target_data": ["chat_records", "call_records", "contacts", "media_files"],
                "query_type": "list",
                "complexity": "simple",
                "confidence": 0.8
            }
        elif any(word in query_lower for word in ["suspicious", "criminal", "illegal", "related with", "relationships", "patterns", "analyze"]):
            return {
                "search_approach": "semantic_only",
                "reasoning": "Complex contextual query - requires semantic understanding",
                "target_data": ["chat_records", "call_records", "contacts"],
                "query_type": "analyze",
                "complexity": "complex",
                "confidence": 0.8
            }
        else:
            return {
                "search_approach": "hybrid",
                "reasoning": "Mixed query - may need both SQL and semantic search",
                "target_data": ["chat_records", "call_records", "contacts", "media_files"],
                "query_type": "search",
                "complexity": "moderate",
                "confidence": 0.6
            }
    
    async def _get_dynamic_schema_info(self, case_number: Optional[str] = None) -> str:
        """Get actual database schema and data statistics using the new schema service"""
        try:
            if not case_number:
                return "Schema information not available - no case specified"
            
            # Check if schema is already cached
            if schema_service.is_schema_cached(case_number):
                print(f"📋 Using cached schema for case {case_number}")
                schema_summary = schema_service.generate_schema_summary(case_number)
                return schema_summary
            else:
                # Extract schema if not cached
                print(f"🔄 Extracting schema for case {case_number}")
                schema_details = await schema_service.extract_case_schema(case_number)
                if schema_details:
                    schema_summary = schema_service.generate_schema_summary(case_number)
                    return schema_summary
                else:
                    return f"Schema extraction failed for case {case_number}"
                    
        except Exception as e:
            print(f"❌ Error getting schema info: {e}")
            return f"Error retrieving schema information: {e}"
    
    async def _generate_contextual_sql(self, query: str, schema_info: str, case_number: Optional[str] = None) -> str:
        """Generate SQL using LLM with full data context - no hardcoding"""
        
        # Get case-specific schema name
        schema_name = ""
        if case_number:
            from app.services.case_manager import case_manager
            case_info = case_manager.get_case_info(case_number)
            if case_info:
                safe_case_name = case_info["safe_case_name"]
                schema_name = f"case_{safe_case_name}"
        
        # Create comprehensive prompt with full context
        contextual_prompt = f"""
        You are an expert forensic data analyst. Generate a PostgreSQL query based on the user's natural language request.

        DATABASE SCHEMA AND DATA CONTEXT:
        {schema_info}

        USER QUERY: "{query}"

        INSTRUCTIONS:
        1. Analyze the user's query to understand what they want to find
        2. Use the actual table names, column names, and data types from the schema above
        3. Generate a PostgreSQL SELECT query that will return the requested data
        4. Use schema-qualified table names: {schema_name}.table_name
        5. Use appropriate WHERE clauses based on the user's intent
        6. Use ILIKE for case-insensitive text search when needed
        7. Use LIMIT 50 for performance
        8. Order results by relevance (timestamp DESC for time-based data)

        EXAMPLES OF QUERY PATTERNS:
        - "show all messages" → SELECT * FROM {schema_name}.chat_records ORDER BY timestamp DESC LIMIT 50
        - "show all whatsapp messages" → SELECT * FROM {schema_name}.chat_records WHERE LOWER(app_name) = 'whatsapp' ORDER BY timestamp DESC LIMIT 50
        - "find messages about money" → SELECT * FROM {schema_name}.chat_records WHERE LOWER(message_content) ILIKE '%money%' ORDER BY timestamp DESC LIMIT 50
        - "show all contacts" → SELECT * FROM {schema_name}.contacts ORDER BY name LIMIT 50
        - "find calls to +1234567890" → SELECT * FROM {schema_name}.call_records WHERE caller_number LIKE '%1234567890%' OR receiver_number LIKE '%1234567890%' ORDER BY timestamp DESC LIMIT 50

        CRITICAL RULES:
        - Return ONLY a SELECT statement
        - Use actual column names from the schema
        - Use schema-qualified table names
        - Handle app-specific queries by filtering on app_name column
        - Handle content searches using ILIKE on message_content
        - Handle phone number searches on caller_number/receiver_number columns
        - For "show all" queries, don't use WHERE clauses unless filtering by app or specific criteria

        Generate the most appropriate SQL query for: "{query}"
        """
        
        try:
            if not self.gemini_model:
                print("⚠️ Gemini model not available for contextual SQL generation")
                return ""
                
            response = self.gemini_model.generate_content(contextual_prompt)
            if not response or not response.text:
                print("⚠️ Empty response from Gemini for contextual SQL generation")
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
                print("⚠️ Generated contextual SQL query too short or empty")
                return ""
            
            # Ensure it's a SELECT query
            if not sql_query.upper().startswith('SELECT'):
                print("⚠️ Generated contextual query is not a SELECT statement")
                return ""
            
            print(f"✅ Generated contextual SQL query: {sql_query[:100]}...")
            return sql_query
            
        except Exception as e:
            print(f"❌ Error generating contextual SQL query: {e}")
            return ""

    async def execute_hybrid_search(self, query: str, case_number: Optional[str] = None) -> Dict[str, Any]:
        """Execute intelligent search with dynamic routing based on query complexity"""
        
        print(f"🔍 Starting dynamic search for: {query} (Case: {case_number})")
        
        try:
            # Store case number for use in response generation
            self._current_case_number = case_number
            
            # Step 1: Analyze query to determine search approach
            analysis = await self.analyze_query_intent(query)
            search_approach = analysis.get("search_approach", "hybrid")
            reasoning = analysis.get("reasoning", "No reasoning provided")
            
            print(f"🧠 Query Analysis: {search_approach} - {reasoning}")
            
            raw_data = {
                "query": query,
                "case_number": case_number,
                "sql_results": [],
                "vector_results": []
            }
            
            # Step 2: Execute search based on analysis
            if search_approach == "sql_only":
                print(f"📊 Using SQL-only approach for simple query")
                raw_data["sql_results"] = await self._execute_sql_only_search(query, case_number)
                
            elif search_approach == "semantic_only":
                print(f"🔍 Using semantic-only approach for complex query")
                raw_data["vector_results"] = await self._execute_semantic_only_search(query, case_number)
                
            elif search_approach == "hybrid":
                print(f"🔄 Using hybrid approach for mixed query")
                raw_data["sql_results"] = await self._execute_sql_only_search(query, case_number)
                raw_data["vector_results"] = await self._execute_semantic_only_search(query, case_number)
            
            # Step 3: Generate human-readable response using LLM with all fetched data
            if raw_data["sql_results"] or raw_data["vector_results"]:
                if self.gemini_model:
                    print(f"🤖 Processing all results through LLM for intelligent response...")
                    human_response = await self._generate_intelligent_response(query, raw_data, analysis)
                else:
                    print(f"⚠️ LLM not available, using fallback response")
                    human_response = self._generate_fallback_response(query, raw_data, analysis)
                
                return {
                    "query": query,
                    "case_number": case_number,
                    "answer": human_response,
                    "success": True,
                    "search_approach": search_approach,
                    "reasoning": reasoning,
                    "data_sources": {
                        "sql_results_count": len(raw_data["sql_results"]),
                        "vector_results_count": len(raw_data["vector_results"])
                    }
                }
            else:
                return {
                    "query": query,
                    "case_number": case_number,
                    "answer": "No results found for your query. Try rephrasing or check if the data exists.",
                    "success": False,
                    "search_approach": search_approach,
                    "reasoning": reasoning,
                    "data_sources": {"sql_results_count": 0, "vector_results_count": 0}
                }
            
        except Exception as e:
            print(f"❌ Error in dynamic search: {e}")
            import traceback
            traceback.print_exc()
            return {
                "query": query,
                "case_number": case_number,
                "answer": f"Error processing your query: {str(e)}",
                "success": False,
                "data_sources": {"sql_results_count": 0, "vector_results_count": 0}
            }

    async def _execute_sql_only_search(self, query: str, case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute SQL-only search for simple queries"""
        if not case_number:
            print("❌ No case number provided for SQL search")
            return []
        
        try:
            # Get schema info and generate SQL
            schema_info = await self._get_dynamic_schema_info(case_number)
            generated_sql = await self._generate_contextual_sql(query, schema_info, case_number)
            
            if generated_sql:
                print(f"🤖 SQL-only search: {generated_sql}")
                results = await self._execute_generated_sql(generated_sql, case_number)
                print(f"📊 SQL search found {len(results)} results")
                return results
            else:
                print("⚠️ Failed to generate SQL for simple query")
                return []
                
        except Exception as e:
            print(f"❌ Error in SQL-only search: {e}")
            return []

    async def _execute_semantic_only_search(self, query: str, case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute semantic-only search for complex queries"""
        if not case_number:
            print("❌ No case number provided for semantic search")
            return []
        
        try:
            from app.services.vector_service import vector_service
            from app.services.case_manager import case_manager
            
            if not vector_service.qdrant_client:
                print("⚠️ Vector service not available for semantic search")
                return []
            
            # Get case-specific collection
            case_info = case_manager.get_case_info(case_number)
            if not case_info:
                print(f"❌ Case {case_number} not found")
                return []
            
            safe_case_name = case_info["safe_case_name"]
            collection_name = f"case_{safe_case_name}"
            
            print(f"🔍 Semantic search in collection: {collection_name}")
            results = await vector_service.search_case_data(
                query=query,
                collection_name=collection_name,
                limit=20
            )
            
            print(f"📊 Semantic search found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"❌ Error in semantic-only search: {e}")
            return []

    async def _execute_sql_search(self, query: str, analysis: Dict[str, Any], case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute SQL search using LLM-generated queries - DEPRECATED, use _execute_sql_only_search"""
        return await self._execute_sql_only_search(query, case_number)
    
    async def _execute_generated_sql(self, sql_query: str, case_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute LLM-generated SQL query safely"""
        try:
            from app.models.database import get_db
            from sqlalchemy import text
            
            if not sql_query or not sql_query.strip():
                print("⚠️ Empty SQL query provided")
                return []
            
            # Strict SQL injection protection - check for dangerous keywords at statement level
            dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE']
            sql_upper = sql_query.upper().strip()
            
            # Check if query starts with dangerous keywords (not just contains them)
            for keyword in dangerous_keywords:
                if sql_upper.startswith(keyword):
                    print(f"🚫 Dangerous SQL keyword detected at start: {keyword}")
                    return []
            
            # Additional check: look for dangerous keywords as complete statements
            # Split by semicolons and check each statement
            statements = [stmt.strip() for stmt in sql_query.split(';') if stmt.strip()]
            for statement in statements:
                statement_upper = statement.upper().strip()
                for keyword in dangerous_keywords:
                    if statement_upper.startswith(keyword):
                        print(f"🚫 Dangerous SQL keyword detected in statement: {keyword}")
                        print(f"🔍 Problematic statement: {statement}")
                        return []
            
            print(f"🔍 SQL validation passed, executing query...")
            
            db = next(get_db())
            results = []
            
            try:
                # Execute the query
                query_result = db.execute(text(sql_query))
                
                # Convert results to list of dictionaries
                for row in query_result:
                    row_dict = {}
                    for key, value in row._mapping.items():
                        # Convert non-serializable types
                        if hasattr(value, 'isoformat'):  # datetime objects
                            row_dict[key] = value.isoformat()
                        else:
                            row_dict[key] = str(value) if value is not None else None
                    results.append(row_dict)
                
                print(f"✅ SQL query executed successfully, returned {len(results)} rows")
                
            except Exception as e:
                print(f"❌ Error executing SQL query: {e}")
                print(f"🔍 Problematic query: {sql_query}")
                return []
            finally:
                db.close()
            
            return results
            
        except Exception as e:
            print(f"❌ Error in SQL execution: {e}")
            return []

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using the vector service"""
        try:
            from app.services.vector_service import vector_service
            
            if not vector_service.embedder:
                print("⚠️ Vector service embedder not available")
                return []
            
            # Use the vector service's embedder
            embeddings = []
            for text in texts:
                if text and text.strip():
                    # Generate embedding for the text
                    embedding = list(vector_service.embedder.embed([text]))[0]
                    embeddings.append(embedding)
                else:
                    # Add zero vector for empty texts
                    embeddings.append([0.0] * vector_service._embedding_dimension)
            
            print(f"✅ Generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            return []

    def _generate_basic_report(self, results: Dict[str, Any]) -> str:
        """Generate a basic report from search results"""
        try:
            sql_count = len(results.get('sql_results', []))
            vector_count = len(results.get('vector_results', []))
            
            if sql_count > 0 or vector_count > 0:
                return f"Found {sql_count} SQL results and {vector_count} vector results for your query."
            else:
                return "No results found for your query. Try rephrasing or checking if the data exists."
                
        except Exception as e:
            print(f"❌ Error generating basic report: {e}")
            return "Error generating report."

    async def _generate_intelligent_response(self, query: str, raw_data: Dict[str, Any], analysis: Dict[str, Any] = None) -> str:
        """Generate intelligent response using LLM with all fetched data"""
        try:
            if not self.gemini_model:
                return self._generate_fallback_response(query, raw_data, analysis)
            
            # Get comprehensive data summary including counts
            data_summary = await self._prepare_comprehensive_data_summary(raw_data)
            search_approach = analysis.get("search_approach", "unknown") if analysis else "unknown"
            query_type = analysis.get("query_type", "search") if analysis else "search"
            
            prompt = f"""
            You are an expert forensic data analyst. Analyze the user's query and the provided data to generate a comprehensive, accurate, and human-readable response.

            USER QUERY: "{query}"
            SEARCH APPROACH USED: {search_approach}
            QUERY TYPE: {query_type}

            AVAILABLE DATA:
            {data_summary}

            INSTRUCTIONS:
            1. Analyze the user's intent and provide the most appropriate response format
            2. For COUNT queries: Provide detailed breakdowns by category (e.g., "Total X evidences found\nChat records: Y\nCall records: Z\nMedia Files: A\nContacts: B")
            3. For LIST queries: Show items in a clean, organized format with ALL relevant details including:
               - For chat records: Show sender, recipient, app, timestamp, AND the full message content
               - For call records: Show caller, recipient, duration, timestamp, call type
               - For media files: Show filename, size, type, timestamp, path
               - For contacts: Show name, phone, email, timestamp
            4. For SEARCH queries: Show specific items found with context and relevance
            5. For ANALYSIS queries: Provide insights, patterns, and findings
            6. For RELATIONSHIP queries: Explain connections and relationships
            7. Use clear, professional language appropriate for forensic analysis
            8. Focus on the most relevant information for the user's query
            9. ALWAYS include full message content for chat records - this is crucial for investigators
            10. Include all available details for each record type
            11. If showing lists, limit to the most important items (max 10-15) but include full details
            12. Don't show raw database fields or technical details unless specifically requested
            13. If no relevant data found, say so clearly and suggest alternatives

            RESPONSE FORMATTING GUIDELINES:
            - For evidence counts: Use structured format with total and breakdown
            - For lists: Use bullet points or numbered lists with complete information
            - For chat records: Always include the full message content
            - For analysis: Use clear paragraphs with insights
            - For relationships: Use clear explanations of connections
            - Always be comprehensive and include all relevant details
            - Format each record as a clear, readable block with all available information

            CRITICAL FORMATTING REQUIREMENTS:
            - When showing chat records, format each record as: "1. App: [app_name] | From: [sender] | To: [receiver] | Time: [timestamp] | Message: [full_message]"
            - When showing call records, format as: "1. From: [caller] | To: [receiver] | Duration: [duration] | Type: [call_type] | Time: [timestamp]"
            - When showing media files, format as: "1. File: [filename] | Size: [size] | Type: [type] | Path: [path] | Time: [timestamp]"
            - When showing contacts, format as: "1. Name: [name] | Phone: [phone] | Email: [email] | Time: [timestamp]"
            - Use consistent formatting with pipe separators (|) for easy parsing
            - Always include the full message content for chat records
            - Use numbered lists (1., 2., 3., etc.) for multiple records
            - Include all available fields for each record type
            - Use the exact field names shown in the data (app_name, sender_number, receiver_number, etc.)

            Generate a response that directly answers the user's question using the available data:
            """
            
            response = self.gemini_model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
            else:
                return self._generate_fallback_response(query, raw_data, analysis)
                
        except Exception as e:
            print(f"❌ Error generating intelligent response: {e}")
            return self._generate_fallback_response(query, raw_data, analysis)

    
    async def _get_evidence_counts(self, case_number: str = None) -> Dict[str, int]:
        """Get dynamic evidence counts from database"""
        try:
            from app.services.case_manager import case_manager
            from app.models.database import get_db
            from sqlalchemy import text
            
            if not case_number:
                # Try to get the most recent active case
                active_cases = case_manager.list_active_cases()
                if not active_cases:
                    return {"chat_records": 0, "call_records": 0, "contacts": 0, "media_files": 0}
                case_number = active_cases[-1]
            
            case_info = case_manager.get_case_info(case_number)
            if not case_info:
                return {"chat_records": 0, "call_records": 0, "contacts": 0, "media_files": 0}
            
            safe_case_name = case_info["safe_case_name"]
            schema_name = f"case_{safe_case_name}"
            
            db = next(get_db())
            counts = {
                "chat_records": 0,
                "call_records": 0,
                "contacts": 0,
                "media_files": 0
            }
            
            try:
                # Get counts from each table
                counts["chat_records"] = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.chat_records")).scalar() or 0
                counts["call_records"] = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.call_records")).scalar() or 0
                counts["contacts"] = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.contacts")).scalar() or 0
                counts["media_files"] = db.execute(text(f"SELECT COUNT(*) FROM {schema_name}.media_files")).scalar() or 0
            except Exception as e:
                print(f"⚠️ Error getting counts from database: {e}")
            finally:
                db.close()
            
            return counts
            
        except Exception as e:
            print(f"❌ Error getting evidence counts: {e}")
            return {"chat_records": 0, "call_records": 0, "contacts": 0, "media_files": 0}

    async def _prepare_comprehensive_data_summary(self, raw_data: Dict[str, Any]) -> str:
        """Prepare comprehensive data summary including counts and detailed information for LLM processing"""
        try:
            summary_parts = []
            
            # Get dynamic counts for the case
            case_number = getattr(self, '_current_case_number', None)
            counts = await self._get_evidence_counts(case_number)
            
            # Add evidence counts summary
            if counts and any(count > 0 for count in counts.values()):
                total_evidence = sum(counts.values())
                summary_parts.append(f"EVIDENCE SUMMARY:")
                summary_parts.append(f"Total evidences: {total_evidence}")
                summary_parts.append(f"Chat records: {counts.get('chat_records', 0)}")
                summary_parts.append(f"Call records: {counts.get('call_records', 0)}")
                summary_parts.append(f"Media files: {counts.get('media_files', 0)}")
                summary_parts.append(f"Contacts: {counts.get('contacts', 0)}")
                summary_parts.append("")
            
            # Process SQL results with detailed information
            sql_results = raw_data.get('sql_results', [])
            if sql_results:
                summary_parts.append(f"SQL SEARCH RESULTS ({len(sql_results)} records):")
                
                # Group results by table type for better organization
                results_by_type = {}
                for result in sql_results:
                    if isinstance(result, dict):
                        # Determine result type based on available fields
                        if 'message_content' in result or 'content' in result:
                            result_type = 'chat_records'
                        elif 'caller_number' in result or 'call_duration' in result:
                            result_type = 'call_records'
                        elif 'file_name' in result or 'file_path' in result:
                            result_type = 'media_files'
                        elif 'contact_name' in result or 'phone_number' in result:
                            result_type = 'contacts'
                        else:
                            result_type = 'other'
                        
                        if result_type not in results_by_type:
                            results_by_type[result_type] = []
                        results_by_type[result_type].append(result)
                
                # Add detailed information for each type with proper formatting
                for result_type, results in results_by_type.items():
                    summary_parts.append(f"\n{result_type.upper().replace('_', ' ')} ({len(results)} items):")
                    for i, result in enumerate(results[:10], 1):  # Increased limit to 10 per type
                        # Format based on record type
                        if result_type == 'chat_records':
                            app_name = result.get('app_name', 'Unknown')
                            sender = result.get('sender_number', 'Unknown')
                            receiver = result.get('receiver_number', 'Unknown')
                            message = result.get('message_content', result.get('content', ''))
                            timestamp = result.get('timestamp', result.get('date', ''))
                            
                            summary_parts.append(f"  {i}. App: {app_name} | From: {sender} | To: {receiver} | Time: {timestamp} | Message: {message}")
                            
                        elif result_type == 'call_records':
                            caller = result.get('caller_number', 'Unknown')
                            receiver = result.get('receiver_number', 'Unknown')
                            duration = result.get('call_duration', result.get('duration', 'Unknown'))
                            call_type = result.get('call_type', 'Unknown')
                            timestamp = result.get('timestamp', result.get('date', ''))
                            
                            summary_parts.append(f"  {i}. From: {caller} | To: {receiver} | Duration: {duration} | Type: {call_type} | Time: {timestamp}")
                            
                        elif result_type == 'media_files':
                            file_name = result.get('file_name', result.get('filename', 'Unknown'))
                            file_size = result.get('file_size', 'Unknown')
                            file_type = result.get('file_type', result.get('mime_type', 'Unknown'))
                            file_path = result.get('file_path', 'Unknown')
                            timestamp = result.get('timestamp', result.get('date', ''))
                            
                            summary_parts.append(f"  {i}. File: {file_name} | Size: {file_size} | Type: {file_type} | Path: {file_path} | Time: {timestamp}")
                            
                        elif result_type == 'contacts':
                            name = result.get('contact_name', result.get('name', 'Unknown'))
                            phone = result.get('phone_number', 'Unknown')
                            email = result.get('contact_email', result.get('email', 'Unknown'))
                            timestamp = result.get('timestamp', result.get('date', ''))
                            
                            summary_parts.append(f"  {i}. Name: {name} | Phone: {phone} | Email: {email} | Time: {timestamp}")
                            
                        else:
                            # Generic formatting for other types
                            record_info = []
                            for key, value in result.items():
                                if value is not None and str(value).strip():
                                    record_info.append(f"{key}: {value}")
                            
                            if record_info:
                                summary_parts.append(f"  {i}. {' | '.join(record_info[:5])}")  # Limit to 5 fields
                    
                    if len(results) > 10:
                        summary_parts.append(f"  ... and {len(results) - 10} more {result_type}")
            
            # Process vector results
            vector_results = raw_data.get('vector_results', [])
            if vector_results:
                summary_parts.append(f"\nSEMANTIC SEARCH RESULTS ({len(vector_results)} items):")
                for i, result in enumerate(vector_results[:5], 1):  # Limit to 5 for summary
                    if isinstance(result, dict):
                        content = result.get('payload', {}).get('content', result.get('content', str(result)))
                        if content:
                            summary_parts.append(f"  {i}. {str(content)[:200]}...")
                
                if len(vector_results) > 5:
                    summary_parts.append(f"  ... and {len(vector_results) - 5} more semantic results")
            
            return "\n".join(summary_parts) if summary_parts else "No data found"
            
        except Exception as e:
            print(f"❌ Error preparing comprehensive data summary: {e}")
            return "Error processing data"

    def _prepare_data_summary(self, raw_data: Dict[str, Any]) -> str:
        """Prepare a clean summary of raw data for LLM processing"""
        try:
            summary_parts = []
            
            # Process SQL results
            sql_results = raw_data.get('sql_results', [])
            if sql_results:
                summary_parts.append(f"Database Records Found: {len(sql_results)}")
                for i, result in enumerate(sql_results[:5], 1):  # Limit to 5 for summary
                    if isinstance(result, dict):
                        # Extract key information based on common fields
                        record_info = []
                        for key, value in result.items():
                            if value is not None and str(value).strip():
                                if key in ['message_content', 'content', 'text']:
                                    record_info.append(f"Message: {str(value)[:100]}")
                                elif key in ['sender_number', 'caller_number', 'phone_number']:
                                    record_info.append(f"From: {value}")
                                elif key in ['receiver_number', 'receiver']:
                                    record_info.append(f"To: {value}")
                                elif key in ['timestamp', 'date', 'time']:
                                    record_info.append(f"Time: {value}")
                                elif key in ['app_name', 'application']:
                                    record_info.append(f"App: {value}")
                                elif key in ['name', 'contact_name']:
                                    record_info.append(f"Name: {value}")
                                elif key in ['file_name', 'filename']:
                                    record_info.append(f"File: {value}")
                        
                        if record_info:
                            summary_parts.append(f"{i}. {' | '.join(record_info[:3])}")
                
                if len(sql_results) > 5:
                    summary_parts.append(f"... and {len(sql_results) - 5} more records")
            
            # Process vector results
            vector_results = raw_data.get('vector_results', [])
            if vector_results:
                summary_parts.append(f"\nSemantic Search Results: {len(vector_results)}")
                for i, result in enumerate(vector_results[:3], 1):  # Limit to 3 for summary
                    if isinstance(result, dict):
                        content = result.get('payload', {}).get('content', result.get('content', str(result)))
                        if content:
                            summary_parts.append(f"{i}. {str(content)[:150]}")
            
            return "\n".join(summary_parts) if summary_parts else "No data found"
            
        except Exception as e:
            print(f"❌ Error preparing data summary: {e}")
            return "Error processing data"

    def _generate_fallback_response(self, query: str, raw_data: Dict[str, Any], analysis: Dict[str, Any] = None) -> str:
        """Generate fallback response when LLM is not available"""
        try:
            sql_count = len(raw_data.get('sql_results', []))
            vector_count = len(raw_data.get('vector_results', []))
            query_type = analysis.get("query_type", "search") if analysis else "search"
            
            if sql_count > 0 or vector_count > 0:
                if query_type == "count":
                    return f"Found {sql_count + vector_count} records in the database."
                elif query_type == "list":
                    return f"Found {sql_count + vector_count} items matching your request."
                elif query_type == "analyze":
                    return f"Analysis found {sql_count + vector_count} relevant items for investigation."
                else:
                    return f"Found {sql_count + vector_count} relevant records for your query."
            else:
                return "No results found for your query. Try rephrasing or check if the data exists."
                
        except Exception as e:
            print(f"❌ Error generating fallback response: {e}")
            return "Error processing your query."

    def render_itemized_answer(self, query: str, results: Dict[str, Any]) -> str:
        """Render itemized answer for show/list style queries - DEPRECATED"""
        # This method is now handled by _generate_human_readable_response
        return self._generate_fallback_response(query, results)

# Create global instance
ai_service = AIService()
