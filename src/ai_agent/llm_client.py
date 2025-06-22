"""
OpenRouter LLM client for enhanced catalyst analysis.
"""
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class OpenRouterClient:
    """Client for interacting with OpenRouter's LLM API."""
    
    def __init__(self):
        """
        Initialize OpenRouter client with Claude Sonnet 4.
        
        This uses Claude's latest and most capable Sonnet model for
        superior biotech catalyst analysis.
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        if self.api_key == "your_openrouter_api_key_here":
            raise ValueError("Please replace the placeholder API key with your actual OpenRouter API key")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )
        self.model = "anthropic/claude-sonnet-4"
        
        # Test the API key with a minimal request
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
        except Exception as e:
            if "401" in str(e):
                raise ValueError("Invalid OpenRouter API key. Please check your OPENROUTER_API_KEY in .env file")
            elif "402" in str(e):
                raise ValueError("OpenRouter account has insufficient credits. Please add credits at https://openrouter.ai/")
            else:
                raise ValueError(f"Failed to connect to OpenRouter: {str(e)}")
    
    def analyze_catalyst(self, analysis_data: Dict[str, Any]) -> str:
        """
        Generate an AI-powered analysis report for a catalyst.
        
        Args:
            analysis_data: Dictionary containing all gathered data about the catalyst
            
        Returns:
            AI-generated comprehensive report
        """
        # Prepare the system prompt
        system_prompt = """You are an expert biotech analyst specializing in catalyst events. 
Your task is to provide a comprehensive, nuanced analysis of biotech catalysts based on multiple data sources.

Key areas to focus on:
1. Interpret the historical success rates in context of the specific indication and stage
2. Assess the company's track record and what it means for this catalyst
3. Analyze financial runway and burn rate implications for catalyst success
4. Extract key insights from SEC filings that impact catalyst probability
5. Evaluate competitive landscape and differentiation
6. Provide an overall risk/reward assessment with specific reasoning

Be direct, data-driven, and highlight both opportunities and risks. Use specific numbers and examples from the data provided."""

        # Format the data for the prompt
        user_prompt = self._format_analysis_prompt(analysis_data)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            raise RuntimeError(f"OpenRouter API error: {str(e)}")
    
    def extract_sec_insights(self, filings: List[Dict[str, Any]], drug_name: str, indication: str) -> str:
        """
        Extract key insights from SEC filings using LLM.
        
        Args:
            filings: List of SEC filing excerpts
            drug_name: Name of the drug to focus on
            indication: Indication being treated
            
        Returns:
            Summary of key insights from SEC filings
        """
        if not filings:
            return "No recent SEC filings found."
        
        prompt = f"""Analyze these SEC filing excerpts for {drug_name} (treating {indication}).
Extract key insights about:
1. Clinical trial progress and results
2. Management commentary on the drug's prospects
3. Regulatory interactions or FDA feedback
4. Partnership or commercialization plans
5. Any risk factors specific to this drug

SEC Filing Excerpts:
{self._format_sec_filings(filings)}

Provide a concise summary of the most important insights:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            raise RuntimeError(f"OpenRouter API error (SEC analysis): {str(e)}")
    
    def _format_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Format the analysis data into a structured prompt."""
        drug_info = data["drug_info"]
        historical = data["historical_analysis"]
        track_record = data["company_track_record"]
        financial = data["financial_health"]
        competitors = data.get("competitive_landscape", [])
        sec_insights = data.get("sec_insights", [])
        
        prompt = f"""Analyze this biotech catalyst:

DRUG INFORMATION:
- Drug: {drug_info['name']}
- Company: {drug_info['company']} ({drug_info['ticker']})
- Stage: {drug_info['stage']}
- Indication: {drug_info['indication']}
- Catalyst Date: {drug_info['catalyst_date']}
- Mechanism of Action: {drug_info.get('mechanism_of_action', 'Not specified')}

HISTORICAL SUCCESS ANALYSIS:
- Similar catalysts analyzed: {historical['total_events']}
- Success rate: {historical['success_rate']:.1f}%
- Average price change: {historical['average_price_change']:.1f}%
- Positive outcomes: {historical['positive_outcomes']}

COMPANY TRACK RECORD:
- Total pipeline drugs: {track_record['total_drugs']}
- Approved drugs: {track_record['approved_drugs']}
- Failed drugs: {track_record['failed_drugs']}
- Company success rate: {track_record['success_rate']:.1f}%

Recent catalysts:
{self._format_recent_catalysts(track_record.get('recent_catalysts', []))}

FINANCIAL HEALTH:
- Cash on hand: ${financial['cash_on_hand']:,.0f}
- Quarterly burn rate: ${financial['quarterly_burn_rate']:,.0f}
- Estimated runway: {financial['runway_months']:.1f} months
- Annual revenue: ${financial['revenue']:,.0f}
- Market cap: ${financial['market_cap']:,.0f}

COMPETITIVE LANDSCAPE:
{self._format_competitors(competitors[:5])}

SEC FILING INSIGHTS:
{self._format_sec_summary(sec_insights[:3])}

Based on this comprehensive data, provide a detailed catalyst analysis report including:
1. Overall catalyst assessment (probability of success and rationale)
2. Key opportunities and catalysts for upside
3. Major risks and potential downside scenarios
4. How this catalyst compares to historical precedents
5. Investment recommendation with specific reasoning"""
        
        return prompt
    
    def _format_recent_catalysts(self, catalysts: List[Dict]) -> str:
        """Format recent catalyst history."""
        if not catalysts:
            return "No recent catalyst history available."
        
        formatted = []
        for cat in catalysts[:3]:
            outcome = cat.get('outcome', 'No details')[:100] + '...' if len(cat.get('outcome', '')) > 100 else cat.get('outcome', 'No details')
            formatted.append(f"- {cat['date']}: {cat['drug']} ({cat['stage']}) - {outcome}")
        
        return "\n".join(formatted)
    
    def _format_competitors(self, competitors: List[Dict]) -> str:
        """Format competitive landscape."""
        if not competitors:
            return "No direct competitors identified."
        
        formatted = []
        for comp in competitors:
            formatted.append(
                f"- {comp['company']} ({comp['ticker']}): {comp['drug_name']} - "
                f"{comp['stage']} - Market Cap: ${comp['market_cap']:,.0f}"
            )
        
        return "\n".join(formatted)
    
    def _format_sec_summary(self, filings: List[Dict]) -> str:
        """Format SEC filing insights summary."""
        if not filings:
            return "No recent relevant SEC filings found."
        
        formatted = []
        for filing in filings:
            formatted.append(f"{filing['filing_type']} ({filing['filing_date']}): {len(filing.get('matches', []))} relevant mentions")
        
        return "\n".join(formatted)
    
    def _format_sec_filings(self, filings: List[Dict]) -> str:
        """Format SEC filings for analysis."""
        formatted = []
        for filing in filings:
            formatted.append(f"\n{filing['filing_type']} - {filing['filing_date']}:")
            for match in filing.get('matches', []):
                formatted.append(f"- {match['section']}: {match['excerpt']}")
        
        return "\n".join(formatted)