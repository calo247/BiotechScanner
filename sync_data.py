"""Command-line interface for data synchronization."""

import argparse
import logging
from datetime import datetime

from src.database.database import init_db
from src.data_sync import data_synchronizer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description='Sync data from BiopharmIQ API')
    parser.add_argument(
        '--force', 
        action='store_true', 
        help='Force refresh, bypassing cache'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show sync status only'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of drugs to sync (for testing)'
    )
    parser.add_argument(
        '--stocks',
        action='store_true',
        help='Sync stock data only'
    )
    parser.add_argument(
        '--ticker',
        type=str,
        help='Sync stock data for specific ticker only'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Sync both drugs and stock data'
    )
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    if args.status:
        # Show status
        status = data_synchronizer.get_sync_status()
        print("\n=== Synchronization Status ===")
        print(f"Total drugs: {status['total_drugs']}")
        print(f"Total companies: {status['total_companies']}")
        print(f"Drugs with catalysts: {status['drugs_with_catalysts']}")
        print(f"Stock data records: {status['stock_data_records']}")
        print(f"Companies with stock data: {status['companies_with_stock_data']}")
        
        if status['last_sync']:
            print(f"Last sync: {status['last_sync'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # Check if cache is still valid
            if status['cache_expires'] > datetime.utcnow():
                remaining = status['cache_expires'] - datetime.utcnow()
                hours = remaining.total_seconds() / 3600
                print(f"Cache valid for: {hours:.1f} hours")
            else:
                print("Cache expired - next sync will fetch fresh data")
        else:
            print("No previous sync found")
    
    elif args.stocks:
        # Sync stock data only
        print("\n=== Stock Data Sync ===")
        if args.ticker:
            print(f"Syncing stock data for {args.ticker}...")
            data_synchronizer.sync_stock_data(ticker=args.ticker)
        else:
            print("Syncing stock data for all companies...")
            data_synchronizer.sync_stock_data()
    
    elif args.all:
        # Sync everything
        print("\n=== Full Data Sync ===")
        data_synchronizer.sync_all(force_refresh=args.force, limit=args.limit)
        
    else:
        # Default: sync drugs only
        print("\n=== Starting BiopharmIQ Data Sync ===")
        print(f"Force refresh: {args.force}")
        if args.limit:
            print(f"Limiting to {args.limit} drugs")
        
        data_synchronizer.sync_drugs(force_refresh=args.force, limit=args.limit)
        
        # Show final status
        status = data_synchronizer.get_sync_status()
        print(f"\nDatabase now contains:")
        print(f"  - {status['total_drugs']} drugs")
        print(f"  - {status['total_companies']} companies")
        print(f"  - {status['drugs_with_catalysts']} drugs with upcoming catalysts")


if __name__ == "__main__":
    main()