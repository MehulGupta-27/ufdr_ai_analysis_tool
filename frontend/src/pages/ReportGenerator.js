import React, { useState } from 'react';
import { FileText, Download, AlertCircle, CheckCircle, Loader, Shield, TrendingUp } from 'lucide-react';
import axios from 'axios';
import './ReportGenerator.css';

const ReportGenerator = ({ currentCase }) => {
  const [generating, setGenerating] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const generateReport = async () => {
    if (!currentCase) return;

    setGenerating(true);
    setError(null);
    setReportData(null);

    try {
      const formData = new FormData();
      formData.append('case_number', currentCase.case_number);

      const response = await axios.post('/api/v1/generate-comprehensive-report', formData);
      
      if (response.data.success) {
        setReportData(response.data.report);
      } else {
        setError(response.data.error || 'Failed to generate report');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate report');
    } finally {
      setGenerating(false);
    }
  };

  const downloadPdf = async () => {
    if (!currentCase) return;

    setDownloadingPdf(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('case_number', currentCase.case_number);

      const response = await axios.post('/api/v1/generate-pdf-report', formData);
      
      if (response.data.success) {
        // Convert base64 to blob and download
        const byteCharacters = atob(response.data.pdf_data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'application/pdf' });
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = response.data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } else {
        setError(response.data.error || 'Failed to generate PDF');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate PDF');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const formatRiskLevel = (risk) => {
    if (risk >= 80) return { level: 'HIGH', color: '#dc3545', icon: '🔴' };
    if (risk >= 60) return { level: 'MEDIUM-HIGH', color: '#fd7e14', icon: '🟠' };
    if (risk >= 40) return { level: 'MEDIUM', color: '#ffc107', icon: '🟡' };
    if (risk >= 20) return { level: 'LOW-MEDIUM', color: '#20c997', icon: '🟢' };
    return { level: 'LOW', color: '#28a745', icon: '🟢' };
  };

  if (!currentCase) {
    return (
      <div className="report-page">
        <div className="no-case-message">
          <FileText size={64} className="no-case-icon" />
          <h2>No Case Selected</h2>
          <p>Please upload a UFDR file first to generate forensic reports.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="report-page">
      <div className="report-header">
        <div className="header-info">
          <FileText className="header-icon" />
          <div>
            <h1>Report Generator</h1>
            <p>Generate comprehensive forensic analysis reports for case {currentCase.case_number}</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      <div className="report-actions">
        <div className="action-card">
          <div className="action-header">
            <TrendingUp className="action-icon" />
            <div>
              <h3>Comprehensive Analysis Report</h3>
              <p>Generate a detailed forensic investigation report with criminal risk assessment</p>
            </div>
          </div>
          <div className="action-buttons">
            <button 
              className="btn btn-primary"
              onClick={generateReport}
              disabled={generating}
            >
              {generating ? (
                <>
                  <Loader className="loading-spinner" size={16} />
                  Generating...
                </>
              ) : (
                <>
                  <TrendingUp size={16} />
                  Generate Report
                </>
              )}
            </button>
          </div>
        </div>

        <div className="action-card">
          <div className="action-header">
            <Download className="action-icon" />
            <div>
              <h3>PDF Download</h3>
              <p>Download a professional PDF report for case documentation</p>
            </div>
          </div>
          <div className="action-buttons">
            <button 
              className="btn btn-outline"
              onClick={downloadPdf}
              disabled={downloadingPdf}
            >
              {downloadingPdf ? (
                <>
                  <Loader className="loading-spinner" size={16} />
                  Generating PDF...
                </>
              ) : (
                <>
                  <Download size={16} />
                  Download PDF
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {reportData && (
        <div className="report-results">
          <div className="alert alert-success">
            <CheckCircle size={20} />
            Report generated successfully! Review the analysis below.
          </div>

          <div className="report-summary">
            <div className="summary-header">
              <Shield className="summary-icon" />
              <h2>Executive Summary</h2>
            </div>
            
            <div className="summary-stats">
              <div className="stat-card">
                <div className="stat-number">{reportData.statistics?.total_contacts || 0}</div>
                <div className="stat-label">Total Contacts</div>
              </div>
              <div className="stat-card">
                <div className="stat-number">{reportData.statistics?.total_messages || 0}</div>
                <div className="stat-label">Messages</div>
              </div>
              <div className="stat-card">
                <div className="stat-number">{reportData.statistics?.total_calls || 0}</div>
                <div className="stat-label">Call Records</div>
              </div>
              <div className="stat-card">
                <div className="stat-number">{reportData.statistics?.suspicious_activities || 0}</div>
                <div className="stat-label">Suspicious Activities</div>
              </div>
            </div>
          </div>

          {reportData.risk_assessment && (
            <div className="risk-assessment">
              <h3>Criminal Risk Assessment</h3>
              <div className="risk-contacts">
                {Object.entries(reportData.risk_assessment).map(([contact, data]) => {
                  const risk = formatRiskLevel(data.risk_score);
                  return (
                    <div key={contact} className="risk-contact">
                      <div className="contact-info">
                        <div className="contact-name">{contact}</div>
                        <div className="contact-details">{data.name || 'Unknown'}</div>
                      </div>
                      <div className="risk-info">
                        <div className="risk-score" style={{ color: risk.color }}>
                          {risk.icon} {data.risk_score}% {risk.level}
                        </div>
                        <div className="risk-reasons">
                          {data.reasons?.slice(0, 2).map((reason, index) => (
                            <span key={index} className="risk-reason">{reason}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {reportData.key_findings && (
            <div className="key-findings">
              <h3>Key Findings</h3>
              <div className="findings-list">
                {reportData.key_findings.map((finding, index) => (
                  <div key={index} className="finding-item">
                    <div className="finding-title">{finding.title}</div>
                    <div className="finding-description">{finding.description}</div>
                    {finding.evidence && (
                      <div className="finding-evidence">
                        <strong>Evidence:</strong> {finding.evidence}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {reportData.recommendations && (
            <div className="recommendations">
              <h3>Recommendations</h3>
              <div className="recommendations-list">
                {reportData.recommendations.map((rec, index) => (
                  <div key={index} className="recommendation-item">
                    <div className="recommendation-priority">
                      {rec.priority === 'HIGH' && '🔴'}
                      {rec.priority === 'MEDIUM' && '🟡'}
                      {rec.priority === 'LOW' && '🟢'}
                      {rec.priority}
                    </div>
                    <div className="recommendation-content">
                      <div className="recommendation-title">{rec.title}</div>
                      <div className="recommendation-description">{rec.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReportGenerator;