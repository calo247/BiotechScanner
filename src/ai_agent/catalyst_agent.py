"""
AI Research Agent for comprehensive catalyst analysis.
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

from ..database.database import get_db_session
from ..database.models import Drug, Company, CatalystReport
from .tools import CatalystAnalysisTools
from .llm_client import OpenRouterClient
import time
import re


class CatalystResearchAgent:
    """AI agent that analyzes biotech catalysts using multiple data sources."""
    
    def __init__(self):
        self.tools = CatalystAnalysisTools()
        self.session = get_db_session()
        
        # Always require LLM client with Claude Sonnet 4
        try:
            self.llm_client = OpenRouterClient()
        except ValueError as e:
            # Clean up resources before raising
            self.tools.close()
            self.session.close()
            raise ValueError(f"LLM client initialization failed: {e}\n"
                           "Please set OPENROUTER_API_KEY in your .env file.\n"
                           "Get your API key at: https://openrouter.ai/keys")
    
    def analyze_catalyst(self, drug_id: int) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of a specific catalyst.
        
        Args:
            drug_id: ID of the drug/catalyst to analyze
            
        Returns:
            Comprehensive report including all analysis results
        """
        # Get drug and company info
        drug = self.session.query(Drug).filter(Drug.id == drug_id).first()
        if not drug:
            return {"error": "Drug not found"}
        
        company = drug.company
        
        # Gather all relevant data using our tools
        analysis_data = {
            "drug_info": {
                "name": drug.drug_name,
                "company": company.name,
                "ticker": company.ticker,
                "stage": drug.stage,
                "indication": drug.indications_text,
                "catalyst_date": drug.catalyst_date.isoformat() if drug.catalyst_date else None,
                "mechanism_of_action": drug.mechanism_of_action
            }
        }
        
        # 1. Historical Success Rate Analysis
        stage_parts = drug.stage.split()
        main_stage = stage_parts[0] if stage_parts else drug.stage
        
        # Extract indication from the drug data
        indication = None
        if drug.indications:
            if isinstance(drug.indications, list) and drug.indications:
                # Handle list of indications (might be strings or dicts)
                first_indication = drug.indications[0]
                if isinstance(first_indication, dict):
                    indication = first_indication.get('indication', '') or first_indication.get('name', '')
                else:
                    indication = str(first_indication)
            elif isinstance(drug.indications, dict):
                indication = drug.indications.get('indication', '') or drug.indications.get('name', '')
            else:
                indication = str(drug.indications)
        
        # Fall back to indications_text if needed
        if not indication and drug.indications_text:
            indication = drug.indications_text
        
        analysis_data["historical_analysis"] = self.tools.get_historical_success_rate(
            stage=main_stage,
            indication=indication
        )
        
        # 2. Company Track Record
        analysis_data["company_track_record"] = self.tools.get_company_track_record(company.id)
        
        # 3. Financial Health
        analysis_data["financial_health"] = self.tools.analyze_financial_health(company.id)
        
        # 4. SEC Filing Analysis
        search_terms = [drug.drug_name]
        if indication:
            search_terms.append(indication)
        
        analysis_data["sec_insights"] = self.tools.search_sec_filings(
            company_id=company.id,
            search_terms=search_terms,
            filing_types=['10-K', '10-Q', '8-K']
        )
        
        # 5. Competitive Landscape
        if indication:
            analysis_data["competitive_landscape"] = self.tools.get_competitive_landscape(
                indication=indication,
                stage=main_stage
            )
        else:
            analysis_data["competitive_landscape"] = []
        
        # 6. Generate Report using LLM
        # Use LLM for enhanced SEC insights if available
        if analysis_data["sec_insights"] and drug.drug_name:
            enhanced_sec = self.llm_client.extract_sec_insights(
                analysis_data["sec_insights"],
                drug.drug_name,
                indication or "unspecified indication"
            )
            analysis_data["sec_insights_summary"] = enhanced_sec
        
        # Generate LLM-powered report
        start_time = time.time()
        llm_report = self.llm_client.analyze_catalyst(analysis_data)
        if not llm_report:
            raise RuntimeError("Failed to generate LLM report. Please check your OpenRouter API key and internet connection.")
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        # Save report to database
        report_record = self._save_report(
            drug=drug,
            company=company,
            report=llm_report,
            analysis_data=analysis_data,
            generation_time_ms=generation_time_ms
        )
        
        return {
            "analysis_data": analysis_data,
            "report": llm_report,
            "report_id": report_record.id
        }
    
    
    def _save_report(self, drug: Drug, company: Company, report: str, 
                     analysis_data: Dict[str, Any], generation_time_ms: int) -> CatalystReport:
        """Save the generated report to the database."""
        # Extract key metrics from the report
        success_prob = self._extract_success_probability(report)
        recommendation = self._extract_recommendation(report)
        upside, downside = self._extract_price_targets(report)
        risk_level = self._extract_risk_level(report)
        summary = self._extract_summary(report)
        
        # Create report record
        report_record = CatalystReport(
            drug_id=drug.id,
            company_id=company.id,
            report_type='full_analysis',
            model_used='anthropic/claude-sonnet-4',
            report_markdown=report,
            report_summary=summary,
            success_probability=success_prob,
            price_target_upside=upside,
            price_target_downside=downside,
            recommendation=recommendation,
            risk_level=risk_level,
            analysis_data=analysis_data,
            generation_time_ms=generation_time_ms
        )
        
        self.session.add(report_record)
        self.session.commit()
        
        return report_record
    
    def _extract_success_probability(self, report: str) -> Optional[float]:
        """Extract success probability from report text."""
        # Look for patterns like "65-75%" or "45%" or "Probability of Success: 65%"
        patterns = [
            r'Probability of Success:\s*(\d+)(?:-\d+)?%',
            r'Success Probability:\s*(\d+)(?:-\d+)?%',
            r'Estimated Success Probability:\s*(\d+)(?:-\d+)?%',
            r'probability.*?(\d+)(?:-\d+)?%'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, report, re.IGNORECASE)
            if match:
                return float(match.group(1)) / 100.0
        
        return None
    
    def _extract_recommendation(self, report: str) -> Optional[str]:
        """Extract investment recommendation from report."""
        # Look for patterns like "BUY with High Risk" or "HOLD" or "Rating: BUY"
        patterns = [
            r'RATING:\s*([A-Z][A-Za-z\s]+)',
            r'Rating:\s*([A-Z][A-Za-z\s]+)',
            r'RECOMMENDATION:\s*([A-Z][A-Za-z\s]+)',
            r'Recommendation:\s*([A-Z][A-Za-z\s]+)',
            r'\*\*RATING:\s*([A-Z][A-Za-z\s]+)\*\*',
            r'\*\*([A-Z]+(?:\s+with\s+[A-Za-z\s]+)?)\*\*'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, report)
            if match:
                rec = match.group(1).strip()
                if any(word in rec.upper() for word in ['BUY', 'SELL', 'HOLD', 'AVOID']):
                    return rec
        
        return None
    
    def _extract_price_targets(self, report: str) -> tuple[Optional[str], Optional[str]]:
        """Extract upside and downside price targets."""
        upside = None
        downside = None
        
        # Look for upside patterns
        upside_patterns = [
            r'upside.*?(\d+[-–]\d+%)',
            r'upside.*?(\d+%)',
            r'(\d+[-–]\d+%)\s*upside',
            r'(\d+%)\s*upside'
        ]
        
        for pattern in upside_patterns:
            match = re.search(pattern, report, re.IGNORECASE)
            if match:
                upside = match.group(1)
                break
        
        # Look for downside patterns
        downside_patterns = [
            r'downside.*?(\d+[-–]\d+%)',
            r'downside.*?(\d+%)',
            r'(\d+[-–]\d+%)\s*(?:downside|decline)',
            r'(\d+%)\s*(?:downside|decline)'
        ]
        
        for pattern in downside_patterns:
            match = re.search(pattern, report, re.IGNORECASE)
            if match:
                downside = match.group(1)
                break
        
        return upside, downside
    
    def _extract_risk_level(self, report: str) -> Optional[str]:
        """Extract risk level from report."""
        # Look for explicit risk mentions
        if re.search(r'high.{0,10}risk|risk.{0,10}high', report, re.IGNORECASE):
            return "High"
        elif re.search(r'moderate.{0,10}risk|risk.{0,10}moderate', report, re.IGNORECASE):
            return "Moderate"
        elif re.search(r'low.{0,10}risk|risk.{0,10}low', report, re.IGNORECASE):
            return "Low"
        
        return None
    
    def _extract_summary(self, report: str) -> Optional[str]:
        """Extract or generate a brief summary from the report."""
        # Look for executive summary or overall assessment sections
        summary_match = re.search(
            r'(?:Executive Summary|Overall.*Assessment|OVERALL.*ASSESSMENT)[:\n]+(.+?)(?:\n\n|\n#)',
            report,
            re.IGNORECASE | re.DOTALL
        )
        
        if summary_match:
            summary = summary_match.group(1).strip()
            # Limit to first 500 characters
            if len(summary) > 500:
                summary = summary[:497] + "..."
            return summary
        
        # Fallback: use first paragraph after title
        lines = report.split('\n')
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and not line.startswith('#'):
                return line.strip()[:500]
        
        return None
    
    def close(self):
        """Clean up resources."""
        self.tools.close()
        self.session.close()