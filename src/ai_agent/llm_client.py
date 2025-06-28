"""
OpenRouter LLM client for enhanced catalyst analysis.
"""
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv
import json
import re

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
Your task is to provide a comprehensive, nuanced analysis of biotech catalysts for a PUBLIC REPORT.

IMPORTANT: This is a public-facing investment report. Do NOT mention:
- How the data was gathered or searched
- Technical details about databases or search methods
- Internal workflow or research process
- Just present the findings and analysis directly

Key areas to focus on:
1. Interpret the historical success rates in context of the specific indication and stage
2. Assess the company's track record and what it means for this catalyst
3. Analyze financial runway and burn rate implications for catalyst success
4. Present key insights from regulatory filings and announcements
5. Evaluate competitive landscape and differentiation
6. Provide an overall risk/reward assessment with specific reasoning

Be direct, data-driven, and highlight both opportunities and risks. Use specific numbers and examples from the data provided.
Write as if you have direct knowledge of the information, not as if you searched for it."""

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
            outcome = cat.get('outcome', 'No details')
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
    
    def generate_search_query(self, context: Dict[str, Any], search_history: List[Dict]) -> Dict[str, Any]:
        """
        Generate the next search query based on context and previous searches.
        
        Returns:
            Dictionary with 'query', 'reasoning', 'looking_for', and optionally 'done'
        """
        # Build context for the LLM
        prompt = f"""You are researching a biotech catalyst using SEC filing search AND company press releases. 
You can search both SEC filings and recent press releases. Press releases often contain the most recent catalyst data before it appears in SEC filings.
Based on the information gathered so far, decide what to search for next.

CATALYST INFORMATION:
- Drug: {context['drug_info']['name']}
- Company: {context['drug_info']['company']} ({context['drug_info']['ticker']})
- Stage: {context['drug_info']['stage']}
- Indication: {context['drug_info']['indication']}
- Catalyst Date: {context['drug_info']['catalyst_date']}

CONTEXT FROM OTHER SOURCES:
- Historical Success Rate: {context.get('historical_analysis', {}).get('success_rate', 'Unknown')}%
- Company Track Record: {context.get('company_track_record', {}).get('success_rate', 'Unknown')}%

COMPLETE FINANCIAL DATA (from XBRL - no need to search for this):
- Cash on Hand: ${context.get('financial_health', {}).get('cash_on_hand', 0):,.0f}
- Quarterly Burn Rate: ${context.get('financial_health', {}).get('quarterly_burn_rate', 0):,.0f}
- Cash Runway: {context.get('financial_health', {}).get('runway_months', 'Unknown')} months
- Annual Revenue: ${context.get('financial_health', {}).get('revenue', 0):,.0f}
- Market Cap: ${context.get('financial_health', {}).get('market_cap', 0):,.0f}

PREVIOUS SEARCHES PERFORMED:"""
        
        if search_history:
            for i, search in enumerate(search_history):
                prompt += f"\n\nSearch {i+1}: '{search['query']}'"
                prompt += f"\n- Found {search['results_found']} results"
                if search.get('key_findings'):
                    prompt += f"\n- Key findings: {search['key_findings']}"
        else:
            prompt += "\nNo searches performed yet."
        
        prompt += """

IMPORTANT: We already have complete financial data from XBRL filings in our database, including:
- Cash position: Already known from structured data
- Burn rate: Already calculated from quarterly filings
- Revenue: Already extracted from financial statements
DO NOT search for basic financial metrics - focus on clinical, regulatory, and strategic information.

Based on what you know and what has been searched, what should we search for next? Consider:
1. What critical CLINICAL or REGULATORY information is still missing?
2. What findings about the DRUG DEVELOPMENT need follow-up investigation?
3. Are there safety, efficacy, or trial design details to explore?
4. Should we look for FDA correspondence or regulatory feedback?
5. Are there partnership, licensing, or commercialization strategies to investigate?
6. What does management say about the drug's progress and prospects?

Focus on information that provides context BEYOND the numbers we already have.

If you have gathered sufficient information (typically after 4-6 targeted searches), set "done": true.

Respond with a JSON object:
{
    "query": "specific search terms to use",
    "reasoning": "why this search is important for the catalyst analysis",
    "looking_for": "what specific information you hope to find",
    "search_type": "sec" or "press_release",
    "done": false
}

Or if sufficient information has been gathered:
{
    "done": true,
    "summary": "brief summary of key findings"
}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=300
            )
            
            # Extract JSON from response
            response_text = response.choices[0].message.content
            
            # Try to find JSON in the response
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Fallback: create structured response from text
                    pass
            
            # If no valid JSON, create a structured response
            if "done" in response_text.lower() and "true" in response_text.lower():
                return {"done": True, "summary": "Sufficient information gathered"}
            
            # Default to a reasonable next search
            return {
                "query": f"{context['drug_info']['name']} clinical trial data",
                "reasoning": "Need to understand trial design and results",
                "looking_for": "Primary endpoints, patient population, efficacy data",
                "done": False
            }
            
        except Exception as e:
            print(f"Error generating search query: {e}")
            # Return a default search
            return {
                "query": f"{context['drug_info']['name']} development update",
                "reasoning": "General search for drug information",
                "looking_for": "Recent updates on drug development",
                "done": False
            }
    
    def analyze_search_results(self, query: str, results: List[Dict], 
                             drug_info: Dict) -> Dict[str, Any]:
        """
        Analyze search results to extract key findings.
        
        Returns:
            Dictionary with 'key_findings' and 'follow_up_needed'
        """
        if not results:
            return {
                "key_findings": "No results found for this query.",
                "follow_up_needed": False
            }
        
        # Prepare results for analysis
        results_text = f"Query: '{query}'\nFound {len(results)} results:\n\n"
        
        for i, result in enumerate(results[:3]):  # Analyze top 3 results
            results_text += f"Result {i+1} - {result['filing_type']} ({result['filing_date']}):\n"
            results_text += f"Section: {result.get('section', 'Unknown')}\n"
            results_text += f"Excerpt: {result.get('excerpt', '')}\n\n"
        
        prompt = f"""Analyze these SEC filing search results for {drug_info['name']}.

{results_text}

Extract the most important findings relevant to the catalyst analysis. Focus on:
1. Clinical trial data (endpoints, results, patient numbers)
2. Safety information (adverse events, discontinuations)
3. Regulatory updates (FDA feedback, filing plans)
4. Commercial plans (partnerships, market sizing)
5. Any red flags or positive signals

Provide a concise summary of key findings and indicate if follow-up searches are needed."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=400
            )
            
            findings = response.choices[0].message.content
            
            # Determine if follow-up is needed based on the findings
            follow_up_needed = any(term in findings.lower() for term in 
                                 ["further investigation", "unclear", "more information needed", 
                                  "follow up", "additional details"])
            
            return {
                "key_findings": findings,
                "follow_up_needed": follow_up_needed
            }
            
        except Exception as e:
            print(f"Error analyzing search results: {e}")
            return {
                "key_findings": f"Found {len(results)} results mentioning {query}",
                "follow_up_needed": False
            }