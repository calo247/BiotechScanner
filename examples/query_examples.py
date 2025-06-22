"""Examples of using the query module for catalyst data analysis."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.database import get_db
from src.queries import CatalystQuery, CompanyQuery
from src.queries.filters import MarketCapFilter


def example_upcoming_catalysts():
    """Example: Find upcoming Phase 3 catalysts in next 30 days for small cap companies."""
    print("\n=== Upcoming Phase 3 Catalysts (Next 30 Days, Small Cap) ===")
    
    with get_db() as db:
        results = CatalystQuery(db)\
            .upcoming(days=30)\
            .by_stage("Phase 3")\
            .by_market_cap_category("small")\
            .with_stock_data()\
            .order_by("date", "asc")\
            .to_dict_list()
        
        print(f"Found {len(results)} catalysts:")
        for catalyst in results[:5]:  # Show first 5
            print(f"\n- {catalyst['company']['ticker']}: {catalyst['drug_name']}")
            print(f"  Date: {catalyst['catalyst_date_text'] or catalyst['catalyst_date']}")
            print(f"  Stage: {catalyst['stage']}")
            print(f"  Market Cap: {MarketCapFilter.format_market_cap(catalyst['company']['market_cap'])}")
            if catalyst['indications_text']:
                print(f"  Indication: {catalyst['indications_text'][:100]}...")


def example_search_catalysts():
    """Example: Search for oncology-related catalysts."""
    print("\n=== Searching for Oncology Catalysts ===")
    
    with get_db() as db:
        results = CatalystQuery(db)\
            .upcoming()\
            .search("oncology")\
            .order_by("date", "asc")\
            .paginate(page=1, per_page=10)
        
        print(f"Found {results['pagination']['total']} total catalysts")
        print(f"Showing page {results['pagination']['page']} of {results['pagination']['total_pages']}")
        
        for drug in results['results'][:3]:  # Show first 3
            print(f"\n- {drug.company.ticker}: {drug.drug_name}")
            print(f"  Stage: {drug.stage}")
            if drug.indications_text and 'oncology' in drug.indications_text.lower():
                print(f"  Indications: {drug.indications_text[:100]}...")


def example_company_analysis():
    """Example: Analyze companies with upcoming catalysts."""
    print("\n=== Company Analysis ===")
    
    with get_db() as db:
        # Find companies with catalysts
        companies = CompanyQuery(db)\
            .with_catalysts()\
            .with_stock_data()\
            .order_by_ticker()\
            .all()
        
        print(f"Found {len(companies)} companies with catalysts")
        
        # Get summary stats
        stats = CompanyQuery(db).with_catalysts().get_summary_stats()
        print(f"\nSummary Statistics:")
        print(f"- Total companies: {stats['total_companies']}")
        print(f"- Companies with catalysts: {stats['companies_with_catalysts']}")
        print(f"- Total drugs: {stats['total_drugs']}")
        print(f"- Drugs with catalysts: {stats['drugs_with_catalysts']}")


def example_multi_stage_filter():
    """Example: Find catalysts in multiple stages."""
    print("\n=== Multi-Stage Filter Example ===")
    
    with get_db() as db:
        results = CatalystQuery(db)\
            .upcoming(days=90)\
            .by_stages(["Phase 2", "Phase 3", "NDA"])\
            .order_by("stage", "asc")\
            .to_dict_list()
        
        # Group by stage
        by_stage = {}
        for catalyst in results:
            stage = catalyst['stage']
            if stage not in by_stage:
                by_stage[stage] = []
            by_stage[stage].append(catalyst)
        
        print(f"Found {len(results)} catalysts across stages:")
        for stage, catalysts in sorted(by_stage.items()):
            print(f"\n{stage}: {len(catalysts)} catalysts")
            for cat in catalysts[:2]:  # Show first 2 per stage
                print(f"  - {cat['company']['ticker']}: {cat['drug_name']} ({cat['catalyst_date_text']})")


def example_market_cap_ranges():
    """Example: Analyze catalysts by market cap ranges."""
    print("\n=== Market Cap Analysis ===")
    
    with get_db() as db:
        # Define custom ranges
        ranges = [
            ("Micro Cap (<$300M)", 0, 300_000_000),
            ("Small Cap ($300M-$2B)", 300_000_000, 2_000_000_000),
            ("Mid Cap ($2B-$10B)", 2_000_000_000, 10_000_000_000),
            ("Large Cap (>$10B)", 10_000_000_000, None)
        ]
        
        for label, min_cap, max_cap in ranges:
            count = CatalystQuery(db)\
                .upcoming(days=180)\
                .by_market_cap_range(min_cap, max_cap)\
                .count()
            
            print(f"{label}: {count} upcoming catalysts")


if __name__ == "__main__":
    print("BiotechScanner Query Module Examples")
    print("=" * 40)
    
    # Run examples
    example_upcoming_catalysts()
    example_search_catalysts()
    example_company_analysis()
    example_multi_stage_filter()
    example_market_cap_ranges()