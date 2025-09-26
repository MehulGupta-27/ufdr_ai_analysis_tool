import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  Upload, 
  MessageSquare, 
  FileText, 
  Menu,
  Shield,
  ChevronLeft
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = ({ isOpen, currentCase, onToggle }) => {
  const location = useLocation();

  const menuItems = [
    {
      path: '/upload',
      icon: Upload,
      label: 'Upload UFDR',
      description: 'Upload forensic data files'
    },
    {
      path: '/analyzer',
      icon: MessageSquare,
      label: 'AI Analyzer',
      description: 'Chat and query analysis',
      disabled: !currentCase
    },
    {
      path: '/reports',
      icon: FileText,
      label: 'Generate Report',
      description: 'Create PDF summaries',
      disabled: !currentCase
    }
  ];

  return (
    <>
      <div className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <Shield className="brand-icon" />
            {isOpen && (
              <div className="brand-text">
                <h2>UFDR Analyzer</h2>
                <span>Forensic Investigation</span>
              </div>
            )}
          </div>
          <button 
            className="sidebar-toggle"
            onClick={onToggle}
            title={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {isOpen ? <ChevronLeft size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {currentCase && isOpen && (
          <div className="current-case">
            <div className="case-info">
              <h4>Current Case</h4>
              <p>{currentCase.case_number}</p>
              <span className="case-status">Active</span>
            </div>
          </div>
        )}

        <nav className="sidebar-nav">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            const isDisabled = item.disabled;

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}`}
                title={isDisabled ? 'Upload a UFDR file first' : item.description}
                onClick={(e) => isDisabled && e.preventDefault()}
              >
                <Icon className="nav-icon" size={20} />
                {isOpen && (
                  <div className="nav-content">
                    <span className="nav-label">{item.label}</span>
                    <span className="nav-description">{item.description}</span>
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {isOpen && (
          <div className="sidebar-footer">
            <div className="footer-info">
              <p>Version 2.0.0</p>
              <p>AI-Powered Analysis</p>
            </div>
          </div>
        )}
      </div>
      
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="sidebar-overlay"
          onClick={onToggle}
        />
      )}
    </>
  );
};

export default Sidebar;