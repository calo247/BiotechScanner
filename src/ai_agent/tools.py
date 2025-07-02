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
    
    def get_historical_catalysts(self, stage: str, indication: Optional[str] = None, 
                               indication_specific: Optional[str] = None,
                               indication_generic: Optional[str] = None) -> Dict[str, Any]:
        """
        Get historical catalyst data across all stages for given indications.
        Searches both specific and generic indications, prioritizing specific matches.
        
        Args:
            stage: Development stage
            indication: Legacy parameter (for backward compatibility)
            indication_specific: Specific indication text
            indication_generic: CSV of generic indication categories
            
        Returns:
            - total_events: number of historical catalysts found
            - note: descriptive message about the data
            - catalyst_details: list of historical catalysts with full outcome text and price changes
            - same_stage_count: number of catalysts at the same stage
            - specific_matches: number of matches from specific indication
            - generic_matches: number of matches from generic indications
        """
        specific_catalysts = []
        generic_catalysts = []
        
        # Use new parameters if provided, otherwise fall back to legacy indication
        if not indication_specific and not indication_generic:
            indication_specific = indication
            indication_generic = indication
        
        # First, search for specific indication matches
        if indication_specific:
            # Split CSV and search for each specific indication
            specific_indications = [ind.strip() for ind in indication_specific.split(',') if ind.strip()]
            
            # Build OR conditions for all specific indications
            specific_conditions = []
            for ind in specific_indications:
                specific_conditions.append(
                    HistoricalCatalyst.drug_indication.ilike(f'%{ind}%')
                )
            
            if specific_conditions:
                specific_catalysts = self.session.query(HistoricalCatalyst).filter(
                    or_(*specific_conditions)
                ).all()
        
        # Then, search for generic indication matches
        if indication_generic:
            # Split CSV and search for each indication
            generic_indications = [ind.strip() for ind in indication_generic.split(',') if ind.strip()]
            
            # Build OR conditions for all generic indications
            generic_conditions = []
            for ind in generic_indications:
                generic_conditions.append(
                    HistoricalCatalyst.drug_indication.ilike(f'%{ind}%')
                )
            
            if generic_conditions:
                generic_catalysts = self.session.query(HistoricalCatalyst).filter(
                    or_(*generic_conditions)
                ).all()
        
        # Combine results, removing duplicates (specific matches take precedence)
        seen_ids = set()
        all_catalysts = []
        
        # Add specific matches first
        for cat in specific_catalysts:
            if cat.id not in seen_ids:
                seen_ids.add(cat.id)
                all_catalysts.append((cat, 'specific'))
        
        # Add generic matches that aren't already in specific
        for cat in generic_catalysts:
            if cat.id not in seen_ids:
                seen_ids.add(cat.id)
                all_catalysts.append((cat, 'generic'))
        
        # If no indication provided, fall back to stage-based search
        if not all_catalysts and not indication_specific and not indication_generic:
            stage_catalysts = self.session.query(HistoricalCatalyst).filter(
                HistoricalCatalyst.stage.ilike(f'%{stage}%')
            ).all()
            all_catalysts = [(cat, 'stage') for cat in stage_catalysts]
        
        # Count matches by type
        specific_match_count = sum(1 for cat, match_type in all_catalysts if match_type == 'specific')
        generic_match_count = sum(1 for cat, match_type in all_catalysts if match_type == 'generic')
        
        # Count how many are at the same stage
        same_stage_count = sum(1 for cat, _ in all_catalysts if stage.lower() in cat.stage.lower())
        
        if not all_catalysts:
            search_desc = []
            if indication_specific:
                search_desc.append(f"specific: '{indication_specific}'")
            if indication_generic:
                search_desc.append(f"generic: '{indication_generic}'")
            search_str = " and ".join(search_desc) if search_desc else f"{stage} stage"
            
            return {
                "total_events": 0,
                "same_stage_count": 0,
                "specific_matches": 0,
                "generic_matches": 0,
                "note": f"No historical catalysts found for {search_str}",
                "catalyst_details": []
            }
        
        # Sort catalysts: specific matches first, then same-stage, then by date (newest first)
        all_catalysts_sorted = sorted(all_catalysts, 
                                     key=lambda x: (
                                         x[1] != 'specific',  # 0 for specific, 1 for generic/stage
                                         not (stage.lower() in x[0].stage.lower()),  # 0 for same stage, 1 for different
                                         -(x[0].catalyst_date or datetime.min).timestamp() if x[0].catalyst_date else 0  # Negative for reverse date sort
                                     ))
        
        # Include ALL catalyst events for LLM to analyze
        catalyst_details = []
        for catalyst, match_type in all_catalysts_sorted:
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
                "is_same_stage": stage.lower() in catalyst.stage.lower(),
                "match_type": match_type  # 'specific', 'generic', or 'stage'
            })
        
        # Create informative note
        note_parts = []
        if specific_match_count > 0:
            note_parts.append(f"{specific_match_count} specific indication matches")
        if generic_match_count > 0:
            note_parts.append(f"{generic_match_count} generic indication matches")
        
        if note_parts:
            note = f"Found {len(all_catalysts)} historical events ({', '.join(note_parts)}) across all stages ({same_stage_count} at {stage} stage)"
        else:
            note = f"Found {len(all_catalysts)} historical events at {stage} stage (stage-based search only)"
        
        return {
            "total_events": len(all_catalysts),
            "same_stage_count": same_stage_count,
            "specific_matches": specific_match_count,
            "generic_matches": generic_match_count,
            "note": note,
            "catalyst_details": catalyst_details
        }
    
    def get_company_track_record(self, company_id: int, indication: Optional[str] = None, 
                                drug_name: Optional[str] = None,
                                indication_specific: Optional[str] = None,
                                indication_generic: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a company's historical track record, filtered by indication and/or drug.
        Searches both specific and generic indications, prioritizing specific matches.
        
        Args:
            company_id: Company ID
            indication: Legacy parameter (for backward compatibility)
            drug_name: If provided, only look at catalysts for this specific drug
            indication_specific: Specific indication text
            indication_generic: CSV of generic indication categories
        
        Returns:
            - total_events: number of relevant historical events
            - note: descriptive message about the data
            - recent_catalysts: list of catalyst outcomes with full text and price changes
            - specific_matches: number of matches from specific indication
            - generic_matches: number of matches from generic indications
        """
        # Build base query for historical catalysts
        base_query = self.session.query(HistoricalCatalyst).filter(
            HistoricalCatalyst.company_id == company_id
        )
        
        # Filter by drug name if provided
        if drug_name:
            base_query = base_query.filter(
                HistoricalCatalyst.drug_name.ilike(f'%{drug_name}%')
            )
        
        # Use new parameters if provided, otherwise fall back to legacy indication
        if not indication_specific and not indication_generic and indication:
            # Legacy behavior: extract key terms
            key_terms = []
            stop_words = {'lung', 'metastatic', 'recurrent', 'advanced', 'pediatric', 'adult'}
            indication_words = indication.lower().split()
            
            for word in indication_words:
                if word not in stop_words and len(word) > 3:
                    key_terms.append(word)
            
            if key_terms:
                most_specific_term = max(key_terms, key=len)
                indication_specific = most_specific_term
                indication_generic = indication
        
        specific_catalysts = []
        generic_catalysts = []
        
        # Search for specific indication matches
        if indication_specific:
            # Split CSV and search for each specific indication
            specific_indications = [ind.strip() for ind in indication_specific.split(',') if ind.strip()]
            
            # Build OR conditions for all specific indications
            specific_conditions = []
            for ind in specific_indications:
                specific_conditions.append(
                    HistoricalCatalyst.drug_indication.ilike(f'%{ind}%')
                )
            
            if specific_conditions:
                specific_catalysts = base_query.filter(
                    or_(*specific_conditions)
                ).all()
        
        # Search for generic indication matches
        if indication_generic:
            # Split CSV and search for each indication
            generic_indications = [ind.strip() for ind in indication_generic.split(',') if ind.strip()]
            
            # Build OR conditions for all generic indications
            generic_conditions = []
            for ind in generic_indications:
                generic_conditions.append(
                    HistoricalCatalyst.drug_indication.ilike(f'%{ind}%')
                )
            
            if generic_conditions:
                generic_catalysts = base_query.filter(
                    or_(*generic_conditions)
                ).all()
        
        # If no indication filters, get all company catalysts
        if not indication_specific and not indication_generic:
            all_company_catalysts = base_query.order_by(HistoricalCatalyst.catalyst_date.desc()).all()
            historical = [(cat, 'company') for cat in all_company_catalysts]
        else:
            # Combine results, removing duplicates (specific matches take precedence)
            seen_ids = set()
            historical = []
            
            # Add specific matches first
            for cat in specific_catalysts:
                if cat.id not in seen_ids:
                    seen_ids.add(cat.id)
                    historical.append((cat, 'specific'))
            
            # Add generic matches that aren't already in specific
            for cat in generic_catalysts:
                if cat.id not in seen_ids:
                    seen_ids.add(cat.id)
                    historical.append((cat, 'generic'))
            
            # Sort by date (newest first)
            historical.sort(key=lambda x: x[0].catalyst_date or datetime.min, reverse=True)
        
        # Count matches by type
        specific_match_count = sum(1 for cat, match_type in historical if match_type == 'specific')
        generic_match_count = sum(1 for cat, match_type in historical if match_type == 'generic')
        
        if not historical:
            context_desc = []
            if drug_name:
                context_desc.append(f"drug {drug_name}")
            if indication_specific:
                context_desc.append(f"specific indication '{indication_specific}'")
            if indication_generic:
                context_desc.append(f"generic indication '{indication_generic}'")
            context_str = " and ".join(context_desc) if context_desc else "this company"
            
            return {
                "total_events": 0,
                "recent_catalysts": [],
                "specific_matches": 0,
                "generic_matches": 0,
                "note": f"No historical catalysts found for {context_str}"
            }
        
        # Format all relevant catalysts for LLM analysis
        recent_catalysts = []
        for catalyst, match_type in historical:
            # Use the pre-calculated 3-day price change
            price_change = catalyst.price_change_3d
            
            recent_catalysts.append({
                "date": catalyst.catalyst_date.isoformat() if catalyst.catalyst_date else None,
                "drug": catalyst.drug_name,
                "indication": catalyst.drug_indication,
                "stage": catalyst.stage,
                "outcome": catalyst.catalyst_text,  # Full text for LLM analysis
                "source_url": catalyst.catalyst_source,
                "price_change_3d": price_change,
                "match_type": match_type  # 'specific', 'generic', or 'company'
            })
        
        # Create informative note
        note_parts = []
        if specific_match_count > 0:
            note_parts.append(f"{specific_match_count} specific indication matches")
        if generic_match_count > 0:
            note_parts.append(f"{generic_match_count} generic indication matches")
        
        if note_parts:
            note = f"Found {len(historical)} company events ({', '.join(note_parts)})"
        else:
            note = f"Found {len(historical)} company events (all catalysts for drug '{drug_name}')" if drug_name else f"Found {len(historical)} company events"
        
        return {
            "total_events": len(historical),
            "recent_catalysts": recent_catalysts,
            "specific_matches": specific_match_count,
            "generic_matches": generic_match_count,
            "note": note
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
        
        # Check for prior announcements if this looks like a presentation
        catalyst_desc = drug_info.get('catalyst_description', '').lower()
        if any(word in catalyst_desc for word in ['presentation', 'poster', 'oral', 'abstract', 'meeting', 'conference']):
            print("\n" + "="*60)
            print("🔍 DETECTED PRESENTATION EVENT - SEARCHING FOR PRIOR DATA ANNOUNCEMENTS")
            print("="*60)
            
            # Search for prior announcements of this drug's data
            prior_search = self._search_prior_announcements(
                company_id=company_id,
                drug_name=drug_info['name'],
                indication=drug_info.get('indication', ''),
                catalyst_date=drug_info.get('catalyst_date')
            )
            
            if prior_search['results']:
                print(f"⚠️ Found {len(prior_search['results'])} potential prior announcements")
                context['prior_announcements'] = prior_search
                all_results.extend(prior_search['results'])
                all_stats['prior_announcement_search'] = True
        
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
    
    def get_competitive_landscape(self, indication: str, stage: str, 
                                exclude_drug_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Find other companies with drugs in similar stage for same indication.
        
        Args:
            indication: Indication to search for
            stage: Development stage to match
            exclude_drug_id: Drug ID to exclude from results (typically the drug being analyzed)
        
        Returns:
            List of competing drugs and companies
        """
        if not indication or not isinstance(indication, str):
            return []
            
        query = self.session.query(Drug).join(Company).filter(
            and_(
                or_(
                    Drug.indication_generic.ilike(f'%{indication}%'),
                    Drug.indication_specific.ilike(f'%{indication}%')
                ),
                Drug.stage.ilike(f'%{stage}%'),
                Drug.has_catalyst == True
            )
        )
        
        # Exclude the current drug if specified
        if exclude_drug_id:
            query = query.filter(Drug.id != exclude_drug_id)
        
        drugs = query.all()
        
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
    
    
    def _search_prior_announcements(self, company_id: int, drug_name: str, 
                                   indication: str, catalyst_date: str) -> Dict[str, Any]:
        """
        Search for prior announcements of drug data before the catalyst date.
        This helps identify if upcoming presentations are showing new or recycled data.
        """
        results = []
        
        # Parse catalyst date
        catalyst_dt = None
        if catalyst_date:
            try:
                catalyst_dt = datetime.fromisoformat(catalyst_date.replace('Z', '+00:00'))
            except:
                catalyst_dt = None
        
        # Search press releases for prior data announcements
        company = self.session.query(Company).filter_by(id=company_id).first()
        if company:
            # Build search terms focusing on data announcements
            search_terms = [drug_name, "data", "results", "topline", "efficacy", "safety"]
            
            try:
                pr_results = self.search_company_press_releases(
                    company_name=company.name,
                    ticker=company.ticker,
                    search_terms=search_terms,
                    days_back=365  # Look back 1 year
                )
                
                # Filter for results before catalyst date and likely to be data announcements
                for pr in pr_results:
                    # Check if this looks like a data announcement
                    title_lower = pr.get('title', '').lower()
                    snippet_lower = pr.get('snippet', '').lower()
                    
                    data_keywords = ['data', 'results', 'topline', 'efficacy', 'safety', 'endpoint', 'response']
                    if any(keyword in title_lower or keyword in snippet_lower for keyword in data_keywords):
                        # Check date if available
                        pr_date_str = pr.get('date')
                        if pr_date_str and catalyst_dt:
                            try:
                                pr_date = datetime.strptime(pr_date_str, '%Y-%m-%d')
                                if pr_date < catalyst_dt:
                                    pr['days_before_catalyst'] = (catalyst_dt - pr_date).days
                                    results.append(pr)
                            except:
                                # If we can't parse date, include it anyway
                                results.append(pr)
                        else:
                            results.append(pr)
                
                # Sort by relevance and recency
                results.sort(key=lambda x: x.get('days_before_catalyst', 999))
                
            except Exception as e:
                print(f"Error searching for prior announcements: {e}")
        
        return {
            "results": results[:5],  # Top 5 most relevant
            "total_found": len(results)
        }
    
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
    
    def analyze_presentation_patterns(self, stage: str, indication: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze historical patterns to distinguish between presentation events and new data releases.
        This helps calibrate expectations for stock movement.
        
        Returns:
            Dict with patterns for presentation vs. new data events
        """
        # Keywords that typically indicate presentations of existing data
        presentation_keywords = ['presentation', 'poster', 'oral', 'abstract', 'conference', 
                               'meeting', 'symposium', 'congress', 'update on', 'additional data']
        
        # Keywords that typically indicate new data releases
        new_data_keywords = ['topline', 'top-line', 'primary endpoint', 'announces results', 
                           'reports results', 'achieves', 'meets', 'fails', 'data from']
        
        # Get historical catalysts for analysis
        all_catalysts = self.session.query(HistoricalCatalyst).filter(
            HistoricalCatalyst.price_change_3d.isnot(None)  # Only those with price data
        )
        
        # Filter by stage if provided
        if stage:
            all_catalysts = all_catalysts.filter(
                HistoricalCatalyst.stage.ilike(f'%{stage}%')
            )
        
        # Filter by indication if provided
        if indication:
            all_catalysts = all_catalysts.filter(
                HistoricalCatalyst.drug_indication.ilike(f'%{indication}%')
            )
        
        catalysts = all_catalysts.all()
        
        # Categorize events
        presentation_events = []
        new_data_events = []
        unclear_events = []
        
        for catalyst in catalysts:
            text_lower = (catalyst.catalyst_text or '').lower()
            
            # Check for presentation keywords
            is_presentation = any(kw in text_lower for kw in presentation_keywords)
            is_new_data = any(kw in text_lower for kw in new_data_keywords)
            
            event_data = {
                'company': catalyst.ticker,
                'drug': catalyst.drug_name,
                'stage': catalyst.stage,
                'date': catalyst.catalyst_date.isoformat() if catalyst.catalyst_date else None,
                'price_change': catalyst.price_change_3d,
                'description': catalyst.catalyst_text[:100] + '...' if len(catalyst.catalyst_text) > 100 else catalyst.catalyst_text
            }
            
            if is_presentation and not is_new_data:
                presentation_events.append(event_data)
            elif is_new_data and not is_presentation:
                new_data_events.append(event_data)
            else:
                unclear_events.append(event_data)
        
        # Calculate statistics
        def calculate_stats(events):
            if not events:
                return {
                    'count': 0,
                    'avg_price_change': 0,
                    'median_price_change': 0,
                    'positive_rate': 0,
                    'big_move_rate': 0  # >10% move
                }
            
            price_changes = [e['price_change'] for e in events]
            positive_count = sum(1 for pc in price_changes if pc > 0)
            big_move_count = sum(1 for pc in price_changes if abs(pc) > 10)
            
            return {
                'count': len(events),
                'avg_price_change': sum(price_changes) / len(price_changes),
                'median_price_change': sorted(price_changes)[len(price_changes)//2],
                'positive_rate': (positive_count / len(events)) * 100,
                'big_move_rate': (big_move_count / len(events)) * 100,
                'examples': events[:3]  # Top 3 examples
            }
        
        return {
            'presentation_events': calculate_stats(presentation_events),
            'new_data_events': calculate_stats(new_data_events),
            'unclear_events': calculate_stats(unclear_events),
            'analysis_summary': {
                'total_analyzed': len(catalysts),
                'stage_filter': stage or 'all stages',
                'indication_filter': indication or 'all indications',
                'pattern': self._summarize_pattern(
                    calculate_stats(presentation_events),
                    calculate_stats(new_data_events)
                )
            }
        }
    
    def _summarize_pattern(self, presentation_stats: Dict, new_data_stats: Dict) -> str:
        """Summarize the pattern difference between presentations and new data."""
        if presentation_stats['count'] < 5 or new_data_stats['count'] < 5:
            return "Insufficient data for pattern analysis"
        
        avg_diff = new_data_stats['avg_price_change'] - presentation_stats['avg_price_change']
        
        if avg_diff > 5:
            return f"New data events show {avg_diff:.1f}% higher average price movement than presentations"
        elif avg_diff < -5:
            return f"Presentations actually show {-avg_diff:.1f}% higher average price movement (unusual pattern)"
        else:
            return "Similar price movements for presentations and new data releases"
    
    def close(self):
        """Close the database session."""
        self.session.close()