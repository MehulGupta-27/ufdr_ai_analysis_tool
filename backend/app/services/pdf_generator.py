"""
PDF Report Generator for UFDR Analysis Reports.
"""

from typing import Dict, Any
import os
from datetime import datetime
from io import BytesIO
import base64

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

class PDFReportGenerator:
    def __init__(self):
        self.styles = None
        if REPORTLAB_AVAILABLE:
            self._setup_styles()
    
    def _setup_styles(self):
        """Setup PDF styles."""
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY
        ))
        
        self.styles.add(ParagraphStyle(
            name='RiskHigh',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.red,
            backColor=colors.lightgrey
        ))
        
        self.styles.add(ParagraphStyle(
            name='RiskMedium',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.orange
        ))
        
        self.styles.add(ParagraphStyle(
            name='RiskLow',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.green
        ))
    
    def generate_pdf_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate PDF report from report data."""
        
        if not REPORTLAB_AVAILABLE:
            return {
                "success": False,
                "error": "ReportLab library not available. Install with: pip install reportlab"
            }
        
        try:
            # Create PDF in memory
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Build PDF content
            story = []
            
            # Title page
            story.extend(self._create_title_page(report_data))
            story.append(PageBreak())
            
            # Executive summary
            story.extend(self._create_executive_summary(report_data))
            
            # Key findings
            story.extend(self._create_key_findings(report_data))
            
            # Risk assessment
            story.extend(self._create_risk_assessment(report_data))
            
            # Network analysis
            story.extend(self._create_network_analysis(report_data))
            
            # Evidence details
            story.extend(self._create_evidence_details(report_data))
            
            # Recommendations
            story.extend(self._create_recommendations(report_data))
            
            # Build PDF
            doc.build(story)
            
            # Get PDF data
            pdf_data = buffer.getvalue()
            buffer.close()
            
            # Encode as base64 for transmission
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            return {
                "success": True,
                "pdf_data": pdf_base64,
                "filename": f"UFDR_Report_{report_data.get('case_number', 'Unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "size": len(pdf_data)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF generation failed: {str(e)}"
            }
    
    def _create_title_page(self, report_data: Dict[str, Any]) -> list:
        """Create title page elements."""
        
        elements = []
        
        # Title
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("COMPREHENSIVE UFDR FORENSIC ANALYSIS REPORT", self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.5*inch))
        
        # Case information table
        case_info = [
            ['Case Number:', report_data.get('case_number', 'Unknown')],
            ['Analysis Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Generated By:', 'UFDR AI Analysis System'],
            ['Report Type:', 'Comprehensive Digital Forensic Analysis']
        ]
        
        case_table = Table(case_info, colWidths=[2*inch, 3*inch])
        case_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        elements.append(case_table)
        elements.append(Spacer(1, 1*inch))
        
        # Metadata summary
        metadata = report_data.get('metadata', {})
        summary_data = [
            ['Total Chat Records:', str(metadata.get('total_chat_records', 0))],
            ['Total Call Records:', str(metadata.get('total_call_records', 0))],
            ['Total Contacts:', str(metadata.get('total_contacts', 0))],
            ['Total Media Files:', str(metadata.get('total_media_files', 0))]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 1*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ]))
        
        elements.append(summary_table)
        
        return elements
    
    def _create_executive_summary(self, report_data: Dict[str, Any]) -> list:
        """Create executive summary section."""
        
        elements = []
        elements.append(Paragraph("EXECUTIVE SUMMARY", self.styles['CustomHeading']))
        
        # Extract key information
        analysis_results = report_data.get('analysis_results', {})
        risk_assessment = analysis_results.get('risk_assessment', {})
        
        summary_text = f"""
        This comprehensive forensic analysis report presents findings from the examination of digital evidence 
        extracted from mobile devices in case {report_data.get('case_number', 'Unknown')}. 
        
        The analysis processed {report_data.get('metadata', {}).get('total_chat_records', 0)} chat records, 
        {report_data.get('metadata', {}).get('total_call_records', 0)} call records, 
        {report_data.get('metadata', {}).get('total_contacts', 0)} contacts, and 
        {report_data.get('metadata', {}).get('total_media_files', 0)} media files.
        
        Overall Risk Assessment: {risk_assessment.get('risk_level', 'Unknown')} 
        (Risk Score: {risk_assessment.get('overall_risk_score', 0)}/100)
        """
        
        elements.append(Paragraph(summary_text, self.styles['CustomBody']))
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_key_findings(self, report_data: Dict[str, Any]) -> list:
        """Create key findings section."""
        
        elements = []
        elements.append(Paragraph("KEY FINDINGS & EVIDENCE", self.styles['CustomHeading']))
        
        analysis_results = report_data.get('analysis_results', {})
        comm_patterns = analysis_results.get('communication_patterns', {})
        
        # Communication patterns table
        patterns_data = [
            ['Metric', 'Value'],
            ['Total Communications', str(comm_patterns.get('total_communications', 0))],
            ['Apps Used', ', '.join(comm_patterns.get('apps_used', {}).keys())],
            ['Deleted Messages', str(comm_patterns.get('deleted_messages', 0))]
        ]
        
        patterns_table = Table(patterns_data, colWidths=[2.5*inch, 2.5*inch])
        patterns_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(patterns_table)
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_risk_assessment(self, report_data: Dict[str, Any]) -> list:
        """Create risk assessment section."""
        
        elements = []
        elements.append(Paragraph("CRIMINAL RISK ASSESSMENT", self.styles['CustomHeading']))
        
        analysis_results = report_data.get('analysis_results', {})
        risk_assessment = analysis_results.get('risk_assessment', {})
        
        # Overall risk
        risk_level = risk_assessment.get('risk_level', 'Unknown')
        risk_score = risk_assessment.get('overall_risk_score', 0)
        
        risk_style = self.styles['RiskLow']
        if risk_level == 'High':
            risk_style = self.styles['RiskHigh']
        elif risk_level == 'Medium':
            risk_style = self.styles['RiskMedium']
        
        elements.append(Paragraph(f"Overall Risk Level: {risk_level} ({risk_score}/100)", risk_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Contact risk scores
        contact_risks = risk_assessment.get('contact_risk_scores', {})
        if contact_risks:
            elements.append(Paragraph("Individual Contact Risk Scores:", self.styles['CustomBody']))
            
            risk_data = [['Contact', 'Risk %', 'Total Messages', 'Suspicious Messages']]
            
            for contact, risk_info in contact_risks.items():
                risk_percentage = risk_info.get('risk_percentage', 0)
                total_msgs = risk_info.get('total_messages', 0)
                suspicious_msgs = risk_info.get('suspicious_messages', 0)
                
                risk_data.append([
                    contact,
                    f"{risk_percentage}%",
                    str(total_msgs),
                    str(suspicious_msgs)
                ])
            
            risk_table = Table(risk_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(risk_table)
        
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_network_analysis(self, report_data: Dict[str, Any]) -> list:
        """Create network analysis section."""
        
        elements = []
        elements.append(Paragraph("NETWORK ANALYSIS", self.styles['CustomHeading']))
        
        analysis_results = report_data.get('analysis_results', {})
        network_analysis = analysis_results.get('network_analysis', {})
        
        network_text = f"""
        Network Structure Analysis:
        • Total Network Nodes: {network_analysis.get('total_nodes', 0)}
        • Total Relationships: {network_analysis.get('total_relationships', 0)}
        • Network Density: {network_analysis.get('network_density', 'Unknown')}
        """
        
        elements.append(Paragraph(network_text, self.styles['CustomBody']))
        
        # Key players
        key_players = network_analysis.get('key_players', [])
        if key_players:
            elements.append(Paragraph("Key Players (Most Connected Individuals):", self.styles['CustomBody']))
            
            players_data = [['Name', 'Phone', 'Connections', 'Total Interactions']]
            
            for player in key_players[:5]:  # Top 5
                players_data.append([
                    player.get('name', 'Unknown'),
                    player.get('phone', 'Unknown'),
                    str(player.get('connections', 0)),
                    str(player.get('total_interactions', 0))
                ])
            
            players_table = Table(players_data, colWidths=[1.5*inch, 1.5*inch, 1*inch, 1*inch])
            players_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(players_table)
        
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_evidence_details(self, report_data: Dict[str, Any]) -> list:
        """Create evidence details section."""
        
        elements = []
        elements.append(Paragraph("EVIDENCE DETAILS", self.styles['CustomHeading']))
        
        # Sample evidence from raw data
        raw_data = report_data.get('raw_data', {})
        
        # Chat evidence
        chat_records = raw_data.get('chat_records', [])
        if chat_records:
            elements.append(Paragraph("Sample Chat Records:", self.styles['CustomBody']))
            
            for i, chat in enumerate(chat_records[:3]):  # Show first 3
                chat_text = f"""
                Record {i+1}: {chat.get('app_name', 'Unknown')} message
                From: {chat.get('sender_number', 'Unknown')} 
                To: {chat.get('receiver_number', 'Unknown')}
                Time: {chat.get('timestamp', 'Unknown')}
                Content: {chat.get('message_content', 'N/A')[:100]}...
                """
                elements.append(Paragraph(chat_text, self.styles['CustomBody']))
        
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_recommendations(self, report_data: Dict[str, Any]) -> list:
        """Create recommendations section."""
        
        elements = []
        elements.append(Paragraph("RECOMMENDATIONS FOR FURTHER INVESTIGATION", self.styles['CustomHeading']))
        
        recommendations = [
            "1. Focus investigation on high-risk contacts (>50% risk score)",
            "2. Analyze deleted messages for potential evidence destruction",
            "3. Cross-reference communication timelines with known events",
            "4. Investigate zero-duration calls for failed contact attempts",
            "5. Review media files for additional evidence",
            "6. Conduct deeper analysis of suspicious keyword patterns",
            "7. Map complete communication network for all identified contacts"
        ]
        
        for rec in recommendations:
            elements.append(Paragraph(rec, self.styles['CustomBody']))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Data limitations
        elements.append(Paragraph("DATA LIMITATIONS & MISSING INFORMATION", self.styles['CustomHeading']))
        
        limitations = [
            "• Some metadata may be incomplete depending on extraction method",
            "• Network analysis limited to available relationship data",
            "• Content analysis depends on message preservation and accessibility",
            "• Risk assessment based on available communication patterns only"
        ]
        
        for limitation in limitations:
            elements.append(Paragraph(limitation, self.styles['CustomBody']))
        
        return elements

# Global instance
pdf_generator = PDFReportGenerator()