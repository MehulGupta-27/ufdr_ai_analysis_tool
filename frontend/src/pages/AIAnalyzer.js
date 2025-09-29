import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, Bot, User, AlertCircle, Loader, ChevronDown, ChevronRight, Phone, MessageCircle, FileText, Users, Clock, Hash, Smartphone, Mail, Calendar, MapPin, Tag, Shield, Search, BarChart3, Database, Key, Eye } from 'lucide-react';
import axios from 'axios';
import { useApp } from '../context/AppContext';
import './AIAnalyzer.css';

// Component for expandable record blocks
const RecordBlock = ({ record, index, type }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getRecordIcon = (type) => {
    switch (type) {
      case 'chat_records':
        return <MessageCircle size={16} />;
      case 'call_records':
        return <Phone size={16} />;
      case 'media_files':
        return <FileText size={16} />;
      case 'contacts':
        return <Users size={16} />;
      case 'search_results':
        return <Search size={16} />;
      case 'analysis_results':
        return <AlertCircle size={16} />;
      default:
        return <Hash size={16} />;
    }
  };

  const getRecordTypeLabel = (type) => {
    switch (type) {
      case 'chat_records':
        return 'Chat Record';
      case 'call_records':
        return 'Call Record';
      case 'media_files':
        return 'File';
      case 'contacts':
        return 'Contact';
      case 'search_results':
        return 'Search Result';
      case 'analysis_results':
        return 'Analysis Result';
      case 'device_info':
        return 'Device Info';
      default:
        return 'Record';
    }
  };

  const getFieldIcon = (fieldLabel) => {
    const label = fieldLabel.toLowerCase();
    
    // Time-related fields
    if (label.includes('time') || label.includes('date') || label.includes('timestamp')) {
      return <Clock size={14} />;
    }
    
    // Phone/communication fields
    if (label.includes('phone') || label.includes('from') || label.includes('to') || 
        label.includes('caller') || label.includes('receiver') || label.includes('sender')) {
      return <Phone size={14} />;
    }
    
    // App/platform fields
    if (label.includes('app') || label.includes('application') || label.includes('platform')) {
      return <Smartphone size={14} />;
    }
    
    // Email fields
    if (label.includes('email') || label.includes('mail')) {
      return <Mail size={14} />;
    }
    
    // Name/contact fields
    if (label.includes('name') || label.includes('contact')) {
      return <User size={14} />;
    }
    
    // File-related fields
    if (label.includes('file') || label.includes('filename') || label.includes('path')) {
      return <FileText size={14} />;
    }
    
    // Size/capacity fields
    if (label.includes('size') || label.includes('capacity')) {
      return <Database size={14} />;
    }
    
    // Type/category fields
    if (label.includes('type') || label.includes('category')) {
      return <Tag size={14} />;
    }
    
    // Duration fields
    if (label.includes('duration') || label.includes('length')) {
      return <Clock size={14} />;
    }
    
    // Message/content fields
    if (label.includes('message') || label.includes('content') || label.includes('text')) {
      return <MessageCircle size={14} />;
    }
    
    // Relevance/score fields
    if (label.includes('relevance') || label.includes('score') || label.includes('confidence')) {
      return <BarChart3 size={14} />;
    }
    
    // Evidence/ID fields
    if (label.includes('evidence') || label.includes('id') || label.includes('reference')) {
      return <Key size={14} />;
    }
    
    // Finding/analysis fields
    if (label.includes('finding') || label.includes('analysis') || label.includes('description')) {
      return <Eye size={14} />;
    }
    
    // Security/risk fields
    if (label.includes('risk') || label.includes('security') || label.includes('threat')) {
      return <Shield size={14} />;
    }
    
    // Search fields
    if (label.includes('search') || label.includes('query')) {
      return <Search size={14} />;
    }
    
    // Location fields
    if (label.includes('location') || label.includes('address') || label.includes('path')) {
      return <MapPin size={14} />;
    }
    
    // Default icon for unknown fields
    return <Hash size={14} />;
  };

  const formatRecordData = (record) => {
    const fields = [];
    
    // Common fields
    if (record.app_name || record.application) {
      fields.push({ label: 'App', value: record.app_name || record.application });
    }
    if (record.sender_number || record.caller_number) {
      fields.push({ label: 'From', value: record.sender_number || record.caller_number });
    }
    if (record.receiver_number || record.receiver) {
      fields.push({ label: 'To', value: record.receiver_number || record.receiver });
    }
    if (record.timestamp || record.date || record.time) {
      fields.push({ label: 'Time', value: record.timestamp || record.date || record.time });
    }
    
    // Type-specific fields
    if (type === 'chat_records' && record.message_content) {
      fields.push({ label: 'Message', value: record.message_content, isMessage: true });
    }
    if (type === 'call_records' && record.call_duration) {
      fields.push({ label: 'Duration', value: record.call_duration });
    }
    if (type === 'call_records' && record.call_type) {
      fields.push({ label: 'Type', value: record.call_type });
    }
    if (type === 'media_files' && record.file_name) {
      fields.push({ label: 'File', value: record.file_name });
    }
    if (type === 'media_files' && record.file_size) {
      fields.push({ label: 'Size', value: record.file_size });
    }
    if (type === 'media_files' && record.file_type) {
      fields.push({ label: 'Type', value: record.file_type });
    }
    if (type === 'contacts' && record.contact_name) {
      fields.push({ label: 'Name', value: record.contact_name });
    }
    if (type === 'contacts' && record.phone_number) {
      fields.push({ label: 'Phone', value: record.phone_number });
    }
    if (type === 'contacts' && record.contact_email) {
      fields.push({ label: 'Email', value: record.contact_email });
    }
    
    // Search results specific fields
    if (type === 'search_results' && record.risk_level) {
      fields.push({ label: 'Risk Level', value: record.risk_level, isRiskLevel: true });
    }
    if (type === 'search_results' && record.relevance_score) {
      fields.push({ label: 'Score', value: `${(record.relevance_score * 100).toFixed(1)}%` });
    }
    if (type === 'search_results' && record.suspicious_indicators) {
      fields.push({ label: 'Suspicious Indicators', value: record.suspicious_indicators });
    }
    if (type === 'search_results' && record.evidence_id) {
      fields.push({ label: 'Evidence ID', value: record.evidence_id });
    }
    if (type === 'search_results' && record.content) {
      fields.push({ label: 'Content', value: record.content, isMessage: true });
    }
    if (type === 'search_results' && record.message_content) {
      fields.push({ label: 'Message', value: record.message_content, isMessage: true });
    }
    
    // Analysis results specific fields
    if (type === 'analysis_results' && record.confidence) {
      fields.push({ label: 'Confidence', value: `${(record.confidence * 100).toFixed(1)}%` });
    }
    if (type === 'analysis_results' && record.finding) {
      fields.push({ label: 'Finding', value: record.finding, isMessage: true });
    }
    if (type === 'analysis_results' && record.evidence) {
      fields.push({ label: 'Evidence', value: record.evidence });
    }
    
    // Device info specific fields
    if (type === 'device_info' && record.model) {
      fields.push({ label: 'Model', value: record.model });
    }
    if (type === 'device_info' && record.manufacturer) {
      fields.push({ label: 'Manufacturer', value: record.manufacturer });
    }
    if (type === 'device_info' && record.os_version) {
      fields.push({ label: 'OS Version', value: record.os_version });
    }
    if (type === 'device_info' && record.imei) {
      fields.push({ label: 'IMEI', value: record.imei });
    }
    if (type === 'device_info' && record.serial_number) {
      fields.push({ label: 'Serial Number', value: record.serial_number });
    }
    if (type === 'device_info' && record.extraction_date) {
      fields.push({ label: 'Extraction Date', value: record.extraction_date });
    }
    if (type === 'device_info' && record.extraction_tool) {
      fields.push({ label: 'Extraction Tool', value: record.extraction_tool });
    }
    if (type === 'device_info' && record.case_officer) {
      fields.push({ label: 'Case Officer', value: record.case_officer });
    }
    
    // Generic fallback: include any additional parsed fields so design stays consistent
    if (Array.isArray(record._otherFields)) {
      record._otherFields.forEach((kv) => {
        if (kv && kv.label && kv.value) {
          fields.push({ label: kv.label, value: kv.value });
        }
      });
    }
    
    return fields;
  };

  const recordData = formatRecordData(record);
  const summaryFields = recordData.slice(0, 3); // Show first 3 fields in summary
  const hasMoreFields = recordData.length > 3;

  return (
    <div className="record-block" data-type={type}>
      <div 
        className="record-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="record-icon">
          {getRecordIcon(type)}
        </div>
        <div className="record-summary">
          <div className="record-type">
            {getRecordTypeLabel(type)} #{index + 1}
          </div>
          <div className="record-preview">
            {summaryFields.map((field, idx) => (
              <span key={idx} className="field-preview">
                <strong>{field.label}:</strong> {field.value}
                {idx < summaryFields.length - 1 && ' | '}
              </span>
            ))}
            {hasMoreFields && !isExpanded && (
              <span className="more-indicator">... (click to expand)</span>
            )}
          </div>
        </div>
        <div className="expand-icon">
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </div>
      
      {isExpanded && (
        <div className="record-details">
          {recordData.map((field, idx) => (
            <div key={idx} className={`field-detail ${field.isMessage ? 'message-field' : ''}`}>
              <div className="field-label">
                {getFieldIcon(field.label)}
                {field.label}:
              </div>
              <div className="field-value">
                {field.isMessage ? (
                  <div className="message-content">
                    {field.value}
                  </div>
                ) : field.isRiskLevel ? (
                  <span className={`risk-level risk-${field.value.toLowerCase()}`}>
                    {field.value}
                  </span>
                ) : (
                  field.value
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Component to parse and render structured data
const StructuredDataRenderer = ({ content }) => {
  const [expandedRecords, setExpandedRecords] = useState({});

  // Enhanced parsing to handle various AI response formats
  const parseRecords = (content) => {
    const records = [];
    const lines = content.split('\n');
    let currentType = null;
    let recordIndex = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // Enhanced record type header detection for all data types
      if (line.includes('CHAT RECORDS') || line.includes('Chat records') || line.includes('CHAT_RECORDS') || 
          line.includes('Chat Records') || line.includes('chat records')) {
        currentType = 'chat_records';
        continue;
      } else if (line.includes('CALL RECORDS') || line.includes('Call records') || line.includes('CALL_RECORDS') || 
                 line.includes('Call Records') || line.includes('call records')) {
        currentType = 'call_records';
        continue;
      } else if (line.includes('MEDIA FILES') || line.includes('Media files') || line.includes('MEDIA_FILES') || 
                 line.includes('Media Files') || line.includes('media files') || line.includes('FILES') || 
                 line.includes('Files') || line.includes('files')) {
        currentType = 'media_files';
        continue;
      } else if (line.includes('CONTACTS') || line.includes('Contacts') || line.includes('contacts')) {
        currentType = 'contacts';
        continue;
      } else if (line.includes('SEARCH RESULTS') || line.includes('Search results') || line.includes('SEARCH_RESULTS') || 
                 line.includes('Search Results') || line.includes('search results')) {
        currentType = 'search_results';
        continue;
      } else if (line.includes('ANALYSIS RESULTS') || line.includes('Analysis results') || line.includes('ANALYSIS_RESULTS') || 
                 line.includes('Analysis Results') || line.includes('analysis results')) {
        currentType = 'analysis_results';
        continue;
      } else if (line.includes('DEVICE INFORMATION') || line.includes('Device information') || line.includes('DEVICE_INFO') || 
                 line.includes('Device Information') || line.includes('device information')) {
        currentType = 'device_info';
        continue;
      }
      
      // Enhanced pattern matching for different formats
      const patterns = [
        /^\s*(\d+)\.\s*(.+)/,  // 1. App: WhatsApp | From: +123 | To: +456 | Message: Hello
        /^\s*(\d+)\s*-\s*(.+)/, // 1 - App: WhatsApp | From: +123 | To: +456 | Message: Hello
        /^\s*(\d+)\s*:\s*(.+)/, // 1: App: WhatsApp | From: +123 | To: +456 | Message: Hello
        /^\s*(\d+)\s*(.+)/,     // 1 App: WhatsApp | From: +123 | To: +456 | Message: Hello
      ];

      let recordMatch = null;
      for (const pattern of patterns) {
        recordMatch = line.match(pattern);
        if (recordMatch) break;
      }

      if (recordMatch) {
        const recordText = recordMatch[2];
        const record = parseRecordText(recordText, currentType);
        if (Object.keys(record).length > 0) {
          // Determine record type dynamically based on content
          const detectedType = detectRecordType(record, currentType);
          
          // If we detected a different type than the current section, update currentType
          // This handles cases where the AI doesn't include proper section headers
          if (detectedType !== currentType && detectedType !== 'unknown') {
            currentType = detectedType;
          }
          
          records.push({ ...record, type: detectedType, index: recordIndex++ });
        }
      }
    }
    
    return records;
  };

  // Dynamic record type detection based on content
  const detectRecordType = (record, fallbackType) => {
    // If we have a specific type from headers, use it
    if (fallbackType) {
      return fallbackType;
    }
    
    // Enhanced detection based on field presence and content patterns
    // Priority order: search_results > analysis_results > media_files > call_records > chat_records > contacts
    
    // Search results detection (highest priority)
    if (record.relevance_score || record.evidence_id || record.search_score || 
        record.app && record.relevance) {
      return 'search_results';
    }
    
    // Analysis results detection
    if (record.confidence || record.finding || record.analysis_score || 
        record.description && record.confidence) {
      return 'analysis_results';
    }
    
    // Media files detection
    if (record.file_name || record.file_size || record.file_type || record.file_path || 
        record.filename || record.file_size || record.mime_type) {
      return 'media_files';
    }
    
    // Call records detection
    if (record.call_duration || record.call_type || record.duration || 
        (record.caller_number && record.receiver_number && !record.file_name && !record.message_content)) {
      return 'call_records';
    }
    
    // Chat records detection
    if (record.message_content || record.content || record.text || record.app_name || 
        record.application || (record.sender_number && record.receiver_number && record.message_content)) {
      return 'chat_records';
    }
    
    // Contacts detection
    if (record.contact_name || record.name || record.phone_number || record.contact_email || 
        record.email || (record.phone && record.name)) {
      return 'contacts';
    }
    
    // Device info detection
    if (record.phone_number && (record.model || record.manufacturer || record.imei || 
        record.serial_number || record.os_version || record.extraction_date || record.extraction_tool)) {
      return 'device_info';
    }
    
    // Default fallback
    return 'unknown';
  };

  const parseRecordText = (text, type) => {
    const record = {};
    
    // Handle different separator patterns
    const separators = ['|', '•', '-', ';'];
    let parts = [text];
    
    for (const sep of separators) {
      if (text.includes(sep)) {
        parts = text.split(sep);
        break;
      }
    }
    
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed.includes(':')) {
        const colonIndex = trimmed.indexOf(':');
        const key = trimmed.substring(0, colonIndex).trim().toLowerCase();
        const value = trimmed.substring(colonIndex + 1).trim();
        
        // Enhanced key mapping for all data types
        switch (key) {
          // Common fields
          case 'app':
          case 'application':
          case 'platform':
            record.app_name = value;
            break;
          case 'from':
          case 'sender':
          case 'caller':
            record.sender_number = value;
            break;
          case 'to':
          case 'recipient':
          case 'receiver':
            record.receiver_number = value;
            break;
          case 'time':
          case 'timestamp':
          case 'date':
            record.timestamp = value;
            break;
          case 'message':
          case 'content':
          case 'text':
            record.message_content = value;
            break;
          
          // Call record specific
          case 'duration':
          case 'call_duration':
            record.call_duration = value;
            break;
          case 'call_type':
          case 'type':
            record.call_type = value;
            break;
          
          // Media file specific
          case 'file':
          case 'filename':
          case 'file_name':
            record.file_name = value;
            break;
          case 'size':
          case 'file_size':
            record.file_size = value;
            break;
          case 'file_type':
          case 'mime_type':
            record.file_type = value;
            break;
          case 'path':
          case 'file_path':
            record.file_path = value;
            break;
          
          // Contact specific
          case 'name':
          case 'contact_name':
            record.contact_name = value;
            break;
          case 'phone':
          case 'phone_number':
            record.phone_number = value;
            break;
          case 'email':
          case 'contact_email':
            record.contact_email = value;
            break;
          
          // Search results specific
          case 'relevance':
          case 'relevance_score':
          case 'score':
            record.relevance_score = parseFloat(value.replace('%', '')) / 100;
            break;
          case 'risk':
          case 'risk_level':
            record.risk_level = value;
            break;
          case 'indicators':
          case 'suspicious_indicators':
            record.suspicious_indicators = value;
            break;
          case 'evidence_id':
          case 'evidence':
            record.evidence_id = value;
            break;
          case 'search_score':
            record.search_score = parseFloat(value);
            break;
          
          // Analysis results specific
          case 'confidence':
          case 'confidence_score':
            record.confidence = parseFloat(value.replace('%', '')) / 100;
            break;
          case 'finding':
          case 'description':
            record.finding = value;
            break;
          case 'analysis_score':
            record.analysis_score = parseFloat(value);
            break;
          case 'references':
            record.evidence = value;
            break;
          
          // Device info specific
          case 'model':
          case 'device_model':
            record.model = value;
            break;
          case 'manufacturer':
          case 'device_manufacturer':
            record.manufacturer = value;
            break;
          case 'os_version':
          case 'operating_system':
            record.os_version = value;
            break;
          case 'imei':
          case 'device_imei':
            record.imei = value;
            break;
          case 'serial_number':
          case 'device_serial':
            record.serial_number = value;
            break;
          case 'extraction_date':
          case 'extraction_time':
            record.extraction_date = value;
            break;
          case 'extraction_tool':
          case 'tool_used':
            record.extraction_tool = value;
            break;
          case 'case_officer':
          case 'investigator':
            record.case_officer = value;
            break;
          default:
            // Preserve unknown fields for consistent rendering
            if (!record._otherFields) record._otherFields = [];
            // Capitalize first letter for label display
            const label = key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
            record._otherFields.push({ label, value });
            break;
        }
      }
    }
    
    return record;
  };

  const records = parseRecords(content);
  
  // Debug logging to help identify parsing issues
  if (process.env.NODE_ENV === 'development') {
    console.log('Parsed records:', records);
    console.log('Content length:', content.length);
    console.log('Content preview:', content.substring(0, 200));
    console.log('Content lines:', content.split('\n').slice(0, 10));
  }
  
  if (records.length === 0) {
    // If no structured records found, render as plain text with better formatting
    return (
      <div className="message-text">
        {content.split('\n').map((line, index) => {
          // Add some basic formatting for common patterns
          if (line.includes('**') || line.includes('*')) {
            return (
              <div key={index} className="formatted-line" dangerouslySetInnerHTML={{
                __html: line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>')
              }} />
            );
          }
           // Check if line looks like a structured record and try to parse it
           if (line.match(/^\s*\d+\.\s*.+\|/)) {
             const recordMatch = line.match(/^\s*(\d+)\.\s*(.+)/);
             if (recordMatch) {
               const recordText = recordMatch[2];
               const record = parseRecordText(recordText, 'unknown');
               
               // Use dynamic record type detection
               const recordType = detectRecordType(record, null);
               let icon = <Hash size={16} />;
               let typeLabel = 'Record';
               
               // Set icon and label based on detected type
               switch (recordType) {
                 case 'chat_records':
                   icon = <MessageCircle size={16} />;
                   typeLabel = 'Chat Record';
                   break;
                 case 'call_records':
                   icon = <Phone size={16} />;
                   typeLabel = 'Call Record';
                   break;
                 case 'media_files':
                   icon = <FileText size={16} />;
                   typeLabel = 'File';
                   break;
                 case 'contacts':
                   icon = <Users size={16} />;
                   typeLabel = 'Contact';
                   break;
                 case 'device_info':
                   icon = <Smartphone size={16} />;
                   typeLabel = 'Device Info';
                   break;
                 default:
                   icon = <Hash size={16} />;
                   typeLabel = 'Record';
               }
               
               if (Object.keys(record).length > 0) {
                 return (
                   <div key={index} className="record-block" data-type={recordType}>
                     <div className="record-header">
                       <div className="record-icon">
                         {icon}
                       </div>
                       <div className="record-summary">
                         <div className="record-type">{typeLabel} #{recordMatch[1]}</div>
                         <div className="record-preview">
                           {record.app_name && <span><strong>App:</strong> {record.app_name}</span>}
                           {record.sender_number && <span> | <strong>From:</strong> {record.sender_number}</span>}
                           {record.receiver_number && <span> | <strong>To:</strong> {record.receiver_number}</span>}
                           {record.message_content && <span> | <strong>Message:</strong> {record.message_content.substring(0, 100)}{record.message_content.length > 100 ? '...' : ''}</span>}
                           {record.call_duration && <span> | <strong>Duration:</strong> {record.call_duration}</span>}
                           {record.call_type && <span> | <strong>Type:</strong> {record.call_type}</span>}
                           {record.file_name && <span> | <strong>File:</strong> {record.file_name}</span>}
                           {record.file_size && <span> | <strong>Size:</strong> {record.file_size}</span>}
                           {record.contact_name && <span> | <strong>Name:</strong> {record.contact_name}</span>}
                           {record.phone_number && <span> | <strong>Phone:</strong> {record.phone_number}</span>}
                           {record.contact_email && <span> | <strong>Email:</strong> {record.contact_email}</span>}
                         </div>
                       </div>
                     </div>
                   </div>
                 );
               }
             }
           }
          return <div key={index}>{line}</div>;
        })}
      </div>
    );
  }

  // Group records by type for better organization
  const groupedRecords = records.reduce((groups, record, index) => {
    const type = record.type || 'unknown';
    if (!groups[type]) {
      groups[type] = [];
    }
    groups[type].push({ ...record, index });
    return groups;
  }, {});

  // Get type labels for display
  const getTypeLabel = (type) => {
    switch (type) {
      case 'chat_records': return 'Chat Records';
      case 'call_records': return 'Call Records';
      case 'media_files': return 'Files';
      case 'contacts': return 'Contacts';
      case 'search_results': return 'Search Results';
      case 'analysis_results': return 'Analysis Results';
      case 'device_info': return 'Device Information';
      default: return 'Records';
    }
  };

  return (
    <div className="structured-data">
      {Object.entries(groupedRecords).map(([type, typeRecords]) => (
        <div key={type} className="record-type-group" data-type={type}>
          <div className="record-type-header">
            <h3>{getTypeLabel(type)}</h3>
            <span className="record-count">({typeRecords.length} items)</span>
          </div>
          {typeRecords.map((record, index) => (
            <RecordBlock
              key={`${type}-${index}`}
              record={record}
              index={index}
              type={record.type}
            />
          ))}
        </div>
      ))}
    </div>
  );
};

const AIAnalyzer = ({ currentCase }) => {
  const { state, actions } = useApp();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  
  // Get messages for current case from global state
  const messages = currentCase ? (state.chatMessages[currentCase.case_number] || []) : [];
  const ongoingQuery = currentCase ? state.ongoingQueries[currentCase.case_number] : null;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (currentCase && (!messages || messages.length === 0)) {
      // Small delay to ensure any clearing operations complete first
      const timer = setTimeout(() => {
        const welcomeMessage = {
          id: 1,
          type: 'bot',
          content: `Welcome! I'm ready to analyze case ${currentCase.case_number}. You can ask me questions like:
        
• "How many evidences are total found"
• "Show me all the Calls made"
• "Find WhatsApp messages about Money"
• "Whom he called most frequently"
• "What is the IMEI no of the device"
• "Show me suspicious communications"
• "Analyze communication patterns"
• "Find connections between contacts"

What would you like to investigate?`,
          timestamp: new Date()
        };
        actions.setChatMessages(currentCase.case_number, [welcomeMessage]);
      }, 100);

      return () => clearTimeout(timer);
    }
  }, [currentCase, messages, actions]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    // Add user message to global state
    actions.addChatMessage(currentCase.case_number, userMessage);
    
    // Set ongoing query
    actions.setOngoingQuery(currentCase.case_number, inputValue);
    
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await axios.get('/api/v1/quick-query', {
        params: { 
          q: inputValue,
          case_number: currentCase.case_number
        }
      });

      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: response.data.answer,
        timestamp: new Date(),
        dataSources: response.data.data_sources,
        success: response.data.success
      };

      // Add bot message to global state
      actions.addChatMessage(currentCase.case_number, botMessage);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}`,
        timestamp: new Date(),
        isError: true
      };

      // Add error message to global state
      actions.addChatMessage(currentCase.case_number, errorMessage);
    } finally {
      setIsLoading(false);
      // Clear ongoing query
      actions.clearOngoingQuery(currentCase.case_number);
    }
  };

  const formatTime = (timestamp) => {
    try {
      // Handle different timestamp formats
      let date;
      
      if (timestamp instanceof Date) {
        date = timestamp;
      } else if (typeof timestamp === 'string') {
        // Try to parse the string as a date
        date = new Date(timestamp);
        
        // If parsing failed, return the original string
        if (isNaN(date.getTime())) {
          return timestamp;
        }
      } else if (timestamp && typeof timestamp === 'object' && timestamp.constructor === Date) {
        // Handle edge case where it might be a Date object but not instanceof Date
        date = timestamp;
      } else {
        // If it's not a Date or string, return a fallback
        return 'Invalid time';
      }
      
      // Final safety check
      if (!date || isNaN(date.getTime())) {
        return 'Invalid time';
      }
      
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (error) {
      console.warn('Error formatting time:', error, 'timestamp:', timestamp);
      return 'Invalid time';
    }
  };

  const suggestedQueries = [
    "How many evidences are total found",
    "Show me all the Calls made",
    "Find WhatsApp messages about Money",
    "Whom he called most frequently",
    "What is the IMEI no of the device",
    "Show me suspicious communications",
    "Analyze communication patterns",
    "Find connections between contacts"
  ];

  const handleSuggestedQuery = (query) => {
    setInputValue(query);
  };

  if (!currentCase) {
    return (
      <div className="analyzer-page">
        <div className="no-case-message">
          <MessageSquare size={64} className="no-case-icon" />
          <h2>No Case Selected</h2>
          <p>Please upload a UFDR file first to start analyzing forensic data.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="analyzer-page">
      <div className="analyzer-header">
        <div className="header-info">
          <MessageSquare className="header-icon" />
          <div>
            <h1>AI Analyzer</h1>
            <p>Ask questions about case {currentCase.case_number}</p>
          </div>
        </div>
      </div>

      <div className="chat-container">
        <div className="messages-container">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.type}`}>
              <div className="message-avatar">
                {message.type === 'user' ? (
                  <User size={20} />
                ) : (
                  <Bot size={20} />
                )}
              </div>
              <div className="message-content">
                <div className={`message-bubble ${message.isError ? 'error' : ''}`}>
                  {message.isError && <AlertCircle size={16} className="error-icon" />}
                  <StructuredDataRenderer content={message.content} />
                  {message.dataSources && (message.dataSources.sql_results_count > 0 || message.dataSources.vector_results_count > 0) && (
                    <div className="results-info">
                      Found {message.dataSources.sql_results_count + message.dataSources.vector_results_count} results
                      {message.dataSources.sql_results_count > 0 && ` (${message.dataSources.sql_results_count} from database)`}
                      {message.dataSources.vector_results_count > 0 && ` (${message.dataSources.vector_results_count} from semantic search)`}
                    </div>
                  )}
                </div>
                <div className="message-time">
                  {formatTime(message.timestamp)}
                </div>
              </div>
            </div>
          ))}
          
          {(isLoading || ongoingQuery) && (
            <div className="message bot">
              <div className="message-avatar">
                <Bot size={20} />
              </div>
              <div className="message-content">
                <div className="message-bubble loading">
                  <Loader size={16} className="loading-icon" />
                  <span>Analyzing{ongoingQuery ? `: "${ongoingQuery}"` : '...'}</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {messages.length === 1 && (
          <div className="suggested-queries">
            <h3>Try asking:</h3>
            <div className="query-suggestions">
              {suggestedQueries.map((query, index) => (
                <button
                  key={index}
                  className="suggestion-btn"
                  onClick={() => handleSuggestedQuery(query)}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="chat-input-form">
          <div className="input-container">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask me anything about the forensic data..."
              className="chat-input"
              disabled={isLoading}
            />
            <button
              type="submit"
              className="send-button"
              disabled={!inputValue.trim() || isLoading}
            >
              <Send size={20} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AIAnalyzer;