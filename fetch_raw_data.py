"""Fetch and save raw API response for inspection."""

import json
import argparse
from datetime import datetime
from src.api_clients.biopharma_client import biopharma_client

def fetch_and_save_raw_data(limit: int = 10):
    """Fetch raw data from API and save to JSON file."""
    
    print(f"Fetching {limit} drugs from BiopharmIQ API...")
    
    # Test connection first
    if not biopharma_client.test_connection():
        print("Failed to connect to API")
        return
    
    # Fetch drugs without using cache
    drugs = biopharma_client.get_all_drugs(use_cache=False, limit=limit)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"raw_drugs_{timestamp}_limit{limit}.json"
    
    # Save to file with pretty formatting
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(drugs, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(drugs)} drugs to {filename}")
    
    # Print summary of first drug
    if drugs:
        first_drug = drugs[0]
        print("\nFirst drug summary:")
        print(f"  ID: {first_drug.get('id')}")
        print(f"  Name: {first_drug.get('drug_name')}")
        print(f"  Company: {first_drug.get('company')}")
        print(f"  Has catalyst: {first_drug.get('has_catalyst')}")
        
        # Check if company field exists and has expected structure
        company = first_drug.get('company')
        if company:
            print(f"  Company ticker: {company.get('ticker')}")
            print(f"  Company name: {company.get('name')}")
        else:
            print("  WARNING: No company data!")

def main():
    parser = argparse.ArgumentParser(description='Fetch raw drug data from BiopharmIQ API')
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of drugs to fetch (default: 10)'
    )
    
    args = parser.parse_args()
    fetch_and_save_raw_data(args.limit)

if __name__ == "__main__":
    main()