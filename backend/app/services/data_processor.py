from typing import Dict, List, Any, Optional
import uuid
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from qdrant_client.models import PointStruct
import asyncio

from app.models.database import (
    UFDRReport, ChatRecord, CallRecord, Contact, MediaFile, get_db
)
from app.services.ufdr_parser import UFDRParser
from app.services.ai_service import ai_service
from app.core.database_manager import db_manager
from app.repositories.neo4j_repository import neo4j_repo
from app.services.vector_service import vector_service
from app.services.case_manager import case_manager

class DataProcessor:
    def __init__(self):
        self.parser = UFDRParser()
    
    async def process_ufdr_file(self, file_path: str, case_number: str, 
                               investigator: str) -> Dict[str, Any]:
        """Main method to process UFDR file and store in case-specific databases"""
        
        try:
            print(f"🏗️ Setting up case environment for: {case_number}")
            
            # Create case-specific environment
            case_env = await case_manager.create_case_environment(case_number, investigator)
            safe_case_name = case_env["safe_case_name"]
            
            # Parse UFDR file
            parsed_data = self.parser.parse_ufdr_file(file_path)
            
            # Store in case-specific PostgreSQL schema
            print(f"🔄 Storing data in PostgreSQL...")
            ufdr_report_id = await self._store_in_case_postgres(
                parsed_data, file_path, case_number, investigator, safe_case_name
            )
            print(f"✅ PostgreSQL storage completed with report ID: {ufdr_report_id}")
            
            # Store in case-specific Qdrant collection
            print(f"🔄 Starting Qdrant vector storage...")
            await self._store_in_case_qdrant(parsed_data, ufdr_report_id, safe_case_name)
            print(f"✅ Qdrant vector storage completed")
            
            # Store in case-specific Neo4j namespace
            print(f"🔄 Starting Neo4j graph storage...")
            await self._store_in_case_neo4j(parsed_data, safe_case_name)
            print(f"✅ Neo4j graph storage completed")
            
            return {
                "success": True,
                "case_number": case_number,
                "safe_case_name": safe_case_name,
                "ufdr_report_id": str(ufdr_report_id),
                "case_environment": case_env,
                "records_processed": {
                    "chat_records": len(parsed_data.get("chat_records", [])),
                    "call_records": len(parsed_data.get("call_records", [])),
                    "contacts": len(parsed_data.get("contacts", [])),
                    "media_files": len(parsed_data.get("media_files", []))
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_in_case_postgres(self, parsed_data: Dict[str, Any], 
                                      file_path: str, case_number: str, 
                                      investigator: str, safe_case_name: str) -> uuid.UUID:
        """Store parsed data in case-specific PostgreSQL schema"""
        
        db = next(get_db())
        schema_name = f"case_{safe_case_name}"
        
        try:
            # Generate UUID for the report
            report_id = uuid.uuid4()
            print(f"📝 Inserting UFDR report with ID: {report_id}")
            
            # Insert UFDR report record
            ufdr_report_sql = text(f"""
                INSERT INTO {schema_name}.ufdr_reports 
                (id, filename, device_info, extraction_date, case_number, investigator, processed)
                VALUES (:id, :filename, :device_info, :extraction_date, :case_number, :investigator, :processed)
            """)
            
            db.execute(ufdr_report_sql, {
                "id": report_id,
                "filename": file_path.split('/')[-1],
                "device_info": json.dumps(parsed_data.get("device_info", {})),
                "extraction_date": parsed_data.get("metadata", {}).get("extraction_date"),
                "case_number": case_number,
                "investigator": investigator,
                "processed": True
            })
            print(f"✅ UFDR report inserted successfully")
            
            # Store chat records
            for chat_data in parsed_data.get("chat_records", []):
                chat_sql = text(f"""
                    INSERT INTO {schema_name}.chat_records 
                    (ufdr_report_id, app_name, sender_number, receiver_number, message_content, 
                     timestamp, message_type, is_deleted, metadata)
                    VALUES (:ufdr_report_id, :app_name, :sender_number, :receiver_number, :message_content,
                            :timestamp, :message_type, :is_deleted, :metadata)
                """)
                
                db.execute(chat_sql, {
                    "ufdr_report_id": report_id,
                    "app_name": chat_data.get("app_name"),
                    "sender_number": chat_data.get("sender_number"),
                    "receiver_number": chat_data.get("receiver_number"),
                    "message_content": chat_data.get("message_content"),
                    "timestamp": chat_data.get("timestamp"),
                    "message_type": chat_data.get("message_type", "text"),
                    "is_deleted": chat_data.get("is_deleted", False),
                    "metadata": json.dumps(chat_data.get("metadata", {}))
                })
            
            # Store call records
            for call_data in parsed_data.get("call_records", []):
                call_sql = text(f"""
                    INSERT INTO {schema_name}.call_records 
                    (ufdr_report_id, caller_number, receiver_number, call_type, duration, timestamp, metadata)
                    VALUES (:ufdr_report_id, :caller_number, :receiver_number, :call_type, :duration, :timestamp, :metadata)
                """)
                
                db.execute(call_sql, {
                    "ufdr_report_id": report_id,
                    "caller_number": call_data.get("caller_number"),
                    "receiver_number": call_data.get("receiver_number"),
                    "call_type": call_data.get("call_type"),
                    "duration": call_data.get("duration"),
                    "timestamp": call_data.get("timestamp"),
                    "metadata": json.dumps(call_data.get("metadata", {}))
                })
            
            # Store contacts
            for contact_data in parsed_data.get("contacts", []):
                contact_sql = text(f"""
                    INSERT INTO {schema_name}.contacts 
                    (ufdr_report_id, name, phone_numbers, email_addresses, metadata)
                    VALUES (:ufdr_report_id, :name, :phone_numbers, :email_addresses, :metadata)
                """)
                
                db.execute(contact_sql, {
                    "ufdr_report_id": report_id,
                    "name": contact_data.get("name"),
                    "phone_numbers": json.dumps(contact_data.get("phone_numbers", [])),
                    "email_addresses": json.dumps(contact_data.get("email_addresses", [])),
                    "metadata": json.dumps(contact_data.get("metadata", {}))
                })
            
            # Store media files
            for media_data in parsed_data.get("media_files", []):
                media_sql = text(f"""
                    INSERT INTO {schema_name}.media_files 
                    (ufdr_report_id, filename, file_path, file_type, file_size, created_date, 
                     modified_date, hash_md5, hash_sha256, metadata)
                    VALUES (:ufdr_report_id, :filename, :file_path, :file_type, :file_size, :created_date,
                            :modified_date, :hash_md5, :hash_sha256, :metadata)
                """)
                
                db.execute(media_sql, {
                    "ufdr_report_id": report_id,
                    "filename": media_data.get("filename"),
                    "file_path": media_data.get("file_path"),
                    "file_type": media_data.get("file_type"),
                    "file_size": media_data.get("file_size"),
                    "created_date": media_data.get("created_date"),
                    "modified_date": media_data.get("modified_date"),
                    "hash_md5": media_data.get("hash_md5"),
                    "hash_sha256": media_data.get("hash_sha256"),
                    "metadata": json.dumps(media_data.get("metadata", {}))
                })
            
            db.commit()
            print(f"✅ Stored data in PostgreSQL schema: {schema_name}")
            return report_id
            
        except Exception as e:
            print(f"❌ Error in PostgreSQL storage: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            raise e
        finally:
            db.close()
    
    async def _store_in_case_qdrant(self, parsed_data: Dict[str, Any], 
                                   ufdr_report_id: uuid.UUID, safe_case_name: str):
        """Store data in case-specific Qdrant collection"""
        
        collection_name = f"case_{safe_case_name}"
        print(f"🔄 Starting vector storage in collection: {collection_name}")
        
        try:
            # Process chat records
            chat_records = parsed_data.get("chat_records", [])
            print(f"📱 Found {len(chat_records)} chat records to vectorize")
            if chat_records:
                await self._vectorize_and_store_case_chats(chat_records, ufdr_report_id, collection_name)
            
            # Process call records
            call_records = parsed_data.get("call_records", [])
            print(f"📞 Found {len(call_records)} call records to vectorize")
            if call_records:
                await self._vectorize_and_store_case_calls(call_records, ufdr_report_id, collection_name)
            
            # Process contacts
            contacts = parsed_data.get("contacts", [])
            print(f"👥 Found {len(contacts)} contacts to vectorize")
            if contacts:
                await self._vectorize_and_store_case_contacts(contacts, ufdr_report_id, collection_name)
            
            # Process media files
            media_files = parsed_data.get("media_files", [])
            print(f"📁 Found {len(media_files)} media files to vectorize")
            if media_files:
                await self._vectorize_and_store_case_media(media_files, ufdr_report_id, collection_name)
            
            print(f"✅ Completed vector storage for collection: {collection_name}")
            
        except Exception as e:
            print(f"❌ Error in vector storage: {e}")
            import traceback
            traceback.print_exc()
    
    async def _vectorize_and_store_case_chats(self, chat_records: List[Dict], 
                                             ufdr_report_id: uuid.UUID, collection_name: str):
        """Vectorize and store chat records in case-specific Qdrant collection"""
        
        # Prepare texts for embedding
        texts = []
        points = []
        
        for i, chat in enumerate(chat_records):
            # Create searchable text combining all relevant fields
            text_content = f"""
            App: {chat.get('app_name', 'Unknown')}
            Sender: {chat.get('sender_number', 'Unknown')}
            Receiver: {chat.get('receiver_number', 'Unknown')}
            Message: {chat.get('message_content', '')}
            Type: {chat.get('message_type', 'text')}
            Timestamp: {chat.get('timestamp', '')}
            """.strip()
            
            texts.append(text_content)
        
        # Generate embeddings
        print(f"🔄 Generating embeddings for {len(texts)} chat records...")
        embeddings = await ai_service.generate_embeddings(texts)
        print(f"✅ Generated {len(embeddings)} embeddings")
        
        # Create points for Qdrant
        for i, (chat, embedding) in enumerate(zip(chat_records, embeddings)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "data_type": "chat_record",
                    "app_name": chat.get("app_name"),
                    "sender_number": chat.get("sender_number"),
                    "receiver_number": chat.get("receiver_number"),
                    "message_content": chat.get("message_content"),
                    "timestamp": str(chat.get("timestamp")) if chat.get("timestamp") else None,
                    "message_type": chat.get("message_type"),
                    "is_deleted": chat.get("is_deleted", False)
                }
            )
            points.append(point)
        
        # Store in case-specific Qdrant collection
        if points:
            try:
                print(f"🔄 Storing {len(points)} chat vectors in collection: {collection_name}")
                vector_service.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"✅ Successfully stored {len(points)} chat vectors in {collection_name}")
                
                # Verify storage
                collection_info = vector_service.qdrant_client.get_collection(collection_name)
                print(f"📊 Collection {collection_name} now has {collection_info.points_count} total points")
                
            except Exception as e:
                print(f"❌ Error storing chat vectors in {collection_name}: {e}")
                import traceback
                traceback.print_exc()
    
    async def _vectorize_and_store_case_calls(self, call_records: List[Dict], 
                                             ufdr_report_id: uuid.UUID, collection_name: str):
        """Vectorize and store call records in case-specific Qdrant collection"""
        
        texts = []
        points = []
        
        for call in call_records:
            text_content = f"""
            Caller: {call.get('caller_number', 'Unknown')}
            Receiver: {call.get('receiver_number', 'Unknown')}
            Type: {call.get('call_type', 'Unknown')}
            Duration: {call.get('duration', 0)} seconds
            Timestamp: {call.get('timestamp', '')}
            """.strip()
            
            texts.append(text_content)
        
        print(f"🔄 Generating embeddings for {len(texts)} call records...")
        embeddings = await ai_service.generate_embeddings(texts)
        
        for call, embedding in zip(call_records, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "data_type": "call_record",
                    "caller_number": call.get("caller_number"),
                    "receiver_number": call.get("receiver_number"),
                    "call_type": call.get("call_type"),
                    "duration": call.get("duration"),
                    "timestamp": str(call.get("timestamp")) if call.get("timestamp") else None
                }
            )
            points.append(point)
        
        if points:
            try:
                print(f"🔄 Storing {len(points)} call vectors in collection: {collection_name}")
                vector_service.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"✅ Successfully stored {len(points)} call vectors in {collection_name}")
            except Exception as e:
                print(f"❌ Error storing call vectors: {e}")
    
    async def _vectorize_and_store_case_contacts(self, contacts: List[Dict], 
                                                ufdr_report_id: uuid.UUID, collection_name: str):
        """Vectorize and store contacts in case-specific Qdrant collection"""
        
        texts = []
        points = []
        
        for contact in contacts:
            text_content = f"""
            Name: {contact.get('name', 'Unknown')}
            Phone Numbers: {', '.join(contact.get('phone_numbers', []))}
            Email Addresses: {', '.join(contact.get('email_addresses', []))}
            """.strip()
            
            texts.append(text_content)
        
        print(f"🔄 Generating embeddings for {len(texts)} contacts...")
        embeddings = await ai_service.generate_embeddings(texts)
        
        for contact, embedding in zip(contacts, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "data_type": "contact",
                    "name": contact.get("name"),
                    "phone_numbers": contact.get("phone_numbers", []),
                    "email_addresses": contact.get("email_addresses", [])
                }
            )
            points.append(point)
        
        if points:
            try:
                print(f"🔄 Storing {len(points)} contact vectors in collection: {collection_name}")
                vector_service.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"✅ Successfully stored {len(points)} contact vectors in {collection_name}")
            except Exception as e:
                print(f"❌ Error storing contact vectors: {e}")
    
    async def _vectorize_and_store_case_media(self, media_files: List[Dict], 
                                             ufdr_report_id: uuid.UUID, collection_name: str):
        """Vectorize and store media files in case-specific Qdrant collection"""
        
        texts = []
        points = []
        
        for media in media_files:
            text_content = f"""
            Filename: {media.get('filename', 'Unknown')}
            File Type: {media.get('file_type', 'Unknown')}
            File Size: {media.get('file_size', 0)} bytes
            Created: {media.get('created_date', '')}
            Modified: {media.get('modified_date', '')}
            Path: {media.get('file_path', '')}
            """.strip()
            
            texts.append(text_content)
        
        print(f"🔄 Generating embeddings for {len(texts)} media files...")
        embeddings = await ai_service.generate_embeddings(texts)
        
        for media, embedding in zip(media_files, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "data_type": "media_file",
                    "filename": media.get("filename"),
                    "file_type": media.get("file_type"),
                    "file_size": media.get("file_size"),
                    "file_path": media.get("file_path"),
                    "created_date": str(media.get("created_date")) if media.get("created_date") else None,
                    "modified_date": str(media.get("modified_date")) if media.get("modified_date") else None,
                    "hash_md5": media.get("hash_md5"),
                    "hash_sha256": media.get("hash_sha256")
                }
            )
            points.append(point)
        
        if points:
            try:
                print(f"🔄 Storing {len(points)} media vectors in collection: {collection_name}")
                vector_service.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"✅ Successfully stored {len(points)} media vectors in {collection_name}")
            except Exception as e:
                print(f"❌ Error storing media vectors: {e}")
    
    async def _store_in_case_neo4j(self, parsed_data: Dict[str, Any], safe_case_name: str):
        """Store relationship data in case-specific Neo4j namespace"""
        
        try:
            person_label = f"Person_{safe_case_name}"
            communication_label = f"Communication_{safe_case_name}"
            
            # Extract unique persons from communications
            persons = set()
            
            # From chat records
            for chat in parsed_data.get("chat_records", []):
                persons.add(chat.get("sender_number", ""))
                persons.add(chat.get("receiver_number", ""))
            
            # From call records
            for call in parsed_data.get("call_records", []):
                persons.add(call.get("caller_number", ""))
                persons.add(call.get("receiver_number", ""))
            
            persons.discard("")  # Remove empty strings
            
            # Create case-specific person nodes
            person_nodes = {}
            for person in persons:
                person_data = {
                    'id': f'{safe_case_name}_person_{person}',
                    'phone_number': person,
                    'name': person,  # Will be updated if found in contacts
                    'case_id': safe_case_name,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Check if person exists in contacts
                for contact in parsed_data.get("contacts", []):
                    if person in contact.get('phone_numbers', []):
                        person_data['name'] = contact.get('name', person)
                        person_data['email_addresses'] = contact.get('email_addresses', [])
                        break
                
                # Create person node with case-specific label
                await neo4j_repo.execute_cypher(f"""
                    CREATE (p:{person_label} $properties)
                    RETURN p.id as node_id
                """, {"properties": person_data})
                
                person_nodes[person] = person_data
            
            # Create communication relationships with detailed tracking
            communication_pairs = {}
            
            # From chat records - track individual messages
            for chat in parsed_data.get("chat_records", []):
                sender = chat.get("sender_number", "")
                receiver = chat.get("receiver_number", "")
                
                if sender and receiver:
                    pair_key = tuple(sorted([sender, receiver]))
                    if pair_key not in communication_pairs:
                        communication_pairs[pair_key] = {
                            'message_count': 0,
                            'call_count': 0,
                            'total_interactions': 0,
                            'first_contact': chat.get('timestamp'),
                            'last_contact': chat.get('timestamp'),
                            'apps_used': set(),
                            'message_types': set()
                        }
                    
                    communication_pairs[pair_key]['message_count'] += 1
                    communication_pairs[pair_key]['total_interactions'] += 1
                    communication_pairs[pair_key]['apps_used'].add(chat.get('app_name', 'Unknown'))
                    communication_pairs[pair_key]['message_types'].add(chat.get('message_type', 'text'))
                    
                    # Update timestamps
                    if chat.get('timestamp'):
                        if not communication_pairs[pair_key]['first_contact'] or chat.get('timestamp') < communication_pairs[pair_key]['first_contact']:
                            communication_pairs[pair_key]['first_contact'] = chat.get('timestamp')
                        if not communication_pairs[pair_key]['last_contact'] or chat.get('timestamp') > communication_pairs[pair_key]['last_contact']:
                            communication_pairs[pair_key]['last_contact'] = chat.get('timestamp')
            
            # From call records
            for call in parsed_data.get("call_records", []):
                caller = call.get("caller_number", "")
                receiver = call.get("receiver_number", "")
                
                if caller and receiver:
                    pair_key = tuple(sorted([caller, receiver]))
                    if pair_key not in communication_pairs:
                        communication_pairs[pair_key] = {
                            'message_count': 0,
                            'call_count': 0,
                            'total_interactions': 0,
                            'first_contact': call.get('timestamp'),
                            'last_contact': call.get('timestamp'),
                            'apps_used': set(),
                            'message_types': set(),
                            'call_types': set(),
                            'total_call_duration': 0
                        }
                    
                    communication_pairs[pair_key]['call_count'] += 1
                    communication_pairs[pair_key]['total_interactions'] += 1
                    communication_pairs[pair_key].setdefault('call_types', set()).add(call.get('call_type', 'unknown'))
                    communication_pairs[pair_key].setdefault('total_call_duration', 0)
                    communication_pairs[pair_key]['total_call_duration'] += call.get('duration', 0)
                    
                    # Update timestamps
                    if call.get('timestamp'):
                        if not communication_pairs[pair_key]['first_contact'] or call.get('timestamp') < communication_pairs[pair_key]['first_contact']:
                            communication_pairs[pair_key]['first_contact'] = call.get('timestamp')
                        if not communication_pairs[pair_key]['last_contact'] or call.get('timestamp') > communication_pairs[pair_key]['last_contact']:
                            communication_pairs[pair_key]['last_contact'] = call.get('timestamp')
            
            # Create enhanced relationships in Neo4j
            for pair_key, data in communication_pairs.items():
                person1, person2 = pair_key
                
                # Calculate communication strength based on multiple factors
                message_weight = min(data['message_count'] * 0.1, 5.0)  # Max 5 points from messages
                call_weight = min(data['call_count'] * 0.3, 5.0)  # Max 5 points from calls
                duration_weight = min(data.get('total_call_duration', 0) / 3600, 2.0)  # Max 2 points from duration (hours)
                app_diversity = len(data.get('apps_used', set())) * 0.5  # Bonus for using multiple apps
                
                strength = min(10.0, message_weight + call_weight + duration_weight + app_diversity) / 10.0
                
                rel_data = {
                    'id': f'{safe_case_name}_comm_{person1}_{person2}',
                    'case_id': safe_case_name,
                    'frequency': data['total_interactions'],
                    'message_count': data['message_count'],
                    'call_count': data['call_count'],
                    'total_call_duration': data.get('total_call_duration', 0),
                    'communication_strength': round(strength, 3),
                    'apps_used': list(data.get('apps_used', set())),
                    'message_types': list(data.get('message_types', set())),
                    'call_types': list(data.get('call_types', set())),
                    'first_contact': str(data['first_contact']) if data['first_contact'] else None,
                    'last_contact': str(data['last_contact']) if data['last_contact'] else None,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Create relationship with case-specific labels
                await neo4j_repo.execute_cypher(f"""
                    MATCH (a:{person_label} {{phone_number: $person1}})
                    MATCH (b:{person_label} {{phone_number: $person2}})
                    CREATE (a)-[r:COMMUNICATES_WITH $properties]->(b)
                    RETURN r.id as rel_id
                """, {
                    "person1": person1,
                    "person2": person2,
                    "properties": rel_data
                })
            
            print(f"✅ Stored {len(person_nodes)} persons and {len(communication_pairs)} relationships in Neo4j namespace: {safe_case_name}")
            
        except Exception as e:
            print(f"❌ Error storing in Neo4j: {str(e)}")
            # Continue processing even if Neo4j fails

# Global data processor instance
data_processor = DataProcessor()