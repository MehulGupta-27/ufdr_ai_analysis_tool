import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppProvider, useApp } from './context/AppContext';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import UploadPage from './pages/UploadPage';
import AIAnalyzer from './pages/AIAnalyzer';
import ConnectionGraph from './pages/ConnectionGraph';
import ReportGenerator from './pages/ReportGenerator';
import './App.css';

function AppContent() {
  const { state, actions } = useApp();
  const { currentCase, sidebarOpen } = state;

  return (
    <Router>
      <div className="app">
        <Sidebar 
          isOpen={sidebarOpen} 
          currentCase={currentCase}
          onToggle={() => actions.setSidebarOpen(!sidebarOpen)}
        />
        <div className={`main-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          <Header 
            onToggleSidebar={() => actions.setSidebarOpen(!sidebarOpen)}
            currentCase={currentCase}
          />
          <div className="content">
            <Routes>
              <Route 
                path="/" 
                element={<UploadPage onCaseCreated={actions.setCurrentCase} />} 
              />
              <Route 
                path="/upload" 
                element={<UploadPage onCaseCreated={actions.setCurrentCase} />} 
              />
              <Route 
                path="/analyzer" 
                element={<AIAnalyzer currentCase={currentCase} />} 
              />
              <Route 
                path="/connections" 
                element={<ConnectionGraph currentCase={currentCase} />} 
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

function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

export default App;