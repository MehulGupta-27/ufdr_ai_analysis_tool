import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import UploadPage from './pages/UploadPage';
import AIAnalyzer from './pages/AIAnalyzer';
import ReportGenerator from './pages/ReportGenerator';
import './App.css';

function App() {
  const [currentCase, setCurrentCase] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <Router>
      <div className="app">
        <Sidebar 
          isOpen={sidebarOpen} 
          currentCase={currentCase}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
        />
        <div className={`main-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          <Header 
            onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
            currentCase={currentCase}
          />
          <div className="content">
            <Routes>
              <Route 
                path="/" 
                element={<UploadPage onCaseCreated={setCurrentCase} />} 
              />
              <Route 
                path="/upload" 
                element={<UploadPage onCaseCreated={setCurrentCase} />} 
              />
              <Route 
                path="/analyzer" 
                element={<AIAnalyzer currentCase={currentCase} />} 
              />
              <Route 
                path="/reports" 
                element={<ReportGenerator currentCase={currentCase} />} 
              />
            </Routes>
          </div>
        </div>
      </div>
    </Router>
  );
}

export default App;