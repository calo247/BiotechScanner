#!/usr/bin/env python3
"""Command-line tool for querying catalyst data using the new query module."""

import argparse
from datetime import datetime
from tabulate import tabulate

from src.database.database import get_db, init_db
from src.queries import CatalystQuery
from src.queries.filters import MarketCapFilter


def main():
    parser = argparse.ArgumentParser(description='Query upcoming biotech catalysts')
    
    # Filter arguments
    parser.add_argument('--days', type=int, help='Show catalysts in next N days')
    parser.add_argument('--stage', type=str, help='Filter by stage (e.g., "Phase 3", "NDA")')
    parser.add_argument('--ticker', type=str, help='Filter by ticker symbol')
    parser.add_argument('--marketcap', choices=['micro', 'small', 'mid', 'large', 'mega'],
                       help='Filter by market cap category')
    parser.add_argument('--min-marketcap', type=float, help='Minimum market cap (e.g., 100000000 for $100M)')
    parser.add_argument('--max-marketcap', type=float, help='Maximum market cap (e.g., 5000000000 for $5B)')
    parser.add_argument('--search', type=str, help='Search across all fields')
    
    # Display arguments
    parser.add_argument('--limit', type=int, default=25, help='Number of results to show')
    parser.add_argument('--sort', choices=['date', 'ticker', 'company', 'stage', 'marketcap'],
                       default='date', help='Sort by field')
    parser.add_argument('--desc', action='store_true', help='Sort in descending order')
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    with get_db() as db:
        # Build query
        query = CatalystQuery(db).with_stock_data()
        
        # Apply filters
        if args.days:
            query = query.upcoming(days=args.days)
        else:
            query = query.upcoming()
        
        if args.stage:
            query = query.by_stage(args.stage)
        
        if args.ticker:
            query = query.by_ticker(args.ticker)
        
        if args.marketcap:
            query = query.by_market_cap_category(args.marketcap)
        elif args.min_marketcap is not None or args.max_marketcap is not None:
            # Use custom range if provided
            query = query.by_market_cap_range(args.min_marketcap, args.max_marketcap)
        
        if args.search:
            query = query.search(args.search)
        
        # Apply sorting
        sort_dir = 'desc' if args.desc else 'asc'
        query = query.order_by(args.sort, sort_dir)
        
        # Get results
        results = query.to_dict_list(include_stock_data=True)[:args.limit]
        
        if not results:
            print("No catalysts found matching your criteria.")
            return
        
        # Prepare data for table
        table_data = []
        for catalyst in results:
            table_data.append([
                catalyst['catalyst_date_text'] or catalyst['catalyst_date'][:10],
                catalyst['company']['ticker'],
                catalyst['company']['name'][:30],
                catalyst['drug_name'][:40],
                catalyst['stage'],
                MarketCapFilter.format_market_cap(catalyst['company']['market_cap']),
                f"${catalyst['company']['stock_price']:.2f}" if catalyst['company']['stock_price'] else 'N/A'
            ])
        
        # Print results
        headers = ['Date', 'Ticker', 'Company', 'Drug', 'Stage', 'Market Cap', 'Price']
        print(f"\nFound {len(results)} upcoming catalysts:")
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        # Print summary
        if results:
            stages = {}
            for r in results:
                stage = r['stage']
                stages[stage] = stages.get(stage, 0) + 1
            
            print(f"\nStage distribution:")
            for stage, count in sorted(stages.items()):
                print(f"  {stage}: {count}")


if __name__ == "__main__":
    main()