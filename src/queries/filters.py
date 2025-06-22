"""Common filters for database queries."""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from enum import Enum


class StageCategory(Enum):
    """Standardized stage categories."""
    PRECLINICAL = "Preclinical"
    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    PHASE_1_2 = "Phase 1/2"
    PHASE_2_3 = "Phase 2/3"
    NDA_BLA = "NDA/BLA"
    APPROVED = "Approved"
    OTHER = "Other"


class StageFilter:
    """Handles stage filtering with normalization."""
    
    # Mapping of common variations to standardized stages
    STAGE_MAPPINGS = {
        # Phase 1 variations
        "phase 1": StageCategory.PHASE_1,
        "phase i": StageCategory.PHASE_1,
        "p1": StageCategory.PHASE_1,
        "phase1": StageCategory.PHASE_1,
        "phase 1a": StageCategory.PHASE_1,
        "phase 1b": StageCategory.PHASE_1,
        
        # Phase 2 variations
        "phase 2": StageCategory.PHASE_2,
        "phase ii": StageCategory.PHASE_2,
        "p2": StageCategory.PHASE_2,
        "phase2": StageCategory.PHASE_2,
        "phase 2a": StageCategory.PHASE_2,
        "phase 2b": StageCategory.PHASE_2,
        
        # Phase 3 variations
        "phase 3": StageCategory.PHASE_3,
        "phase iii": StageCategory.PHASE_3,
        "p3": StageCategory.PHASE_3,
        "phase3": StageCategory.PHASE_3,
        
        # Combination phases
        "phase 1/2": StageCategory.PHASE_1_2,
        "phase i/ii": StageCategory.PHASE_1_2,
        "phase 2/3": StageCategory.PHASE_2_3,
        "phase ii/iii": StageCategory.PHASE_2_3,
        
        # Regulatory
        "nda": StageCategory.NDA_BLA,
        "bla": StageCategory.NDA_BLA,
        "nda/bla": StageCategory.NDA_BLA,
        "nda filed": StageCategory.NDA_BLA,
        "bla filed": StageCategory.NDA_BLA,
        
        # Approved
        "approved": StageCategory.APPROVED,
        "marketed": StageCategory.APPROVED,
        "commercial": StageCategory.APPROVED,
        
        # Preclinical
        "preclinical": StageCategory.PRECLINICAL,
        "pre-clinical": StageCategory.PRECLINICAL,
        "discovery": StageCategory.PRECLINICAL,
    }
    
    @classmethod
    def normalize_stage(cls, stage: str) -> StageCategory:
        """Normalize a stage string to a standard category."""
        if not stage:
            return StageCategory.OTHER
            
        stage_lower = stage.lower().strip()
        
        # Direct mapping check
        if stage_lower in cls.STAGE_MAPPINGS:
            return cls.STAGE_MAPPINGS[stage_lower]
        
        # Check for partial matches
        for pattern, category in cls.STAGE_MAPPINGS.items():
            if pattern in stage_lower:
                return category
        
        return StageCategory.OTHER
    
    @classmethod
    def get_sql_pattern(cls, stage_filter: str) -> str:
        """Get SQL LIKE pattern for a stage filter."""
        # For now, keep the simple pattern matching
        # In future, we could use the normalized categories
        return f"%{stage_filter}%"


class DateRangeFilter:
    """Handles date range filtering."""
    
    @staticmethod
    def upcoming_days(days: int) -> tuple[datetime, datetime]:
        """Get date range for upcoming X days."""
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=days)
        return start, end
    
    @staticmethod
    def past_days(days: int) -> tuple[datetime, datetime]:
        """Get date range for past X days."""
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=days)
        return start, end
    
    @staticmethod
    def date_range(start: Optional[datetime] = None, end: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[datetime]]:
        """Get custom date range."""
        return start, end


class MarketCapFilter:
    """Handles market cap filtering."""
    
    # Common market cap ranges
    MICRO_CAP = (0, 300_000_000)  # < $300M
    SMALL_CAP = (300_000_000, 2_000_000_000)  # $300M - $2B
    MID_CAP = (2_000_000_000, 10_000_000_000)  # $2B - $10B
    LARGE_CAP = (10_000_000_000, 200_000_000_000)  # $10B - $200B
    MEGA_CAP = (200_000_000_000, None)  # > $200B
    
    @classmethod
    def get_range(cls, category: str) -> tuple[Optional[float], Optional[float]]:
        """Get market cap range by category name."""
        ranges = {
            "micro": cls.MICRO_CAP,
            "small": cls.SMALL_CAP,
            "mid": cls.MID_CAP,
            "large": cls.LARGE_CAP,
            "mega": cls.MEGA_CAP,
        }
        return ranges.get(category.lower(), (None, None))
    
    @staticmethod
    def format_market_cap(value: Optional[float]) -> str:
        """Format market cap for display."""
        if not value:
            return "N/A"
        if value >= 1e12:
            return f"${value / 1e12:.1f}T"
        if value >= 1e9:
            return f"${value / 1e9:.1f}B"
        if value >= 1e6:
            return f"${value / 1e6:.1f}M"
        return f"${value:,.0f}"