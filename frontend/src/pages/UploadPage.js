import React, { useState } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, User, Hash } from 'lucide-react';
import axios from 'axios';
import './UploadPage.css';

const UploadPage = ({ onCaseCreated }) => {
  const [file, setFile] = useState(null);
  const [caseNumber, setCaseNumber] = useState('');
  const [investigator, setInvestigator] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setError(null);
    setUploadResult(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    setFile(droppedFile);
    setError(null);
    setUploadResult(null);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!file || !caseNumber || !investigator) {
      setError('Please fill in all fields and select a file');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      console.log('Starting upload...', { file: file.name, caseNumber, investigator });
      
      const formData = new FormData();
      formData.append('file', file);
      formData.append('case_number', caseNumber);
      formData.append('investigator', investigator);

      console.log('Sending request to /api/v1/upload-ufdr');
      
      const response = await axios.post('/api/v1/upload-ufdr', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 30000, // 30 second timeout
      });

      console.log('Upload successful:', response.data);
      
      setUploadResult(response.data);
      onCaseCreated({
        case_number: caseNumber,
        investigator: investigator,
        filename: file.name
      });

      // Reset form
      setFile(null);
      setCaseNumber('');
      setInvestigator('');
      
    } catch (err) {
      console.error('Upload error:', err);
      
      if (err.code === 'ECONNABORTED') {
        setError('Upload timeout - please check if the backend server is running');
      } else if (err.response) {
        setError(`Server error: ${err.response.data?.detail || err.response.statusText}`);
      } else if (err.request) {
        setError('Cannot connect to server - please check if the backend is running on http://localhost:8000');
      } else {
        setError(`Upload failed: ${err.message}`);
      }
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const testConnection = async () => {
    try {
      setConnectionStatus('testing');
      const response = await axios.get('/api/v1/health', { timeout: 5000 });
      setConnectionStatus('connected');
      console.log('Backend connection successful:', response.data);
    } catch (err) {
      setConnectionStatus('failed');
      console.error('Backend connection failed:', err);
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-container">
        <div className="upload-header">
          <h1>Upload UFDR File</h1>
          <p>Upload forensic data files for AI-powered analysis</p>
        </div>

        {error && (
          <div className="alert alert-error">
            <AlertCircle size={20} />
            {error}
          </div>
        )}

        {uploadResult && (
          <div className="alert alert-success">
            <CheckCircle size={20} />
            File uploaded successfully! Case {uploadResult.case_number} is ready for analysis.
          </div>
        )}

        <div className="connection-test">
          <button 
            type="button" 
            className="btn btn-secondary"
            onClick={testConnection}
            disabled={connectionStatus === 'testing'}
          >
            {connectionStatus === 'testing' ? (
              <>
                <div className="loading-spinner" />
                Testing Connection...
              </>
            ) : (
              'Test Backend Connection'
            )}
          </button>
          
          {connectionStatus === 'connected' && (
            <span className="connection-status success">✅ Backend Connected</span>
          )}
          {connectionStatus === 'failed' && (
            <span className="connection-status error">❌ Backend Not Available</span>
          )}
        </div>

        <form onSubmit={handleSubmit} className="upload-form">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">
                <Hash size={16} />
                Case Number
              </label>
              <input
                type="text"
                className="form-input"
                value={caseNumber}
                onChange={(e) => setCaseNumber(e.target.value)}
                placeholder="e.g., CASE-2025-001"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <User size={16} />
                Investigator Name
              </label>
              <input
                type="text"
                className="form-input"
                value={investigator}
                onChange={(e) => setInvestigator(e.target.value)}
                placeholder="e.g., Detective Smith"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <FileText size={16} />
              UFDR File
            </label>
            <div 
              className={`file-drop-zone ${file ? 'has-file' : ''}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
            >
              <input
                type="file"
                id="file-input"
                className="file-input"
                onChange={handleFileChange}
                accept=".ufdr"
              />
              
              {!file ? (
                <div className="drop-zone-content">
                  <Upload size={48} className="upload-icon" />
                  <h3>Drop your UFDR file here</h3>
                  <p>or <label htmlFor="file-input" className="file-link">browse to choose a file</label></p>
                  <div className="supported-formats">
                    <span>Supported formats: XML, JSON, CSV, XLSX, UFDR, ZIP, TXT</span>
                  </div>
                </div>
              ) : (
                <div className="file-info">
                  <FileText size={32} className="file-icon" />
                  <div className="file-details">
                    <h4>{file.name}</h4>
                    <p>{formatFileSize(file.size)}</p>
                  </div>
                  <button 
                    type="button" 
                    className="remove-file"
                    onClick={() => setFile(null)}
                  >
                    ×
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="form-actions">
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={uploading || !file || !caseNumber || !investigator}
            >
              {uploading ? (
                <>
                  <div className="loading-spinner" />
                  Processing...
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Upload & Process
                </>
              )}
            </button>
          </div>
        </form>

        <div className="upload-info">
          <h3>What happens next?</h3>
          <div className="info-steps">
            <div className="info-step">
              <div className="step-number">1</div>
              <div className="step-content">
                <h4>File Processing</h4>
                <p>Your UFDR file will be parsed and analyzed</p>
              </div>
            </div>
            <div className="info-step">
              <div className="step-number">2</div>
              <div className="step-content">
                <h4>AI Analysis</h4>
                <p>AI will extract insights and relationships</p>
              </div>
            </div>
            <div className="info-step">
              <div className="step-number">3</div>
              <div className="step-content">
                <h4>Ready for Investigation</h4>
                <p>Query the data and generate reports</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;