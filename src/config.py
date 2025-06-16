"""Configuration management for the Biotech Catalyst Tool."""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # API Keys
    BIOPHARMA_API_KEY = os.getenv('BIOPHARMA_API_KEY')
    if not BIOPHARMA_API_KEY:
        raise ValueError("BIOPHARMA_API_KEY environment variable is required")
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/catalyst.db')
    
    # BiopharmIQ API Settings
    BIOPHARMA_BASE_URL = "https://api.bpiq.com/api/v1"
    BIOPHARMA_CACHE_HOURS = 12  # Cache API data for 12 hours
    
    # Yahoo Finance Settings
    YAHOO_BATCH_SIZE = 50  # Number of tickers to fetch at once
    
    # Data Update Settings
    STOCK_DATA_DAYS_BACK = 30  # How many days of historical data to fetch
    
    # Request timeouts
    REQUEST_TIMEOUT = 30  # seconds
    
    # SEC EDGAR Settings
    SEC_USER_AGENT = os.getenv('SEC_USER_AGENT', 'BiotechScanner/1.0 (your-email@example.com)')
    SEC_FILING_TYPES = ['10-K', '10-Q', '8-K', 'DEF 14A']  # Filing types to fetch
    SEC_DAYS_BACK = 365  # How many days of filings to fetch
    
    @classmethod
    def get_cache_expiry(cls):
        """Get cache expiry as timedelta."""
        return timedelta(hours=cls.BIOPHARMA_CACHE_HOURS)


# Create a single instance
config = Config()