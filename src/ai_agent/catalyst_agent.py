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
        
        print("\n" + "="*60)
        print("📋 INITIAL DRUG AND COMPANY DATA")
        print("="*60)
        print(f"Drug ID: {drug.id}")
        print(f"Drug Name: {drug.drug_name}")
        print(f"Company: {company.name}")
        print(f"Ticker: {company.ticker}")
        print(f"Company ID: {company.id}")
        print(f"Stage: {drug.stage}")
        print(f"Stage Event Label: {drug.stage_event_label}")
        print(f"Catalyst Date: {drug.catalyst_date}")
        print(f"Catalyst Date Text: {drug.catalyst_date_text}")
        print(f"Has Catalyst: {drug.has_catalyst}")
        print(f"Mechanism of Action: {drug.mechanism_of_action}")
        print(f"Market Info: {drug.market_info}")
        print(f"Note: {drug.note}")
        print(f"Catalyst Source: {drug.catalyst_source}")
        print(f"Last Update Name: {drug.last_update_name}")
        print(f"API Last Updated: {drug.api_last_updated}")
        print("="*60)
        
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
        # Extract the main stage (e.g., "Phase 2" from "Phase 2 - randomized")
        # We want to keep "Phase X" together, not just "Phase"
        if drug.stage.startswith("Phase"):
            # Match "Phase" followed by a space and number/roman numeral
            import re
            phase_match = re.match(r'(Phase\s+\w+)', drug.stage)
            if phase_match:
                main_stage = phase_match.group(1)
            else:
                # If no number found, just use the whole thing before hyphen
                main_stage = drug.stage.split('-')[0].strip()
        else:
            # For non-Phase stages (like "Approved", "NDA", etc.)
            main_stage = drug.stage.split('-')[0].strip()
        
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
        
        print("\n" + "="*60)
        print("🔎 EXTRACTING INDICATION FROM DRUG DATA")
        print("="*60)
        print(f"Raw indications data: {drug.indications}")
        print(f"Indications text: {drug.indications_text}")
        print(f"Extracted indication: {indication}")
        print(f"Main stage extracted: {main_stage}")
        print("="*60)
        
        analysis_data["historical_analysis"] = self.tools.get_historical_success_rate(
            stage=main_stage,
            indication=indication
        )
        
        # Print historical analysis for logging
        print("\n" + "="*60)
        print("📊 HISTORICAL SUCCESS RATE ANALYSIS")
        print("="*60)
        # Flush output to ensure header appears before any fetch logs
        import sys
        sys.stdout.flush()
        hist = analysis_data["historical_analysis"]
        print(f"Stage: {main_stage}")
        print(f"Indication: {indication}")
        print(f"Total historical events found: {hist['total_events']}")
        if hist['total_events'] > 0:
            if 'note' in hist:
                print(f"Note: {hist['note']}")
            print(f"\nALL Historical catalyst details ({len(hist.get('catalyst_details', []))} total):")
            
            
            # Print ALL catalyst details, not limited
            for i, cat in enumerate(hist.get('catalyst_details', [])):
                print(f"\n{i+1}. {cat['date']}: {cat['company']} - {cat['drug']}")
                print(f"   Stage: {cat['stage']}")
                print(f"   Indication: {cat['indication']}")
                print(f"   Full Outcome Text: {cat['outcome']}")
                if cat.get('source_url'):
                    print(f"   Source: {cat['source_url']}")
                if cat.get('price_change') is not None:
                    print(f"   Price Change: {cat['price_change']:.1f}%")
                    if cat.get('price_change_note'):
                        print(f"   Note: {cat['price_change_note']}")
                elif cat.get('source_url'):
                    # If we have a URL but no price change, it means no price data was available
                    print(f"   Price Change: No data available (likely future event or insufficient trading history)")
        else:
            if 'note' in hist:
                print(f"Note: {hist['note']}")
        
        # 2. Company Track Record (filtered by indication/drug)
        analysis_data["company_track_record"] = self.tools.get_company_track_record(
            company_id=company.id,
            indication=indication,
            drug_name=drug.drug_name
        )
        
        # Print company track record for logging
        print("\n" + "="*60)
        print("🏢 COMPANY-SPECIFIC TRACK RECORD")
        print("="*60)
        track = analysis_data["company_track_record"]
        print(f"Company: {company.name} ({company.ticker})")
        print(f"Drug filter: {drug.drug_name}")
        print(f"Indication filter: {indication}")
        print(f"Total company events found: {track['total_events']}")
        if 'note' in track:
            print(f"Note: {track['note']}")
        if track.get('recent_catalysts'):
            print(f"\nALL Company catalyst history ({len(track['recent_catalysts'])} total):")
            
            
            for i, cat in enumerate(track['recent_catalysts']):
                print(f"\n{i+1}. {cat['date']}: {cat['drug']}")
                if cat.get('indication'):
                    print(f"   Indication: {cat['indication']}")
                print(f"   Stage: {cat['stage']}")
                print(f"   Full Outcome Text: {cat['outcome']}")
                if cat.get('source_url'):
                    print(f"   Source: {cat['source_url']}")
                if cat.get('price_change') is not None:
                    print(f"   Price Change: {cat['price_change']:.1f}%")
                    if cat.get('price_change_note'):
                        print(f"   Note: {cat['price_change_note']}")
                elif cat.get('source_url'):
                    # If we have a URL but no price change, it means no price data was available
                    print(f"   Price Change: No data available (likely future event or insufficient trading history)")
        else:
            print("No company-specific catalyst history found")
        
        # 3. Financial Health
        analysis_data["financial_health"] = self.tools.analyze_financial_health(company.id)
        
        # Print financial analysis for logging
        print("\n" + "="*60)
        print("💰 FINANCIAL HEALTH ANALYSIS")
        print("="*60)
        fin = analysis_data["financial_health"]
        print(f"Cash on hand: ${fin['cash_on_hand']:,.0f}")
        print(f"Annual revenue: ${fin['revenue']:,.0f}")
        print(f"Market cap: ${fin['market_cap']:,.0f}")
        print(f"Cash runway: {fin['cash_runway_guidance']}")
        
        if fin['revenue'] > 0:
            print(f"Revenue positive: Yes")
            if fin['market_cap'] > 0:
                price_to_sales = fin['market_cap'] / fin['revenue']
                print(f"Price-to-Sales ratio: {price_to_sales:.2f}x")
        else:
            print(f"Revenue positive: No (pre-revenue company)")
        
        if fin['cash_on_hand'] == 0:
            print("⚠️ WARNING: Company shows $0 cash - may indicate financial distress or stale data")
        
        print("\n📝 Note: Cash runway guidance will be searched in SEC filings during research phase")
        
        # 4. SEC Filing & Press Release Analysis - Dynamic LLM-driven search
        print("\n" + "="*60)
        print("🔬 STARTING AI-DRIVEN RESEARCH")
        print("="*60)
        drug_info_for_search = {
            "name": drug.drug_name,
            "company": company.name,
            "ticker": company.ticker,
            "stage": drug.stage,
            "indication": indication or drug.indications_text,
            "catalyst_date": drug.catalyst_date.isoformat() if drug.catalyst_date else None
        }
        
        # Use dynamic LLM-driven search
        sec_search_result = self.tools.dynamic_sec_research(
            company_id=company.id,
            drug_info=drug_info_for_search,
            initial_context={
                "historical_analysis": analysis_data["historical_analysis"],
                "company_track_record": analysis_data["company_track_record"],
                "financial_health": analysis_data["financial_health"]
            },
            llm_client=self.llm_client
        )
        
        analysis_data["sec_insights"] = sec_search_result["results"]
        analysis_data["sec_search_stats"] = sec_search_result["stats"]
        analysis_data["sec_search_history"] = sec_search_result["search_history"]
        
        # 5. Competitive Landscape
        if indication:
            analysis_data["competitive_landscape"] = self.tools.get_competitive_landscape(
                indication=indication,
                stage=main_stage
            )
        else:
            analysis_data["competitive_landscape"] = []
        
        # Print competitive landscape for logging
        print("\n" + "="*60)
        print("🏁 COMPETITIVE LANDSCAPE")
        print("="*60)
        competitors = analysis_data["competitive_landscape"]
        if competitors:
            print(f"Found {len(competitors)} competitors in {main_stage} for {indication}:")
            print(f"\nALL Competitors (sorted by market cap):")
            for i, comp in enumerate(competitors):
                print(f"\n{i+1}. {comp['company']} ({comp['ticker']})")
                print(f"   Drug: {comp['drug_name']}")
                print(f"   Stage: {comp['stage']}")
                print(f"   Catalyst Date: {comp.get('catalyst_date', 'Unknown')}")
                print(f"   Market Cap: ${comp['market_cap']:,.0f}")
                
                # Calculate relative market cap
                if fin['market_cap'] > 0 and comp['market_cap'] > 0:
                    relative_size = comp['market_cap'] / fin['market_cap']
                    print(f"   Relative Size: {relative_size:.1f}x vs analyzed company")
        else:
            print("No direct competitors found")
            print(f"This may indicate:")
            print(f"  - Novel approach to {indication}")
            print(f"  - Very rare indication with limited competition")
            print(f"  - First-in-class drug mechanism")
        
        # 6. Generate Report using LLM
        print("\n" + "="*60)
        print("📝 GENERATING FINAL CATALYST ANALYSIS REPORT")
        print("="*60)
        
        # Use LLM for enhanced SEC insights if available
        if analysis_data["sec_insights"] and drug.drug_name:
            print("Extracting enhanced SEC insights...")
            print(f"Number of SEC/Press Release results to analyze: {len(analysis_data['sec_insights'])}")
            
            enhanced_sec = self.llm_client.extract_sec_insights(
                analysis_data["sec_insights"],
                drug.drug_name,
                indication or "unspecified indication"
            )
            analysis_data["sec_insights_summary"] = enhanced_sec
            
            print("\n📊 ENHANCED SEC INSIGHTS:")
            print("-"*40)
            print(enhanced_sec)
            print("-"*40)
        
        # Generate LLM-powered report
        print("\n🤖 Generating comprehensive catalyst analysis report...")
        print(f"Analysis data includes:")
        print(f"  - Drug information")
        print(f"  - Historical success analysis ({analysis_data['historical_analysis']['total_events']} events)")
        print(f"  - Company track record ({analysis_data['company_track_record']['total_events']} events)")
        print(f"  - Financial health data")
        print(f"  - SEC/Press release insights ({len(analysis_data.get('sec_insights', []))} documents)")
        print(f"  - Competitive landscape ({len(analysis_data.get('competitive_landscape', []))} competitors)")
        
        start_time = time.time()
        llm_report = self.llm_client.analyze_catalyst(analysis_data)
        if not llm_report:
            raise RuntimeError("Failed to generate LLM report. Please check your OpenRouter API key and internet connection.")
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        print(f"\n✅ Report generated successfully in {generation_time_ms}ms")
        print("="*60)
        
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
            # Return full summary without truncation
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