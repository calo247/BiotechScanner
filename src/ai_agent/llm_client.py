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
1. ANALYZE THE HISTORICAL CATALYST OUTCOMES - Read each outcome text and determine success/failure patterns yourself
2. Assess the company's track record by analyzing their specific catalyst outcomes
3. Analyze financial runway and burn rate implications for catalyst success
4. Present key insights from regulatory filings and announcements
5. Evaluate competitive landscape and differentiation
6. Provide an overall risk/reward assessment with specific reasoning

IMPORTANT: You are provided with full historical catalyst outcome texts. YOU must analyze these outcomes to determine success rates and patterns - don't rely on pre-calculated success rates.

Be direct, data-driven, and highlight both opportunities and risks. Use specific numbers and examples from the data provided.
Write as if you have direct knowledge of the information, not as if you searched for it."""

        # Format the data for the prompt
        user_prompt = self._format_analysis_prompt(analysis_data)
        
        # Print the final analysis prompt for logging
        print("\n" + "="*60)
        print("📤 LLM PROMPT FOR FINAL CATALYST ANALYSIS")
        print("="*60)
        print("System Prompt:")
        print(system_prompt)
        print("\nUser Prompt:")
        print(user_prompt)
        print("="*60 + "\n")
        
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

        # Print the SEC insights extraction prompt for logging
        print("\n" + "-"*60)
        print("📤 LLM PROMPT FOR SEC INSIGHTS EXTRACTION")
        print("-"*60)
        print(prompt)
        print("-"*60 + "\n")

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
- Note: {historical.get('note', '')}

Historical catalyst outcomes:
{self._format_historical_catalysts(historical.get('catalyst_details', []))}

COMPANY TRACK RECORD:
- Total relevant events: {track_record['total_events']}
- Note: {track_record.get('note', '')}

Company-specific catalyst history:
{self._format_company_catalysts(track_record.get('recent_catalysts', []))}

FINANCIAL HEALTH:
- Cash on hand: ${financial['cash_on_hand']:,.0f}
- Annual revenue: ${financial['revenue']:,.0f}
- Market cap: ${financial['market_cap']:,.0f}
- Cash runway: Search SEC filings for management guidance

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
    
    def _format_success_rate(self, rate) -> str:
        """Format success rate which might be a number or string."""
        if isinstance(rate, str):
            return rate
        else:
            return f"{rate}%"
    
    def _format_historical_rate(self, historical: Dict) -> str:
        """Format historical success rate with additional context."""
        rate = historical.get('success_rate', 'Unknown')
        if isinstance(rate, str):
            # Include the note if available
            note = historical.get('note', '')
            return f"{rate} ({note})" if note else rate
        else:
            events_with_outcomes = historical.get('events_with_outcomes', historical.get('positive_outcomes', 0))
            if events_with_outcomes > 0:
                return f"{rate:.1f}% ({events_with_outcomes} events with clear outcomes)"
            else:
                return f"{rate:.1f}%"
    
    def _format_company_rate(self, track_record: Dict) -> str:
        """Format company-specific success rate."""
        rate = track_record.get('success_rate', 'Unknown')
        if isinstance(rate, str):
            note = track_record.get('note', '')
            return f"{rate} ({note})" if note else rate
        else:
            events = track_record.get('events_with_outcomes', 0)
            if events > 0:
                return f"{rate:.1f}% (based on {events} similar trials)"
            else:
                return f"{rate:.1f}%"
    
    def _format_historical_catalysts(self, catalysts: List[Dict]) -> str:
        """Format historical catalyst details for analysis."""
        if not catalysts:
            return "No historical catalyst details available."
        
        if len(catalysts) > 10:
            # If many catalysts, show first 10 with note
            formatted = []
            for cat in catalysts[:10]:
                formatted.append(
                    f"- {cat.get('date', 'Unknown date')}: {cat.get('company', 'Unknown')} - "
                    f"{cat.get('drug', 'Unknown drug')} for {cat.get('indication', 'Unknown indication')} "
                    f"({cat.get('stage', 'Unknown stage')})\n"
                    f"  Outcome: {cat.get('outcome', 'No outcome reported')}" +
                    (f"\n  Price Change: {cat.get('price_change', 0):.1f}%" if cat.get('price_change') is not None else "")
                )
            formatted.append(f"\n... and {len(catalysts) - 10} more historical events")
            return "\n".join(formatted)
        else:
            # Show all if 10 or fewer
            formatted = []
            for cat in catalysts:
                formatted.append(
                    f"- {cat.get('date', 'Unknown date')}: {cat.get('company', 'Unknown')} - "
                    f"{cat.get('drug', 'Unknown drug')} for {cat.get('indication', 'Unknown indication')} "
                    f"({cat.get('stage', 'Unknown stage')})\n"
                    f"  Outcome: {cat.get('outcome', 'No outcome reported')}" +
                    (f"\n  Price Change: {cat.get('price_change', 0):.1f}%" if cat.get('price_change') is not None else "")
                )
            return "\n".join(formatted)
    
    def _format_company_catalysts(self, catalysts: List[Dict]) -> str:
        """Format company-specific catalyst history (all relevant events)."""
        if not catalysts:
            return "No company-specific catalyst history available."
        
        formatted = []
        for cat in catalysts:  # Show all, not just 3
            outcome = cat.get('outcome', 'No details')
            indication = f" for {cat.get('indication')}" if cat.get('indication') else ""
            formatted.append(
                f"- {cat.get('date', 'Unknown date')}: {cat.get('drug', 'Unknown drug')}{indication} "
                f"({cat.get('stage', 'Unknown stage')})\n"
                f"  Outcome: {outcome}"
            )
        
        return "\n".join(formatted)
    
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
- Historical Events Found: {context.get('historical_analysis', {}).get('total_events', 0)} similar catalysts
- Company Track Record: {context.get('company_track_record', {}).get('total_events', 0)} relevant company events

COMPLETE FINANCIAL DATA (from XBRL):
- Cash on Hand: ${context.get('financial_health', {}).get('cash_on_hand', 0):,.0f}
- Annual Revenue: ${context.get('financial_health', {}).get('revenue', 0):,.0f}
- Market Cap: ${context.get('financial_health', {}).get('market_cap', 0):,.0f}

IMPORTANT: You should search for cash runway guidance in SEC filings. Look for phrases like:
- "cash runway"
- "sufficient cash to fund operations"
- "believe our cash will be sufficient"
- "fund operations through"
- "cash to last until"

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

IMPORTANT: We have basic financial metrics from XBRL, but you SHOULD search for:
- Cash runway guidance (management's stated expectations)
- Funding plans or upcoming financing needs
- Statements about when cash will last until

DO NOT search for basic metrics like cash balance or revenue (we have those).
DO search for forward-looking statements about cash sufficiency.

Based on what you know and what has been searched, what should we search for next? Consider:
1. CASH RUNWAY: Have we found management's guidance on how long their cash will last?
2. What critical CLINICAL or REGULATORY information is still missing?
3. What findings about the DRUG DEVELOPMENT need follow-up investigation?
4. Are there safety, efficacy, or trial design details to explore?
5. Should we look for FDA correspondence or regulatory feedback?
6. Are there partnership, licensing, or commercialization strategies to investigate?
7. What does management say about the drug's progress and prospects?

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

        # Print the prompt for logging
        print("\n" + "="*60)
        print("📤 LLM PROMPT FOR SEARCH DECISION")
        print("="*60)
        print(prompt)
        print("="*60 + "\n")

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

        # Print the analysis prompt for logging
        print("\n" + "-"*60)
        print("📤 LLM PROMPT FOR ANALYZING SEARCH RESULTS")
        print("-"*60)
        print(prompt)
        print("-"*60 + "\n")

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
    
    def extract_announcement_time(self, text: str, url: str) -> Dict[str, Any]:
        """
        Use LLM to extract the actual announcement time from a press release or SEC filing.
        Distinguishes between announcement time and other times (conference calls, etc).
        
        Args:
            text: The document text (first 3000 chars)
            url: The URL of the document (for context)
            
        Returns:
            Dictionary with announcement timing info or empty dict if not found
        """
        prompt = f"""Extract ONLY the announcement/publication TIME (not date) from this document.
        
