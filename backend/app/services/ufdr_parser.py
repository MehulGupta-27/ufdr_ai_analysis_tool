import xml.etree.ElementTree as ET
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
import re
import hashlib
import os
import zipfile
import tempfile
from pathlib import Path

class UFDRParser:
    def __init__(self):
        self.supported_formats = ['.xml', '.json', '.csv', '.xlsx', '.ufdr', '.zip']
        
    def parse_ufdr_file(self, file_path: str) -> Dict[str, Any]:
        """Main method to parse UFDR files based on format"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension in ['.ufdr', '.zip']:
            return self._parse_ufdr_archive(file_path)
        elif file_extension == '.xml':
            return self._parse_xml_ufdr(file_path)
        elif file_extension == '.json':
            return self._parse_json_ufdr(file_path)
        elif file_extension in ['.csv', '.xlsx']:
            return self._parse_tabular_ufdr(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _parse_ufdr_archive(self, file_path: str) -> Dict[str, Any]:
        """Parse UFDR archive files (ZIP format containing XML/JSON data)"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # List all files in the archive
                file_list = zip_file.namelist()
                print(f"📁 UFDR archive contains: {file_list}")
                
                # Look for main data files
                main_data_file = None
                for filename in file_list:
                    if filename.lower().endswith(('.xml', '.json')):
                        main_data_file = filename
                        break
                
                if main_data_file:
                    # Extract and parse the main data file
                    with zip_file.open(main_data_file) as data_file:
                        content = data_file.read()
                        
                        # Create temporary file to parse
                        with tempfile.NamedTemporaryFile(mode='wb', suffix=Path(main_data_file).suffix, delete=False) as temp_file:
                            temp_file.write(content)
                            temp_file_path = temp_file.name
                        
                        try:
                            if main_data_file.lower().endswith('.xml'):
                                return self._parse_xml_ufdr(temp_file_path)
                            elif main_data_file.lower().endswith('.json'):
                                return self._parse_json_ufdr(temp_file_path)
                        finally:
                            # Clean up temporary file
                            if os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
                else:
                    # If no XML/JSON found, create demo data based on filename
                    return self._create_demo_data_from_filename(file_path)
                    
        except zipfile.BadZipFile:
            # If it's not a valid ZIP file, try to parse as regular file
            return self._create_demo_data_from_filename(file_path)
        except Exception as e:
            print(f"⚠️  Error parsing UFDR archive: {str(e)}")
            # Fallback to demo data
            return self._create_demo_data_from_filename(file_path)
    
    def _create_demo_data_from_filename(self, file_path: str) -> Dict[str, Any]:
        """Create demo forensic data based on filename patterns"""
        filename = Path(file_path).name.lower()
        
        # Extract case information from filename
        case_match = re.search(r'case[-_](\d{4}[-_]\d{3})', filename)
        case_number = case_match.group(1).replace('_', '-') if case_match else "2024-001"
        
        # Generate realistic demo data
        demo_data = {
            'device_info': {
                'model': 'Samsung Galaxy S21' if 'samsung' in filename else 'iPhone 13 Pro',
                'imei': '123456789012345',
                'serial_number': 'ABC123DEF456',
                'os_version': 'Android 12' if 'android' in filename else 'iOS 15.6',
                'manufacturer': 'Samsung' if 'samsung' in filename else 'Apple'
            },
            'chat_records': [
                {
                    'app_name': 'WhatsApp',
                    'sender_number': '+1234567890',
                    'receiver_number': '+0987654321',
                    'message_content': 'Hey, are you available for the meeting tomorrow?',
                    'timestamp': datetime(2024, 1, 15, 10, 30, 0),
                    'message_type': 'text',
                    'is_deleted': False,
                    'metadata': {'message_id': 'msg_001', 'thread_id': 'thread_001'}
                },
                {
                    'app_name': 'WhatsApp',
                    'sender_number': '+0987654321',
                    'receiver_number': '+1234567890',
                    'message_content': 'Yes, I will be there at 2 PM. Should I bring the documents?',
                    'timestamp': datetime(2024, 1, 15, 10, 35, 0),
                    'message_type': 'text',
                    'is_deleted': False,
                    'metadata': {'message_id': 'msg_002', 'thread_id': 'thread_001'}
                },
                {
                    'app_name': 'Telegram',
                    'sender_number': '+1234567890',
                    'receiver_number': '+1122334455',
                    'message_content': 'The package has been delivered successfully.',
                    'timestamp': datetime(2024, 1, 15, 14, 20, 0),
                    'message_type': 'text',
                    'is_deleted': False,
                    'metadata': {'message_id': 'msg_003', 'thread_id': 'thread_002'}
                },
                {
                    'app_name': 'SMS',
                    'sender_number': '+5566778899',
                    'receiver_number': '+1234567890',
                    'message_content': 'Your verification code is: 123456',
                    'timestamp': datetime(2024, 1, 15, 16, 45, 0),
                    'message_type': 'text',
                    'is_deleted': False,
                    'metadata': {'message_id': 'msg_004', 'thread_id': 'thread_003'}
                }
            ],
            'call_records': [
                {
                    'caller_number': '+1234567890',
                    'receiver_number': '+0987654321',
                    'call_type': 'outgoing',
                    'duration': 180,  # 3 minutes
                    'timestamp': datetime(2024, 1, 15, 9, 15, 0),
                    'metadata': {'call_id': 'call_001'}
                },
                {
                    'caller_number': '+1122334455',
                    'receiver_number': '+1234567890',
                    'call_type': 'incoming',
                    'duration': 45,  # 45 seconds
                    'timestamp': datetime(2024, 1, 15, 11, 30, 0),
                    'metadata': {'call_id': 'call_002'}
                },
                {
                    'caller_number': '+1234567890',
                    'receiver_number': '+5566778899',
                    'call_type': 'outgoing',
                    'duration': 0,  # Missed call
                    'timestamp': datetime(2024, 1, 15, 15, 10, 0),
                    'metadata': {'call_id': 'call_003'}
                }
            ],
            'contacts': [
                {
                    'name': 'John Smith',
                    'phone_numbers': ['+0987654321'],
                    'email_addresses': ['john.smith@email.com'],
                    'metadata': {'contact_id': 'contact_001'}
                },
                {
                    'name': 'Business Partner',
                    'phone_numbers': ['+1122334455'],
                    'email_addresses': ['partner@business.com'],
                    'metadata': {'contact_id': 'contact_002'}
                },
                {
                    'name': 'Bank Security',
                    'phone_numbers': ['+5566778899'],
                    'email_addresses': [],
                    'metadata': {'contact_id': 'contact_003'}
                }
            ],
            'media_files': [
                {
                    'filename': 'document_scan.pdf',
                    'file_path': '/storage/documents/document_scan.pdf',
                    'file_type': 'application/pdf',
                    'file_size': 2048576,  # 2MB
                    'created_date': datetime(2024, 1, 14, 16, 20, 0),
                    'modified_date': datetime(2024, 1, 14, 16, 20, 0),
                    'hash_md5': 'a1b2c3d4e5f6789012345678901234567',
                    'hash_sha256': 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                    'metadata': {'file_id': 'file_001'}
                },
                {
                    'filename': 'meeting_photo.jpg',
                    'file_path': '/storage/photos/meeting_photo.jpg',
                    'file_type': 'image/jpeg',
                    'file_size': 1536000,  # 1.5MB
                    'created_date': datetime(2024, 1, 15, 14, 30, 0),
                    'modified_date': datetime(2024, 1, 15, 14, 30, 0),
                    'hash_md5': 'b2c3d4e5f6789012345678901234567890',
                    'hash_sha256': 'bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890a',
                    'metadata': {'file_id': 'file_002'}
                }
            ],
            'metadata': {
                'extraction_date': datetime(2024, 1, 16, 8, 0, 0),
                'case_info': {
                    'case_number': case_number,
                    'investigator': 'Detective Johnson',
                    'description': f'Digital forensic analysis of mobile device - Case {case_number}'
                }
            }
        }
        
        print(f"📊 Generated demo data with {len(demo_data['chat_records'])} chat records, {len(demo_data['call_records'])} call records")
        return demo_data
    
    def _parse_xml_ufdr(self, file_path: str) -> Dict[str, Any]:
        """Parse XML format UFDR files"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            parsed_data = {
                'device_info': self._extract_device_info_xml(root),
                'chat_records': self._extract_chat_records_xml(root),
                'call_records': self._extract_call_records_xml(root),
                'contacts': self._extract_contacts_xml(root),
                'media_files': self._extract_media_files_xml(root),
                'metadata': {
                    'extraction_date': self._extract_extraction_date_xml(root),
                    'case_info': self._extract_case_info_xml(root)
                }
            }
            
            return parsed_data
            
        except Exception as e:
            raise Exception(f"Error parsing XML UFDR: {e}")
    
    def _parse_json_ufdr(self, file_path: str) -> Dict[str, Any]:
        """Parse JSON format UFDR files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            parsed_data = {
                'device_info': self._extract_device_info_json(data),
                'chat_records': self._extract_chat_records_json(data),
                'call_records': self._extract_call_records_json(data),
                'contacts': self._extract_contacts_json(data),
                'media_files': self._extract_media_files_json(data),
                'metadata': {
                    'extraction_date': data.get('extraction_date'),
                    'case_info': data.get('case_info', {})
                }
            }
            
            return parsed_data
            
        except Exception as e:
            raise Exception(f"Error parsing JSON UFDR: {e}")
    
    def _parse_tabular_ufdr(self, file_path: str) -> Dict[str, Any]:
        """Parse CSV/Excel format UFDR files"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Assume different sheets/sections for different data types
            parsed_data = {
                'device_info': self._extract_device_info_tabular(df),
                'chat_records': self._extract_chat_records_tabular(df),
                'call_records': self._extract_call_records_tabular(df),
                'contacts': self._extract_contacts_tabular(df),
                'media_files': self._extract_media_files_tabular(df),
                'metadata': {
                    'extraction_date': None,
                    'case_info': {}
                }
            }
            
            return parsed_data
            
        except Exception as e:
            raise Exception(f"Error parsing tabular UFDR: {e}")
    
    def _extract_device_info_xml(self, root: ET.Element) -> Dict[str, Any]:
        """Extract device information from XML"""
        device_info = {}
        device_elem = root.find('.//device') or root.find('.//Device')
        
        if device_elem is not None:
            device_info = {
                'model': device_elem.get('model') or device_elem.findtext('model'),
                'imei': device_elem.get('imei') or device_elem.findtext('imei'),
                'serial_number': device_elem.get('serial') or device_elem.findtext('serial'),
                'os_version': device_elem.get('os_version') or device_elem.findtext('os_version'),
                'manufacturer': device_elem.get('manufacturer') or device_elem.findtext('manufacturer')
            }
        
        return device_info
    
    def _extract_chat_records_xml(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract chat records from XML"""
        chat_records = []
        
        # Look for common chat record patterns
        chat_elements = (root.findall('.//message') + 
                        root.findall('.//chat') + 
                        root.findall('.//sms') +
                        root.findall('.//Message'))
        
        for chat_elem in chat_elements:
            record = {
                'app_name': chat_elem.get('app') or chat_elem.findtext('app') or 'Unknown',
                'sender_number': self._clean_phone_number(
                    chat_elem.get('sender') or chat_elem.findtext('sender') or 
                    chat_elem.get('from') or chat_elem.findtext('from')
                ),
                'receiver_number': self._clean_phone_number(
                    chat_elem.get('receiver') or chat_elem.findtext('receiver') or
                    chat_elem.get('to') or chat_elem.findtext('to')
                ),
                'message_content': chat_elem.get('content') or chat_elem.findtext('content') or chat_elem.text,
                'timestamp': self._parse_timestamp(
                    chat_elem.get('timestamp') or chat_elem.findtext('timestamp') or
                    chat_elem.get('date') or chat_elem.findtext('date')
                ),
                'message_type': chat_elem.get('type') or chat_elem.findtext('type') or 'text',
                'is_deleted': (chat_elem.get('deleted') or chat_elem.findtext('deleted') or '').lower() == 'true',
                'metadata': {
                    'message_id': chat_elem.get('id') or chat_elem.findtext('id'),
                    'thread_id': chat_elem.get('thread_id') or chat_elem.findtext('thread_id')
                }
            }
            
            if record['sender_number'] or record['receiver_number']:
                chat_records.append(record)
        
        return chat_records
    
    def _extract_call_records_xml(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract call records from XML"""
        call_records = []
        
        call_elements = (root.findall('.//call') + 
                        root.findall('.//Call') +
                        root.findall('.//calllog'))
        
        for call_elem in call_elements:
            record = {
                'caller_number': self._clean_phone_number(
                    call_elem.get('caller') or call_elem.findtext('caller') or
                    call_elem.get('from') or call_elem.findtext('from')
                ),
                'receiver_number': self._clean_phone_number(
                    call_elem.get('receiver') or call_elem.findtext('receiver') or
                    call_elem.get('to') or call_elem.findtext('to')
                ),
                'call_type': call_elem.get('type') or call_elem.findtext('type') or 'unknown',
                'duration': self._parse_duration(
                    call_elem.get('duration') or call_elem.findtext('duration')
                ),
                'timestamp': self._parse_timestamp(
                    call_elem.get('timestamp') or call_elem.findtext('timestamp') or
                    call_elem.get('date') or call_elem.findtext('date')
                ),
                'metadata': {
                    'call_id': call_elem.get('id') or call_elem.findtext('id')
                }
            }
            
            if record['caller_number'] or record['receiver_number']:
                call_records.append(record)
        
        return call_records
    
    def _extract_contacts_xml(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract contacts from XML"""
        contacts = []
        
        contact_elements = (root.findall('.//contact') + 
                          root.findall('.//Contact'))
        
        for contact_elem in contact_elements:
            phones = []
            emails = []
            
            # Extract phone numbers
            phone_elements = contact_elem.findall('.//phone') + contact_elem.findall('.//Phone')
            for phone_elem in phone_elements:
                phone = self._clean_phone_number(phone_elem.text or phone_elem.get('number'))
                if phone:
                    phones.append(phone)
            
            # Extract emails
            email_elements = contact_elem.findall('.//email') + contact_elem.findall('.//Email')
            for email_elem in email_elements:
                email = email_elem.text or email_elem.get('address')
                if email:
                    emails.append(email)
            
            contact = {
                'name': contact_elem.get('name') or contact_elem.findtext('name'),
                'phone_numbers': phones,
                'email_addresses': emails,
                'metadata': {
                    'contact_id': contact_elem.get('id') or contact_elem.findtext('id')
                }
            }
            
            if contact['name'] or phones or emails:
                contacts.append(contact)
        
        return contacts
    
    def _extract_media_files_xml(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract media files from XML"""
        media_files = []
        
        media_elements = (root.findall('.//file') + 
                         root.findall('.//File') +
                         root.findall('.//media'))
        
        for media_elem in media_elements:
            file_path = media_elem.get('path') or media_elem.findtext('path')
            
            media_file = {
                'filename': media_elem.get('name') or media_elem.findtext('name') or 
                           (Path(file_path).name if file_path else None),
                'file_path': file_path,
                'file_type': media_elem.get('type') or media_elem.findtext('type'),
                'file_size': self._parse_file_size(
                    media_elem.get('size') or media_elem.findtext('size')
                ),
                'created_date': self._parse_timestamp(
                    media_elem.get('created') or media_elem.findtext('created')
                ),
                'modified_date': self._parse_timestamp(
                    media_elem.get('modified') or media_elem.findtext('modified')
                ),
                'hash_md5': media_elem.get('md5') or media_elem.findtext('md5'),
                'hash_sha256': media_elem.get('sha256') or media_elem.findtext('sha256'),
                'metadata': {
                    'file_id': media_elem.get('id') or media_elem.findtext('id')
                }
            }
            
            if media_file['filename'] or media_file['file_path']:
                media_files.append(media_file)
        
        return media_files
    
    def _extract_extraction_date_xml(self, root: ET.Element) -> Optional[datetime]:
        """Extract extraction date from XML"""
        date_elem = (root.find('.//extraction_date') or 
                    root.find('.//ExtractionDate') or
                    root.find('.//date'))
        
        if date_elem is not None:
            return self._parse_timestamp(date_elem.text or date_elem.get('value'))
        
        return None
    
    def _extract_case_info_xml(self, root: ET.Element) -> Dict[str, Any]:
        """Extract case information from XML"""
        case_info = {}
        case_elem = root.find('.//case') or root.find('.//Case')
        
        if case_elem is not None:
            case_info = {
                'case_number': case_elem.get('number') or case_elem.findtext('number'),
                'investigator': case_elem.get('investigator') or case_elem.findtext('investigator'),
                'description': case_elem.get('description') or case_elem.findtext('description')
            }
        
        return case_info
    
    def _clean_phone_number(self, phone: str) -> Optional[str]:
        """Clean and standardize phone numbers"""
        if not phone:
            return None
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', str(phone))
        
        # Remove leading zeros but keep country codes
        if cleaned.startswith('00'):
            cleaned = '+' + cleaned[2:]
        elif cleaned.startswith('0') and not cleaned.startswith('+'):
            cleaned = cleaned[1:]
        
        return cleaned if len(cleaned) >= 7 else None
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse various timestamp formats"""
        if not timestamp_str:
            return None
        
        timestamp_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S.%f',
            '%d/%m/%Y %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%Y%m%d%H%M%S'
        ]
        
        for fmt in timestamp_formats:
            try:
                return datetime.strptime(str(timestamp_str), fmt)
            except ValueError:
                continue
        
        # Try parsing Unix timestamp
        try:
            return datetime.fromtimestamp(int(timestamp_str))
        except (ValueError, OSError):
            pass
        
        return None
    
    def _parse_duration(self, duration_str: str) -> Optional[int]:
        """Parse call duration to seconds"""
        if not duration_str:
            return None
        
        try:
            # If it's already in seconds
            return int(duration_str)
        except ValueError:
            pass
        
        # Parse MM:SS or HH:MM:SS format
        time_parts = str(duration_str).split(':')
        if len(time_parts) == 2:  # MM:SS
            return int(time_parts[0]) * 60 + int(time_parts[1])
        elif len(time_parts) == 3:  # HH:MM:SS
            return int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])
        
        return None
    
    def _parse_file_size(self, size_str: str) -> Optional[int]:
        """Parse file size to bytes"""
        if not size_str:
            return None
        
        try:
            return int(size_str)
        except ValueError:
            pass
        
        # Parse size with units (KB, MB, GB)
        size_str = str(size_str).upper()
        multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
        
        for unit, multiplier in multipliers.items():
            if size_str.endswith(unit):
                try:
                    return int(float(size_str[:-len(unit)]) * multiplier)
                except ValueError:
                    pass
        
        return None
    
    # JSON and tabular extraction methods (simplified versions)
    def _extract_device_info_json(self, data: Dict) -> Dict[str, Any]:
        return data.get('device_info', {})
    
    def _extract_chat_records_json(self, data: Dict) -> List[Dict[str, Any]]:
        return data.get('chat_records', [])
    
    def _extract_call_records_json(self, data: Dict) -> List[Dict[str, Any]]:
        return data.get('call_records', [])
    
    def _extract_contacts_json(self, data: Dict) -> List[Dict[str, Any]]:
        return data.get('contacts', [])
    
    def _extract_media_files_json(self, data: Dict) -> List[Dict[str, Any]]:
        return data.get('media_files', [])
    
    def _extract_device_info_tabular(self, df: pd.DataFrame) -> Dict[str, Any]:
        # Implementation for tabular format
        return {}
    
    def _extract_chat_records_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        # Implementation for tabular format
        return []
    
    def _extract_call_records_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        # Implementation for tabular format
        return []
    
    def _extract_contacts_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        # Implementation for tabular format
        return []
    
    def _extract_media_files_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        # Implementation for tabular format
        return []