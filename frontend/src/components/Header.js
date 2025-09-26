import React from 'react';
import { Menu, Shield } from 'lucide-react';
import './Header.css';

const Header = ({ onToggleSidebar, currentCase }) => {
  return (
    <header className="header">
      <div className="header-left">
        <button 
          className="mobile-menu-btn"
          onClick={onToggleSidebar}
        >
          <Menu size={20} />
        </button>
        <div className="header-title">
          <Shield className="header-icon" />
          <h1>UFDR Forensic Analyzer</h1>
        </div>
      </div>
      
      <div className="header-right">
        {currentCase && (
          <div className="case-badge">
            <span className="case-label">Case:</span>
            <span className="case-number">{currentCase.case_number}</span>
          </div>
        )}
        <div className="status-indicator">
          <div className="status-dot active"></div>
          <span>System Online</span>
        </div>
      </div>
    </header>
  );
};

export default Header;