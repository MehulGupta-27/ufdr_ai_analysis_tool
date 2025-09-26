"""
UFDR Comprehensive Report Generator with PDF export functionality.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.ai_service import ai_service
from app.services.vector_service import vector_service
from app.repositories.neo4j_repository import neo4j_repo
from config.settings import settings

class UFDRReportGenerator:
    def __init__(self):
        pass
    
    async def generate_comprehensive_report(self, case_number: str) -> Dict[str, Any]:
        """Generate a comprehensive UFDR analysis report for a case."""
        
        print(f"🔍 Generating comprehensive UFDR report for case: {case_number}")
        
        # Step 1: Gather all data
        case_data = await self._gather_case_data(case_number)
        
        if not case_data or not case_data.get('has_data'):
            return {
                "success": False,
                "error": "No data found for the specified case"
            }
        
        # Step 2: Perform comprehensive analysis
        analysis_results = await self._perform_comprehensive_analysis(case_data)
        
        # Step 3: Generate LLM-powered report
        report_content = await self._generate_llm_report(case_data, analysis_results)
        
        # Step 4: Structure the final report
        # Build dynamic statistics expected by frontend (no hardcoding of values)
        total_chats = len(case_data.get('chat_records', []))
        total_calls = len(case_data.get('call_records', []))
        total_contacts = len(case_data.get('contacts', []))
        total_media = len(case_data.get('media_files', []))
        suspicious_activities = (
            sum(1 for c in case_data.get('chat_records', []) if c.get('is_deleted'))
            + sum(1 for c in case_data.get('call_records', []) if (c.get('duration') or 0) == 0)
        )

        final_report = {
            "success": True,
            "case_number": case_number,
            "generated_at": datetime.now().isoformat(),
            "report_content": report_content,
            "raw_data": case_data,
            "analysis_results": analysis_results,
            # New: statistics block consumed by frontend summary tiles
            "statistics": {
                "total_contacts": total_contacts,
                "total_messages": total_chats,
                "total_calls": total_calls,
                "total_media_files": total_media,
                "suspicious_activities": suspicious_activities
            },
            "metadata": {
                "total_chat_records": total_chats,
                "total_call_records": total_calls,
                "total_contacts": total_contacts,
                "total_media_files": total_media,
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        return final_report
    
    async def _gather_case_data(self, case_number: str) -> Dict[str, Any]:
        """Gather all available data for a case."""
        
        case_data = {
            "case_number": case_number,
            "chat_records": [],
            "call_records": [],
            "contacts": [],
            "media_files": [],
            "ufdr_reports": [],
            "has_data": False
        }
        
        try:
            from app.services.case_manager import case_manager
            
            # Get case info to determine schema
            case_info = case_manager.get_case_info(case_number)
            if not case_info:
                print(f"❌ Case {case_number} not found in case manager")
                return case_data
            
            safe_case_name = case_info["safe_case_name"]
            schema_name = f"case_{safe_case_name}"
            print(f"🔍 Gathering data from schema: {schema_name}")
            
            db = next(get_db())
            
            # Get UFDR reports for this case from case-specific schema
            ufdr_query = text(f"""
                SELECT id, filename, device_info, extraction_date, investigator, processed
                FROM {schema_name}.ufdr_reports 
                WHERE case_number = :case_number
            """)
            ufdr_results = db.execute(ufdr_query, {"case_number": case_number}).fetchall()
            
            if not ufdr_results:
                print(f"⚠️ No UFDR reports found for case {case_number} in schema {schema_name}")
                return case_data
            
            for ufdr in ufdr_results:
                case_data["ufdr_reports"].append({
                    "id": str(ufdr.id),
                    "filename": ufdr.filename,
                    "device_info": ufdr.device_info,
                    "extraction_date": str(ufdr.extraction_date) if ufdr.extraction_date else None,
                    "investigator": ufdr.investigator,
                    "processed": ufdr.processed
                })
                
                ufdr_id = ufdr.id
                
                # Get chat records from case-specific schema
                chat_query = text(f"""
                    SELECT app_name, sender_number, receiver_number, message_content, 
                           timestamp, message_type, is_deleted, metadata
                    FROM {schema_name}.chat_records 
                    WHERE ufdr_report_id = :ufdr_id
                    ORDER BY timestamp DESC
                """)
                chat_results = db.execute(chat_query, {"ufdr_id": ufdr_id}).fetchall()
                
                for chat in chat_results:
                    case_data["chat_records"].append({
                        "app_name": chat.app_name,
                        "sender_number": chat.sender_number,
                        "receiver_number": chat.receiver_number,
                        "message_content": chat.message_content,
                        "timestamp": str(chat.timestamp) if chat.timestamp else None,
                        "message_type": chat.message_type,
                        "is_deleted": chat.is_deleted,
                        "metadata": chat.metadata
                    })
                
                # Get call records from case-specific schema
                call_query = text(f"""
                    SELECT caller_number, receiver_number, call_type, duration, timestamp, metadata
                    FROM {schema_name}.call_records 
                    WHERE ufdr_report_id = :ufdr_id
                    ORDER BY timestamp DESC
                """)
                call_results = db.execute(call_query, {"ufdr_id": ufdr_id}).fetchall()
                
                for call in call_results:
                    case_data["call_records"].append({
                        "caller_number": call.caller_number,
                        "receiver_number": call.receiver_number,
                        "call_type": call.call_type,
                        "duration": call.duration,
                        "timestamp": str(call.timestamp) if call.timestamp else None,
                        "metadata": call.metadata
                    })
                
                # Get contacts from case-specific schema
                contact_query = text(f"""
                    SELECT name, phone_numbers, email_addresses, metadata
                    FROM {schema_name}.contacts 
                    WHERE ufdr_report_id = :ufdr_id
                """)
                contact_results = db.execute(contact_query, {"ufdr_id": ufdr_id}).fetchall()
                
                for contact in contact_results:
                    case_data["contacts"].append({
                        "name": contact.name,
                        "phone_numbers": contact.phone_numbers,
                        "email_addresses": contact.email_addresses,
                        "metadata": contact.metadata
                    })
                
                # Get media files from case-specific schema
                media_query = text(f"""
                    SELECT filename, file_path, file_type, file_size, created_date, 
                           modified_date, hash_md5, hash_sha256, metadata
                    FROM {schema_name}.media_files 
                    WHERE ufdr_report_id = :ufdr_id
                """)
                media_results = db.execute(media_query, {"ufdr_id": ufdr_id}).fetchall()
                
                for media in media_results:
                    case_data["media_files"].append({
                        "filename": media.filename,
                        "file_path": media.file_path,
                        "file_type": media.file_type,
                        "file_size": media.file_size,
                        "created_date": str(media.created_date) if media.created_date else None,
                        "modified_date": str(media.modified_date) if media.modified_date else None,
                        "hash_md5": media.hash_md5,
                        "hash_sha256": media.hash_sha256,
                        "metadata": media.metadata
                    })
            
            db.close()
            
            # Check if we have any data
            total_records = (len(case_data["chat_records"]) + 
                           len(case_data["call_records"]) + 
                           len(case_data["contacts"]) + 
                           len(case_data["media_files"]))
            
            case_data["has_data"] = total_records > 0
            
            print(f"📊 Gathered data: {len(case_data['chat_records'])} chats, {len(case_data['call_records'])} calls, {len(case_data['contacts'])} contacts, {len(case_data['media_files'])} files")
            
        except Exception as e:
            print(f"❌ Error gathering case data: {e}")
        
        return case_data
    
    async def _perform_comprehensive_analysis(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive analysis on the case data."""
        
        analysis = {
            "communication_patterns": {},
            "network_analysis": {},
            "risk_assessment": {},
            "timeline_analysis": {},
            "content_analysis": {},
            "device_analysis": {}
        }
        
        try:
            # Communication Patterns Analysis
            analysis["communication_patterns"] = self._analyze_communication_patterns(case_data)
            
            # Network Analysis (Neo4j)
            analysis["network_analysis"] = await self._analyze_network_relationships(case_data)
            
            # Risk Assessment
            analysis["risk_assessment"] = self._assess_criminal_risk(case_data)
            
            # Timeline Analysis
            analysis["timeline_analysis"] = self._analyze_timeline(case_data)
            
            # Content Analysis
            analysis["content_analysis"] = await self._analyze_content(case_data)
            
            # Device Analysis
            analysis["device_analysis"] = self._analyze_device_info(case_data)
            
        except Exception as e:
            print(f"❌ Error in comprehensive analysis: {e}")
        
        return analysis
    
    def _analyze_communication_patterns(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze communication patterns."""
        
        patterns = {
            "total_communications": 0,
            "apps_used": {},
            "most_active_contacts": {},
            "communication_frequency": {},
            "deleted_messages": 0
        }
        
        # Analyze chat records
        for chat in case_data.get("chat_records", []):
            patterns["total_communications"] += 1
            
            app = chat.get("app_name", "Unknown")
            patterns["apps_used"][app] = patterns["apps_used"].get(app, 0) + 1
            
            sender = chat.get("sender_number", "Unknown")
            receiver = chat.get("receiver_number", "Unknown")
            
            for contact in [sender, receiver]:
                if contact != "Unknown":
                    patterns["most_active_contacts"][contact] = patterns["most_active_contacts"].get(contact, 0) + 1
            
            if chat.get("is_deleted", False):
                patterns["deleted_messages"] += 1
        
        # Analyze call records
        for call in case_data.get("call_records", []):
            patterns["total_communications"] += 1
            
            caller = call.get("caller_number", "Unknown")
            receiver = call.get("receiver_number", "Unknown")
            
            for contact in [caller, receiver]:
                if contact != "Unknown":
                    patterns["most_active_contacts"][contact] = patterns["most_active_contacts"].get(contact, 0) + 1
        
        return patterns
    
    async def _analyze_network_relationships(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze network relationships using Neo4j."""
        
        network = {
            "total_nodes": 0,
            "total_relationships": 0,
            "key_players": [],
            "connection_strength": {},
            "network_density": "Unknown"
        }
        
        try:
            # Get network statistics
            node_result = await neo4j_repo.execute_cypher("MATCH (n) RETURN count(n) as count")
            network["total_nodes"] = node_result[0]["count"] if node_result else 0
            
            rel_result = await neo4j_repo.execute_cypher("MATCH ()-[r]->() RETURN count(r) as count")
            network["total_relationships"] = rel_result[0]["count"] if rel_result else 0
            
            # Get key players (centrality analysis)
            centrality_query = """
            MATCH (p:Person)-[r]-(other:Person)
            WITH p, count(DISTINCT other) as connections, count(r) as total_interactions
            WHERE connections > 0
            RETURN p.name as name, p.phone_number as phone, 
                   connections, total_interactions
            ORDER BY connections DESC, total_interactions DESC
            LIMIT 5
            """
            
            key_players = await neo4j_repo.execute_cypher(centrality_query)
            network["key_players"] = key_players or []
            
            # Calculate network density
            if network["total_nodes"] > 1:
                max_possible_edges = network["total_nodes"] * (network["total_nodes"] - 1) / 2
                density = network["total_relationships"] / max_possible_edges if max_possible_edges > 0 else 0
                if density > 0.7:
                    network["network_density"] = "High"
                elif density > 0.3:
                    network["network_density"] = "Medium"
                else:
                    network["network_density"] = "Low"
            
        except Exception as e:
            print(f"❌ Error in network analysis: {e}")
        
        return network
    
    def _assess_criminal_risk(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess criminal risk based on communication patterns and content."""
        
        risk_factors = {
            "overall_risk_score": 0,
            "risk_level": "Low",
            "risk_factors": [],
            "suspicious_indicators": [],
            "contact_risk_scores": {}
        }
        
        risk_score = 0
        
        # Check for suspicious keywords in messages
        suspicious_keywords = [
            "verification code", "bank", "password", "account", "transfer", "money",
            "cash", "deal", "package", "delivery", "crypto", "bitcoin", "urgent",
            "secret", "delete", "destroy", "evidence"
        ]
        
        suspicious_count = 0
        for chat in case_data.get("chat_records", []):
            content = chat.get("message_content", "").lower()
            for keyword in suspicious_keywords:
                if keyword in content:
                    suspicious_count += 1
                    risk_factors["suspicious_indicators"].append(f"Message contains '{keyword}': {content[:50]}...")
                    break
        
        # Risk scoring
        if suspicious_count > 0:
            risk_score += min(suspicious_count * 10, 30)
            risk_factors["risk_factors"].append(f"Suspicious content detected in {suspicious_count} messages")
        
        # Check for deleted messages
        deleted_count = sum(1 for chat in case_data.get("chat_records", []) if chat.get("is_deleted", False))
        if deleted_count > 0:
            risk_score += min(deleted_count * 5, 20)
            risk_factors["risk_factors"].append(f"{deleted_count} deleted messages found")
        
        # Check for unusual call patterns (0-second calls)
        zero_calls = sum(1 for call in case_data.get("call_records", []) if call.get("duration", 0) == 0)
        if zero_calls > 0:
            risk_score += min(zero_calls * 15, 25)
            risk_factors["risk_factors"].append(f"{zero_calls} zero-duration calls (potential failed attempts)")
        
        # Check for multiple apps usage (potential evasion)
        apps_used = set(chat.get("app_name") for chat in case_data.get("chat_records", []))
        if len(apps_used) > 3:
            risk_score += 10
            risk_factors["risk_factors"].append(f"Multiple communication apps used: {', '.join(apps_used)}")
        
        # Assess individual contact risk
        contact_interactions = {}
        for chat in case_data.get("chat_records", []):
            sender = chat.get("sender_number")
            receiver = chat.get("receiver_number")
            content = chat.get("message_content", "").lower()
            
            for contact in [sender, receiver]:
                if contact and contact != "Unknown":
                    if contact not in contact_interactions:
                        contact_interactions[contact] = {"messages": 0, "suspicious": 0}
                    contact_interactions[contact]["messages"] += 1
                    
                    # Check for suspicious content from this contact
                    for keyword in suspicious_keywords:
                        if keyword in content:
                            contact_interactions[contact]["suspicious"] += 1
                            break
        
        # Calculate contact risk scores
        for contact, data in contact_interactions.items():
            contact_risk = 0
            if data["suspicious"] > 0:
                contact_risk = min((data["suspicious"] / data["messages"]) * 100, 100)
            risk_factors["contact_risk_scores"][contact] = {
                "risk_percentage": round(contact_risk, 1),
                "total_messages": data["messages"],
                "suspicious_messages": data["suspicious"]
            }
        
        # Final risk assessment
        risk_factors["overall_risk_score"] = min(risk_score, 100)
        
        if risk_score >= 70:
            risk_factors["risk_level"] = "High"
        elif risk_score >= 40:
            risk_factors["risk_level"] = "Medium"
        else:
            risk_factors["risk_level"] = "Low"
        
        return risk_factors
    
    def _analyze_timeline(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze timeline of communications."""
        
        timeline = {
            "date_range": {},
            "activity_patterns": {},
            "peak_activity_times": [],
            "communication_sequence": []
        }
        
        all_events = []
        
        # Collect all timestamped events
        for chat in case_data.get("chat_records", []):
            if chat.get("timestamp"):
                all_events.append({
                    "timestamp": chat["timestamp"],
                    "type": "chat",
                    "app": chat.get("app_name", "Unknown"),
                    "participants": [chat.get("sender_number"), chat.get("receiver_number")]
                })
        
        for call in case_data.get("call_records", []):
            if call.get("timestamp"):
                all_events.append({
                    "timestamp": call["timestamp"],
                    "type": "call",
                    "call_type": call.get("call_type", "Unknown"),
                    "duration": call.get("duration", 0),
                    "participants": [call.get("caller_number"), call.get("receiver_number")]
                })
        
        # Sort by timestamp
        all_events.sort(key=lambda x: x["timestamp"])
        
        if all_events:
            timeline["date_range"] = {
                "start": all_events[0]["timestamp"],
                "end": all_events[-1]["timestamp"]
            }
            timeline["communication_sequence"] = all_events[:10]  # First 10 events
        
        return timeline
    
    async def _analyze_content(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze content using vector search for semantic insights."""
        
        content_analysis = {
            "key_topics": [],
            "sentiment_indicators": [],
            "language_patterns": {},
            "content_categories": {}
        }
        
        try:
            # Analyze message content for key topics
            all_messages = [chat.get("message_content", "") for chat in case_data.get("chat_records", []) if chat.get("message_content")]
            
            if all_messages:
                # Use vector search to find similar content patterns
                sample_queries = [
                    "business transaction",
                    "meeting appointment", 
                    "financial discussion",
                    "security verification",
                    "personal conversation"
                ]
                
                for query in sample_queries:
                    try:
                        results = await vector_service.semantic_search(query, limit=3)
                        if results:
                            content_analysis["key_topics"].append({
                                "topic": query,
                                "matches": len(results),
                                "relevance": results[0].get("score", 0.0) if results else 0.0
                            })
                    except:
                        continue
            
        except Exception as e:
            print(f"❌ Error in content analysis: {e}")
        
        return content_analysis
    
    def _analyze_device_info(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze device information."""
        
        device_analysis = {
            "devices_analyzed": [],
            "device_types": [],
            "os_versions": [],
            "extraction_methods": []
        }
        
        for ufdr in case_data.get("ufdr_reports", []):
            device_info = ufdr.get("device_info", {})
            if device_info:
                device_analysis["devices_analyzed"].append({
                    "filename": ufdr.get("filename", "Unknown"),
                    "device_info": device_info,
                    "extraction_date": ufdr.get("extraction_date"),
                    "investigator": ufdr.get("investigator")
                })
        
        return device_analysis
    
    async def _generate_llm_report(self, case_data: Dict[str, Any], analysis_results: Dict[str, Any]) -> str:
        """Generate comprehensive LLM-powered forensic report."""
        
        # Prepare data summary for LLM
        data_summary = {
            "case_number": case_data.get("case_number"),
            "total_chat_records": len(case_data.get("chat_records", [])),
            "total_call_records": len(case_data.get("call_records", [])),
            "total_contacts": len(case_data.get("contacts", [])),
            "total_media_files": len(case_data.get("media_files", [])),
            "communication_patterns": analysis_results.get("communication_patterns", {}),
            "network_analysis": analysis_results.get("network_analysis", {}),
            "risk_assessment": analysis_results.get("risk_assessment", {}),
            "timeline_analysis": analysis_results.get("timeline_analysis", {}),
            "device_analysis": analysis_results.get("device_analysis", {})
        }
        
        # Create comprehensive prompt for LLM
        report_prompt = f"""
Generate a comprehensive forensic investigation report based on the following UFDR analysis data:

CASE DATA SUMMARY:
{json.dumps(data_summary, indent=2, default=str)}

SAMPLE COMMUNICATIONS:
{self._get_sample_communications(case_data)}

REQUIREMENTS:
1. Generate a professional forensic report suitable for law enforcement
2. Include executive summary, key findings, evidence analysis, risk assessment, and recommendations
3. Provide criminal risk percentage for each contact based on communication patterns
4. Mention if any information is not available or insufficient
5. Keep the report comprehensive but focused on actionable intelligence
6. Include specific evidence references and timestamps where available
7. Assess the overall threat level and provide investigation priorities

FORMAT:
- Executive Summary
- Key Findings & Evidence
- Network Analysis & Key Players
- Criminal Risk Assessment (with percentages)
- Timeline Analysis
- Recommendations for Further Investigation
- Data Limitations & Missing Information

Generate a complete, professional forensic investigation report now:
"""
        
        try:
            if ai_service.gemini_model:
                response = ai_service.gemini_model.generate_content(report_prompt)
                if response and response.text:
                    return response.text
            
            # Fallback report if LLM is not available
            return self._generate_fallback_report(case_data, analysis_results)
            
        except Exception as e:
            print(f"❌ Error generating LLM report: {e}")
            return self._generate_fallback_report(case_data, analysis_results)
    
    def _get_sample_communications(self, case_data: Dict[str, Any]) -> str:
        """Get sample communications for LLM context."""
        
        samples = []
        
        # Get sample chat records
        for i, chat in enumerate(case_data.get("chat_records", [])[:5]):
            samples.append(f"Chat {i+1}: {chat.get('app_name')} - {chat.get('sender_number')} to {chat.get('receiver_number')}: {chat.get('message_content', '')[:100]}...")
        
        # Get sample call records
        for i, call in enumerate(case_data.get("call_records", [])[:3]):
            samples.append(f"Call {i+1}: {call.get('call_type')} - {call.get('caller_number')} to {call.get('receiver_number')} ({call.get('duration', 0)}s)")
        
        return "\n".join(samples)
    
    def _generate_fallback_report(self, case_data: Dict[str, Any], analysis_results: Dict[str, Any]) -> str:
        """Generate fallback report when LLM is not available."""
        
        risk_assessment = analysis_results.get("risk_assessment", {})
        network_analysis = analysis_results.get("network_analysis", {})
        
        report = f"""
# COMPREHENSIVE UFDR FORENSIC ANALYSIS REPORT

**Case Number:** {case_data.get('case_number', 'Unknown')}
**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Report Generated By:** UFDR AI Analysis System

## EXECUTIVE SUMMARY

This report presents a comprehensive analysis of digital forensic data extracted from mobile devices. The analysis covers {len(case_data.get('chat_records', []))} chat records, {len(case_data.get('call_records', []))} call records, {len(case_data.get('contacts', []))} contacts, and {len(case_data.get('media_files', []))} media files.

**Overall Risk Level:** {risk_assessment.get('risk_level', 'Unknown')}
**Risk Score:** {risk_assessment.get('overall_risk_score', 0)}/100

## KEY FINDINGS & EVIDENCE

### Communication Patterns
- Total Communications: {analysis_results.get('communication_patterns', {}).get('total_communications', 0)}
- Apps Used: {', '.join(analysis_results.get('communication_patterns', {}).get('apps_used', {}).keys())}
- Deleted Messages: {analysis_results.get('communication_patterns', {}).get('deleted_messages', 0)}

### Network Analysis
- Network Nodes: {network_analysis.get('total_nodes', 0)}
- Network Relationships: {network_analysis.get('total_relationships', 0)}
- Network Density: {network_analysis.get('network_density', 'Unknown')}

## CRIMINAL RISK ASSESSMENT

### Contact Risk Scores:
"""
        
        # Add contact risk scores
        contact_risks = risk_assessment.get('contact_risk_scores', {})
        for contact, risk_data in contact_risks.items():
            report += f"\n- **{contact}**: {risk_data.get('risk_percentage', 0)}% risk ({risk_data.get('suspicious_messages', 0)}/{risk_data.get('total_messages', 0)} suspicious messages)"
        
        report += f"""

### Risk Factors Identified:
"""
        
        for factor in risk_assessment.get('risk_factors', []):
            report += f"\n- {factor}"
        
        report += f"""

## RECOMMENDATIONS

1. **High Priority Contacts**: Focus investigation on contacts with risk scores above 50%
2. **Content Analysis**: Review suspicious messages for criminal intent
3. **Network Mapping**: Investigate connections between high-risk contacts
4. **Timeline Correlation**: Cross-reference communication times with known events

## DATA LIMITATIONS

- LLM analysis service was not available for advanced content interpretation
- Some metadata may be incomplete depending on extraction method
- Network analysis limited to available relationship data

**End of Report**
"""
        
        return report

# Global instance
ufdr_report_generator = UFDRReportGenerator()