"""
AI Research Agent for comprehensive catalyst analysis.
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

from ..database.database import get_db_session
from ..database.models import Drug, Company
from .tools import CatalystAnalysisTools


class CatalystResearchAgent:
    """AI agent that analyzes biotech catalysts using multiple data sources."""
    
    def __init__(self, llm_client=None):
        self.tools = CatalystAnalysisTools()
        self.llm_client = llm_client  # Will integrate OpenRouter here
        self.session = get_db_session()
    
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
        
        # 6. Generate Report
        report = self._generate_report(analysis_data)
        
        return {
            "analysis_data": analysis_data,
            "report": report
        }
    
    def _generate_report(self, data: Dict[str, Any]) -> str:
        """
        Generate a comprehensive report from the analysis data.
        For now, this is template-based. Will integrate LLM later.
        """
        drug_info = data["drug_info"]
        historical = data["historical_analysis"]
        track_record = data["company_track_record"]
        financial = data["financial_health"]
        
        report = f"""
# Catalyst Analysis Report: {drug_info['name']}

## Executive Summary

**Company:** {drug_info['company']} ({drug_info['ticker']})  
**Drug:** {drug_info['name']}  
**Stage:** {drug_info['stage']}  
**Indication:** {drug_info['indication']}  
**Catalyst Date:** {drug_info['catalyst_date']}  

## Historical Success Rate Analysis

Based on {historical['total_events']} similar historical catalysts:
- **Success Rate:** {historical['success_rate']:.1f}%
- **Average Price Movement:** {historical['average_price_change']:.1f}%
- **Positive Outcomes:** {historical['positive_outcomes']} out of {historical['total_events']}

## Company Track Record

{drug_info['company']} has a total of {track_record['total_drugs']} drugs in their pipeline:
- **Approved Drugs:** {track_record['approved_drugs']}
- **Failed Drugs:** {track_record['failed_drugs']}
- **Overall Success Rate:** {track_record['success_rate']:.1f}%

### Recent Catalyst History:
"""
        
        for catalyst in track_record.get('recent_catalysts', [])[:3]:
            report += f"- {catalyst['date']}: {catalyst['drug']} ({catalyst['stage']}) - {catalyst['outcome'][:100]}...\n"
        
        report += f"""

## Financial Health Assessment

- **Cash on Hand:** ${financial['cash_on_hand']:,.0f}
- **Quarterly Burn Rate:** ${financial['quarterly_burn_rate']:,.0f}
- **Estimated Runway:** {financial['runway_months']:.1f} months
- **Annual Revenue:** ${financial['revenue']:,.0f}
- **Market Cap:** ${financial['market_cap']:,.0f}

## Risk Assessment

"""
        
        # Financial risk
        if financial['runway_months'] < 12:
            report += "⚠️ **Financial Risk:** Company has less than 12 months of cash runway.\n"
        elif financial['runway_months'] < 24:
            report += "⚡ **Moderate Financial Risk:** Company has 12-24 months of runway.\n"
        else:
            report += "✅ **Low Financial Risk:** Company has over 24 months of runway.\n"
        
        # Historical risk
        if historical['success_rate'] < 30:
            report += "⚠️ **Historical Risk:** Similar catalysts have low success rate (<30%).\n"
        elif historical['success_rate'] < 60:
            report += "⚡ **Moderate Historical Risk:** Similar catalysts have moderate success rate (30-60%).\n"
        else:
            report += "✅ **Low Historical Risk:** Similar catalysts have high success rate (>60%).\n"
        
        # Competition
        competitors = data.get('competitive_landscape', [])
        if len(competitors) > 5:
            report += f"⚡ **Competitive Risk:** {len(competitors)} competing drugs in similar stage.\n"
        
        report += "\n## SEC Filing Insights\n\n"
        
        sec_insights = data.get('sec_insights', [])
        if sec_insights:
            for filing in sec_insights[:3]:
                report += f"**{filing['filing_type']} ({filing['filing_date']}):**\n"
                for match in filing['matches'][:2]:
                    report += f"- {match['section']}: {match['excerpt']}\n"
                report += "\n"
        else:
            report += "No recent relevant mentions in SEC filings.\n"
        
        return report
    
    def close(self):
        """Clean up resources."""
        self.tools.close()
        self.session.close()