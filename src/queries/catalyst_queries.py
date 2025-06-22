"""Query builder for catalyst-related database operations."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, Query, joinedload

from ..database.models import Drug, Company, StockData, HistoricalCatalyst
from .filters import StageFilter, DateRangeFilter, MarketCapFilter


class CatalystQuery:
    """Chainable query builder for catalyst data."""
    
    def __init__(self, session: Session):
        self.session = session
        self._query = session.query(Drug).join(Company)
        self._include_stock_data = False
        self._stock_data_subquery = None
        
    def upcoming(self, days: Optional[int] = None) -> 'CatalystQuery':
        """Filter for upcoming catalysts."""
        self._query = self._query.filter(
            Drug.has_catalyst == True,
            Drug.catalyst_date.isnot(None)
        )
        
        if days:
            start, end = DateRangeFilter.upcoming_days(days)
            self._query = self._query.filter(
                Drug.catalyst_date >= start,
                Drug.catalyst_date <= end
            )
        else:
            # Default: all future catalysts
            today = datetime.now(timezone.utc).date()
            self._query = self._query.filter(func.date(Drug.catalyst_date) >= today)
        
        return self
    
    def past(self, days: int) -> 'CatalystQuery':
        """Filter for past catalysts within X days."""
        start, end = DateRangeFilter.past_days(days)
        self._query = self._query.filter(
            Drug.has_catalyst == True,
            Drug.catalyst_date >= start,
            Drug.catalyst_date <= end
        )
        return self
    
    def date_range(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> 'CatalystQuery':
        """Filter by custom date range."""
        if start:
            self._query = self._query.filter(Drug.catalyst_date >= start)
        if end:
            self._query = self._query.filter(Drug.catalyst_date <= end)
        return self
    
    def by_stage(self, stage: str) -> 'CatalystQuery':
        """Filter by development stage."""
        if stage:
            pattern = StageFilter.get_sql_pattern(stage)
            self._query = self._query.filter(Drug.stage.like(pattern))
        return self
    
    def by_stages(self, stages: List[str]) -> 'CatalystQuery':
        """Filter by multiple development stages."""
        if stages:
            conditions = [Drug.stage.like(StageFilter.get_sql_pattern(stage)) for stage in stages]
            self._query = self._query.filter(or_(*conditions))
        return self
    
    def by_ticker(self, ticker: str) -> 'CatalystQuery':
        """Filter by company ticker."""
        if ticker:
            self._query = self._query.filter(Company.ticker == ticker.upper())
        return self
    
    def by_tickers(self, tickers: List[str]) -> 'CatalystQuery':
        """Filter by multiple company tickers."""
        if tickers:
            upper_tickers = [t.upper() for t in tickers]
            self._query = self._query.filter(Company.ticker.in_(upper_tickers))
        return self
    
    def by_market_cap_range(self, min_cap: Optional[float] = None, max_cap: Optional[float] = None) -> 'CatalystQuery':
        """Filter by market cap range."""
        if min_cap is not None or max_cap is not None:
            self._ensure_stock_data_join()
            
            if min_cap is not None:
                self._query = self._query.filter(StockData.market_cap >= min_cap)
            if max_cap is not None:
                self._query = self._query.filter(StockData.market_cap <= max_cap)
        
        return self
    
    def by_market_cap_category(self, category: str) -> 'CatalystQuery':
        """Filter by market cap category (micro, small, mid, large, mega)."""
        min_cap, max_cap = MarketCapFilter.get_range(category)
        return self.by_market_cap_range(min_cap, max_cap)
    
    def by_stock_price_range(self, min_price: Optional[float] = None, max_price: Optional[float] = None) -> 'CatalystQuery':
        """Filter by stock price range."""
        if min_price is not None or max_price is not None:
            self._ensure_stock_data_join()
            
            if min_price is not None:
                self._query = self._query.filter(StockData.close >= min_price)
            if max_price is not None:
                self._query = self._query.filter(StockData.close <= max_price)
        
        return self
    
    def search(self, search_term: str) -> 'CatalystQuery':
        """Search across multiple fields."""
        if search_term:
            pattern = f"%{search_term}%"
            self._query = self._query.filter(
                or_(
                    Company.ticker.ilike(pattern),
                    Company.name.ilike(pattern),
                    Drug.drug_name.ilike(pattern),
                    Drug.stage.ilike(pattern),
                    Drug.mechanism_of_action.ilike(pattern),
                    Drug.note.ilike(pattern),
                    Drug.indications_text.ilike(pattern)
                )
            )
        return self
    
    def with_stock_data(self) -> 'CatalystQuery':
        """Include latest stock data in results."""
        self._include_stock_data = True
        return self
    
    def order_by(self, field: str, direction: str = 'asc') -> 'CatalystQuery':
        """Order results by specified field."""
        # Map field names to model attributes
        field_map = {
            'date': Drug.catalyst_date,
            'catalyst_date': Drug.catalyst_date,
            'ticker': Company.ticker,
            'company': Company.name,
            'company_name': Company.name,
            'drug': Drug.drug_name,
            'drug_name': Drug.drug_name,
            'stage': Drug.stage,
        }
        
        # Handle fields that require stock data join
        stock_fields = {'market_cap', 'marketcap', 'price', 'stock_price'}
        if field.lower() in stock_fields:
            self._ensure_stock_data_join()
            if field.lower() in ('market_cap', 'marketcap'):
                sort_column = StockData.market_cap
            else:
                sort_column = StockData.close
        else:
            sort_column = field_map.get(field, Drug.catalyst_date)
        
        # Apply ordering
        if direction.lower() == 'desc':
            self._query = self._query.order_by(desc(sort_column))
        else:
            self._query = self._query.order_by(asc(sort_column))
        
        return self
    
    def _ensure_stock_data_join(self):
        """Ensure stock data is joined for queries that need it."""
        if not self._stock_data_subquery:
            # Create subquery for latest stock data per company
            self._stock_data_subquery = self.session.query(
                StockData.company_id,
                func.max(StockData.date).label('max_date')
            ).group_by(StockData.company_id).subquery()
            
            # Join with the latest stock data
            self._query = self._query.outerjoin(
                self._stock_data_subquery,
                Drug.company_id == self._stock_data_subquery.c.company_id
            ).outerjoin(
                StockData,
                and_(
                    StockData.company_id == self._stock_data_subquery.c.company_id,
                    StockData.date == self._stock_data_subquery.c.max_date
                )
            )
    
    def count(self) -> int:
        """Get total count of results."""
        return self._query.count()
    
    def all(self) -> List[Drug]:
        """Get all results."""
        return self._query.all()
    
    def first(self) -> Optional[Drug]:
        """Get first result."""
        return self._query.first()
    
    def paginate(self, page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """Get paginated results with metadata."""
        total = self.count()
        total_pages = (total + per_page - 1) // per_page
        offset = (page - 1) * per_page
        
        # Get the results
        results = self._query.offset(offset).limit(per_page).all()
        
        # If stock data requested, fetch it efficiently
        stock_data = {}
        if self._include_stock_data and results:
            company_ids = [drug.company_id for drug in results]
            stock_data = self._get_latest_stock_data(company_ids)
        
        return {
            'results': results,
            'stock_data': stock_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
    
    def _get_latest_stock_data(self, company_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch latest stock data for given companies."""
        if not company_ids:
            return {}
        
        # Subquery to get latest date for each company
        subq = self.session.query(
            StockData.company_id,
            func.max(StockData.date).label('max_date')
        ).filter(
            StockData.company_id.in_(company_ids)
        ).group_by(StockData.company_id).subquery()
        
        # Get the actual stock data
        stock_data = self.session.query(StockData).join(
            subq,
            and_(
                StockData.company_id == subq.c.company_id,
                StockData.date == subq.c.max_date
            )
        ).all()
        
        # Convert to dict keyed by company_id
        return {
            sd.company_id: {
                'close': sd.close,
                'market_cap': sd.market_cap,
                'volume': sd.volume,
                'pe_ratio': sd.pe_ratio,
                'week_52_high': sd.week_52_high,
                'week_52_low': sd.week_52_low,
                'date': sd.date.isoformat() if sd.date else None
            }
            for sd in stock_data
        }
    
    def to_dict_list(self, include_stock_data: bool = True) -> List[Dict[str, Any]]:
        """Convert results to list of dictionaries."""
        results = self.all()
        
        # Get stock data if requested
        stock_data = {}
        if include_stock_data and results:
            company_ids = [drug.company_id for drug in results]
            stock_data = self._get_latest_stock_data(company_ids)
        
        # Convert to dictionaries
        dict_list = []
        for drug in results:
            company_stock = stock_data.get(drug.company_id, {})
            
            dict_list.append({
                'id': drug.id,
                'drug_name': drug.drug_name,
                'mechanism_of_action': drug.mechanism_of_action,
                'stage': drug.stage,
                'stage_event_label': drug.stage_event_label,
                'catalyst_date': drug.catalyst_date.isoformat() if drug.catalyst_date else None,
                'catalyst_date_text': drug.catalyst_date_text,
                'indications': drug.indications or [],
                'indications_text': drug.indications_text,
                'note': drug.note,
                'market_info': drug.market_info,
                'catalyst_source': drug.catalyst_source,
                'company': {
                    'id': drug.company.id,
                    'ticker': drug.company.ticker,
                    'name': drug.company.name,
                    'market_cap': company_stock.get('market_cap'),
                    'stock_price': company_stock.get('close'),
                    'price_date': company_stock.get('date')
                }
            })
        
        return dict_list


