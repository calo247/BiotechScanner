"""Database models for the Biotech Catalyst Tool."""

from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, 
    Boolean, Text, ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


def utc_now():
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Company(Base):
    """Company information."""
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True)
    biopharma_id = Column(Integer, unique=True, index=True)  # BiopharmIQ's company ID
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(Text, nullable=False)  # Company names can be long
    sector = Column(String(100))
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    drugs = relationship("Drug", back_populates="company", cascade="all, delete-orphan")
    stock_data = relationship("StockData", back_populates="company", cascade="all, delete-orphan")
    sec_filings = relationship("SECFiling", back_populates="company", cascade="all, delete-orphan")
    financial_metrics = relationship("FinancialMetric", back_populates="company", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Company(ticker='{self.ticker}', name='{self.name}')>"


class Drug(Base):
    """Drug information from BiopharmIQ."""
    __tablename__ = 'drugs'
    
    id = Column(Integer, primary_key=True)
    biopharma_id = Column(Integer, unique=True, nullable=False)  # ID from API
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # Drug information
    drug_name = Column(Text, nullable=False)  # No length limit
    mechanism_of_action = Column(Text)
    
    # Indication information (storing as JSON for flexibility)
    indications = Column(JSON)  # List of indication objects
    indications_text = Column(Text)  # No length limit
    
    # Stage and event
    stage = Column(String(100))  # This is probably fine with a limit
    stage_event_label = Column(Text)  # No length limit
    event_score = Column(Integer)  # Score from API
    
    # Catalyst information
    catalyst_date = Column(DateTime)
    catalyst_date_text = Column(String(100))  # This is probably fine with a limit
    has_catalyst = Column(Boolean, default=False)
    catalyst_source = Column(Text)  # URLs can be long
    
    # Analysis flags
    is_big_mover = Column(Boolean, default=False)
    is_suspected_mover = Column(Boolean, default=False)
    
    # Additional data
    note = Column(Text)
    market_info = Column(Text)
    last_update_name = Column(Text)
    
    # Tracking
    api_last_updated = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    company = relationship("Company", back_populates="drugs")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_catalyst_date', 'catalyst_date'),
        Index('idx_stage', 'stage'),
        Index('idx_has_catalyst', 'has_catalyst'),
    )
    
    def __repr__(self):
        return f"<Drug(name='{self.drug_name}', company='{self.company.ticker if self.company else 'N/A'}', has_catalyst={self.has_catalyst})>"


class StockData(Base):
    """Daily stock price and volume data."""
    __tablename__ = 'stock_data'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # Price data
    date = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float, nullable=False)
    adjusted_close = Column(Float)
    volume = Column(Integer)
    
    # Additional metrics
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    week_52_high = Column(Float)
    week_52_low = Column(Float)
    
    # Tracking
    source = Column(String(50), default='yahoo')  # Data source
    created_at = Column(DateTime, default=utc_now)
    
    # Relationships
    company = relationship("Company", back_populates="stock_data")
    
    # Unique constraint to prevent duplicate entries
    __table_args__ = (
        UniqueConstraint('company_id', 'date', name='_company_date_uc'),
        Index('idx_stock_date', 'date'),
    )
    
    def __repr__(self):
        return f"<StockData(ticker='{self.company.ticker if self.company else 'N/A'}', date='{self.date}', close={self.close})>"


class SECFiling(Base):
    """SEC filing references."""
    __tablename__ = 'sec_filings'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # Filing information
    filing_type = Column(String(20), nullable=False)  # 10-K, 10-Q, 8-K, etc.
    filing_date = Column(DateTime, nullable=False)
    accession_number = Column(String(25), unique=True, nullable=False)
    filing_url = Column(String(500))
    
    # File storage
    file_path = Column(String(500))  # Path to compressed text file
    file_size = Column(Integer)  # Size in bytes
    
    # Metadata for quick filtering
    word_count = Column(Integer)
    mentions_clinical_trial = Column(Boolean, default=False)
    
    # Content (storing key sections as JSON)
    parsed_content = Column(JSON)  # Flexible storage for different filing types
    
    # Tracking
    created_at = Column(DateTime, default=utc_now)
    
    # Relationships
    company = relationship("Company", back_populates="sec_filings")
    
    # Indexes
    __table_args__ = (
        Index('idx_filing_date', 'filing_date'),
        Index('idx_filing_type', 'filing_type'),
    )
    
    def __repr__(self):
        return f"<SECFiling(ticker='{self.company.ticker if self.company else 'N/A'}', type='{self.filing_type}', date='{self.filing_date}')>"


class FinancialMetric(Base):
    """Financial metrics from SEC XBRL data."""
    __tablename__ = 'financial_metrics'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # Metric identification
    concept = Column(String(200), nullable=False)  # XBRL concept name
    label = Column(String(500))  # Human-readable label
    
    # Value
    value = Column(Float)  # Using Float to handle decimals
    unit = Column(String(50))  # USD, shares, etc.
    
    # Time period
    fiscal_year = Column(Integer)
    fiscal_period = Column(String(10))  # FY, Q1, Q2, Q3, Q4
    form = Column(String(20))  # 10-K, 10-Q, etc.
    filed_date = Column(DateTime)
    
    # Reference
    accession_number = Column(String(25))
    
    # Tracking
    created_at = Column(DateTime, default=utc_now)
    
    # Relationships
    company = relationship("Company", back_populates="financial_metrics")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_company_concept', 'company_id', 'concept'),
        Index('idx_fiscal_period', 'fiscal_year', 'fiscal_period'),
        UniqueConstraint('company_id', 'concept', 'fiscal_year', 'fiscal_period', 'form', 
                        name='_company_metric_period_uc'),
    )
    
    def __repr__(self):
        return f"<FinancialMetric(company='{self.company.ticker if self.company else 'N/A'}', concept='{self.concept}', value={self.value}, period='{self.fiscal_year}-{self.fiscal_period}')>"


class APICache(Base):
    """Cache for API responses to respect rate limits."""
    __tablename__ = 'api_cache'
    
    id = Column(Integer, primary_key=True)
    endpoint = Column(String(255), unique=True, nullable=False)
    response_data = Column(JSON, nullable=False)
    last_fetched = Column(DateTime, nullable=False, default=utc_now)
    created_at = Column(DateTime, default=utc_now)
    
    def __repr__(self):
        return f"<APICache(endpoint='{self.endpoint}', last_fetched='{self.last_fetched}')>"