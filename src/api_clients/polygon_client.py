"""Polygon.io client for fetching stock data."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import signal
import time
from tqdm import tqdm
from polygon import RESTClient
from polygon.rest.models import Agg

from ..config import config
from ..database.database import get_db
from ..database.models import Company, StockData

# Set up logging
logger = logging.getLogger(__name__)


class PolygonClient:
    """Client for fetching stock data from Polygon.io."""
    
    def __init__(self):
        self.client = RESTClient(config.POLYGON_API_KEY)
        self.interrupted = False
        self.last_request_time = 0
        self.rate_limit_delay = config.POLYGON_RATE_LIMIT_DELAY
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        logger.info("\n\nReceived interrupt signal. Finishing current stock and stopping...")
        self.interrupted = True
    
    def _rate_limit(self):
        """Ensure we don't exceed Polygon rate limits."""
        # Skip rate limiting for premium tier
        if self.rate_limit_delay == 0:
            return
            
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def fetch_stock_data(self, ticker: str, days_back: int = None) -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data for a ticker using Polygon.io.
        
        Args:
            ticker: Stock ticker symbol
            days_back: Number of days of history to fetch (default from config)
            
        Returns:
            DataFrame with stock data or None if failed
        """
        if days_back is None:
            days_back = config.STOCK_DATA_DAYS_BACK
        
        self._rate_limit()
        
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            # Format dates for Polygon API
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"Fetching {ticker} from Polygon.io ({days_back} days)...")
            
            # Get daily aggregates with adjusted prices
            aggs = []
            for agg in self.client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=start_str,
                to=end_str,
                adjusted=True,  # Get split-adjusted prices
                limit=50000
            ):
                aggs.append(agg)
            
            if not aggs:
                logger.warning(f"No data found for {ticker}")
                return None
            
            # Convert to DataFrame
            data = []
            for agg in aggs:
                data.append({
                    'Date': pd.Timestamp(agg.timestamp, unit='ms').tz_localize(None),  # Convert to naive UTC
                    'Open': agg.open,
                    'High': agg.high,
                    'Low': agg.low,
                    'Close': agg.close,  # This is adjusted close when adjusted=True
                    'Volume': agg.volume,
                    'VWAP': agg.vwap if hasattr(agg, 'vwap') else None,
                    'Transactions': agg.transactions if hasattr(agg, 'transactions') else None
                })
            
            df = pd.DataFrame(data)
            df.set_index('Date', inplace=True)
            
            # Get ticker details for additional info
            self._rate_limit()
            try:
                ticker_details = self.client.get_ticker_details(ticker)
                
                # Add market cap if available
                if hasattr(ticker_details, 'market_cap'):
                    df['MarketCap'] = ticker_details.market_cap
                
                # Add shares outstanding for P/E calculation
                if hasattr(ticker_details, 'weighted_shares_outstanding'):
                    df['SharesOutstanding'] = ticker_details.weighted_shares_outstanding
                    
            except Exception as e:
                logger.debug(f"Could not fetch ticker details for {ticker}: {e}")
            
            logger.info(f"Fetched {len(df)} days of data for {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def get_latest_price(self, ticker: str) -> Optional[Dict[str, float]]:
        """
        Get the latest stock price and other data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dict with price data or None
        """
        self._rate_limit()
        
        try:
            # Get previous close
            prev_close = self.client.get_previous_close(ticker)
            
            return {
                'close': prev_close.close,
                'high': prev_close.high,
                'low': prev_close.low,
                'open': prev_close.open,
                'volume': prev_close.volume,
                'vwap': prev_close.vwap if hasattr(prev_close, 'vwap') else None
            }
            
        except Exception as e:
            logger.error(f"Error getting latest price for {ticker}: {e}")
            return None
    
    def update_company_stock_data(self, company_id: int, ticker: str, days_back: int = None, initial_load: bool = False) -> int:
        """
        Update stock data for a company in the database.
        
        Args:
            company_id: Company database ID
            ticker: Company ticker symbol
            days_back: Number of days to fetch (overrides automatic detection)
            initial_load: If True, fetch full historical data
            
        Returns:
            Number of records added/updated
        """
        # Determine how much data to fetch
        if days_back is not None:
            # Manual override
            fetch_days = days_back
        elif initial_load:
            # Initial load - get 5 years
            fetch_days = config.STOCK_DATA_INITIAL_YEARS * 365
        else:
            # Incremental update - check last sync date
            with get_db() as db:
                last_record = db.query(StockData).filter(
                    StockData.company_id == company_id
                ).order_by(StockData.date.desc()).first()
                
                if last_record:
                    # Calculate days since last record
                    days_since = (datetime.utcnow() - last_record.date).days
                    # Always refetch the last day (in case of partial day sync) plus days since
                    # Add 1 to include the last record date itself
                    fetch_days = days_since + 1
                    logger.debug(f"{ticker}: Last record {days_since} days ago, fetching {fetch_days} days (including last day refetch)")
                else:
                    # No existing data - do initial load
                    fetch_days = config.STOCK_DATA_INITIAL_YEARS * 365
                    logger.info(f"{ticker}: No existing data, fetching {config.STOCK_DATA_INITIAL_YEARS} years")
        
        # Fetch data from Polygon
        df = self.fetch_stock_data(ticker, fetch_days)
        
        if df is None or df.empty:
            return 0
        
        records_processed = 0
        
        with get_db() as db:
            # Process each row
            for date, row in df.iterrows():
                # Check if we already have data for this date
                existing = db.query(StockData).filter(
                    StockData.company_id == company_id,
                    StockData.date == date
                ).first()
                
                if existing:
                    # Update existing record with latest data
                    existing.open = row.get('Open')
                    existing.high = row.get('High')
                    existing.low = row.get('Low')
                    existing.close = row.get('Close')  # Adjusted close from Polygon
                    existing.volume = int(row.get('Volume', 0))
                    existing.market_cap = row.get('MarketCap')
                    existing.source = 'polygon'
                    logger.debug(f"Updated existing record for {ticker} on {date}")
                else:
                    # Create new record
                    stock_data = StockData(
                        company_id=company_id,
                        date=date,
                        open=row.get('Open'),
                        high=row.get('High'),
                        low=row.get('Low'),
                        close=row.get('Close'),  # Adjusted close from Polygon
                        volume=int(row.get('Volume', 0)),
                        market_cap=row.get('MarketCap'),
                        source='polygon'
                    )
                    
                    db.add(stock_data)
                    records_processed += 1
            
            try:
                db.commit()
                if records_processed > 0:
                    logger.info(f"Added {records_processed} new stock records for {ticker}")
            except Exception as e:
                logger.error(f"Error saving stock data for {ticker}: {e}")
                db.rollback()
                return 0
            
        return records_processed
    
    def update_all_companies_stock_data(self, batch_size: int = None, initial_load: bool = False) -> Dict[str, int]:
        """
        Update stock data for all companies in the database.
        
        Args:
            batch_size: Number of companies to process at once (not used for Polygon)
            initial_load: If True, fetch full historical data
            
        Returns:
            Dictionary with statistics
        """
        if batch_size is None:
            batch_size = config.POLYGON_BATCH_SIZE
            
        stats = {
            'companies_processed': 0,
            'companies_skipped': 0,
            'records_added': 0,
            'errors': 0,
            'interrupted': False
        }
        
        # Reset interrupt flag
        self.interrupted = False
        
        with get_db() as db:
            # Get all companies - just fetch id and ticker
            companies = db.query(Company.id, Company.ticker).all()
            total = len(companies)
            
            mode = "initial load (5 years)" if initial_load else "incremental update"
            logger.info(f"Updating stock data for {total} companies ({mode})...")
            logger.info("Press Ctrl+C to stop gracefully after current stock\n")
        
        # Process companies one by one
        with tqdm(total=total, desc=f"Updating stock data ({mode})", unit="companies") as pbar:
            for company_id, ticker in companies:
                if self.interrupted:
                    stats['interrupted'] = True
                    pbar.set_description("Interrupted - stopping...")
                    break
                    
                try:
                    # Update progress bar with current ticker
                    pbar.set_postfix_str(f"Processing {ticker}")
                    
                    records = self.update_company_stock_data(company_id, ticker, initial_load=initial_load)
                    if records > 0:
                        stats['records_added'] += records
                        stats['companies_processed'] += 1
                    else:
                        stats['companies_skipped'] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    stats['errors'] += 1
                
                pbar.update(1)
            
        if self.interrupted:
            logger.info("\nStock sync interrupted by user")
            
        return stats


# Create singleton instance
polygon_client = PolygonClient()