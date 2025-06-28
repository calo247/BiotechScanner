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
    
    def get_historical_success_rate(self, stage: str, indication: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate historical success rates for catalysts by stage and optionally by indication.
        
        Returns:
            - success_rate: percentage of positive outcomes
            - total_events: number of historical catalysts analyzed
            - positive_outcomes: number of successful catalysts
            - average_price_change: average stock price change around catalyst
        """
        query = self.session.query(HistoricalCatalyst).filter(
            HistoricalCatalyst.stage.ilike(f'%{stage}%')
        )
        
        if indication and isinstance(indication, str):
            query = query.filter(
                HistoricalCatalyst.drug_indication.ilike(f'%{indication}%')
            )
        
        catalysts = query.all()
        
        if not catalysts:
            return {
                "success_rate": 0,
                "total_events": 0,
                "positive_outcomes": 0,
                "average_price_change": 0
            }
        
        # Analyze outcomes based on catalyst_text
        positive_keywords = ['approved', 'positive', 'success', 'met primary', 'significant']
        negative_keywords = ['failed', 'negative', 'missed', 'discontinued', 'terminated']
        
        positive_count = 0
        price_changes = []
        
        for catalyst in catalysts:
            text_lower = catalyst.catalyst_text.lower() if catalyst.catalyst_text else ""
            
            if any(keyword in text_lower for keyword in positive_keywords):
                positive_count += 1
            
            # Get price change around catalyst date
            price_change = self._calculate_price_change(
                catalyst.company_id, 
                catalyst.catalyst_date
            )
            if price_change is not None:
                price_changes.append(price_change)
        
        return {
            "success_rate": (positive_count / len(catalysts)) * 100,
            "total_events": len(catalysts),
            "positive_outcomes": positive_count,
            "average_price_change": sum(price_changes) / len(price_changes) if price_changes else 0
        }
    
    def get_company_track_record(self, company_id: int) -> Dict[str, Any]:
        """
        Get a company's historical track record with FDA approvals and clinical trials.
        
        Returns:
            - total_drugs: number of drugs in pipeline
            - approved_drugs: number of approved drugs
            - failed_drugs: number of failed drugs
            - success_rate: overall success rate
            - recent_catalysts: list of recent catalyst outcomes
        """
        # Get all drugs for the company
        drugs = self.session.query(Drug).filter(Drug.company_id == company_id).all()
        
        # Get historical catalysts
        historical = self.session.query(HistoricalCatalyst).filter(
            HistoricalCatalyst.company_id == company_id
        ).order_by(HistoricalCatalyst.catalyst_date.desc()).limit(10).all()
        
        approved_count = sum(1 for drug in drugs if 'approved' in drug.stage.lower())
        
        # Analyze historical outcomes
        failed_count = 0
        for h in historical:
            if h.catalyst_text and any(word in h.catalyst_text.lower() 
                                     for word in ['failed', 'discontinued', 'terminated']):
                failed_count += 1
        
        recent_catalysts = [
            {
                "date": h.catalyst_date.isoformat() if h.catalyst_date else None,
                "drug": h.drug_name,
                "stage": h.stage,
                "outcome": h.catalyst_text[:200] if h.catalyst_text else None
            }
            for h in historical[:5]
        ]
        
        return {
            "total_drugs": len(drugs),
            "approved_drugs": approved_count,
            "failed_drugs": failed_count,
            "success_rate": (approved_count / len(drugs)) * 100 if drugs else 0,
            "recent_catalysts": recent_catalysts
        }
    
    def analyze_financial_health(self, company_id: int) -> Dict[str, Any]:
        """
        Analyze company's financial health and runway.
        
        Returns:
            - cash_on_hand: latest cash position
            - quarterly_burn_rate: average cash burn per quarter
            - runway_months: estimated months of runway
            - revenue: latest annual revenue
            - market_cap: current market capitalization
        """
        # Get latest financial metrics
        cash_metrics = self.session.query(FinancialMetric).filter(
            and_(
                FinancialMetric.company_id == company_id,
                FinancialMetric.concept.in_(['CashAndCashEquivalentsAtCarryingValue', 
                                            'Cash', 'CashCashEquivalentsAndShortTermInvestments'])
            )
        ).order_by(FinancialMetric.filed_date.desc()).limit(5).all()
        
        # Get operating cash flow or net loss for burn rate
        burn_metrics = self.session.query(FinancialMetric).filter(
            and_(
                FinancialMetric.company_id == company_id,
                FinancialMetric.concept.in_(['NetCashProvidedByUsedInOperatingActivities',
                                            'NetLoss', 'NetIncomeLoss'])
            )
        ).order_by(FinancialMetric.filed_date.desc()).limit(4).all()
        
        # Get revenue
        revenue_metrics = self.session.query(FinancialMetric).filter(
            and_(
                FinancialMetric.company_id == company_id,
                FinancialMetric.concept.in_(['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax'])
            )
        ).order_by(FinancialMetric.filed_date.desc()).first()
        
        # Get latest stock data for market cap
        latest_stock = self.session.query(StockData).filter(
            StockData.company_id == company_id
        ).order_by(StockData.date.desc()).first()
        
        cash_on_hand = cash_metrics[0].value if cash_metrics else 0
        
        # Calculate quarterly burn rate
        quarterly_burn = 0
        if burn_metrics:
            quarterly_burns = []
            for metric in burn_metrics:
                if metric.fiscal_period in ['Q1', 'Q2', 'Q3', 'Q4']:
                    quarterly_burns.append(abs(metric.value))
            if quarterly_burns:
                quarterly_burn = sum(quarterly_burns) / len(quarterly_burns)
        
        runway_months = (cash_on_hand / (quarterly_burn / 3)) if quarterly_burn > 0 else 999
        
        return {
            "cash_on_hand": cash_on_hand,
            "quarterly_burn_rate": quarterly_burn,
            "runway_months": min(runway_months, 999),
            "revenue": revenue_metrics.value if revenue_metrics else 0,
            "market_cap": latest_stock.market_cap if latest_stock else 0
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
                print(f"LLM indicates research complete: {search_decision.get('summary', 'Sufficient information gathered')}")
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
                print("📄 Sample results:")
                for i, res in enumerate(search_result['results'][:3]):
                    if search_type == "press_release":
                        print(f"   {i+1}. {res.get('filing_date', 'Unknown date')} - {res.get('excerpt', '').split('\\n')[0][:100]}...")
                    else:
                        print(f"   {i+1}. {res.get('filing_type')} ({res.get('filing_date')}) - {res.get('section', 'Unknown section')}")
            
            print(f"\n🔍 AI Analysis of findings:")
            print(f"{key_findings}")
        
        # Compile final results
        all_stats["unique_filings_count"] = len(all_stats["unique_filings"])
        # Remove the set from stats since it's not JSON serializable
        del all_stats["unique_filings"]
        all_stats["llm_driven"] = True
        all_stats["search_method"] = "LLM-driven dynamic FAISS search"
        
        print(f"\n{'='*60}")
        print(f"📊 Research Summary:")
        print(f"   Total searches performed: {all_stats['total_searches']}")
        print(f"   Total results found: {all_stats['total_results']}")
        print(f"   Unique SEC filings accessed: {all_stats['unique_filings_count']}")
        print(f"   Press releases found: {all_stats.get('press_releases_found', 0)}")
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
    
    def _calculate_price_change(self, company_id: int, catalyst_date: datetime, 
                               days_before: int = 5, days_after: int = 5) -> Optional[float]:
        """Calculate price change around a catalyst event."""
        if not catalyst_date:
            return None
            
        before_date = catalyst_date - timedelta(days=days_before)
        after_date = catalyst_date + timedelta(days=days_after)
        
        # Get price before
        price_before = self.session.query(func.avg(StockData.close)).filter(
            and_(
                StockData.company_id == company_id,
                StockData.date >= before_date,
                StockData.date < catalyst_date
            )
        ).scalar()
        
        # Get price after
        price_after = self.session.query(func.avg(StockData.close)).filter(
            and_(
                StockData.company_id == company_id,
                StockData.date > catalyst_date,
                StockData.date <= after_date
            )
        ).scalar()
        
        if price_before and price_after and price_before > 0:
            return ((price_after - price_before) / price_before) * 100
        
        return None
    
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