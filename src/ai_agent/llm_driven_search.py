"""
LLM-driven dynamic search that lets the AI decide what to search for.
"""
from typing import Dict, List, Any
import json
from ..rag.rag_search import RAGSearchEngine


class LLMDrivenSearch:
    """Let the LLM drive the search process dynamically."""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.rag_engine = RAGSearchEngine(model_type='general-fast')
        self.search_log = []
        self.max_searches = 10  # Prevent runaway searches
    
    def research_catalyst(self, company_id: int, drug_info: Dict, 
                         initial_context: Dict) -> Dict[str, Any]:
        """
        Let the LLM drive the research process.
        """
        # Initial prompt to LLM
        research_prompt = f"""
        You are researching a biotech catalyst with access to SEC filings via search.
        
        Drug Information:
        - Name: {drug_info['name']}
        - Company: {drug_info['company']} ({drug_info['ticker']})
        - Stage: {drug_info['stage']}
        - Indication: {drug_info['indication']}
        - Catalyst Date: {drug_info['catalyst_date']}
        
        Initial Context:
        - Historical Success Rate: {initial_context.get('historical_analysis', {}).get('success_rate', 'Unknown')}%
        - Company has {initial_context.get('company_track_record', {}).get('total_drugs', 0)} drugs in pipeline
        
        You can search SEC filings with specific queries. Based on what you know so far,
        what would you like to search for first? Respond with a JSON object:
        {{
            "search_query": "your search terms here",
            "reasoning": "why this search is important",
            "looking_for": "what you hope to find"
        }}
        """
        
        research_data = {
            "searches": [],
            "findings": [],
            "total_searches": 0
        }
        
        # Iterative search process
        for i in range(self.max_searches):
            # Get next search from LLM
            search_decision = self._get_llm_search_decision(
                research_prompt, 
                research_data["searches"]
            )
            
            if not search_decision or search_decision.get("done"):
                break
            
            # Perform the search
            search_results = self.rag_engine.search(
                query=search_decision["search_query"],
                company_id=company_id,
                k=5
            )
            
            # Record the search
            search_record = {
                "iteration": i + 1,
                "query": search_decision["search_query"],
                "reasoning": search_decision.get("reasoning", ""),
                "looking_for": search_decision.get("looking_for", ""),
                "results_found": len(search_results),
                "results": search_results
            }
            research_data["searches"].append(search_record)
            research_data["total_searches"] += 1
            
            # If no results, let LLM know and continue
            if not search_results:
                research_prompt += f"\n\nSearch {i+1} for '{search_decision['search_query']}' found no results."
                continue
            
            # Analyze results with LLM
            findings = self._analyze_search_results(
                search_decision["search_query"],
                search_results,
                drug_info
            )
            
            if findings:
                research_data["findings"].extend(findings)
                research_prompt += f"\n\nSearch {i+1} findings: {findings[0]}"
        
        return research_data
    
    def _get_llm_search_decision(self, context: str, 
                                previous_searches: List[Dict]) -> Dict:
        """Get the next search query from the LLM."""
        prompt = context
        
        if previous_searches:
            prompt += "\n\nPrevious searches performed:"
            for search in previous_searches[-3:]:  # Show last 3 searches
                prompt += f"\n- Query: '{search['query']}' (found {search['results_found']} results)"
        
        prompt += "\n\nWhat should we search for next? Or are we done (set 'done': true)?"
        
        # Call LLM (simplified - in practice would use your LLM client)
        # response = self.llm_client.generate(prompt)
        # return json.loads(response)
        
        # For now, return a mock response
        if len(previous_searches) >= 3:
            return {"done": True}
        
        # Example progressive search strategy
        if len(previous_searches) == 0:
            return {
                "search_query": f"{context.split('Name: ')[1].split()[0]} clinical trial results",
                "reasoning": "Start with direct drug name search",
                "looking_for": "Trial design, endpoints, and results"
            }
        elif len(previous_searches) == 1:
            return {
                "search_query": "adverse events safety discontinuation",
                "reasoning": "Understand safety profile",
                "looking_for": "Safety issues that might affect approval"
            }
        else:
            return {
                "search_query": "market opportunity revenue forecast",
                "reasoning": "Assess commercial potential",
                "looking_for": "Market size and revenue projections"
            }
    
    def _analyze_search_results(self, query: str, results: List[Dict], 
                               drug_info: Dict) -> List[str]:
        """Have LLM analyze what was found."""
        # In practice, would send results to LLM for analysis
        # For now, return mock findings
        findings = []
        for result in results[:2]:
            findings.append(
                f"Found {result.get('filing_type')} filing discussing "
                f"{query} with relevance score {result.get('score', 0):.3f}"
            )
        return findings
    
    def close(self):
        """Clean up resources."""
        self.rag_engine.close()