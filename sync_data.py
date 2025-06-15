"""Command-line interface for data synchronization."""

import argparse
import logging
from datetime import datetime, timezone

from src.database.database import init_db
from src.data_sync import data_synchronizer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description='Sync data from BiopharmIQ API and Yahoo Finance')
    
    # Main action flags (mutually exclusive would be ideal, but we'll handle in logic)
    parser.add_argument(
        '--drugs',
        action='store_true',
        help='Sync drug data (respects cache unless --force is used)'
    )
    parser.add_argument(
        '--stocks',
        action='store_true',
        help='Sync stock data only'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Sync both drugs and stocks (respects cache unless --force is used)'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show sync status only'
    )
    
    # Modifier flags
    parser.add_argument(
        '--force', 
        action='store_true', 
        help='Force refresh, bypassing cache (use with --drugs or --all)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of drugs to sync (for testing)'
    )
    parser.add_argument(
        '--ticker',
        type=str,
        help='Sync stock data for specific ticker only (use with --stocks)'
    )
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    # Default behavior if no flags specified
    if not any([args.drugs, args.stocks, args.all, args.status]):
        args.all = True  # Default to full sync
    
    # Handle commands
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
            print(f"\nLast drug sync: {status['last_sync'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # Check if cache is still valid
            if status['cache_expires'] > datetime.now(timezone.utc):
                remaining = status['cache_expires'] - datetime.now(timezone.utc)
                hours = remaining.total_seconds() / 3600
                print(f"Cache status: VALID (expires in {hours:.1f} hours)")
            else:
                print("Cache status: EXPIRED")
        else:
            print("\nNo previous sync found")
    
    elif args.drugs and not args.all:
        # Sync drugs only
        if not args.force:
            # Check if cache is valid
            status = data_synchronizer.get_sync_status()
            if status['last_sync'] and status['cache_expires'] > datetime.now(timezone.utc):
                remaining = status['cache_expires'] - datetime.now(timezone.utc)
                hours = remaining.total_seconds() / 3600
                print(f"\n=== Drug Data Cache Still Valid ===")
                print(f"Cache expires in {hours:.1f} hours")
                print(f"Use --force to sync anyway")
                return
        
        print("\n=== BiopharmIQ Drug Data Sync ===")
        print(f"Force refresh: {args.force}")
        if args.limit:
            print(f"Limiting to {args.limit} drugs")
        
        data_synchronizer.sync_drugs(force_refresh=args.force, limit=args.limit)
    
    elif args.stocks and not args.all:
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
        
        # Check drug cache status
        if not args.force:
            status = data_synchronizer.get_sync_status()
            if status['last_sync'] and status['cache_expires'] > datetime.now(timezone.utc):
                remaining = status['cache_expires'] - datetime.now(timezone.utc)
                hours = remaining.total_seconds() / 3600
                print(f"Drug cache still valid for {hours:.1f} hours - skipping drug sync")
                print("(Use --all --force to sync drugs anyway)")
            else:
                print("Drug cache expired - syncing drugs...")
                data_synchronizer.sync_drugs(force_refresh=False, limit=args.limit)
        else:
            print("Force refreshing drug data...")
            data_synchronizer.sync_drugs(force_refresh=True, limit=args.limit)
        
        # Always sync stocks with --all
        if not data_synchronizer.interrupted:
            print("\nSyncing stock data...")
            data_synchronizer.sync_stock_data()
    
    else:
        # This shouldn't happen with our default, but just in case
        parser.print_help()
        
        # Show final status
        status = data_synchronizer.get_sync_status()
        print(f"\nDatabase now contains:")
        print(f"  - {status['total_drugs']} drugs")
        print(f"  - {status['total_companies']} companies")
        print(f"  - {status['drugs_with_catalysts']} drugs with upcoming catalysts")


if __name__ == "__main__":
    main()