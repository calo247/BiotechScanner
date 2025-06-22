"""
Tools for the AI Research Agent to analyze biotech catalysts.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

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
                          days_back: int = 365) -> List[Dict[str, Any]]:
        """
        Search SEC filings for specific terms related to the catalyst.
        Uses RAG pipeline if available, falls back to parsed_content.
        
        Args:
            company_id: Company to search
            search_terms: Terms to search for (e.g., drug name, indication)
            filing_types: Specific filing types to search (default: all)
            days_back: How many days back to search
            
        Returns:
            List of relevant filing excerpts with context
        """
        # Try to use RAG search if available
        try:
            from ..rag.rag_search import RAGSearchEngine
            
            # Initialize RAG engine (cached in production)
            rag_engine = RAGSearchEngine(model_type='general-fast')
            
            # Combine search terms into query
            query = ' '.join(search_terms)
            
            # Search with RAG
            rag_results = rag_engine.search(
                query=query,
                company_id=company_id,
                filing_types=filing_types,
                k=10
            )
            
            # Format results
            results = []
            for result in rag_results:
                # Get expanded context
                context = rag_engine.get_context_window(result, window_size=500)
                
                results.append({
                    "filing_type": result['filing_type'],
                    "filing_date": result['filing_date'],
                    "accession_number": result.get('accession_number', ''),
                    "section": result.get('section', 'Unknown'),
                    "excerpt": context,
                    "relevance_score": result.get('score', 0),
                    "matched_query": query
                })
            
            rag_engine.close()
            return results
            
        except ImportError:
            # Fallback to old method if RAG not available
            pass
        except Exception as e:
            print(f"RAG search failed, falling back to basic search: {e}")
        
        # Original implementation as fallback
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = self.session.query(SECFiling).filter(
            and_(
                SECFiling.company_id == company_id,
                SECFiling.filing_date >= cutoff_date
            )
        )
        
        if filing_types:
            query = query.filter(SECFiling.filing_type.in_(filing_types))
        
        filings = query.order_by(SECFiling.filing_date.desc()).all()
        
        results = []
        for filing in filings:
            if filing.parsed_content:
                # Search in parsed content
                matches = []
                for section, content in filing.parsed_content.items():
                    if isinstance(content, str):
                        content_lower = content.lower()
                        for term in search_terms:
                            if term.lower() in content_lower:
                                # Extract context around match
                                idx = content_lower.find(term.lower())
                                start = max(0, idx - 200)
                                end = min(len(content), idx + 200)
                                matches.append({
                                    "section": section,
                                    "excerpt": "..." + content[start:end] + "...",
                                    "term": term
                                })
                
                if matches:
                    results.append({
                        "filing_type": filing.filing_type,
                        "filing_date": filing.filing_date.isoformat(),
                        "accession_number": filing.accession_number,
                        "matches": matches[:3]  # Limit to 3 matches per filing
                    })
        
        return results[:10]  # Return top 10 most relevant filings
    
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
    
    def close(self):
        """Close the database session."""
        self.session.close()