IMPORTANT: 
- Find the TIME when the PRESS RELEASE was ISSUED/ANNOUNCED/PUBLISHED
- Look for phrases like "announced today at", "issued at", "released at", "published"
- For SEC filings, look for filing timestamps

CRITICAL: DO NOT USE THESE TIMES:
- Conference call times (e.g., "conference call at 8:00 AM")
- Webcast times (e.g., "webcast scheduled for")
- Investor call times
- Management presentation times
- Dial-in times
- ANY time that is for a FUTURE EVENT

The announcement time is when the NEWS was RELEASED, not when a call/webcast will happen.

If the document says something like:
"Company announced results today... will host a conference call at 8:00 AM"
→ The 8:00 AM is NOT the announcement time (that's the call time)
→ Look for when "today" the announcement was made

RULES:
- announcement_time MUST be a TIME (e.g., "7:30 AM ET"), NOT a date
- If you only find a date with NO TIME, return {{"found": false}}
- If you only find conference call times, return {{"found": false}}
- DO NOT GUESS - if there's no announcement time mentioned, return {{"found": false}}

Document URL: {url}

Text:
{text[:3000]}

Return ONLY a JSON object in one of these formats:
{{"announcement_time": "7:30 AM ET", "announcement_timing": "PRE-MARKET"}}
{{"announcement_time": "4:15 PM ET", "announcement_timing": "AFTER-HOURS"}}
{{"announcement_time": "10:00 AM ET", "announcement_timing": "MARKET-HOURS"}}
{{"found": false}}

Market hours are 9:30 AM - 4:00 PM ET. Pre-market is before 9:30 AM, after-hours is after 4:00 PM."""

        try:
            response = self.client.chat.completions.create(
                model="openai/gpt-4o-mini",  # Use cheap, fast model for this simple task
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=100
            )
            
            # Extract JSON from response
            response_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON directly
            try:
                result = json.loads(response_text)
                
                # If found is false, return empty dict
                if result.get("found") is False:
                    return {}
                
                # If we have timing info, validate it's actually a time
                if "announcement_time" in result and "announcement_timing" in result:
                    time_str = result["announcement_time"]
                    # Check if it contains month names (indicating it's a date, not a time)
                    months = ['january', 'february', 'march', 'april', 'may', 'june', 
                             'july', 'august', 'september', 'october', 'november', 'december',
                             'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                    if any(month in time_str.lower() for month in months):
                        # If it contains a month, reject it
                        print(f"Warning: LLM returned date instead of time: {time_str}")
                        return {}
                    else:
                        return {
                            "announcement_time": time_str,
                            "announcement_timing": result["announcement_timing"]
                        }
                
            except json.JSONDecodeError:
                # Try to find JSON in the response
                json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        if result.get("found") is False:
                            return {}
                        if "announcement_time" in result and "announcement_timing" in result:
                            time_str = result["announcement_time"]
                            # Check if it contains month names (indicating it's a date, not a time)
                            months = ['january', 'february', 'march', 'april', 'may', 'june', 
                                     'july', 'august', 'september', 'october', 'november', 'december',
                                     'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
                            if any(month in time_str.lower() for month in months):
                                print(f"Warning: LLM returned date instead of time: {time_str}")
                                return {}
                            else:
                                return result
                    except:
                        pass
            
            return {}
            
        except Exception as e:
            print(f"Error extracting announcement time with LLM: {e}")
            return {}
    
