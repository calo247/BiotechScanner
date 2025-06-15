"""Yahoo Finance client for fetching stock data."""

import yfinance as yf
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import pandas as pd
import signal
import sys
from tqdm import tqdm

from ..config import config
from ..database.database import get_db
from ..database.models import Company, StockData

# Set up logging
logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """Client for fetching stock data from Yahoo Finance."""
    
    def __init__(self):
        # Suppress yfinance logging
        logging.getLogger('yfinance').setLevel(logging.WARNING)
        self.interrupted = False
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        logger.info("\n\nReceived interrupt signal. Finishing current stock and stopping...")
        self.interrupted = True
    
    def fetch_stock_data(self, ticker: str, days_back: int = None) -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            days_back: Number of days of history to fetch (default from config)
            
        Returns:
            DataFrame with stock data or None if failed
        """
        if days_back is None:
            days_back = config.STOCK_DATA_DAYS_BACK
            
        try:
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days_back)
            
            # Fetch data
            logger.info(f"Fetching {ticker} from Yahoo Finance ({days_back} days)...")
            stock = yf.Ticker(ticker)
            
            # Get historical data
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                logger.warning(f"No data found for {ticker}")
                return None
            
            # Get additional info
            info = stock.info
            
            # Add market cap if available
            market_cap = info.get('marketCap')
            if market_cap:
                hist['MarketCap'] = market_cap
            
            # Add other metrics
            hist['PE_Ratio'] = info.get('trailingPE')
            hist['52WeekHigh'] = info.get('fiftyTwoWeekHigh')
            hist['52WeekLow'] = info.get('fiftyTwoWeekLow')
            
            logger.info(f"Fetched {len(hist)} days of data for {ticker}")
            return hist
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def update_company_stock_data(self, company_id: int, ticker: str, days_back: int = None) -> int:
        """
        Update stock data for a company in the database.
        
        Args:
            company_id: Company database ID
            ticker: Company ticker symbol
            days_back: Number of days to fetch
            
        Returns:
            Number of records added/updated
        """
        # Fetch data from Yahoo
        df = self.fetch_stock_data(ticker, days_back)
        
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
                    existing.close = row.get('Close')
                    existing.adjusted_close = row.get('Close')
                    existing.volume = int(row.get('Volume', 0))
                    existing.market_cap = row.get('MarketCap')
                    existing.pe_ratio = row.get('PE_Ratio')
                    existing.week_52_high = row.get('52WeekHigh')
                    existing.week_52_low = row.get('52WeekLow')
                    logger.debug(f"Updated existing record for {ticker} on {date}")
                else:
                    # Create new record
                    stock_data = StockData(
                        company_id=company_id,
                        date=date,
                        open=row.get('Open'),
                        high=row.get('High'),
                        low=row.get('Low'),
                        close=row.get('Close'),
                        adjusted_close=row.get('Close'),  # yfinance returns adjusted prices
                        volume=int(row.get('Volume', 0)),
                        market_cap=row.get('MarketCap'),
                        pe_ratio=row.get('PE_Ratio'),
                        week_52_high=row.get('52WeekHigh'),
                        week_52_low=row.get('52WeekLow'),
                        source='yahoo'
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
    
    def update_all_companies_stock_data(self, batch_size: int = None) -> Dict[str, int]:
        """
        Update stock data for all companies in the database.
        
        Args:
            batch_size: Number of companies to process at once
            
        Returns:
            Dictionary with statistics
        """
        if batch_size is None:
            batch_size = config.YAHOO_BATCH_SIZE
            
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
            
            logger.info(f"Updating stock data for {total} companies...")
            logger.info("Press Ctrl+C to stop gracefully after current stock\n")
        
        # Process with progress bar
        with tqdm(total=total, desc="Updating stock data", unit="companies") as pbar:
            for i in range(0, total, batch_size):
                if self.interrupted:
                    stats['interrupted'] = True
                    pbar.set_description("Interrupted - finishing current batch")
                    break
                    
                batch = companies[i:i + batch_size]
                
                for company_id, ticker in batch:
                    if self.interrupted:
                        stats['interrupted'] = True
                        break
                        
                    try:
                        # Update progress bar with current ticker
                        pbar.set_postfix_str(f"Processing {ticker}")
                        
                        records = self.update_company_stock_data(company_id, ticker)
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
    
    def get_latest_price(self, ticker: str) -> Optional[float]:
        """
        Get the latest stock price for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Latest closing price or None
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest price for {ticker}: {e}")
            return None


# Create singleton instance
yahoo_client = YahooFinanceClient()