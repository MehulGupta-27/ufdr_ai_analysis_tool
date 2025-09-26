import React, { useState, useRef, useEffect } from 'react';
import { Send, MessageSquare, Bot, User, AlertCircle, Loader } from 'lucide-react';
import axios from 'axios';
import './AIAnalyzer.css';

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
        resultsCount: response.data.results_count
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
                  <div className="message-text">
                    {message.content.split('\n').map((line, index) => (
                      <div key={index}>{line}</div>
                    ))}
                  </div>
                  {message.resultsCount && (
                    <div className="results-info">
                      Found {message.resultsCount.sql_results + message.resultsCount.vector_results} results
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