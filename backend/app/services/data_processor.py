from typing import Dict, List, Any, Optional
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
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

class DataProcessor:
    def __init__(self):
        self.parser = UFDRParser()
    
    async def process_ufdr_file(self, file_path: str, case_number: str, 
                               investigator: str) -> Dict[str, Any]:
        """Main method to process UFDR file and store in all databases"""
        
        try:
            # Parse UFDR file
            parsed_data = self.parser.parse_ufdr_file(file_path)
            
            # Store in PostgreSQL
            ufdr_report_id = await self._store_in_postgres(
                parsed_data, file_path, case_number, investigator
            )
            
            # Store in Qdrant (vector database)
            await self._store_in_qdrant(parsed_data, ufdr_report_id)
            
            # Store in Neo4j (graph database)
            await self._store_in_neo4j(parsed_data)
            
            return {
                "success": True,
                "ufdr_report_id": str(ufdr_report_id),
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
    
    async def _store_in_postgres(self, parsed_data: Dict[str, Any], 
                                file_path: str, case_number: str, 
                                investigator: str) -> uuid.UUID:
        """Store parsed data in PostgreSQL"""
        
        db = next(get_db())
        try:
            # Create UFDR report record
            ufdr_report = UFDRReport(
                filename=file_path.split('/')[-1],
                device_info=parsed_data.get("device_info", {}),
                extraction_date=parsed_data.get("metadata", {}).get("extraction_date"),
                case_number=case_number,
                investigator=investigator,
                processed=True
            )
            
            db.add(ufdr_report)
            db.flush()  # Get the ID
            
            # Store chat records
            for chat_data in parsed_data.get("chat_records", []):
                chat_record = ChatRecord(
                    ufdr_report_id=ufdr_report.id,
                    app_name=chat_data.get("app_name"),
                    sender_number=chat_data.get("sender_number"),
                    receiver_number=chat_data.get("receiver_number"),
                    message_content=chat_data.get("message_content"),
                    timestamp=chat_data.get("timestamp"),
                    message_type=chat_data.get("message_type", "text"),
                    is_deleted=chat_data.get("is_deleted", False),
                    metadata=chat_data.get("metadata", {})
                )
                db.add(chat_record)
            
            # Store call records
            for call_data in parsed_data.get("call_records", []):
                call_record = CallRecord(
                    ufdr_report_id=ufdr_report.id,
                    caller_number=call_data.get("caller_number"),
                    receiver_number=call_data.get("receiver_number"),
                    call_type=call_data.get("call_type"),
                    duration=call_data.get("duration"),
                    timestamp=call_data.get("timestamp"),
                    metadata=call_data.get("metadata", {})
                )
                db.add(call_record)
            
            # Store contacts
            for contact_data in parsed_data.get("contacts", []):
                contact = Contact(
                    ufdr_report_id=ufdr_report.id,
                    name=contact_data.get("name"),
                    phone_numbers=contact_data.get("phone_numbers", []),
                    email_addresses=contact_data.get("email_addresses", []),
                    metadata=contact_data.get("metadata", {})
                )
                db.add(contact)
            
            # Store media files
            for media_data in parsed_data.get("media_files", []):
                media_file = MediaFile(
                    ufdr_report_id=ufdr_report.id,
                    filename=media_data.get("filename"),
                    file_path=media_data.get("file_path"),
                    file_type=media_data.get("file_type"),
                    file_size=media_data.get("file_size"),
                    created_date=media_data.get("created_date"),
                    modified_date=media_data.get("modified_date"),
                    hash_md5=media_data.get("hash_md5"),
                    hash_sha256=media_data.get("hash_sha256"),
                    metadata=media_data.get("metadata", {})
                )
                db.add(media_file)
            
            db.commit()
            return ufdr_report.id
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    async def _store_in_qdrant(self, parsed_data: Dict[str, Any], 
                              ufdr_report_id: uuid.UUID):
        """Store data in Qdrant vector database"""
        
        # Process chat records
        chat_records = parsed_data.get("chat_records", [])
        if chat_records:
            await self._vectorize_and_store_chats(chat_records, ufdr_report_id)
        
        # Process call records
        call_records = parsed_data.get("call_records", [])
        if call_records:
            await self._vectorize_and_store_calls(call_records, ufdr_report_id)
        
        # Process contacts
        contacts = parsed_data.get("contacts", [])
        if contacts:
            await self._vectorize_and_store_contacts(contacts, ufdr_report_id)
        
        # Process media files
        media_files = parsed_data.get("media_files", [])
        if media_files:
            await self._vectorize_and_store_media(media_files, ufdr_report_id)
    
    async def _vectorize_and_store_chats(self, chat_records: List[Dict], 
                                        ufdr_report_id: uuid.UUID):
        """Vectorize and store chat records in Qdrant"""
        
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
        embeddings = await ai_service.generate_embeddings(texts)
        
        # Create points for Qdrant
        for i, (chat, embedding) in enumerate(zip(chat_records, embeddings)):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "type": "chat_record",
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
        
        # Store in Qdrant
        if points:
            db_manager.store_vector_data("chat_messages", points)
    
    async def _vectorize_and_store_calls(self, call_records: List[Dict], 
                                        ufdr_report_id: uuid.UUID):
        """Vectorize and store call records in Qdrant"""
        
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
        
        embeddings = await ai_service.generate_embeddings(texts)
        
        for call, embedding in zip(call_records, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "type": "call_record",
                    "caller_number": call.get("caller_number"),
                    "receiver_number": call.get("receiver_number"),
                    "call_type": call.get("call_type"),
                    "duration": call.get("duration"),
                    "timestamp": str(call.get("timestamp")) if call.get("timestamp") else None
                }
            )
            points.append(point)
        
        if points:
            db_manager.store_vector_data("call_records", points)
    
    async def _vectorize_and_store_contacts(self, contacts: List[Dict], 
                                           ufdr_report_id: uuid.UUID):
        """Vectorize and store contacts in Qdrant"""
        
        texts = []
        points = []
        
        for contact in contacts:
            text_content = f"""
            Name: {contact.get('name', 'Unknown')}
            Phone Numbers: {', '.join(contact.get('phone_numbers', []))}
            Email Addresses: {', '.join(contact.get('email_addresses', []))}
            """.strip()
            
            texts.append(text_content)
        
        embeddings = await ai_service.generate_embeddings(texts)
        
        for contact, embedding in zip(contacts, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "type": "contact",
                    "name": contact.get("name"),
                    "phone_numbers": contact.get("phone_numbers", []),
                    "email_addresses": contact.get("email_addresses", [])
                }
            )
            points.append(point)
        
        if points:
            db_manager.store_vector_data("contacts", points)
    
    async def _vectorize_and_store_media(self, media_files: List[Dict], 
                                        ufdr_report_id: uuid.UUID):
        """Vectorize and store media files in Qdrant"""
        
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
        
        embeddings = await ai_service.generate_embeddings(texts)
        
        for media, embedding in zip(media_files, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "ufdr_report_id": str(ufdr_report_id),
                    "type": "media_file",
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
            db_manager.store_vector_data("media_files", points)
    
    async def _store_in_neo4j(self, parsed_data: Dict[str, Any]):
        """Store relationship data in Neo4j"""
        
        try:
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
            
            # Create person nodes
            person_nodes = {}
            for person in persons:
                person_data = {
                    'id': f'person_{person}',
                    'phone_number': person,
                    'name': person,  # Will be updated if found in contacts
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Check if person exists in contacts
                for contact in parsed_data.get("contacts", []):
                    if person in contact.get('phone_numbers', []):
                        person_data['name'] = contact.get('name', person)
                        person_data['email_addresses'] = contact.get('email_addresses', [])
                        break
                
                await neo4j_repo.create_person_node(person_data)
                person_nodes[person] = person_data
            
            # Create communication relationships
            communication_pairs = {}
            
            # From chat records
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
                            'last_contact': chat.get('timestamp')
                        }
                    
                    communication_pairs[pair_key]['message_count'] += 1
                    communication_pairs[pair_key]['total_interactions'] += 1
            
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
                            'last_contact': call.get('timestamp')
                        }
                    
                    communication_pairs[pair_key]['call_count'] += 1
                    communication_pairs[pair_key]['total_interactions'] += 1
            
            # Create relationships in Neo4j
            for pair_key, data in communication_pairs.items():
                person1, person2 = pair_key
                strength = min(1.0, (data['message_count'] * 0.6 + data['call_count'] * 0.4) / 10)
                
                rel_data = {
                    'frequency': data['total_interactions'],
                    'message_count': data['message_count'],
                    'call_count': data['call_count'],
                    'communication_strength': strength,
                    'first_contact': str(data['first_contact']) if data['first_contact'] else None,
                    'last_contact': str(data['last_contact']) if data['last_contact'] else None,
                    'created_at': datetime.utcnow().isoformat()
                }
                
                await neo4j_repo.create_communication_relationship(
                    f'person_{person1}', f'person_{person2}', rel_data
                )
            
        except Exception as e:
            print(f"Error storing in Neo4j: {str(e)}")
            # Continue processing even if Neo4j fails

# Global data processor instance
data_processor = DataProcessor()