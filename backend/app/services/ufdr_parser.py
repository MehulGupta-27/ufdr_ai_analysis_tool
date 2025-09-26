import xml.etree.ElementTree as ET
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import zipfile
import tempfile
from pathlib import Path
import sqlite3
import pandas as pd


class UFDRParser:
    def __init__(self):
        self.supported_formats = ['.ufdr']
    
    def parse_ufdr_file(self, file_path: str) -> Dict[str, Any]:
        """Parse .ufdr files in a dynamic way:
        - If the file is a ZIP archive (typical UFDR), use report.xml + SQLite/CSV/JSON introspection
        - If the file is a JSON payload (some tools export JSON with .ufdr extension), map it directly
        """
        file_extension = Path(file_path).suffix.lower()
        if file_extension != '.ufdr':
            raise Exception("Only .ufdr files are supported")

        # Branch 1: Standard ZIP-based UFDR
        if zipfile.is_zipfile(file_path):
            print(f"🔍 Parsing UFDR archive (ZIP): {file_path}")
            with zipfile.ZipFile(file_path, 'r') as zf:
                report_xml_path = self._find_report_xml(zf)
                report_root = None
                if report_xml_path:
                    report_root = self._read_report_xml(zf, report_xml_path)
                    path_map = self._build_path_map_from_report(report_root)
                else:
                    # Proceed without report.xml for vendor variants
                    path_map = {}
                
                parsed: Dict[str, Any] = {
                    'device_info': self._extract_device_info_from_report(report_root) if report_root is not None else {},
                    'chat_records': [],
                    'call_records': [],
                    'contacts': [],
                    'media_files': [],
                    'metadata': {
                        'extraction_date': datetime.utcnow(),
                        'case_info': self._extract_case_info_from_report(report_root) if report_root is not None else {}
                    }
                }
                
                # Iterate all SQLite databases inside the archive and extract
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    lower_name = member.filename.lower()
                    if lower_name.endswith(('.db', '.sqlite', '.sqlite3')):
                        try:
                            with zf.open(member) as dbstream:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(member.filename).suffix) as tf:
                                    tf.write(dbstream.read())
                                    temp_db_path = tf.name
                            try:
                                self._extract_from_sqlite(
                                    temp_db_path,
                                    member.filename,
                                    path_map,
                                    parsed
                                )
                            finally:
                                if os.path.exists(temp_db_path):
                                    os.unlink(temp_db_path)
                        except Exception as e:
                            print(f"⚠️ SQLite extraction error for {member.filename}: {e}")
                            continue
                    elif lower_name.endswith('.csv'):
                        try:
                            with zf.open(member) as f:
                                df = pd.read_csv(f)
                            self._extract_from_dataframe(member.filename, df, parsed)
                        except Exception as e:
                            print(f"⚠️ CSV extraction error for {member.filename}: {e}")
                            continue
                    elif lower_name.endswith('.json'):
                        try:
                            with zf.open(member) as f:
                                # Try both tabular JSON and structured object JSON
                                try:
                                    df = pd.read_json(f)
                                    self._extract_from_dataframe(member.filename, df, parsed)
                                except Exception:
                                    f.seek(0)
                                    data_obj = json.load(f)
                                    self._extract_from_json_object(member.filename, data_obj, parsed)
                        except Exception as e:
                            print(f"⚠️ JSON extraction error for {member.filename}: {e}")
                            continue
                
                print(
                    f"✅ UFDR extraction (ZIP): chats={len(parsed['chat_records'])}, calls={len(parsed['call_records'])}, contacts={len(parsed['contacts'])}, media={len(parsed['media_files'])}"
                )
                return parsed

        # Branch 2: JSON file with .ufdr extension
        print(f"🔍 Parsing UFDR JSON payload: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise Exception(f"Failed to read UFDR JSON: {e}")

        parsed: Dict[str, Any] = {
            'device_info': data.get('device_info', {}),
            'chat_records': [],
            'call_records': [],
            'contacts': [],
            'media_files': [],
            'metadata': data.get('metadata', {'extraction_date': datetime.utcnow()})
        }

        # First, try direct mapping if keys exist
        try:
            # Chats
            for chat in data.get('chat_records', []) or []:
                parsed['chat_records'].append({
                    'app_name': chat.get('app_name'),
                    'sender_number': chat.get('sender_number'),
                    'receiver_number': chat.get('receiver_number'),
                    'message_content': chat.get('message_content'),
                    'timestamp': self._coerce_timestamp(chat.get('timestamp')),
                    'message_type': chat.get('message_type', 'text'),
                    'is_deleted': bool(chat.get('is_deleted', False)),
                    'metadata': chat.get('metadata', {})
                })
            # Calls
            for call in data.get('call_records', []) or []:
                parsed['call_records'].append({
                    'caller_number': call.get('caller_number'),
                    'receiver_number': call.get('receiver_number'),
                    'call_type': call.get('call_type', 'unknown'),
                    'duration': int(call.get('duration', 0)) if call.get('duration') is not None else 0,
                    'timestamp': self._coerce_timestamp(call.get('timestamp')),
                    'metadata': call.get('metadata', {})
                })
            # Contacts
            for contact in data.get('contacts', []) or []:
                parsed['contacts'].append({
                    'name': contact.get('name'),
                    'phone_numbers': contact.get('phone_numbers', []) or [],
                    'email_addresses': contact.get('email_addresses', []) or [],
                    'metadata': contact.get('metadata', {})
                })
            # Media
            for media in data.get('media_files', []) or []:
                parsed['media_files'].append({
                    'filename': media.get('filename'),
                    'file_path': media.get('file_path'),
                    'file_type': media.get('file_type'),
                    'file_size': int(media.get('file_size', 0)) if media.get('file_size') is not None else 0,
                    'created_date': self._coerce_timestamp(media.get('created_date')),
                    'modified_date': self._coerce_timestamp(media.get('modified_date')),
                    'hash_md5': media.get('hash_md5'),
                    'hash_sha256': media.get('hash_sha256'),
                    'metadata': media.get('metadata', {})
                })
        except Exception:
            pass

        # Then, recursively traverse to capture any vendor-specific nesting
        self._traverse_and_extract(data, parsed)

        print(
            f"✅ UFDR extraction (JSON): chats={len(parsed['chat_records'])}, calls={len(parsed['call_records'])}, contacts={len(parsed['contacts'])}, media={len(parsed['media_files'])}"
        )
        return parsed
    
    def _find_report_xml(self, zf: zipfile.ZipFile) -> Optional[str]:
        for name in zf.namelist():
            lower = name.lower()
            if lower.endswith('.xml') and 'report' in lower:
                return name
        # Fallback: any xml
        for name in zf.namelist():
            if name.lower().endswith('.xml'):
                return name
        return None

    def _read_report_xml(self, zf: zipfile.ZipFile, xml_path: str) -> ET.Element:
        with zf.open(xml_path) as f:
            content = f.read().decode('utf-8', errors='ignore')
        return ET.fromstring(content)

    def _build_path_map_from_report(self, root: ET.Element) -> Dict[str, Dict[str, Any]]:
        """Build mapping of categorized items back to their local/original paths from report.xml.
        Returns dict indexed by any available identifier/path with metadata.
        """
        path_map: Dict[str, Dict[str, Any]] = {}
        for file_elem in root.findall('.//file'):
            info: Dict[str, Any] = {}
            # capture attributes
            for attr in ['id', 'name', 'path', 'size', 'type']:
                val = file_elem.get(attr)
                if val is not None:
                    info[attr] = val
            # capture metadata local path and section
            metadata_section = file_elem.find('.//metadata')
            if metadata_section is not None:
                local_path = None
                section = metadata_section.get('section')
                for item in metadata_section.findall('.//item'):
                    if item.get('name') == 'Local Path':
                        local_path = item.text
                        break
                if section:
                    info['section'] = section
                if local_path:
                    info['local_path'] = local_path
                    path_map[local_path] = info
            # fallback index by file path if present
            if 'path' in info:
                path_map.setdefault(info['path'], info)
        return path_map

    def _extract_device_info_from_report(self, root: ET.Element) -> Dict[str, Any]:
        device_info: Dict[str, Any] = {}
        device_elem = root.find('.//device_info') or root.find('.//device') or root.find('.//Device')
        if device_elem is not None:
            for tag in ['make', 'model', 'imei', 'android_version', 'build_number', 'os_version', 'manufacturer']:
                val = device_elem.findtext(tag)
                if val:
                    # normalize keys
                    key = 'manufacturer' if tag in ['make', 'manufacturer'] else tag
                    device_info[key] = val
        return device_info

    def _extract_case_info_from_report(self, root: ET.Element) -> Dict[str, Any]:
        case_info: Dict[str, Any] = {}
        case_elem = root.find('.//case_info') or root.find('.//case') or root.find('.//Case')
        if case_elem is not None:
            for tag in ['case_number', 'examiner', 'description', 'extraction_date', 'number', 'investigator']:
                val = case_elem.findtext(tag)
                if val:
                    key = 'case_number' if tag == 'number' else tag
                    case_info[key] = val
        return case_info

    def _extract_from_sqlite(
        self,
        db_path: str,
        archive_member_path: str,
        path_map: Dict[str, Dict[str, Any]],
        parsed: Dict[str, Any]
    ) -> None:
        """Open SQLite, introspect tables/columns, and extract records into parsed structure."""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            schema: Dict[str, List[str]] = {}
            for t in tables:
                cols = [r[1] for r in cursor.execute(f"PRAGMA table_info('{t}')")]
                schema[t] = cols
            
            # Extract chats (WhatsApp/SMS-like)
            self._extract_chats(cursor, schema, parsed)
            # Extract calls
            self._extract_calls(cursor, schema, parsed)
            # Extract contacts
            self._extract_contacts(cursor, schema, parsed)
            # Extract media metadata (if present in DB)
            self._extract_media(cursor, schema, parsed)
        finally:
            conn.close()

    def _has_columns(self, cols: List[str], required: List[str]) -> bool:
        cols_lower = set(c.lower() for c in cols)
        return all(req.lower() in cols_lower for req in required)

    def _extract_chats(self, cursor: sqlite3.Cursor, schema: Dict[str, List[str]], parsed: Dict[str, Any]) -> None:
        """Schema-driven chat extraction without regex, no hardcoded app assumptions.
        Heuristics are based on column presence and types.
        """
        for t, cols in schema.items():
            try:
                lower_cols = [c.lower() for c in cols]
                # Candidate text columns
                text_candidates = [c for c in lower_cols if any(k in c for k in ['data', 'message', 'body', 'text', 'content'])]
                # Candidate sender/receiver columns
                sender_candidates = [c for c in lower_cols if any(k in c for k in ['sender', 'from', 'author', 'address', 'src', 'caller'])]
                receiver_candidates = [c for c in lower_cols if any(k in c for k in ['receiver', 'to', 'dest', 'remote', 'chat', 'recipient', 'callee'])]
                # Candidate timestamp columns
                ts_candidates = [c for c in lower_cols if any(k in c for k in ['time', 'date', 'timestamp'])]
                if not text_candidates:
                    continue
                # Build select columns dynamically
                select_cols: List[str] = []
                sel_sender = sender_candidates[0] if sender_candidates else None
                sel_receiver = receiver_candidates[0] if receiver_candidates else None
                sel_text = text_candidates[0]
                sel_ts = ts_candidates[0] if ts_candidates else None
                if sel_sender:
                    select_cols.append(sel_sender)
                if sel_receiver:
                    select_cols.append(sel_receiver)
                select_cols.append(sel_text)
                if sel_ts:
                    select_cols.append(sel_ts)
                query = f"SELECT {', '.join(select_cols)} FROM {t}"
                for row in cursor.execute(query):
                    idx = 0
                    sender = row[idx] if sel_sender else None
                    if sel_sender:
                        idx += 1
                    receiver = row[idx] if sel_receiver else None
                    if sel_receiver:
                        idx += 1
                    content = row[idx]
                    idx += 1
                    timestamp = row[idx] if sel_ts else None
                    parsed['chat_records'].append({
                        'app_name': 'Chat',
                        'sender_number': sender,
                        'receiver_number': receiver,
                        'message_content': content,
                        'timestamp': self._coerce_timestamp(timestamp),
                        'message_type': 'text',
                        'is_deleted': False,
                        'metadata': {'source_table': t}
                    })
            except Exception as e:
                # Skip tables that are not message-like
                continue

    def _extract_calls(self, cursor: sqlite3.Cursor, schema: Dict[str, List[str]], parsed: Dict[str, Any]) -> None:
        call_tables = [
            (t, cols) for t, cols in schema.items() if self._has_columns(cols, ['number', 'type', 'duration']) or self._has_columns(cols, ['caller', 'receiver', 'duration'])
        ]
        for t, cols in call_tables:
            try:
                colset = set(c.lower() for c in cols)
                if {'caller', 'receiver', 'duration'} <= colset:
                    query = f"SELECT caller, receiver, duration, type, date FROM {t}"
                else:
                    # Android calls: number, type, duration, date
                    query = f"SELECT number, number, duration, type, date FROM {t}"
                for a, b, duration, call_type, date_val in cursor.execute(query):
                    parsed['call_records'].append({
                        'caller_number': a,
                        'receiver_number': b,
                        'call_type': str(call_type) if call_type is not None else 'unknown',
                        'duration': int(duration) if duration is not None else 0,
                        'timestamp': self._coerce_timestamp(date_val),
                        'metadata': {'source_table': t}
                    })
            except Exception as e:
                print(f"⚠️ Call extraction error from {t}: {e}")

    def _extract_contacts(self, cursor: sqlite3.Cursor, schema: Dict[str, List[str]], parsed: Dict[str, Any]) -> None:
        for t, cols in schema.items():
            try:
                lower_cols = [c.lower() for c in cols]
                name_cols = [c for c in lower_cols if any(k in c for k in ['display_name', 'name', 'given_name'])]
                phone_cols = [c for c in lower_cols if any(k in c for k in ['phone', 'number', 'msisdn'])]
                email_cols = [c for c in lower_cols if 'email' in c]
                if not name_cols:
                    continue
                select_cols = [name_cols[0]]
                if phone_cols:
                    select_cols.append(phone_cols[0])
                if email_cols:
                    select_cols.append(email_cols[0])
                query = f"SELECT {', '.join(select_cols)} FROM {t}"
                for row in cursor.execute(query):
                    idx = 0
                    name = row[idx]
                    idx += 1
                    phone_numbers: List[str] = []
                    email_addresses: List[str] = []
                    if phone_cols:
                        val = row[idx]
                        idx += 1
                        if val is not None and str(val).strip() != '':
                            phone_numbers = [str(val)]
                    if email_cols:
                        val = row[idx]
                        if val is not None and str(val).strip() != '':
                            email_addresses = [str(val)]
                    parsed['contacts'].append({
                        'name': name,
                        'phone_numbers': phone_numbers,
                        'email_addresses': email_addresses,
                        'metadata': {'source_table': t}
                    })
            except Exception:
                continue

    def _extract_media(self, cursor: sqlite3.Cursor, schema: Dict[str, List[str]], parsed: Dict[str, Any]) -> None:
        for t, cols in schema.items():
            try:
                lower_cols = [c.lower() for c in cols]
                filename_col = None
                path_col = None
                mime_col = None
                size_col = None
                created_col = None
                modified_col = None
                for c in lower_cols:
                    if filename_col is None and any(k in c for k in ['filename', 'name']):
                        filename_col = c
                    if path_col is None and any(k in c for k in ['_data', 'path', 'file_path', 'local_path']):
                        path_col = c
                    if mime_col is None and any(k in c for k in ['mime', 'file_type', 'type']):
                        mime_col = c
                    if size_col is None and 'size' in c:
                        size_col = c
                    if created_col is None and any(k in c for k in ['date_added', 'created']):
                        created_col = c
                    if modified_col is None and any(k in c for k in ['date_modified', 'modified']):
                        modified_col = c
                select_cols = [c for c in [path_col or filename_col, mime_col, size_col, created_col, modified_col] if c]
                if not select_cols:
                    continue
                query = f"SELECT {', '.join(select_cols)} FROM {t}"
                for row in cursor.execute(query):
                    idx = 0
                    path_or_name = row[idx]; idx += 1 if (path_col or filename_col) else 0
                    mime = row[idx] if mime_col else None; idx += 1 if mime_col else 0
                    size = row[idx] if size_col else None; idx += 1 if size_col else 0
                    created = row[idx] if created_col else None; idx += 1 if created_col else 0
                    modified = row[idx] if modified_col else None
                    filename = Path(path_or_name).name if path_col and path_or_name else (path_or_name if filename_col else None)
                    parsed['media_files'].append({
                        'filename': filename,
                        'file_path': path_or_name if path_col else None,
                        'file_type': mime,
                        'file_size': int(size) if size is not None else 0,
                        'created_date': self._coerce_timestamp(created),
                        'modified_date': self._coerce_timestamp(modified),
                        'hash_md5': None,
                        'hash_sha256': None,
                        'metadata': {'source_table': t}
                    })
            except Exception:
                continue

    def _extract_from_dataframe(self, table_name: str, df: pd.DataFrame, parsed: Dict[str, Any]) -> None:
        """Generic extraction from tabular files (CSV/JSON) using column-based heuristics only."""
        try:
            lower_cols = [c.lower() for c in df.columns]
            # Contacts
            if any(k in lower_cols for k in ['name', 'display_name']):
                name_col = next((c for c in lower_cols if c in ['display_name', 'name']), None)
                phone_col = next((c for c in lower_cols if 'phone' in c or 'number' in c or 'msisdn' in c), None)
                email_col = next((c for c in lower_cols if 'email' in c), None)
                if name_col:
                    for _, row in df.iterrows():
                        name = row.get(name_col)
                        phones = [str(row.get(phone_col))] if phone_col and pd.notna(row.get(phone_col)) else []
                        emails = [str(row.get(email_col))] if email_col and pd.notna(row.get(email_col)) else []
                        if pd.notna(name) or phones or emails:
                            parsed['contacts'].append({
                                'name': str(name) if pd.notna(name) else 'Unknown',
                                'phone_numbers': phones,
                                'email_addresses': emails,
                                'metadata': {'source_table': table_name}
                            })
            # Calls
            if any(k in lower_cols for k in ['duration']) and (any(k in lower_cols for k in ['caller']) or any(k in lower_cols for k in ['number'])):
                caller_col = next((c for c in lower_cols if 'caller' in c or (c == 'number')), None)
                receiver_col = next((c for c in lower_cols if 'receiver' in c or 'to' in c or 'callee' in c), None)
                duration_col = next((c for c in lower_cols if 'duration' in c), None)
                type_col = next((c for c in lower_cols if 'type' in c or 'call_type' in c), None)
                ts_col = next((c for c in lower_cols if 'date' in c or 'time' in c or 'timestamp' in c), None)
                if duration_col and caller_col:
                    for _, row in df.iterrows():
                        parsed['call_records'].append({
                            'caller_number': str(row.get(caller_col)) if pd.notna(row.get(caller_col)) else None,
                            'receiver_number': str(row.get(receiver_col)) if receiver_col and pd.notna(row.get(receiver_col)) else None,
                            'call_type': str(row.get(type_col)) if type_col and pd.notna(row.get(type_col)) else 'unknown',
                            'duration': int(row.get(duration_col)) if pd.notna(row.get(duration_col)) else 0,
                            'timestamp': self._coerce_timestamp(row.get(ts_col)) if ts_col else None,
                            'metadata': {'source_table': table_name}
                        })
            # Chats
            text_col = next((c for c in lower_cols if c in ['message', 'body', 'text', 'content', 'data']), None)
            if text_col:
                sender_col = next((c for c in lower_cols if c in ['sender', 'from', 'author', 'address']), None)
                receiver_col = next((c for c in lower_cols if c in ['receiver', 'to', 'recipient']), None)
                ts_col = next((c for c in lower_cols if c in ['timestamp', 'date', 'time']), None)
                for _, row in df.iterrows():
                    content = row.get(text_col)
                    if pd.notna(content) and str(content).strip() != '':
                        parsed['chat_records'].append({
                            'app_name': None,
                            'sender_number': str(row.get(sender_col)) if sender_col and pd.notna(row.get(sender_col)) else None,
                            'receiver_number': str(row.get(receiver_col)) if receiver_col and pd.notna(row.get(receiver_col)) else None,
                            'message_content': str(content),
                            'timestamp': self._coerce_timestamp(row.get(ts_col)) if ts_col else None,
                            'message_type': 'text',
                            'is_deleted': False,
                            'metadata': {'source_table': table_name}
                        })
        except Exception as e:
            print(f"⚠️ DataFrame extraction error for {table_name}: {e}")

    def _extract_from_json_object(self, name: str, obj: Any, parsed: Dict[str, Any]) -> None:
        """Map structured JSON objects to standard buckets in a schema-agnostic way."""
        try:
            if not isinstance(obj, dict):
                return
            if 'device_info' in obj and isinstance(obj['device_info'], dict):
                parsed['device_info'].update(obj['device_info'])
            mapping = [
                ('chat_records', 'chat_records'),
                ('messages', 'chat_records'),
                ('calls', 'call_records'),
                ('call_records', 'call_records'),
                ('contacts', 'contacts'),
                ('media', 'media_files'),
                ('media_files', 'media_files')
            ]
            for src_key, target in mapping:
                arr = obj.get(src_key)
                if isinstance(arr, list):
                    for item in arr:
                        if not isinstance(item, dict):
                            continue
                        if target == 'chat_records':
                            parsed['chat_records'].append({
                                'app_name': item.get('app_name'),
                                'sender_number': item.get('sender') or item.get('sender_number'),
                                'receiver_number': item.get('receiver') or item.get('receiver_number'),
                                'message_content': item.get('message') or item.get('message_content'),
                                'timestamp': self._coerce_timestamp(item.get('timestamp')),
                                'message_type': item.get('message_type', 'text'),
                                'is_deleted': bool(item.get('is_deleted', False)),
                                'metadata': item.get('metadata', {})
                            })
                        elif target == 'call_records':
                            parsed['call_records'].append({
                                'caller_number': item.get('caller') or item.get('caller_number'),
                                'receiver_number': item.get('receiver') or item.get('receiver_number'),
                                'call_type': item.get('type') or item.get('call_type', 'unknown'),
                                'duration': int(item.get('duration', 0)) if item.get('duration') is not None else 0,
                                'timestamp': self._coerce_timestamp(item.get('timestamp')),
                                'metadata': item.get('metadata', {})
                            })
                        elif target == 'contacts':
                            phones = item.get('phone_numbers')
                            if not phones and item.get('phone') is not None:
                                phones = [str(item.get('phone'))]
                            emails = item.get('email_addresses')
                            if not emails and item.get('email') is not None:
                                emails = [str(item.get('email'))]
                            parsed['contacts'].append({
                                'name': item.get('name'),
                                'phone_numbers': phones or [],
                                'email_addresses': emails or [],
                                'metadata': item.get('metadata', {})
                            })
                        elif target == 'media_files':
                            parsed['media_files'].append({
                                'filename': item.get('filename'),
                                'file_path': item.get('file_path') or item.get('path'),
                                'file_type': item.get('file_type') or item.get('mime'),
                                'file_size': int(item.get('file_size', 0)) if item.get('file_size') is not None else 0,
                                'created_date': self._coerce_timestamp(item.get('created_date')),
                                'modified_date': self._coerce_timestamp(item.get('modified_date')),
                                'hash_md5': item.get('hash_md5'),
                                'hash_sha256': item.get('hash_sha256'),
                                'metadata': item.get('metadata', {})
                            })
        except Exception:
            pass

    def _traverse_and_extract(self, obj: Any, parsed: Dict[str, Any]) -> None:
        """Recursively traverse arbitrary JSON and classify records dynamically.
        This is schema-agnostic and avoids vendor-specific hardcoding.
        """
        try:
            if isinstance(obj, list):
                for item in obj:
                    self._traverse_and_extract(item, parsed)
                return
            if not isinstance(obj, dict):
                return
            lower_keys = set(k.lower() for k in obj.keys())
            # Detect chat-like
            if any(k in lower_keys for k in ['message', 'message_content', 'text', 'body', 'content']):
                parsed['chat_records'].append({
                    'app_name': obj.get('app_name'),
                    'sender_number': obj.get('sender') or obj.get('sender_number') or obj.get('from') or obj.get('author'),
                    'receiver_number': obj.get('receiver') or obj.get('receiver_number') or obj.get('to') or obj.get('recipient'),
                    'message_content': obj.get('message') or obj.get('message_content') or obj.get('text') or obj.get('body') or obj.get('content'),
                    'timestamp': self._coerce_timestamp(obj.get('timestamp') or obj.get('date') or obj.get('time')),
                    'message_type': obj.get('message_type', 'text'),
                    'is_deleted': bool(obj.get('is_deleted', False)),
                    'metadata': obj.get('metadata', {})
                })
                # Also traverse children for nested records
                for v in obj.values():
                    self._traverse_and_extract(v, parsed)
                return
            # Detect call-like
            if ('duration' in lower_keys) and (any(k in lower_keys for k in ['caller', 'caller_number', 'number']) or any(k in lower_keys for k in ['receiver', 'receiver_number', 'callee'])):
                parsed['call_records'].append({
                    'caller_number': obj.get('caller') or obj.get('caller_number') or obj.get('number'),
                    'receiver_number': obj.get('receiver') or obj.get('receiver_number') or obj.get('callee'),
                    'call_type': obj.get('type') or obj.get('call_type', 'unknown'),
                    'duration': int(obj.get('duration', 0)) if obj.get('duration') is not None else 0,
                    'timestamp': self._coerce_timestamp(obj.get('timestamp') or obj.get('date') or obj.get('time')),
                    'metadata': obj.get('metadata', {})
                })
                for v in obj.values():
                    self._traverse_and_extract(v, parsed)
                return
            # Detect contact-like
            if any(k in lower_keys for k in ['name', 'display_name']) and (any('phone' in k for k in lower_keys) or any('email' in k for k in lower_keys)):
                phones = obj.get('phone_numbers')
                if not phones:
                    for k, v in obj.items():
                        if isinstance(v, (str, int)) and 'phone' in k.lower():
                            phones = [str(v)]
                            break
                emails = obj.get('email_addresses')
                if not emails:
                    for k, v in obj.items():
                        if isinstance(v, (str, int)) and 'email' in k.lower():
                            emails = [str(v)]
                            break
                parsed['contacts'].append({
                    'name': obj.get('name') or obj.get('display_name'),
                    'phone_numbers': phones or [],
                    'email_addresses': emails or [],
                    'metadata': obj.get('metadata', {})
                })
                for v in obj.values():
                    self._traverse_and_extract(v, parsed)
                return
            # Detect media-like
            if any(k in lower_keys for k in ['filename']) or (any(k in lower_keys for k in ['path', 'file_path', '_data']) and any(k in lower_keys for k in ['mime', 'file_type', 'type'])):
                parsed['media_files'].append({
                    'filename': obj.get('filename') or (Path(obj.get('path') or obj.get('file_path') or '').name if (obj.get('path') or obj.get('file_path')) else None),
                    'file_path': obj.get('file_path') or obj.get('path'),
                    'file_type': obj.get('file_type') or obj.get('mime') or obj.get('type'),
                    'file_size': int(obj.get('file_size', 0)) if obj.get('file_size') is not None else 0,
                    'created_date': self._coerce_timestamp(obj.get('created_date') or obj.get('date_added')),
                    'modified_date': self._coerce_timestamp(obj.get('modified') or obj.get('modified_date') or obj.get('date_modified')),
                    'hash_md5': obj.get('hash_md5'),
                    'hash_sha256': obj.get('hash_sha256'),
                    'metadata': obj.get('metadata', {})
                })
                for v in obj.values():
                    self._traverse_and_extract(v, parsed)
                return
            # Continue traversal if no classification
            for v in obj.values():
                self._traverse_and_extract(v, parsed)
        except Exception:
            pass

    def _coerce_timestamp(self, value: Any) -> Optional[datetime]:
        try:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                # Handle common Android epoch in milliseconds
                if value > 1e12:
                    return datetime.fromtimestamp(value / 1000.0)
                return datetime.fromtimestamp(value)
            if isinstance(value, str) and value.isdigit():
                iv = int(value)
                if iv > 1e12:
                    return datetime.fromtimestamp(iv / 1000.0)
                return datetime.fromtimestamp(iv)
            return None
        except Exception:
            return None
    
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