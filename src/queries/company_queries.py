"""Query builder for company-related database operations."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session, joinedload

from ..database.models import Company, Drug, StockData, SECFiling, FinancialMetric


class CompanyQuery:
    """Query builder for company data."""
    
    def __init__(self, session: Session):
        self.session = session
        self._query = session.query(Company)
    
    def by_ticker(self, ticker: str) -> 'CompanyQuery':
        """Filter by ticker symbol."""
        if ticker:
            self._query = self._query.filter(Company.ticker == ticker.upper())
        return self
    
    def by_tickers(self, tickers: List[str]) -> 'CompanyQuery':
        """Filter by multiple ticker symbols."""
        if tickers:
            upper_tickers = [t.upper() for t in tickers]
            self._query = self._query.filter(Company.ticker.in_(upper_tickers))
        return self
    
    def with_catalysts(self) -> 'CompanyQuery':
        """Filter companies that have drugs with catalysts."""
        subq = self.session.query(Drug.company_id).filter(
            Drug.has_catalyst == True
        ).distinct().subquery()
        
        self._query = self._query.filter(Company.id.in_(subq))
        return self
    
    def with_stock_data(self) -> 'CompanyQuery':
        """Filter companies that have stock data."""
        subq = self.session.query(StockData.company_id).distinct().subquery()
        self._query = self._query.filter(Company.id.in_(subq))
        return self
    
    def with_sec_filings(self) -> 'CompanyQuery':
        """Filter companies that have SEC filings."""
        subq = self.session.query(SECFiling.company_id).distinct().subquery()
        self._query = self._query.filter(Company.id.in_(subq))
        return self
    
    def search(self, search_term: str) -> 'CompanyQuery':
        """Search by ticker or company name."""
        if search_term:
            pattern = f"%{search_term}%"
            self._query = self._query.filter(
                Company.ticker.ilike(pattern) | Company.name.ilike(pattern)
            )
        return self
    
    def order_by_ticker(self) -> 'CompanyQuery':
        """Order by ticker symbol."""
        self._query = self._query.order_by(Company.ticker)
        return self
    
    def order_by_name(self) -> 'CompanyQuery':
        """Order by company name."""
        self._query = self._query.order_by(Company.name)
        return self
    
    def with_relationships(self, include: List[str]) -> 'CompanyQuery':
        """Eagerly load specified relationships."""
        for rel in include:
            if hasattr(Company, rel):
                self._query = self._query.options(joinedload(getattr(Company, rel)))
        return self
    
    def all(self) -> List[Company]:
        """Get all results."""
        return self._query.all()
    
    def first(self) -> Optional[Company]:
        """Get first result."""
        return self._query.first()
    
    def count(self) -> int:
        """Get count of results."""
        return self._query.count()
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the selected companies."""
        companies = self.all()
        company_ids = [c.id for c in companies]
        
        if not company_ids:
            return {
                'total_companies': 0,
                'companies_with_catalysts': 0,
                'companies_with_stock_data': 0,
                'companies_with_sec_filings': 0,
                'total_drugs': 0,
                'drugs_with_catalysts': 0
            }
        
        # Get counts using efficient queries
        companies_with_catalysts = self.session.query(
            func.count(func.distinct(Drug.company_id))
        ).filter(
            Drug.company_id.in_(company_ids),
            Drug.has_catalyst == True
        ).scalar() or 0
        
        companies_with_stock_data = self.session.query(
            func.count(func.distinct(StockData.company_id))
        ).filter(
            StockData.company_id.in_(company_ids)
        ).scalar() or 0
        
        companies_with_sec_filings = self.session.query(
            func.count(func.distinct(SECFiling.company_id))
        ).filter(
            SECFiling.company_id.in_(company_ids)
        ).scalar() or 0
        
        total_drugs = self.session.query(func.count(Drug.id)).filter(
            Drug.company_id.in_(company_ids)
        ).scalar() or 0
        
        drugs_with_catalysts = self.session.query(func.count(Drug.id)).filter(
            Drug.company_id.in_(company_ids),
            Drug.has_catalyst == True
        ).scalar() or 0
        
        return {
            'total_companies': len(companies),
            'companies_with_catalysts': companies_with_catalysts,
            'companies_with_stock_data': companies_with_stock_data,
            'companies_with_sec_filings': companies_with_sec_filings,
            'total_drugs': total_drugs,
            'drugs_with_catalysts': drugs_with_catalysts
        }
    
    def get_latest_cash_balance(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Get the most recent cash balance for a company."""
        latest_cash = self.session.query(FinancialMetric).filter(
            FinancialMetric.company_id == company_id,
            FinancialMetric.concept == 'CashAndCashEquivalentsAtCarryingValue'
        ).order_by(
            FinancialMetric.fiscal_year.desc(),
            FinancialMetric.fiscal_period.desc()
        ).first()
        
        if latest_cash:
            return {
                'value': latest_cash.value,
                'date': latest_cash.filed_date.isoformat() if latest_cash.filed_date else None,
                'period': f"{latest_cash.fiscal_year} {latest_cash.fiscal_period}"
            }
        
        return None