class HistoricalCatalystQuery:
    """Query builder for historical catalyst data."""
    
    def __init__(self, session: Session):
        self.session = session
        self._query = session.query(HistoricalCatalyst).join(Company)
    
    def past_days(self, days: int) -> 'HistoricalCatalystQuery':
        """Filter for catalysts within past X days."""
        start, _ = DateRangeFilter.past_days(days)
        self._query = self._query.filter(HistoricalCatalyst.catalyst_date >= start)
        return self
    
    def by_stage(self, stage: str) -> 'HistoricalCatalystQuery':
        """Filter by development stage."""
        if stage:
            pattern = StageFilter.get_sql_pattern(stage)
            self._query = self._query.filter(HistoricalCatalyst.stage.like(pattern))
        return self
    
    def by_ticker(self, ticker: str) -> 'HistoricalCatalystQuery':
        """Filter by company ticker."""
        if ticker:
            self._query = self._query.filter(HistoricalCatalyst.ticker == ticker.upper())
        return self
    
    def order_by_date(self, ascending: bool = False) -> 'HistoricalCatalystQuery':
        """Order by catalyst date."""
        if ascending:
            self._query = self._query.order_by(asc(HistoricalCatalyst.catalyst_date))
        else:
            self._query = self._query.order_by(desc(HistoricalCatalyst.catalyst_date))
        return self
    
    def all(self) -> List[HistoricalCatalyst]:
        """Get all results."""
        return self._query.all()
    
    def paginate(self, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Get paginated results."""
        total = self._query.count()
        offset = (page - 1) * per_page
        results = self._query.offset(offset).limit(per_page).all()
        
        return {
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }