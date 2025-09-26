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
        
        print(f"🔍 Parsing UFDR file: {file_path}")
        print(f"📄 File extension: {file_extension}")
        
        # First, try to read the file content to determine the actual format
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(1000)  # Read first 1000 characters
                print(f"📝 File content preview: {content[:200]}...")
                
                # Check if it's JSON
                if content.strip().startswith('{') or content.strip().startswith('['):
                    print("🔍 Detected JSON format")
                    return self._parse_json_ufdr(file_path)
                # Check if it's XML
                elif content.strip().startswith('<'):
                    print("🔍 Detected XML format")
                    return self._parse_xml_ufdr(file_path)
                # Check if it's CSV
                elif ',' in content and '\n' in content:
                    print("🔍 Detected CSV format")
                    return self._parse_tabular_ufdr(file_path)
                    
        except UnicodeDecodeError:
            # File might be binary (ZIP, etc.)
            print("🔍 File appears to be binary, trying archive parsing")
            pass
        except Exception as e:
            print(f"⚠️ Error reading file: {e}")
        
        # Try format-specific parsing based on extension
        if file_extension in ['.ufdr', '.zip']:
            return self._parse_ufdr_archive(file_path)
        elif file_extension == '.xml':
            return self._parse_xml_ufdr(file_path)
        elif file_extension == '.json':
            return self._parse_json_ufdr(file_path)
        elif file_extension in ['.csv', '.xlsx']:
            return self._parse_tabular_ufdr(file_path)
        else:
            print(f"⚠️ Unsupported file format: {file_extension}, analyzing content dynamically")
            # Try to read content for dynamic analysis
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return self._create_dynamic_data_from_content(file_path, content)
            except:
                return self._create_dynamic_data_from_content(file_path, None)
    
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
                    # Check if this is a forensic report XML (contains metadata about other files)
                    if main_data_file.lower().endswith('.xml') and ('report' in main_data_file.lower() or len(file_list) > 5):
                        # This looks like a forensic report with multiple files - use XML-based archive parser
                        print(f"🔍 Found forensic report XML: {main_data_file}")
                        return self._parse_xml_based_ufdr_archive(zip_file, file_path)
                    else:
                        # Extract and parse the main data file as standalone
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
                    # Check for XML report file
                    xml_files = [f for f in file_list if f.lower().endswith('.xml')]
                    if xml_files:
                        print(f"🔍 Found XML report file: {xml_files[0]}")
                        return self._parse_xml_based_ufdr_archive(zip_file, file_path)
                    else:
                        # Parse text-based forensic data from archive
                        print("🔍 No structured data files found, parsing text-based forensic data...")
                        return self._parse_text_based_ufdr_archive(zip_file, file_path)
                    
        except zipfile.BadZipFile:
            # If it's not a valid ZIP file, try to parse as regular file
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return self._create_dynamic_data_from_content(file_path, content)
            except:
                return self._create_dynamic_data_from_content(file_path, None)
        except Exception as e:
            print(f"⚠️  Error parsing UFDR archive: {str(e)}")
            # Fallback to dynamic content analysis
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return self._create_dynamic_data_from_content(file_path, content)
            except:
                return self._create_dynamic_data_from_content(file_path, None)
    
    def _parse_text_based_ufdr_archive(self, zip_file: zipfile.ZipFile, file_path: str) -> Dict[str, Any]:
        """Parse text-based forensic data from UFDR archive"""
        try:
            print("📄 Parsing text-based forensic data from archive...")
            
            # Extract case information from filename
            filename = Path(file_path).name.lower()
            case_match = re.search(r'case[-_](\d{4}[-_]\d{3})', filename)
            case_number = case_match.group(1).replace('_', '-') if case_match else "2025-001"
            
            parsed_data = {
                'device_info': {
                    'model': 'Mobile Device',
                    'extraction_method': 'UFDR Archive',
                    'case_number': case_number
                },
                'chat_records': [],
                'call_records': [],
                'contacts': [],
                'media_files': [],
                'metadata': {
                    'extraction_date': datetime.utcnow(),
                    'case_info': {
                        'case_number': case_number,
                        'description': f'Text-based forensic analysis - Case {case_number}'
                    }
                }
            }
            
            # Process all files in the archive
            for file_info in zip_file.filelist:
                if file_info.is_dir():
                    continue
                    
                try:
                    with zip_file.open(file_info) as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        
                    # Extract data based on file location and content
                    if 'documents' in file_info.filename.lower() or 'notes' in file_info.filename.lower():
                        # Parse as potential chat/communication data
                        contacts_found = self._extract_contacts_from_text(content)
                        parsed_data['contacts'].extend(contacts_found)
                        
                        # Look for phone numbers and create chat records
                        phone_numbers = re.findall(r'\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})', content)
                        for match in phone_numbers:
                            phone = f"+1-{match[0]}-{match[1]}-{match[2]}"
                            # Create a synthetic chat record based on the document
                            parsed_data['chat_records'].append({
                                'app_name': 'Document Reference',
                                'sender_number': phone,
                                'receiver_number': '+1-000-0000',  # Unknown receiver
                                'message_content': f"Contact referenced in document: {file_info.filename}",
                                'timestamp': datetime.utcnow(),
                                'message_type': 'reference',
                                'is_deleted': False,
                                'metadata': {'source_file': file_info.filename, 'extracted_from': 'document'}
                            })
                    
                    elif 'media' in file_info.filename.lower():
                        # Parse as media file metadata
                        media_info = self._extract_media_info_from_text(content, file_info.filename)
                        if media_info:
                            parsed_data['media_files'].append(media_info)
                    
                except Exception as e:
                    print(f"⚠️ Error processing file {file_info.filename}: {e}")
                    continue
            
            # If we found actual data, use it; otherwise try dynamic analysis
            if not parsed_data['contacts'] and not parsed_data['chat_records'] and not parsed_data['media_files']:
                print("📊 No extractable data found in archive, trying dynamic content analysis...")
                # Combine all text content from archive for analysis
                all_content = ""
                for file_info in zip_file.filelist:
                    if not file_info.is_dir():
                        try:
                            with zip_file.open(file_info) as f:
                                all_content += f.read().decode('utf-8', errors='ignore') + "\n"
                        except:
                            continue
                return self._create_dynamic_data_from_content(file_path, all_content)
            
            print(f"✅ Extracted {len(parsed_data['contacts'])} contacts, {len(parsed_data['chat_records'])} chat records, {len(parsed_data['media_files'])} media files")
            return parsed_data
            
        except Exception as e:
            print(f"❌ Error parsing text-based UFDR: {e}")
            return self._create_dynamic_data_from_content(file_path, None)
    
    def _parse_xml_based_ufdr_archive(self, zip_file: zipfile.ZipFile, file_path: str) -> Dict[str, Any]:
        """Parse XML-based forensic data from UFDR archive with report.xml"""
        try:
            print("📄 Parsing XML-based forensic data from archive...")
            
            # Find and parse the XML report
            xml_files = [f for f in zip_file.namelist() if f.lower().endswith('.xml')]
            if not xml_files:
                return self._parse_text_based_ufdr_archive(zip_file, file_path)
            
            xml_file = xml_files[0]
            print(f"📋 Processing XML report: {xml_file}")
            
            # Extract XML content
            with zip_file.open(xml_file) as f:
                xml_content = f.read().decode('utf-8', errors='ignore')
            
            # Parse XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_content)
            
            # Extract case information
            case_info = self._extract_case_info_from_xml(root)
            device_info = self._extract_device_info_from_xml(root)
            
            # Initialize data structure
            parsed_data = {
                'device_info': device_info,
                'chat_records': [],
                'call_records': [],
                'contacts': [],
                'media_files': [],
                'metadata': {
                    'extraction_date': datetime.utcnow(),
                    'case_info': case_info
                }
            }
            
            # Process files referenced in XML
            files = root.findall('.//file')
            print(f"📁 Found {len(files)} file references in XML")
            
            for file_elem in files:
                try:
                    metadata_section = file_elem.find('.//metadata')
                    if metadata_section is not None:
                        section_type = metadata_section.get('section', '').lower()
                        local_path = None
                        
                        # Find local path
                        for item in metadata_section.findall('.//item'):
                            if item.get('name') == 'Local Path':
                                local_path = item.text
                                break
                        
                        if section_type == 'sms' and local_path:
                            # Extract SMS data
                            sms_data = self._extract_sms_from_xml_metadata(metadata_section, zip_file, local_path)
                            if sms_data:
                                parsed_data['chat_records'].append(sms_data)
                        
                        elif section_type == 'contacts' and local_path:
                            # Extract contact data
                            contact_data = self._extract_contact_from_xml_metadata(metadata_section, zip_file, local_path)
                            if contact_data:
                                parsed_data['contacts'].append(contact_data)
                        
                        elif section_type == 'call logs' and local_path:
                            # Extract call data
                            call_data = self._extract_call_from_xml_metadata(metadata_section, zip_file, local_path)
                            if call_data:
                                parsed_data['call_records'].append(call_data)
                        
                        else:
                            # Extract as media file
                            media_data = self._extract_media_from_xml_metadata(file_elem, metadata_section)
                            if media_data:
                                parsed_data['media_files'].append(media_data)
                
                except Exception as e:
                    print(f"⚠️ Error processing file element: {e}")
                    continue
            
            # Also parse WhatsApp group chats and other text files
            for file_info in zip_file.filelist:
                if file_info.filename.startswith('chats/') and file_info.filename.endswith('.txt'):
                    try:
                        with zip_file.open(file_info) as f:
                            content = f.read().decode('utf-8', errors='ignore')
                        
                        if 'whatsapp' in file_info.filename.lower():
                            # Parse WhatsApp group chat
                            whatsapp_messages = self._parse_whatsapp_group_chat(content, file_info.filename)
                            parsed_data['chat_records'].extend(whatsapp_messages)
                    
                    except Exception as e:
                        print(f"⚠️ Error processing chat file {file_info.filename}: {e}")
            
            total_records = (len(parsed_data['chat_records']) + len(parsed_data['call_records']) + 
                            len(parsed_data['contacts']) + len(parsed_data['media_files']))
            
            print(f"✅ XML-based extraction completed:")
            print(f"   📱 Chat records: {len(parsed_data['chat_records'])}")
            print(f"   📞 Call records: {len(parsed_data['call_records'])}")
            print(f"   👥 Contacts: {len(parsed_data['contacts'])}")
            print(f"   📁 Media files: {len(parsed_data['media_files'])}")
            print(f"   📊 Total records: {total_records}")
            
            return parsed_data
            
        except Exception as e:
            print(f"❌ Error parsing XML-based UFDR: {e}")
            import traceback
            traceback.print_exc()
            return self._parse_text_based_ufdr_archive(zip_file, file_path)
    
    def _extract_case_info_from_xml(self, root: ET.Element) -> Dict[str, Any]:
        """Extract case information from XML report"""
        case_info = {}
        
        case_elem = root.find('.//case_info')
        if case_elem is not None:
            case_info['case_number'] = case_elem.findtext('case_number', 'Unknown')
            case_info['examiner'] = case_elem.findtext('examiner', 'Unknown')
            case_info['extraction_date'] = case_elem.findtext('extraction_date', '')
        
        return case_info
    
    def _extract_device_info_from_xml(self, root: ET.Element) -> Dict[str, Any]:
        """Extract device information from XML report"""
        device_info = {}
        
        device_elem = root.find('.//device_info')
        if device_elem is not None:
            device_info['manufacturer'] = device_elem.findtext('make', 'Unknown')
            device_info['model'] = device_elem.findtext('model', 'Unknown')
            device_info['imei'] = device_elem.findtext('imei', '')
            device_info['os_version'] = device_elem.findtext('android_version', '')
            device_info['build_number'] = device_elem.findtext('build_number', '')
        
        return device_info
    
    def _extract_sms_from_xml_metadata(self, metadata_section: ET.Element, zip_file: zipfile.ZipFile, local_path: str) -> Optional[Dict[str, Any]]:
        """Extract SMS data from XML metadata"""
        try:
            sms_data = {
                'app_name': 'SMS',
                'message_type': 'text',
                'is_deleted': False,
                'metadata': {'extracted_from': 'xml_report'}
            }
            
            # Extract metadata
            for item in metadata_section.findall('.//item'):
                name = item.get('name', '')
                value = item.text or ''
                
                if name == 'Party':
                    # Determine direction and set sender/receiver
                    direction = None
                    for dir_item in metadata_section.findall('.//item'):
                        if dir_item.get('name') == 'Direction':
                            direction = dir_item.text
                            break
                    
                    if direction == 'Incoming':
                        sms_data['sender_number'] = self._clean_phone_number(value)
                        sms_data['receiver_number'] = 'Device Owner'
                    else:
                        sms_data['sender_number'] = 'Device Owner'
                        sms_data['receiver_number'] = self._clean_phone_number(value)
                
                elif name == 'Message':
                    sms_data['message_content'] = value
                
                elif name == 'Timestamp':
                    sms_data['timestamp'] = self._parse_timestamp(value)
            
            return sms_data if sms_data.get('message_content') else None
            
        except Exception as e:
            print(f"Error extracting SMS: {e}")
            return None
    
    def _extract_contact_from_xml_metadata(self, metadata_section: ET.Element, zip_file: zipfile.ZipFile, local_path: str) -> Optional[Dict[str, Any]]:
        """Extract contact data from XML metadata"""
        try:
            contact_data = {
                'phone_numbers': [],
                'email_addresses': [],
                'metadata': {'extracted_from': 'xml_report'}
            }
            
            # Extract metadata
            for item in metadata_section.findall('.//item'):
                name = item.get('name', '')
                value = item.text or ''
                
                if name == 'Name':
                    contact_data['name'] = value
                elif name == 'Phone':
                    phone = self._clean_phone_number(value)
                    if phone:
                        contact_data['phone_numbers'].append(phone)
                elif name == 'Email':
                    if value and '@' in value:
                        contact_data['email_addresses'].append(value)
            
            return contact_data if contact_data.get('name') else None
            
        except Exception as e:
            print(f"Error extracting contact: {e}")
            return None
    
    def _extract_call_from_xml_metadata(self, metadata_section: ET.Element, zip_file: zipfile.ZipFile, local_path: str) -> Optional[Dict[str, Any]]:
        """Extract call data from XML metadata"""
        try:
            call_data = {
                'metadata': {'extracted_from': 'xml_report'}
            }
            
            # Extract metadata
            for item in metadata_section.findall('.//item'):
                name = item.get('name', '')
                value = item.text or ''
                
                if name == 'Party':
                    # Determine call type and set caller/receiver
                    call_type = None
                    for type_item in metadata_section.findall('.//item'):
                        if type_item.get('name') == 'Type':
                            call_type = type_item.text
                            break
                    
                    if call_type == 'Incoming':
                        call_data['caller_number'] = self._clean_phone_number(value)
                        call_data['receiver_number'] = 'Device Owner'
                        call_data['call_type'] = 'incoming'
                    else:
                        call_data['caller_number'] = 'Device Owner'
                        call_data['receiver_number'] = self._clean_phone_number(value)
                        call_data['call_type'] = 'outgoing'
                
                elif name == 'Duration':
                    call_data['duration'] = int(value) if value.isdigit() else 0
                
                elif name == 'Timestamp':
                    call_data['timestamp'] = self._parse_timestamp(value)
            
            return call_data if call_data.get('caller_number') else None
            
        except Exception as e:
            print(f"Error extracting call: {e}")
            return None
    
    def _extract_media_from_xml_metadata(self, file_elem: ET.Element, metadata_section: ET.Element) -> Optional[Dict[str, Any]]:
        """Extract media file data from XML metadata"""
        try:
            media_data = {
                'file_path': file_elem.get('path', ''),
                'file_size': int(file_elem.get('size', 0)),
                'created_date': datetime.utcnow(),
                'modified_date': datetime.utcnow(),
                'hash_md5': None,
                'hash_sha256': None,
                'metadata': {'extracted_from': 'xml_report'}
            }
            
            # Extract local path as filename
            for item in metadata_section.findall('.//item'):
                if item.get('name') == 'Local Path':
                    local_path = item.text or ''
                    media_data['filename'] = local_path.split('/')[-1] if '/' in local_path else local_path
                    break
            
            # Guess file type from filename
            if media_data.get('filename'):
                media_data['file_type'] = self._guess_file_type(media_data['filename'])
            
            return media_data if media_data.get('filename') else None
            
        except Exception as e:
            print(f"Error extracting media: {e}")
            return None
    
    def _parse_whatsapp_group_chat(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """Parse WhatsApp group chat from text content"""
        messages = []
        
        try:
            lines = content.strip().split('\n')
            
            for line in lines:
                # Parse WhatsApp format: [2024-09-25 10:30:15] John Smith: Hey, are we still meeting today?
                match = re.match(r'\[([^\]]+)\]\s*([^:]+):\s*(.+)', line.strip())
                if match:
                    timestamp_str, sender, message = match.groups()
                    
                    messages.append({
                        'app_name': 'WhatsApp',
                        'sender_number': sender.strip(),
                        'receiver_number': 'Group Chat',
                        'message_content': message.strip(),
                        'timestamp': self._parse_timestamp(timestamp_str),
                        'message_type': 'text',
                        'is_deleted': False,
                        'metadata': {
                            'extracted_from': 'whatsapp_group_chat',
                            'source_file': filename
                        }
                    })
            
            print(f"📱 Extracted {len(messages)} WhatsApp messages from {filename}")
            return messages
            
        except Exception as e:
            print(f"Error parsing WhatsApp chat: {e}")
            return []
    
    def _extract_contacts_from_text(self, content: str) -> List[Dict[str, Any]]:
        """Extract contact information from text content"""
        contacts = []
        
        # Look for name: phone patterns
        name_phone_pattern = r'([A-Za-z\s]+):\s*(\+?1?[-.\s]?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4}))'
        matches = re.findall(name_phone_pattern, content)
        
        for match in matches:
            name = match[0].strip()
            phone = f"+1-{match[2]}-{match[3]}-{match[4]}"
            
            contacts.append({
                'name': name,
                'phone_numbers': [phone],
                'email_addresses': [],
                'metadata': {'extracted_from': 'text_document'}
            })
        
        return contacts
    
    def _extract_media_info_from_text(self, content: str, filename: str) -> Optional[Dict[str, Any]]:
        """Extract media file information from text content"""
        try:
            # Look for common media metadata patterns
            size_match = re.search(r'Size:\s*([0-9.]+\s*[KMGT]?B)', content)
            resolution_match = re.search(r'Resolution:\s*(\d+x\d+)', content)
            gps_match = re.search(r'GPS:\s*([-0-9.]+),\s*([-0-9.]+)', content)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', content)
            
            # Extract original filename if mentioned
            original_filename_match = re.search(r'Original filename:\s*([^\n]+)', content)
            original_filename = original_filename_match.group(1).strip() if original_filename_match else filename
            
            return {
                'filename': original_filename,
                'file_path': f'/extracted/{original_filename}',
                'file_type': 'image/jpeg' if 'jpg' in original_filename.lower() else 'unknown',
                'file_size': self._parse_file_size(size_match.group(1)) if size_match else 0,
                'created_date': datetime.strptime(date_match.group(1), '%Y-%m-%d') if date_match else datetime.utcnow(),
                'modified_date': datetime.strptime(date_match.group(1), '%Y-%m-%d') if date_match else datetime.utcnow(),
                'hash_md5': None,
                'hash_sha256': None,
                'metadata': {
                    'resolution': resolution_match.group(1) if resolution_match else None,
                    'gps_coordinates': f"{gps_match.group(1)}, {gps_match.group(2)}" if gps_match else None,
                    'extracted_from': 'text_metadata'
                }
            }
        except Exception as e:
            print(f"Error extracting media info: {e}")
            return None
    
    def _extract_device_info_from_content(self, content: str, filename: str) -> Dict[str, Any]:
        """Extract device information dynamically from content"""
        device_info = {
            'extraction_source': filename,
            'extraction_date': datetime.utcnow().isoformat()
        }
        
        if not content:
            return device_info
        
        try:
            # Look for device patterns in content
            content_lower = content.lower()
            
            # Extract manufacturer
            if 'apple' in content_lower or 'iphone' in content_lower or 'ios' in content_lower:
                device_info['manufacturer'] = 'Apple'
                device_info['model'] = 'iPhone' if 'iphone' in content_lower else 'iOS Device'
            elif 'samsung' in content_lower or 'galaxy' in content_lower:
                device_info['manufacturer'] = 'Samsung'
                device_info['model'] = 'Galaxy Device'
            elif 'android' in content_lower:
                device_info['manufacturer'] = 'Android'
                device_info['model'] = 'Android Device'
            else:
                device_info['manufacturer'] = 'Unknown'
                device_info['model'] = 'Mobile Device'
            
            # Extract IMEI if present
            imei_match = re.search(r'imei[:\s]*(\d{15})', content_lower)
            if imei_match:
                device_info['imei'] = imei_match.group(1)
            
            # Extract serial number
            serial_match = re.search(r'serial[:\s]*([A-Z0-9]{8,})', content, re.IGNORECASE)
            if serial_match:
                device_info['serial_number'] = serial_match.group(1)
            
            # Extract OS version
            ios_match = re.search(r'ios[:\s]*(\d+\.\d+(?:\.\d+)?)', content_lower)
            android_match = re.search(r'android[:\s]*(\d+(?:\.\d+)?)', content_lower)
            
            if ios_match:
                device_info['os_version'] = f"iOS {ios_match.group(1)}"
            elif android_match:
                device_info['os_version'] = f"Android {android_match.group(1)}"
            
        except Exception as e:
            print(f"Error extracting device info: {e}")
        
        return device_info
    
    def _extract_chat_records_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract chat records dynamically from content"""
        chat_records = []
        
        if not content:
            return chat_records
        
        try:
            # Look for message patterns
            message_patterns = [
                # WhatsApp pattern: [timestamp] sender: message
                r'\[([^\]]+)\]\s*([^:]+):\s*(.+)',
                # SMS pattern: From: +number, To: +number, Message: text
                r'From:\s*([+\d\-\s]+),?\s*To:\s*([+\d\-\s]+),?\s*(?:Message|Text):\s*(.+)',
                # General chat pattern: sender -> receiver: message
                r'([+\d\-\s]+)\s*->\s*([+\d\-\s]+):\s*(.+)',
                # App-based pattern: [App] sender to receiver: message
                r'\[([^\]]+)\]\s*([+\d\-\s]+)\s*to\s*([+\d\-\s]+):\s*(.+)'
            ]
            
            for i, pattern in enumerate(message_patterns):
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                
                for match in matches:
                    try:
                        if i == 0:  # WhatsApp pattern
                            timestamp_str, sender, message = match
                            chat_records.append({
                                'app_name': 'WhatsApp',
                                'sender_number': self._clean_phone_number(sender),
                                'receiver_number': 'Unknown',
                                'message_content': message.strip(),
                                'timestamp': self._parse_timestamp(timestamp_str),
                                'message_type': 'text',
                                'is_deleted': False,
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'whatsapp'}
                            })
                        elif i == 1:  # SMS pattern
                            sender, receiver, message = match
                            chat_records.append({
                                'app_name': 'SMS',
                                'sender_number': self._clean_phone_number(sender),
                                'receiver_number': self._clean_phone_number(receiver),
                                'message_content': message.strip(),
                                'timestamp': datetime.utcnow(),
                                'message_type': 'text',
                                'is_deleted': False,
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'sms'}
                            })
                        elif i == 2:  # General chat pattern
                            sender, receiver, message = match
                            chat_records.append({
                                'app_name': 'Chat',
                                'sender_number': self._clean_phone_number(sender),
                                'receiver_number': self._clean_phone_number(receiver),
                                'message_content': message.strip(),
                                'timestamp': datetime.utcnow(),
                                'message_type': 'text',
                                'is_deleted': False,
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'general'}
                            })
                        elif i == 3:  # App-based pattern
                            app, sender, receiver, message = match
                            chat_records.append({
                                'app_name': app,
                                'sender_number': self._clean_phone_number(sender),
                                'receiver_number': self._clean_phone_number(receiver),
                                'message_content': message.strip(),
                                'timestamp': datetime.utcnow(),
                                'message_type': 'text',
                                'is_deleted': False,
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'app_based'}
                            })
                    except Exception as e:
                        print(f"Error processing chat match: {e}")
                        continue
            
            # Remove duplicates based on content and sender
            seen = set()
            unique_records = []
            for record in chat_records:
                key = (record['sender_number'], record['message_content'][:50])
                if key not in seen:
                    seen.add(key)
                    unique_records.append(record)
            
            print(f"📱 Extracted {len(unique_records)} unique chat records from content")
            return unique_records
            
        except Exception as e:
            print(f"Error extracting chat records: {e}")
            return []
    
    def _extract_call_records_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract call records dynamically from content"""
        call_records = []
        
        if not content:
            return call_records
        
        try:
            # Look for call patterns
            call_patterns = [
                # Call: from +number to +number, duration: X seconds
                r'Call:\s*from\s*([+\d\-\s]+)\s*to\s*([+\d\-\s]+),?\s*duration:\s*(\d+)',
                # Outgoing/Incoming: +number, duration: X
                r'(Outgoing|Incoming):\s*([+\d\-\s]+),?\s*duration:\s*(\d+)',
                # +number called +number for X seconds
                r'([+\d\-\s]+)\s*called\s*([+\d\-\s]+)\s*for\s*(\d+)\s*seconds?',
                # Call log: caller, receiver, duration
                r'([+\d\-\s]+),\s*([+\d\-\s]+),\s*(\d+)'
            ]
            
            for i, pattern in enumerate(call_patterns):
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                
                for match in matches:
                    try:
                        if i == 0:  # Call: from X to Y pattern
                            caller, receiver, duration = match
                            call_records.append({
                                'caller_number': self._clean_phone_number(caller),
                                'receiver_number': self._clean_phone_number(receiver),
                                'call_type': 'outgoing',
                                'duration': int(duration),
                                'timestamp': datetime.utcnow(),
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'call_from_to'}
                            })
                        elif i == 1:  # Outgoing/Incoming pattern
                            call_type, number, duration = match
                            call_records.append({
                                'caller_number': self._clean_phone_number(number) if call_type.lower() == 'outgoing' else 'Unknown',
                                'receiver_number': self._clean_phone_number(number) if call_type.lower() == 'incoming' else 'Unknown',
                                'call_type': call_type.lower(),
                                'duration': int(duration),
                                'timestamp': datetime.utcnow(),
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'call_type'}
                            })
                        elif i == 2:  # X called Y pattern
                            caller, receiver, duration = match
                            call_records.append({
                                'caller_number': self._clean_phone_number(caller),
                                'receiver_number': self._clean_phone_number(receiver),
                                'call_type': 'outgoing',
                                'duration': int(duration),
                                'timestamp': datetime.utcnow(),
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'called_for'}
                            })
                        elif i == 3:  # CSV-like pattern
                            caller, receiver, duration = match
                            call_records.append({
                                'caller_number': self._clean_phone_number(caller),
                                'receiver_number': self._clean_phone_number(receiver),
                                'call_type': 'unknown',
                                'duration': int(duration),
                                'timestamp': datetime.utcnow(),
                                'metadata': {'extracted_from': 'content_analysis', 'pattern': 'csv_like'}
                            })
                    except Exception as e:
                        print(f"Error processing call match: {e}")
                        continue
            
            print(f"📞 Extracted {len(call_records)} call records from content")
            return call_records
            
        except Exception as e:
            print(f"Error extracting call records: {e}")
            return []
    
    def _extract_contacts_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract contacts dynamically from content"""
        contacts = []
        
        if not content:
            return contacts
        
        try:
            # Enhanced contact patterns
            contact_patterns = [
                # Name: +number
                r'([A-Za-z\s]{2,30}):\s*([+\d\-\s\(\)]{8,20})',
                # Contact: Name, +number
                r'Contact:\s*([A-Za-z\s]{2,30}),\s*([+\d\-\s\(\)]{8,20})',
                # Name <email> +number
                r'([A-Za-z\s]{2,30})\s*<([^>]+@[^>]+)>\s*([+\d\-\s\(\)]{8,20})',
                # Name - +number - email
                r'([A-Za-z\s]{2,30})\s*-\s*([+\d\-\s\(\)]{8,20})\s*-\s*([^@\s]+@[^\s]+)'
            ]
            
            seen_contacts = set()
            
            for i, pattern in enumerate(contact_patterns):
                matches = re.findall(pattern, content, re.MULTILINE)
                
                for match in matches:
                    try:
                        if i == 0:  # Name: +number
                            name, phone = match
                            name = name.strip()
                            phone = self._clean_phone_number(phone)
                            
                            if name and phone and (name, phone) not in seen_contacts:
                                seen_contacts.add((name, phone))
                                contacts.append({
                                    'name': name,
                                    'phone_numbers': [phone],
                                    'email_addresses': [],
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'name_phone'}
                                })
                        elif i == 1:  # Contact: Name, +number
                            name, phone = match
                            name = name.strip()
                            phone = self._clean_phone_number(phone)
                            
                            if name and phone and (name, phone) not in seen_contacts:
                                seen_contacts.add((name, phone))
                                contacts.append({
                                    'name': name,
                                    'phone_numbers': [phone],
                                    'email_addresses': [],
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'contact_format'}
                                })
                        elif i == 2:  # Name <email> +number
                            name, email, phone = match
                            name = name.strip()
                            phone = self._clean_phone_number(phone)
                            
                            if name and phone and (name, phone) not in seen_contacts:
                                seen_contacts.add((name, phone))
                                contacts.append({
                                    'name': name,
                                    'phone_numbers': [phone],
                                    'email_addresses': [email.strip()],
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'name_email_phone'}
                                })
                        elif i == 3:  # Name - +number - email
                            name, phone, email = match
                            name = name.strip()
                            phone = self._clean_phone_number(phone)
                            
                            if name and phone and (name, phone) not in seen_contacts:
                                seen_contacts.add((name, phone))
                                contacts.append({
                                    'name': name,
                                    'phone_numbers': [phone],
                                    'email_addresses': [email.strip()],
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'name_phone_email'}
                                })
                    except Exception as e:
                        print(f"Error processing contact match: {e}")
                        continue
            
            print(f"👥 Extracted {len(contacts)} unique contacts from content")
            return contacts
            
        except Exception as e:
            print(f"Error extracting contacts: {e}")
            return []
    
    def _extract_media_files_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract media files dynamically from content"""
        media_files = []
        
        if not content:
            return media_files
        
        try:
            # Media file patterns
            media_patterns = [
                # File: filename.ext, Size: X, Type: Y
                r'File:\s*([^\s,]+\.[a-zA-Z0-9]{2,4}),?\s*Size:\s*([^,]+),?\s*Type:\s*([^\n,]+)',
                # filename.ext (size, type)
                r'([^\s]+\.[a-zA-Z0-9]{2,4})\s*\(([^,)]+),?\s*([^)]+)\)',
                # Media: filename, size, date
                r'Media:\s*([^,]+),\s*([^,]+),\s*([^\n]+)',
                # Just filenames with extensions
                r'([A-Za-z0-9_\-]+\.[a-zA-Z0-9]{2,4})'
            ]
            
            seen_files = set()
            
            for i, pattern in enumerate(media_patterns):
                matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
                
                for match in matches:
                    try:
                        if i == 0:  # File: filename, Size: X, Type: Y
                            filename, size, file_type = match
                            if filename not in seen_files:
                                seen_files.add(filename)
                                media_files.append({
                                    'filename': filename.strip(),
                                    'file_path': f'/extracted/{filename.strip()}',
                                    'file_type': file_type.strip(),
                                    'file_size': self._parse_file_size(size.strip()),
                                    'created_date': datetime.utcnow(),
                                    'modified_date': datetime.utcnow(),
                                    'hash_md5': None,
                                    'hash_sha256': None,
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'file_size_type'}
                                })
                        elif i == 1:  # filename (size, type)
                            filename, size, file_type = match
                            if filename not in seen_files:
                                seen_files.add(filename)
                                media_files.append({
                                    'filename': filename.strip(),
                                    'file_path': f'/extracted/{filename.strip()}',
                                    'file_type': file_type.strip(),
                                    'file_size': self._parse_file_size(size.strip()),
                                    'created_date': datetime.utcnow(),
                                    'modified_date': datetime.utcnow(),
                                    'hash_md5': None,
                                    'hash_sha256': None,
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'filename_parentheses'}
                                })
                        elif i == 2:  # Media: filename, size, date
                            filename, size, date_str = match
                            if filename not in seen_files:
                                seen_files.add(filename)
                                media_files.append({
                                    'filename': filename.strip(),
                                    'file_path': f'/extracted/{filename.strip()}',
                                    'file_type': self._guess_file_type(filename),
                                    'file_size': self._parse_file_size(size.strip()),
                                    'created_date': self._parse_timestamp(date_str.strip()) or datetime.utcnow(),
                                    'modified_date': self._parse_timestamp(date_str.strip()) or datetime.utcnow(),
                                    'hash_md5': None,
                                    'hash_sha256': None,
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'media_format'}
                                })
                        elif i == 3:  # Just filenames
                            filename = match
                            if filename not in seen_files and len(filename) > 3:  # Avoid false positives
                                seen_files.add(filename)
                                media_files.append({
                                    'filename': filename.strip(),
                                    'file_path': f'/extracted/{filename.strip()}',
                                    'file_type': self._guess_file_type(filename),
                                    'file_size': 0,
                                    'created_date': datetime.utcnow(),
                                    'modified_date': datetime.utcnow(),
                                    'hash_md5': None,
                                    'hash_sha256': None,
                                    'metadata': {'extracted_from': 'content_analysis', 'pattern': 'filename_only'}
                                })
                    except Exception as e:
                        print(f"Error processing media match: {e}")
                        continue
            
            print(f"📁 Extracted {len(media_files)} media files from content")
            return media_files
            
        except Exception as e:
            print(f"Error extracting media files: {e}")
            return []
    
    def _guess_file_type(self, filename: str) -> str:
        """Guess file type from extension"""
        ext = Path(filename).suffix.lower()
        
        type_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif',
            '.mp4': 'video/mp4', '.avi': 'video/avi', '.mov': 'video/quicktime',
            '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4',
            '.pdf': 'application/pdf', '.doc': 'application/msword', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain', '.csv': 'text/csv', '.json': 'application/json', '.xml': 'application/xml'
        }
        
        return type_map.get(ext, 'application/octet-stream')
    
    def _create_dynamic_data_from_content(self, file_path: str, content: str = None) -> Dict[str, Any]:
        """Create forensic data by analyzing file content dynamically - NO HARDCODED VALUES"""
        filename = Path(file_path).name.lower()
        
        # Extract case information from filename
        case_match = re.search(r'case[-_](\d{4}[-_]\d{3})', filename)
        case_number = case_match.group(1).replace('_', '-') if case_match else f"extracted-{datetime.now().strftime('%Y-%m-%d')}"
        
        print(f"🔍 Dynamically analyzing content for case: {case_number}")
        
        # Initialize empty data structure
        dynamic_data = {
            'device_info': self._extract_device_info_from_content(content, filename),
            'chat_records': self._extract_chat_records_from_content(content),
            'call_records': self._extract_call_records_from_content(content),
            'contacts': self._extract_contacts_from_content(content),
            'media_files': self._extract_media_files_from_content(content),
            'metadata': {
                'extraction_date': datetime.utcnow(),
                'case_info': {
                    'case_number': case_number,
                    'description': f'Dynamic forensic analysis - Case {case_number}',
                    'extraction_method': 'Content Analysis'
                }
            }
        }
        
        total_records = (len(dynamic_data['chat_records']) + len(dynamic_data['call_records']) + 
                        len(dynamic_data['contacts']) + len(dynamic_data['media_files']))
        
        print(f"📊 Dynamically extracted {total_records} total records from content analysis")
        return dynamic_data
    
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
        """Parse JSON format UFDR files with robust error handling"""
        try:
            # First try standard JSON parsing
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            print(f"📊 JSON data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing error: {e}")
            print("🔧 Attempting to fix malformed JSON...")
            
            # Try to fix common JSON issues
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                # Fix common JSON issues
                fixed_content = self._fix_malformed_json(content)
                data = json.loads(fixed_content)
                print("✅ Successfully fixed and parsed malformed JSON")
                
            except Exception as fix_error:
                print(f"❌ Could not fix JSON: {fix_error}")
                print("🔄 Falling back to dynamic content analysis")
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return self._create_dynamic_data_from_content(file_path, content)
                except:
                    return self._create_dynamic_data_from_content(file_path, None)
        
        except Exception as e:
            print(f"❌ Error reading JSON file: {e}")
            print("🔄 Falling back to dynamic content analysis")
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return self._create_dynamic_data_from_content(file_path, content)
            except:
                return self._create_dynamic_data_from_content(file_path, None)
        
        try:
            # Handle different JSON structures
            if isinstance(data, list):
                # If it's a list, assume it's a list of records
                parsed_data = self._parse_json_record_list(data)
            elif isinstance(data, dict):
                # If it's a dict, extract data based on common UFDR structures
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
            else:
                print("⚠️ Unexpected JSON structure, trying dynamic content analysis")
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return self._create_dynamic_data_from_content(file_path, content)
                except:
                    return self._create_dynamic_data_from_content(file_path, None)
            
            # Log what we found
            print(f"📱 Found {len(parsed_data.get('chat_records', []))} chat records")
            print(f"📞 Found {len(parsed_data.get('call_records', []))} call records")
            print(f"👥 Found {len(parsed_data.get('contacts', []))} contacts")
            print(f"📁 Found {len(parsed_data.get('media_files', []))} media files")
            
            return parsed_data
            
        except Exception as e:
            print(f"❌ Error processing JSON data: {e}")
            print("🔄 Falling back to dynamic content analysis")
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return self._create_dynamic_data_from_content(file_path, content)
            except:
                return self._create_dynamic_data_from_content(file_path, None)
    
    def _fix_malformed_json(self, content: str) -> str:
        """Attempt to fix common JSON formatting issues"""
        import re
        
        # Remove trailing commas before closing brackets/braces
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Fix unescaped quotes in strings (basic attempt)
        # This is a simple fix and might not work for all cases
        content = re.sub(r'(?<!\\)"(?=[^,}\]]*[,}\]])', r'\\"', content)
        
        # Remove any trailing commas at the end of objects/arrays
        content = re.sub(r',(\s*})$', r'\1', content, flags=re.MULTILINE)
        content = re.sub(r',(\s*])$', r'\1', content, flags=re.MULTILINE)
        
        # Try to fix incomplete JSON by adding closing braces if needed
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        if open_braces > 0:
            content += '}' * open_braces
        if open_brackets > 0:
            content += ']' * open_brackets
        
        return content
    
    def _parse_tabular_ufdr(self, file_path: str) -> Dict[str, Any]:
        """Parse CSV/Excel format UFDR files"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            print(f"📊 Tabular data shape: {df.shape}")
            print(f"📋 Columns: {list(df.columns)}")
            
            # Try to identify data type based on columns
            columns_lower = [col.lower() for col in df.columns]
            
            if any(col in columns_lower for col in ['message', 'text', 'content', 'chat']):
                # This looks like chat data
                chat_records = self._extract_chat_records_tabular(df)
                parsed_data = {
                    'device_info': {},
                    'chat_records': chat_records,
                    'call_records': [],
                    'contacts': [],
                    'media_files': [],
                    'metadata': {'extraction_date': datetime.utcnow()}
                }
            elif any(col in columns_lower for col in ['call', 'duration', 'caller']):
                # This looks like call data
                call_records = self._extract_call_records_tabular(df)
                parsed_data = {
                    'device_info': {},
                    'chat_records': [],
                    'call_records': call_records,
                    'contacts': [],
                    'media_files': [],
                    'metadata': {'extraction_date': datetime.utcnow()}
                }
            elif any(col in columns_lower for col in ['name', 'contact', 'phone']):
                # This looks like contact data
                contacts = self._extract_contacts_tabular(df)
                parsed_data = {
                    'device_info': {},
                    'chat_records': [],
                    'call_records': [],
                    'contacts': contacts,
                    'media_files': [],
                    'metadata': {'extraction_date': datetime.utcnow()}
                }
            else:
                # Try to extract all types
                parsed_data = {
                    'device_info': self._extract_device_info_tabular(df),
                    'chat_records': self._extract_chat_records_tabular(df),
                    'call_records': self._extract_call_records_tabular(df),
                    'contacts': self._extract_contacts_tabular(df),
                    'media_files': self._extract_media_files_tabular(df),
                    'metadata': {'extraction_date': datetime.utcnow()}
                }
            
            # Log what we found
            print(f"📱 Extracted {len(parsed_data.get('chat_records', []))} chat records")
            print(f"📞 Extracted {len(parsed_data.get('call_records', []))} call records")
            print(f"👥 Extracted {len(parsed_data.get('contacts', []))} contacts")
            print(f"📁 Extracted {len(parsed_data.get('media_files', []))} media files")
            
            return parsed_data
            
        except Exception as e:
            print(f"❌ Error parsing tabular UFDR: {e}")
            print("🔄 Falling back to dynamic content analysis")
            try:
                # Try to read as text for content analysis
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return self._create_dynamic_data_from_content(file_path, content)
            except:
                return self._create_dynamic_data_from_content(file_path, None)
    
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
    
    def _parse_json_record_list(self, data: List) -> Dict[str, Any]:
        """Parse JSON data that's a list of records"""
        chat_records = []
        call_records = []
        contacts = []
        media_files = []
        
        for record in data:
            if isinstance(record, dict):
                # Try to identify record type based on fields
                if 'message' in record or 'text' in record or 'content' in record:
                    chat_records.append(self._normalize_chat_record(record))
                elif 'call_type' in record or 'duration' in record or 'caller' in record:
                    call_records.append(self._normalize_call_record(record))
                elif 'name' in record and ('phone' in record or 'number' in record):
                    contacts.append(self._normalize_contact_record(record))
                elif 'filename' in record or 'file_path' in record:
                    media_files.append(self._normalize_media_record(record))
        
        return {
            'device_info': {},
            'chat_records': chat_records,
            'call_records': call_records,
            'contacts': contacts,
            'media_files': media_files,
            'metadata': {'extraction_date': datetime.utcnow()}
        }
    
    def _normalize_chat_record(self, record: Dict) -> Dict[str, Any]:
        """Normalize a chat record from various formats"""
        return {
            'app_name': record.get('app_name') or record.get('app') or record.get('source') or 'Unknown',
            'sender_number': record.get('sender_number') or record.get('sender') or record.get('from') or 'Unknown',
            'receiver_number': record.get('receiver_number') or record.get('receiver') or record.get('to') or 'Unknown',
            'message_content': record.get('message_content') or record.get('message') or record.get('text') or record.get('content') or '',
            'timestamp': self._parse_timestamp(record.get('timestamp') or record.get('date') or record.get('time')),
            'message_type': record.get('message_type') or record.get('type') or 'text',
            'is_deleted': record.get('is_deleted', False),
            'metadata': {k: v for k, v in record.items() if k not in ['app_name', 'sender_number', 'receiver_number', 'message_content', 'timestamp', 'message_type', 'is_deleted']}
        }
    
    def _normalize_call_record(self, record: Dict) -> Dict[str, Any]:
        """Normalize a call record from various formats"""
        return {
            'caller_number': record.get('caller_number') or record.get('caller') or record.get('from') or 'Unknown',
            'receiver_number': record.get('receiver_number') or record.get('receiver') or record.get('to') or 'Unknown',
            'call_type': record.get('call_type') or record.get('type') or 'unknown',
            'duration': self._parse_duration(record.get('duration')),
            'timestamp': self._parse_timestamp(record.get('timestamp') or record.get('date') or record.get('time')),
            'metadata': {k: v for k, v in record.items() if k not in ['caller_number', 'receiver_number', 'call_type', 'duration', 'timestamp']}
        }
    
    def _normalize_contact_record(self, record: Dict) -> Dict[str, Any]:
        """Normalize a contact record from various formats"""
        phone_numbers = []
        if record.get('phone_numbers'):
            phone_numbers = record['phone_numbers'] if isinstance(record['phone_numbers'], list) else [record['phone_numbers']]
        elif record.get('phone'):
            phone_numbers = [record['phone']]
        elif record.get('number'):
            phone_numbers = [record['number']]
        
        email_addresses = []
        if record.get('email_addresses'):
            email_addresses = record['email_addresses'] if isinstance(record['email_addresses'], list) else [record['email_addresses']]
        elif record.get('email'):
            email_addresses = [record['email']]
        
        return {
            'name': record.get('name') or 'Unknown',
            'phone_numbers': phone_numbers,
            'email_addresses': email_addresses,
            'metadata': {k: v for k, v in record.items() if k not in ['name', 'phone_numbers', 'email_addresses', 'phone', 'number', 'email']}
        }
    
    def _normalize_media_record(self, record: Dict) -> Dict[str, Any]:
        """Normalize a media file record from various formats"""
        return {
            'filename': record.get('filename') or record.get('name') or 'Unknown',
            'file_path': record.get('file_path') or record.get('path') or '',
            'file_type': record.get('file_type') or record.get('type') or record.get('mime_type') or 'unknown',
            'file_size': self._parse_file_size(record.get('file_size') or record.get('size')),
            'created_date': self._parse_timestamp(record.get('created_date') or record.get('created') or record.get('date')),
            'modified_date': self._parse_timestamp(record.get('modified_date') or record.get('modified')),
            'hash_md5': record.get('hash_md5') or record.get('md5'),
            'hash_sha256': record.get('hash_sha256') or record.get('sha256'),
            'metadata': {k: v for k, v in record.items() if k not in ['filename', 'file_path', 'file_type', 'file_size', 'created_date', 'modified_date', 'hash_md5', 'hash_sha256']}
        }

    # JSON and tabular extraction methods (enhanced versions)
    def _extract_device_info_json(self, data: Dict) -> Dict[str, Any]:
        """Extract device info from JSON with multiple possible structures"""
        device_info = data.get('device_info', {})
        if not device_info:
            # Try other common field names
            device_info = data.get('device', {}) or data.get('phone_info', {}) or data.get('mobile_info', {})
        return device_info
    
    def _extract_chat_records_json(self, data: Dict) -> List[Dict[str, Any]]:
        """Extract chat records from JSON with multiple possible structures"""
        chat_records = data.get('chat_records', [])
        if not chat_records:
            # Try other common field names
            chat_records = (data.get('messages', []) or 
                          data.get('chats', []) or 
                          data.get('sms', []) or 
                          data.get('communications', []))
        
        # Normalize the records
        normalized_records = []
        for record in chat_records:
            if isinstance(record, dict):
                normalized_records.append(self._normalize_chat_record(record))
        
        return normalized_records
    
    def _extract_call_records_json(self, data: Dict) -> List[Dict[str, Any]]:
        """Extract call records from JSON with multiple possible structures"""
        call_records = data.get('call_records', [])
        if not call_records:
            # Try other common field names
            call_records = (data.get('calls', []) or 
                          data.get('call_logs', []) or 
                          data.get('phone_calls', []))
        
        # Normalize the records
        normalized_records = []
        for record in call_records:
            if isinstance(record, dict):
                normalized_records.append(self._normalize_call_record(record))
        
        return normalized_records
    
    def _extract_contacts_json(self, data: Dict) -> List[Dict[str, Any]]:
        """Extract contacts from JSON with multiple possible structures"""
        contacts = data.get('contacts', [])
        if not contacts:
            # Try other common field names
            contacts = (data.get('phonebook', []) or 
                       data.get('address_book', []) or 
                       data.get('people', []))
        
        # Normalize the records
        normalized_records = []
        for record in contacts:
            if isinstance(record, dict):
                normalized_records.append(self._normalize_contact_record(record))
        
        return normalized_records
    
    def _extract_media_files_json(self, data: Dict) -> List[Dict[str, Any]]:
        """Extract media files from JSON with multiple possible structures"""
        media_files = data.get('media_files', [])
        if not media_files:
            # Try other common field names
            media_files = (data.get('files', []) or 
                          data.get('media', []) or 
                          data.get('attachments', []))
        
        # Normalize the records
        normalized_records = []
        for record in media_files:
            if isinstance(record, dict):
                normalized_records.append(self._normalize_media_record(record))
        
        return normalized_records
    
    def _extract_device_info_tabular(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract device info from tabular data"""
        # Look for device info in the first row or metadata
        device_info = {}
        for col in df.columns:
            if 'device' in col.lower() or 'phone' in col.lower() or 'model' in col.lower():
                if not df[col].empty:
                    device_info[col.lower()] = str(df[col].iloc[0])
        return device_info
    
    def _extract_chat_records_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract chat records from tabular data"""
        chat_records = []
        
        # Map common column names
        column_mapping = {
            'app_name': ['app', 'application', 'source', 'platform'],
            'sender_number': ['sender', 'from', 'from_number', 'sender_number'],
            'receiver_number': ['receiver', 'to', 'to_number', 'receiver_number'],
            'message_content': ['message', 'text', 'content', 'body'],
            'timestamp': ['timestamp', 'date', 'time', 'datetime'],
            'message_type': ['type', 'message_type']
        }
        
        # Find the actual column names
        actual_columns = {}
        for target_col, possible_names in column_mapping.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    actual_columns[target_col] = col
                    break
        
        # Extract records if we have the minimum required columns
        if 'message_content' in actual_columns or any(col in df.columns for col in ['message', 'text', 'content']):
            for _, row in df.iterrows():
                record = {}
                for target_col, actual_col in actual_columns.items():
                    if pd.notna(row[actual_col]):
                        if target_col == 'timestamp':
                            record[target_col] = self._parse_timestamp(str(row[actual_col]))
                        else:
                            record[target_col] = str(row[actual_col])
                
                # Set defaults for missing fields
                record.setdefault('app_name', 'Unknown')
                record.setdefault('sender_number', 'Unknown')
                record.setdefault('receiver_number', 'Unknown')
                record.setdefault('message_content', '')
                record.setdefault('message_type', 'text')
                record.setdefault('is_deleted', False)
                record.setdefault('metadata', {})
                
                if record['message_content']:  # Only add if there's actual content
                    chat_records.append(record)
        
        return chat_records
    
    def _extract_call_records_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract call records from tabular data"""
        call_records = []
        
        # Map common column names
        column_mapping = {
            'caller_number': ['caller', 'from', 'from_number', 'caller_number'],
            'receiver_number': ['receiver', 'to', 'to_number', 'receiver_number'],
            'call_type': ['type', 'call_type', 'direction'],
            'duration': ['duration', 'length', 'time'],
            'timestamp': ['timestamp', 'date', 'time', 'datetime']
        }
        
        # Find the actual column names
        actual_columns = {}
        for target_col, possible_names in column_mapping.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    actual_columns[target_col] = col
                    break
        
        # Extract records if we have call-related columns
        if any(col in df.columns for col in ['duration', 'call_type', 'caller']):
            for _, row in df.iterrows():
                record = {}
                for target_col, actual_col in actual_columns.items():
                    if pd.notna(row[actual_col]):
                        if target_col == 'timestamp':
                            record[target_col] = self._parse_timestamp(str(row[actual_col]))
                        elif target_col == 'duration':
                            record[target_col] = self._parse_duration(str(row[actual_col]))
                        else:
                            record[target_col] = str(row[actual_col])
                
                # Set defaults for missing fields
                record.setdefault('caller_number', 'Unknown')
                record.setdefault('receiver_number', 'Unknown')
                record.setdefault('call_type', 'unknown')
                record.setdefault('duration', 0)
                record.setdefault('metadata', {})
                
                call_records.append(record)
        
        return call_records
    
    def _extract_contacts_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract contacts from tabular data"""
        contacts = []
        
        # Map common column names
        column_mapping = {
            'name': ['name', 'contact_name', 'display_name'],
            'phone_numbers': ['phone', 'number', 'phone_number', 'mobile'],
            'email_addresses': ['email', 'email_address']
        }
        
        # Find the actual column names
        actual_columns = {}
        for target_col, possible_names in column_mapping.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    actual_columns[target_col] = col
                    break
        
        # Extract records if we have contact-related columns
        if 'name' in actual_columns or any(col in df.columns for col in ['name', 'contact', 'phone']):
            for _, row in df.iterrows():
                record = {}
                
                # Extract name
                if 'name' in actual_columns and pd.notna(row[actual_columns['name']]):
                    record['name'] = str(row[actual_columns['name']])
                else:
                    record['name'] = 'Unknown'
                
                # Extract phone numbers
                phone_numbers = []
                if 'phone_numbers' in actual_columns and pd.notna(row[actual_columns['phone_numbers']]):
                    phone_str = str(row[actual_columns['phone_numbers']])
                    # Handle multiple phone numbers separated by commas or semicolons
                    phone_numbers = [p.strip() for p in re.split('[,;]', phone_str) if p.strip()]
                record['phone_numbers'] = phone_numbers
                
                # Extract email addresses
                email_addresses = []
                if 'email_addresses' in actual_columns and pd.notna(row[actual_columns['email_addresses']]):
                    email_str = str(row[actual_columns['email_addresses']])
                    # Handle multiple emails separated by commas or semicolons
                    email_addresses = [e.strip() for e in re.split('[,;]', email_str) if e.strip()]
                record['email_addresses'] = email_addresses
                
                record['metadata'] = {}
                
                # Only add if we have meaningful data
                if record['name'] != 'Unknown' or phone_numbers or email_addresses:
                    contacts.append(record)
        
        return contacts
    
    def _extract_media_files_tabular(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract media files from tabular data"""
        media_files = []
        
        # Map common column names
        column_mapping = {
            'filename': ['filename', 'name', 'file_name'],
            'file_path': ['path', 'file_path', 'location'],
            'file_type': ['type', 'file_type', 'mime_type'],
            'file_size': ['size', 'file_size'],
            'created_date': ['created', 'created_date', 'date_created'],
            'modified_date': ['modified', 'modified_date', 'date_modified']
        }
        
        # Find the actual column names
        actual_columns = {}
        for target_col, possible_names in column_mapping.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    actual_columns[target_col] = col
                    break
        
        # Extract records if we have file-related columns
        if any(col in df.columns for col in ['filename', 'file_name', 'name']):
            for _, row in df.iterrows():
                record = {}
                for target_col, actual_col in actual_columns.items():
                    if pd.notna(row[actual_col]):
                        if target_col in ['created_date', 'modified_date']:
                            record[target_col] = self._parse_timestamp(str(row[actual_col]))
                        elif target_col == 'file_size':
                            record[target_col] = self._parse_file_size(str(row[actual_col]))
                        else:
                            record[target_col] = str(row[actual_col])
                
                # Set defaults for missing fields
                record.setdefault('filename', 'Unknown')
                record.setdefault('file_path', '')
                record.setdefault('file_type', 'unknown')
                record.setdefault('file_size', 0)
                record.setdefault('hash_md5', None)
                record.setdefault('hash_sha256', None)
                record.setdefault('metadata', {})
                
                if record['filename'] != 'Unknown':  # Only add if we have a filename
                    media_files.append(record)
        
        return media_files