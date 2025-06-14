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
    else:
        # Run sync
        print("\n=== Starting BiopharmIQ Data Sync ===")
        print(f"Force refresh: {args.force}")
        
        data_synchronizer.sync_drugs(force_refresh=args.force)
        
        # Show final status
        status = data_synchronizer.get_sync_status()
        print(f"\nDatabase now contains:")
        print(f"  - {status['total_drugs']} drugs")
        print(f"  - {status['total_companies']} companies")
        print(f"  - {status['drugs_with_catalysts']} drugs with upcoming catalysts")


if __name__ == "__main__":
    main()