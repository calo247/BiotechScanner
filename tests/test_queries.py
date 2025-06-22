"""Unit tests for the query module."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock

from src.queries import CatalystQuery, CompanyQuery
from src.queries.filters import StageFilter, DateRangeFilter, MarketCapFilter, StageCategory


class TestStageFilter:
    """Test stage filter normalization."""
    
    def test_normalize_stage_phase_variations(self):
        """Test normalization of phase variations."""
        assert StageFilter.normalize_stage("Phase 1") == StageCategory.PHASE_1
        assert StageFilter.normalize_stage("phase i") == StageCategory.PHASE_1
        assert StageFilter.normalize_stage("P1") == StageCategory.PHASE_1
        assert StageFilter.normalize_stage("Phase 1a") == StageCategory.PHASE_1
        assert StageFilter.normalize_stage("PHASE 1B") == StageCategory.PHASE_1
    
    def test_normalize_stage_combination_phases(self):
        """Test normalization of combination phases."""
        assert StageFilter.normalize_stage("Phase 1/2") == StageCategory.PHASE_1_2
        assert StageFilter.normalize_stage("Phase I/II") == StageCategory.PHASE_1_2
        assert StageFilter.normalize_stage("Phase 2/3") == StageCategory.PHASE_2_3
    
    def test_normalize_stage_regulatory(self):
        """Test normalization of regulatory stages."""
        assert StageFilter.normalize_stage("NDA") == StageCategory.NDA_BLA
        assert StageFilter.normalize_stage("BLA") == StageCategory.NDA_BLA
        assert StageFilter.normalize_stage("NDA Filed") == StageCategory.NDA_BLA
    
    def test_normalize_stage_other(self):
        """Test normalization of unknown stages."""
        assert StageFilter.normalize_stage("Unknown") == StageCategory.OTHER
        assert StageFilter.normalize_stage("") == StageCategory.OTHER
        assert StageFilter.normalize_stage(None) == StageCategory.OTHER
    
    def test_get_sql_pattern(self):
        """Test SQL pattern generation."""
        assert StageFilter.get_sql_pattern("Phase 3") == "%Phase 3%"
        assert StageFilter.get_sql_pattern("NDA") == "%NDA%"


class TestDateRangeFilter:
    """Test date range filter utilities."""
    
    def test_upcoming_days(self):
        """Test upcoming days calculation."""
        start, end = DateRangeFilter.upcoming_days(30)
        
        # Start should be today at midnight UTC
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        assert start.microsecond == 0
        
        # End should be 30 days from start
        expected_end = start + timedelta(days=30)
        assert end == expected_end
    
    def test_past_days(self):
        """Test past days calculation."""
        start, end = DateRangeFilter.past_days(90)
        
        # End should be today at midnight UTC
        assert end.hour == 0
        assert end.minute == 0
        
        # Start should be 90 days before end
        expected_start = end - timedelta(days=90)
        assert start == expected_start


class TestMarketCapFilter:
    """Test market cap filter utilities."""
    
    def test_get_range(self):
        """Test market cap range retrieval."""
        assert MarketCapFilter.get_range("micro") == (0, 300_000_000)
        assert MarketCapFilter.get_range("small") == (300_000_000, 2_000_000_000)
        assert MarketCapFilter.get_range("mid") == (2_000_000_000, 10_000_000_000)
        assert MarketCapFilter.get_range("large") == (10_000_000_000, 200_000_000_000)
        assert MarketCapFilter.get_range("mega") == (200_000_000_000, None)
        assert MarketCapFilter.get_range("unknown") == (None, None)
    
    def test_format_market_cap(self):
        """Test market cap formatting."""
        assert MarketCapFilter.format_market_cap(None) == "N/A"
        assert MarketCapFilter.format_market_cap(0) == "N/A"
        assert MarketCapFilter.format_market_cap(500_000) == "$500,000"
        assert MarketCapFilter.format_market_cap(1_500_000) == "$1.5M"
        assert MarketCapFilter.format_market_cap(2_500_000_000) == "$2.5B"
        assert MarketCapFilter.format_market_cap(1_200_000_000_000) == "$1.2T"


class TestCatalystQuery:
    """Test CatalystQuery builder."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.mock_query = Mock()
        self.mock_session.query.return_value = self.mock_query
        self.mock_query.join.return_value = self.mock_query
        self.mock_query.filter.return_value = self.mock_query
        self.mock_query.order_by.return_value = self.mock_query
    
    def test_initialization(self):
        """Test query initialization."""
        query = CatalystQuery(self.mock_session)
        assert query.session == self.mock_session
        self.mock_session.query.assert_called_once()
    
    def test_upcoming_filter(self):
        """Test upcoming catalyst filter."""
        query = CatalystQuery(self.mock_session)
        result = query.upcoming(days=30)
        
        # Should return self for chaining
        assert result == query
        
        # Should have called filter multiple times
        assert self.mock_query.filter.call_count >= 2
    
    def test_by_stage_filter(self):
        """Test stage filtering."""
        query = CatalystQuery(self.mock_session)
        result = query.by_stage("Phase 3")
        
        assert result == query
        self.mock_query.filter.assert_called()
    
    def test_search_filter(self):
        """Test search functionality."""
        query = CatalystQuery(self.mock_session)
        result = query.search("oncology")
        
        assert result == query
        self.mock_query.filter.assert_called()
    
    def test_order_by(self):
        """Test ordering."""
        query = CatalystQuery(self.mock_session)
        
        # Test ascending
        query.order_by("date", "asc")
        self.mock_query.order_by.assert_called()
        
        # Reset mock
        self.mock_query.reset_mock()
        
        # Test descending
        query.order_by("ticker", "desc")
        self.mock_query.order_by.assert_called()
    
    def test_chaining(self):
        """Test method chaining."""
        query = CatalystQuery(self.mock_session)
        
        # Chain multiple filters
        result = query\
            .upcoming(days=30)\
            .by_stage("Phase 3")\
            .search("cancer")\
            .order_by("date", "asc")
        
        # Should return self for chaining
        assert result == query
        
        # All filters should have been applied
        assert self.mock_query.filter.call_count >= 3
        assert self.mock_query.order_by.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__])