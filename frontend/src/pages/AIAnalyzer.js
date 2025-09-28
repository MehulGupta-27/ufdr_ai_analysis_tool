import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, Bot, User, AlertCircle, Loader, ChevronDown, ChevronRight, Phone, MessageCircle, FileText, Users, Clock, Hash } from 'lucide-react';
import axios from 'axios';
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
        return 'Media File';
      case 'contacts':
        return 'Contact';
      default:
        return 'Record';
    }
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
                <Clock size={14} />
                {field.label}:
              </div>
              <div className="field-value">
                {field.isMessage ? (
                  <div className="message-content">
                    {field.value}
                  </div>
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
      
      // Check for record type headers
      if (line.includes('CHAT RECORDS') || line.includes('Chat records') || line.includes('CHAT_RECORDS')) {
        currentType = 'chat_records';
        continue;
      } else if (line.includes('CALL RECORDS') || line.includes('Call records') || line.includes('CALL_RECORDS')) {
        currentType = 'call_records';
        continue;
      } else if (line.includes('MEDIA FILES') || line.includes('Media files') || line.includes('MEDIA_FILES')) {
        currentType = 'media_files';
        continue;
      } else if (line.includes('CONTACTS') || line.includes('Contacts')) {
        currentType = 'contacts';
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

      if (recordMatch && currentType) {
        const recordText = recordMatch[2];
        const record = parseRecordText(recordText, currentType);
        if (Object.keys(record).length > 0) {
          records.push({ ...record, type: currentType, index: recordIndex++ });
        }
      }
    }
    
    return records;
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
               
               // Determine record type based on available fields
               let recordType = 'unknown';
               let icon = <Hash size={16} />;
               let typeLabel = 'Record';
               
               if (record.message_content || record.app_name) {
                 recordType = 'chat_records';
                 icon = <MessageCircle size={16} />;
                 typeLabel = 'Chat Record';
               } else if (record.call_duration || record.call_type) {
                 recordType = 'call_records';
                 icon = <Phone size={16} />;
                 typeLabel = 'Call Record';
               } else if (record.file_name || record.file_size) {
                 recordType = 'media_files';
                 icon = <FileText size={16} />;
                 typeLabel = 'Media File';
               } else if (record.contact_name || record.phone_number) {
                 recordType = 'contacts';
                 icon = <Users size={16} />;
                 typeLabel = 'Contact';
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

  return (
    <div className="structured-data">
      {records.map((record, index) => (
        <RecordBlock
          key={index}
          record={record}
          index={index}
          type={record.type}
        />
      ))}
    </div>
  );
};

const AIAnalyzer = ({ currentCase }) => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (currentCase) {
      setMessages([
        {
          id: 1,
          type: 'bot',
          content: `Welcome! I'm ready to analyze case ${currentCase.case_number}. You can ask me questions like:
          
• "Find WhatsApp messages about meetings"
• "Who sent verification codes?"
• "Show me suspicious communications"
• "Analyze communication patterns"
• "Find connections between contacts"

What would you like to investigate?`,
          timestamp: new Date()
        }
      ]);
    }
  }, [currentCase]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
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

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}`,
        timestamp: new Date(),
        isError: true
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const suggestedQueries = [
    "Find WhatsApp messages about meetings",
    "Who sent verification codes?",
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
          
          {isLoading && (
            <div className="message bot">
              <div className="message-avatar">
                <Bot size={20} />
              </div>
              <div className="message-content">
                <div className="message-bubble loading">
                  <Loader size={16} className="loading-icon" />
                  <span>Analyzing...</span>
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