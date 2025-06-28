"""
Enhanced search tools that perform multiple adaptive RAG searches.
"""
from typing import Dict, List, Any, Optional
from ..rag.rag_search import RAGSearchEngine


class EnhancedSECSearch:
    """Performs multiple targeted searches based on catalyst context."""
    
    def __init__(self):
        self.rag_engine = RAGSearchEngine(model_type='general-fast')
        self.search_history = []
    
    def multi_phase_search(self, company_id: int, drug_name: str, 
                          indication: str, stage: str) -> Dict[str, Any]:
        """
        Perform multiple searches with different strategies.
        """
        all_results = {
            "searches_performed": [],
            "total_results": 0,
            "unique_filings": set(),
            "results_by_category": {}
        }
        
        # Phase 1: Drug-specific search
        drug_results = self._search_and_track(
            f"{drug_name} {indication}",
            company_id,
            "drug_specific"
        )
        all_results["results_by_category"]["drug_mentions"] = drug_results
        
        # Phase 2: Clinical trial design search
        if "Phase" in stage or "phase" in stage:
            trial_results = self._search_and_track(
                f"primary endpoint secondary endpoint clinical trial design {indication}",
                company_id,
                "trial_design"
            )
            all_results["results_by_category"]["trial_design"] = trial_results
        
        # Phase 3: Safety profile search
        safety_results = self._search_and_track(
            f"adverse events safety profile tolerability {drug_name}",
            company_id,
            "safety"
        )
        all_results["results_by_category"]["safety"] = safety_results
        
        # Phase 4: Competitive landscape
        competitive_results = self._search_and_track(
            f"competitive landscape market opportunity {indication}",
            company_id,
            "competitive"
        )
        all_results["results_by_category"]["competitive"] = competitive_results
        
        # Phase 5: Financial impact
        financial_results = self._search_and_track(
            f"revenue potential peak sales market size {indication} {drug_name}",
            company_id,
            "financial"
        )
        all_results["results_by_category"]["financial"] = financial_results
        
        # Phase 6: Regulatory strategy
        if "PDUFA" in stage or "NDA" in stage or "BLA" in stage:
            regulatory_results = self._search_and_track(
                f"FDA submission regulatory pathway approval {drug_name}",
                company_id,
                "regulatory"
            )
            all_results["results_by_category"]["regulatory"] = regulatory_results
        
        # Compile statistics
        all_results["searches_performed"] = self.search_history
        all_results["total_results"] = sum(
            len(results) for results in all_results["results_by_category"].values()
        )
        
        # Count unique filings across all searches
        for category_results in all_results["results_by_category"].values():
            for result in category_results:
                if result.get('filing_id'):
                    all_results["unique_filings"].add(result['filing_id'])
        
        all_results["unique_filings_count"] = len(all_results["unique_filings"])
        all_results["unique_filings"] = list(all_results["unique_filings"])
        
        return all_results
    
    def _search_and_track(self, query: str, company_id: int, 
                         category: str) -> List[Dict]:
        """Perform a search and track it."""
        results = self.rag_engine.search(
            query=query,
            company_id=company_id,
            k=5  # Fewer results per search since we're doing multiple
        )
        
        # Track search
        self.search_history.append({
            "category": category,
            "query": query,
            "results_found": len(results),
            "best_score": min(r.get('score', 999) for r in results) if results else None
        })
        
        # Add category to each result
        for result in results:
            result['search_category'] = category
            # Get expanded context
            context = self.rag_engine.get_context_window(result, window_size=500)
            result['excerpt'] = context
        
        return results
    
    def adaptive_search(self, company_id: int, initial_results: List[Dict],
                       drug_name: str) -> Dict[str, Any]:
        """
        Perform follow-up searches based on initial findings.
        This is more sophisticated - it analyzes initial results and 
        generates targeted follow-up queries.
        """
        follow_up_results = {
            "adaptive_searches": [],
            "insights_found": []
        }
        
        # Analyze initial results for keywords to explore further
        keywords_to_explore = set()
        
        for result in initial_results[:3]:  # Look at top 3 results
            text = result.get('text', '').lower()
            
            # Look for trial-related terms
            if 'phase' in text and 'trial' in text:
                keywords_to_explore.add("enrollment criteria patient population")
            
            # Look for partnership mentions
            if 'partner' in text or 'collaboration' in text:
                keywords_to_explore.add("partnership collaboration agreement")
            
            # Look for manufacturing mentions
            if 'manufactur' in text or 'production' in text:
                keywords_to_explore.add("manufacturing scale commercial production")
            
            # Look for IP mentions
            if 'patent' in text or 'intellectual property' in text:
                keywords_to_explore.add("patent intellectual property exclusivity")
        
        # Perform adaptive searches
        for keywords in keywords_to_explore:
            query = f"{drug_name} {keywords}"
            results = self._search_and_track(query, company_id, f"adaptive_{keywords[:20]}")
            
            if results:
                follow_up_results["adaptive_searches"].append({
                    "trigger": keywords,
                    "query": query,
                    "results": results
                })
        
        return follow_up_results
    
    def close(self):
        """Clean up resources."""
        self.rag_engine.close()


# Example of how to integrate this into the existing tools
def enhanced_sec_search(company_id: int, drug_name: str, 
                       indication: str, stage: str) -> Dict[str, Any]:
    """
    Wrapper function for enhanced multi-phase SEC search.
    """
    searcher = EnhancedSECSearch()
    try:
        # Run multi-phase search
        results = searcher.multi_phase_search(company_id, drug_name, indication, stage)
        
        # Optionally run adaptive search based on initial findings
        if results["total_results"] > 0:
            # Get top results across all categories
            top_results = []
            for category_results in results["results_by_category"].values():
                top_results.extend(category_results[:2])  # Top 2 from each category
            
            # Run adaptive search
            adaptive = searcher.adaptive_search(company_id, top_results, drug_name)
            results["adaptive_searches"] = adaptive
        
        return results
    finally:
        searcher.close()