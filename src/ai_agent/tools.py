"""
Tools for the AI Research Agent to analyze biotech catalysts.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session
import requests
from bs4 import BeautifulSoup
import re

from ..database.database import get_db_session
from ..database.models import Drug, Company, StockData, HistoricalCatalyst, SECFiling, FinancialMetric


class CatalystAnalysisTools:
    """Tools for analyzing biotech catalysts."""
    
    def __init__(self):
        self.session = get_db_session()
    
    def get_historical_catalysts(self, stage: str, indication: Optional[str] = None) -> Dict[str, Any]:
        """
        Get historical catalyst data across all stages for a given indication.
        Provides raw catalyst outcomes for LLM to analyze patterns.
        
        Returns:
            - total_events: number of historical catalysts found
            - note: descriptive message about the data
            - catalyst_details: list of historical catalysts with full outcome text and price changes
            - same_stage_count: number of catalysts at the same stage
        """
        # Get catalysts for the indication across ALL stages
        if indication:
            # Get all catalysts for this indication
            query = self.session.query(HistoricalCatalyst).filter(
                HistoricalCatalyst.drug_indication.ilike(f'%{indication}%')
            )
        else:
            # If no indication, at least filter by similar stage
            query = self.session.query(HistoricalCatalyst).filter(
                HistoricalCatalyst.stage.ilike(f'%{stage}%')
            )
        
        catalysts = query.all()
        
        # Count how many are at the same stage
        same_stage_count = sum(1 for c in catalysts if stage.lower() in c.stage.lower())
        
        if not catalysts:
            return {
                "total_events": 0,
                "same_stage_count": 0,
                "note": f"No historical catalysts found" + (f" for {indication}" if indication else f" for {stage} stage"),
                "catalyst_details": []
            }
        
        # Sort catalysts so same-stage ones appear first, then by date (newest first)
        # This helps the LLM prioritize more relevant comparisons
        catalysts_sorted = sorted(catalysts, 
                                 key=lambda c: (
                                     not (stage.lower() in c.stage.lower()),  # False (0) for same stage, True (1) for different
                                     -(c.catalyst_date or datetime.min).timestamp() if c.catalyst_date else 0  # Negative for reverse date sort
                                 ))
        
        # Include ALL catalyst events for LLM to analyze
        catalyst_details = []
        for catalyst in catalysts_sorted:
            # Use the pre-calculated 3-day price change
            price_change = catalyst.price_change_3d
            
            catalyst_details.append({
                "date": catalyst.catalyst_date.isoformat() if catalyst.catalyst_date else None,
                "company": catalyst.ticker,
                "drug": catalyst.drug_name,
                "indication": catalyst.drug_indication,
                "stage": catalyst.stage,
                "outcome": catalyst.catalyst_text,
                "source_url": catalyst.catalyst_source,
                "price_change_3d": price_change,
                "is_same_stage": stage.lower() in catalyst.stage.lower()
            })
        
        # Create informative note
        if indication:
            note = f"Found {len(catalysts)} historical events for {indication} across all stages ({same_stage_count} at {stage} stage)"
        else:
            note = f"Found {len(catalysts)} historical events at {stage} stage (no indication filter applied)"
        
        return {
            "total_events": len(catalysts),
            "same_stage_count": same_stage_count,
            "note": note,
            "catalyst_details": catalyst_details
        }
    
    def get_company_track_record(self, company_id: int, indication: Optional[str] = None, 
                                drug_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a company's historical track record, optionally filtered by indication or drug.
        Provides raw catalyst outcomes for LLM to analyze patterns.
        
        Args:
            company_id: Company ID
            indication: If provided, only look at catalysts for this indication
            drug_name: If provided, only look at catalysts for this specific drug
        
        Returns:
            - total_events: number of relevant historical events
            - note: descriptive message about the data
            - recent_catalysts: list of catalyst outcomes with full text and price changes
        """
        # Build query for historical catalysts
        query = self.session.query(HistoricalCatalyst).filter(
            HistoricalCatalyst.company_id == company_id
        )
        
        # Filter by drug name if provided
        if drug_name:
            query = query.filter(
                HistoricalCatalyst.drug_name.ilike(f'%{drug_name}%')
            )
        
        # Filter by indication if provided (using the same logic as historical success rate)
        if indication and isinstance(indication, str):
            # Extract key disease terms
            key_terms = []
            stop_words = {'lung', 'metastatic', 'recurrent', 'advanced', 'pediatric', 'adult'}
            indication_words = indication.lower().split()
            
            for word in indication_words:
                if word not in stop_words and len(word) > 3:
                    key_terms.append(word)
            
            if key_terms:
                most_specific_term = max(key_terms, key=len)
                query = query.filter(
                    HistoricalCatalyst.drug_indication.ilike(f'%{most_specific_term}%')
                )
        
        # Get results ordered by date
        historical = query.order_by(HistoricalCatalyst.catalyst_date.desc()).all()
        
        if not historical:
            context_desc = []
            if drug_name:
                context_desc.append(f"drug {drug_name}")
            if indication:
                context_desc.append(f"indication {indication}")
            context_str = " and ".join(context_desc) if context_desc else "this context"
            
            return {
                "total_events": 0,
                "recent_catalysts": [],
                "note": f"No historical catalysts found for {context_str}"
            }
        
        # Format all relevant catalysts for LLM analysis
        recent_catalysts = []
        for h in historical:  # All catalysts
            # Use the pre-calculated 3-day price change
            price_change = h.price_change_3d
            
            recent_catalysts.append({
                "date": h.catalyst_date.isoformat() if h.catalyst_date else None,
                "drug": h.drug_name,
                "indication": h.drug_indication,
                "stage": h.stage,
                "outcome": h.catalyst_text,  # Full text for LLM analysis
                "source_url": h.catalyst_source,
                "price_change_3d": price_change
            })
        
        return {
            "total_events": len(historical),
            "recent_catalysts": recent_catalysts,
            "note": f"Found {len(historical)} company events for LLM analysis"
        }
    
    def analyze_financial_health(self, company_id: int) -> Dict[str, Any]:
        """
        Get basic financial metrics. Cash runway guidance will be searched in SEC filings.
        
        Returns:
            - cash_on_hand: latest cash position
            - market_cap: current market capitalization
            - cash_runway_guidance: placeholder for SEC search
        """
        # Get latest financial metrics - expand concept names and look for non-zero values
        cash_concepts = [
            'CashAndCashEquivalentsAtCarryingValue',
            'Cash',
            'CashCashEquivalentsAndShortTermInvestments',
            'CashAndCashEquivalents',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
            'CashAndCashEquivalentsPeriodIncreaseDecrease',
            'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations'
        ]
        
        cash_metrics = self.session.query(FinancialMetric).filter(
            and_(
                FinancialMetric.company_id == company_id,
                FinancialMetric.concept.in_(cash_concepts),
                FinancialMetric.value > 0  # Only get non-zero values
            )
        ).order_by(FinancialMetric.filed_date.desc()).limit(10).all()
        
        
        # Get latest stock data for market cap
        latest_stock = self.session.query(StockData).filter(
            StockData.company_id == company_id
        ).order_by(StockData.date.desc()).first()
        
        # Try to find the most reasonable cash value
        cash_on_hand = 0
        if cash_metrics:
            # Prefer CashAndCashEquivalentsAtCarryingValue if available
            for metric in cash_metrics:
                if metric.concept == 'CashAndCashEquivalentsAtCarryingValue':
                    cash_on_hand = metric.value
                    break
            # If not found, use the highest recent value
            if cash_on_hand == 0:
                cash_on_hand = max(m.value for m in cash_metrics)
        
        # If still no cash found, check if company has ANY financial metrics
        if cash_on_hand == 0:
            total_metrics = self.session.query(FinancialMetric).filter(
                FinancialMetric.company_id == company_id
            ).count()
            
            if total_metrics == 0:
                cash_runway_guidance = "No financial data synced - run sync_data.py --sec"
            elif total_metrics < 10:
                # Company might use simplified reporting (distressed or micro-cap)
                cash_runway_guidance = "Limited financial reporting - cash details in SEC filings"
            else:
                cash_runway_guidance = "Cash not found in XBRL - check SEC filings"
        else:
            cash_runway_guidance = "To be searched in SEC filings"
        
        return {
            "cash_on_hand": cash_on_hand,
            "market_cap": latest_stock.market_cap if latest_stock else 0,
            "cash_runway_guidance": cash_runway_guidance
        }
    
    def search_sec_filings(self, company_id: int, search_terms: List[str], 
                          filing_types: Optional[List[str]] = None,
                          days_back: int = 365) -> Dict[str, Any]:
        """Single SEC filing search - used by static analysis."""
        return self._perform_sec_search(' '.join(search_terms), company_id, filing_types)
    
    def dynamic_sec_research(self, company_id: int, drug_info: Dict,
                           initial_context: Dict, llm_client) -> Dict[str, Any]:
        """
        Perform LLM-driven dynamic SEC filing and press release research.
        The LLM decides what to search for based on findings.
        
        Returns:
            Dictionary containing all search iterations and findings
        """
        max_searches = 6  # Limit to prevent runaway costs
        search_history = []
        all_results = []
        all_stats = {
            "total_searches": 0,
            "total_results": 0,
            "unique_filings": set(),
            "search_iterations": [],
            "press_releases_found": 0
        }
        
        # Context for LLM
        context = {
            "drug_info": drug_info,
            "historical_analysis": initial_context.get("historical_analysis", {}),
            "company_track_record": initial_context.get("company_track_record", {}),
            "financial_health": initial_context.get("financial_health", {})
        }
        
        print(f"\n{'='*60}")
        print(f"Starting LLM-driven research for {drug_info['name']}")
        print(f"The AI can search both SEC filings (via FAISS) and press releases (via Google)")
        print(f"{'='*60}")
        
        for iteration in range(max_searches):
            print(f"\n--- Search Iteration {iteration + 1} ---")
            
            # Get next search query from LLM
            search_decision = llm_client.generate_search_query(context, search_history)
            
            # Check if LLM thinks we're done
            if search_decision.get("done", False):
                print("\n" + "="*60)
                print("✅ LLM INDICATES RESEARCH COMPLETE")
                print("="*60)
                print(f"Summary: {search_decision.get('summary', 'Sufficient information gathered')}")
                print(f"Total iterations completed: {iteration + 1}")
                print("="*60)
                break
            
            # Perform the search
            query = search_decision.get("query", f"{drug_info['name']} update")
            search_type = search_decision.get("search_type", "sec")
            
            print(f"\n🔍 Search Type: {'PRESS RELEASES (Google)' if search_type == 'press_release' else 'SEC FILINGS (FAISS)'}")
            print(f"📝 Query: '{query}'")
            print(f"💭 Reasoning: {search_decision.get('reasoning', 'N/A')}")
            print(f"🎯 Looking for: {search_decision.get('looking_for', 'N/A')}")
            
            if search_type == "press_release":
                # Search press releases
                company = self.session.query(Company).filter_by(id=company_id).first()
                pr_results = self.search_company_press_releases(
                    company_name=company.name,
                    ticker=company.ticker,
                    search_terms=query.split(),
                    days_back=90
                )
                
                # Format press release results similar to SEC results
                search_result = {
                    "results": [
                        {
                            "filing_type": "Press Release",
                            "filing_date": pr.get('date', 'Unknown'),
                            "accession_number": pr.get('url', ''),
                            "section": pr.get('source', 'Unknown'),
                            "excerpt": f"{pr.get('title', '')}\n\n{pr.get('snippet', '')}",
                            "relevance_score": 1.0 if pr.get('relevance') == 'high' else 0.5,
                            "matched_query": query,
                            "url": pr.get('url', '')
                        }
                        for pr in pr_results
                    ],
                    "stats": {
                        "results_found": len(pr_results),
                        "source": "press_releases"
                    }
                }
                all_stats["press_releases_found"] += len(pr_results)
            else:
                # Default to SEC search
                search_result = self._perform_sec_search(query, company_id, ['10-K', '10-Q', '8-K'])
            
            # Analyze results with LLM
            if search_result["results"]:
                analysis = llm_client.analyze_search_results(
                    query, 
                    search_result["results"], 
                    drug_info
                )
                key_findings = analysis.get("key_findings", "No significant findings")
            else:
                key_findings = "No results found for this query"
            
            # Record search iteration
            search_record = {
                "iteration": iteration + 1,
                "query": query,
                "reasoning": search_decision.get("reasoning", ""),
                "looking_for": search_decision.get("looking_for", ""),
                "results_found": len(search_result["results"]),
                "key_findings": key_findings,
                "stats": search_result["stats"],
                "search_type": search_type  # Add this to clearly identify the type
            }
            
            search_history.append(search_record)
            all_results.extend(search_result["results"])
            
            # Update stats
            all_stats["total_searches"] += 1
            all_stats["total_results"] += len(search_result["results"])
            all_stats["search_iterations"].append(search_record)
            
            # Track unique filings
            for result in search_result["results"]:
                if result.get("filing_id"):
                    all_stats["unique_filings"].add(result["filing_id"])
            
            print(f"\n✅ Found: {len(search_result['results'])} results")
            if search_result['results']:
                print("\n📄 FULL SEARCH RESULTS:")
                print("-" * 60)
                for i, res in enumerate(search_result['results']):
                    if search_type == "press_release":
                        print(f"\nResult {i+1}: PRESS RELEASE")
                        print(f"   Date: {res.get('filing_date', 'Unknown date')}")
                        print(f"   Source: {res.get('section', 'Unknown')}")
                        print(f"   URL: {res.get('url', 'No URL')}")
                        print(f"   Full Title/Excerpt:")
                        print(f"   {res.get('excerpt', 'No content')}")
                        print("-" * 40)
                    else:
                        print(f"\nResult {i+1}: SEC FILING")
                        print(f"   Type: {res.get('filing_type')}")
                        print(f"   Date: {res.get('filing_date')}")
                        print(f"   Accession: {res.get('accession_number', 'Unknown')}")
                        print(f"   Section: {res.get('section', 'Unknown section')}")
                        print(f"   Relevance Score: {res.get('relevance_score', 0):.4f}")
                        print(f"   Full Excerpt ({len(res.get('excerpt', ''))} chars):")
                        print(f"   {res.get('excerpt', 'No content')}")
                        print("-" * 40)
                print("-" * 60)
            
            print(f"\n🔍 AI ANALYSIS OF FINDINGS:")
            print("="*40)
            print(key_findings)
            print("="*40)
        
        # Compile final results
        all_stats["unique_filings_count"] = len(all_stats["unique_filings"])
        # Remove the set from stats since it's not JSON serializable
        del all_stats["unique_filings"]
        all_stats["llm_driven"] = True
        all_stats["search_method"] = "LLM-driven dynamic FAISS search"
        
        print(f"\n{'='*60}")
        print(f"📊 COMPREHENSIVE RESEARCH SUMMARY:")
        print(f"{'='*60}")
        print(f"Total searches performed: {all_stats['total_searches']}")
        print(f"Total results found: {all_stats['total_results']}")
        print(f"Unique SEC filings accessed: {all_stats['unique_filings_count']}")
        print(f"Press releases found: {all_stats.get('press_releases_found', 0)}")
        
        print(f"\n🔍 SEARCH BREAKDOWN BY TYPE:")
        sec_searches = sum(1 for s in search_history if s.get('search_type', 'sec') == 'sec')
        pr_searches = sum(1 for s in search_history if s.get('search_type') == 'press_release')
        print(f"  SEC Filing searches: {sec_searches}")
        print(f"  Press Release searches: {pr_searches}")
        
        print(f"\n📑 ALL SEARCH QUERIES PERFORMED:")
        for i, search in enumerate(search_history):
            search_type = "Press Release" if search.get('search_type') == 'press_release' else "SEC"
            print(f"  {i+1}. [{search_type}] '{search['query']}' - {search['results_found']} results")
        
        print(f"\n🎯 KEY FINDINGS SUMMARY:")
        for i, search in enumerate(search_history):
            if search.get('key_findings') and search['key_findings'] != "No results found for this query":
                print(f"\nFrom Search {i+1}:")
                print(f"{search['key_findings']}")
        
        print(f"{'='*60}")
        
        return {
            "results": all_results,
            "stats": all_stats,
            "search_history": search_history
        }
    
    def _perform_sec_search(self, query: str, company_id: int, 
                           filing_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform a single SEC filing search.
        """
        # Always use RAG search - fail fast if not available
        from ..rag.rag_search import RAGSearchEngine
        
        # Initialize RAG engine (cached in production)
        rag_engine = RAGSearchEngine(model_type='general-fast')
        
        # Query is already provided as a string parameter
        
        # Get index stats before search
        index_stats = rag_engine.get_stats()
        total_chunks = index_stats.get('total_chunks', 0)
        
        # Search with RAG
        rag_results = rag_engine.search(
            query=query,
            company_id=company_id,
            filing_types=filing_types,
            k=10
        )
        
        # Collect statistics
        unique_filings = set()
        unique_filing_types = set()
        score_range = [float('inf'), float('-inf')] if rag_results else [0, 0]
        
        # Format results
        results = []
        for result in rag_results:
            # Track unique filings
            filing_id = result.get('filing_id')
            filing_type = result.get('filing_type')
            if filing_id:
                unique_filings.add(filing_id)
            if filing_type:
                unique_filing_types.add(filing_type)
            
            # Track score range
            score = result.get('score', 0)
            score_range[0] = min(score_range[0], score)
            score_range[1] = max(score_range[1], score)
            
            # Get expanded context
            context = rag_engine.get_context_window(result, window_size=500)
            
            results.append({
                "filing_id": filing_id,
                "filing_type": filing_type,
                "filing_date": result['filing_date'],
                "accession_number": result.get('accession_number', ''),
                "section": result.get('section', 'Unknown'),
                "excerpt": context,
                "relevance_score": score,
                "matched_query": query
            })
        
        # Compile statistics
        stats = {
            "rag_search_used": True,
            "total_index_chunks": total_chunks,
            "query": query,
            "company_id": company_id,
            "results_found": len(results),
            "unique_filings_matched": len(unique_filings),
            "filing_types_searched": list(filing_types) if filing_types else ["all"],
            "filing_types_found": list(unique_filing_types),
            "relevance_score_range": {
                "best": score_range[0] if results else None,
                "worst": score_range[1] if results else None
            },
            "search_method": "FAISS with Product Quantization"
        }
        
        rag_engine.close()
        
        return {
            "results": results,
            "stats": stats
        }
    
    def get_competitive_landscape(self, indication: str, stage: str) -> List[Dict[str, Any]]:
        """
        Find other companies with drugs in similar stage for same indication.
        
        Returns:
            List of competing drugs and companies
        """
        if not indication or not isinstance(indication, str):
            return []
            
        drugs = self.session.query(Drug).join(Company).filter(
            and_(
                Drug.indications_text.ilike(f'%{indication}%'),
                Drug.stage.ilike(f'%{stage}%'),
                Drug.has_catalyst == True
            )
        ).all()
        
        competitors = []
        for drug in drugs:
            company = drug.company
            latest_stock = self.session.query(StockData).filter(
                StockData.company_id == company.id
            ).order_by(StockData.date.desc()).first()
            
            competitors.append({
                "company": company.name,
                "ticker": company.ticker,
                "drug_name": drug.drug_name,
                "stage": drug.stage,
                "catalyst_date": drug.catalyst_date.isoformat() if drug.catalyst_date else None,
                "market_cap": latest_stock.market_cap if latest_stock else 0
            })
        
        # Sort by market cap
        competitors.sort(key=lambda x: x['market_cap'], reverse=True)
        return competitors[:10]
    
    # Note: _calculate_price_change method removed - we now use pre-calculated 3-day price changes from the database
    
    
    def search_company_press_releases(self, company_name: str, ticker: str, 
                                     search_terms: List[str], days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Search for press releases using free Google search library.
        Fails fast if search doesn't work - no fallbacks.
        
        Returns:
            List of press releases with title, date, url, and excerpt
        """
        # Build Google search query
        query_parts = [
            f'"{ticker}"',  # Exact match ticker
            f'"{company_name}"',  # Exact match company
            '("press release" OR "announces" OR "reports" OR "data")',
            ' '.join(f'"{term}"' for term in search_terms)
        ]
        
        # No site restrictions - allow searching company websites and all sources
        google_query = ' '.join(query_parts)
        
        # Use googlesearch-python library - fail fast if not available
        try:
            from googlesearch import search
        except ImportError:
            raise ImportError("googlesearch-python not installed. Run: pip install googlesearch-python")
        
        print(f"\n🌐 Using Google to search for press releases...")
        print(f"   Company: {company_name} ({ticker})")
        print(f"   Terms: {' '.join(search_terms)}")
        
        results = []
        
        # Search and get up to 15 results
        search_results = list(search(
            google_query, 
            num_results=15,
            lang='en',
            safe='off',
            advanced=True  # Returns SearchResult objects with descriptions
        ))
        
        for result in search_results:
            # Extract details from search result
            title = result.title if hasattr(result, 'title') else ''
            snippet = result.description if hasattr(result, 'description') else ''
            url = result.url if hasattr(result, 'url') else str(result)
            
            # Extract date from title or snippet
            date_text = self._extract_date_from_text(f"{title} {snippet}")
            
            # Check relevance
            relevance = 'high' if any(term.lower() in title.lower() for term in search_terms) else 'medium'
            
            results.append({
                'source': 'googlesearch-python',
                'title': title or url.split('/')[-1],  # Use URL as fallback title
                'url': url,
                'snippet': snippet,
                'date': date_text,
                'relevance': relevance
            })
        
        return results
    
    
    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Extract date from text using common patterns."""
        import re
        from dateutil import parser
        
        # Common date patterns
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or MM-DD-YYYY
            r'(\w+ \d{1,2}, \d{4})',              # Month DD, YYYY
            r'(\d{1,2} \w+ \d{4})',               # DD Month YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date = parser.parse(match.group(1))
                    return date.strftime('%Y-%m-%d')
                except:
                    continue
                    
        return None
    
    def close(self):
        """Close the database session."""
        self.session.close()