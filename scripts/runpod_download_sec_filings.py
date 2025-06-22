#!/usr/bin/env python3
"""
Re-download SEC filings directly on RunPod.
Much faster than uploading 6.4GB from local machine.
"""
import sys
import os
from pathlib import Path
import argparse
import logging
from datetime import datetime
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.database import get_db_session
from src.database.models import Company, SECFiling
from src.api_clients.sec_client import SECClient
from sqlalchemy import func
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def download_company_filings(company, filings, sec_client, dry_run=False):
    """Download all filings for a company."""
    success_count = 0
    
    for filing in filings:
        if filing.file_path and Path(filing.file_path).exists():
            # Already have this filing
            success_count += 1
            continue
        
        if dry_run:
            logger.info(f"  Would download: {filing.filing_type} from {filing.filing_date}")
            continue
        
        try:
            # Use the SEC client's existing download method
            file_path = sec_client.download_filing(
                filing.accession_number,
                filing.filing_url,
                company.ticker,
                company.biopharma_id,
                filing.filing_type,
                filing.filing_date
            )
            
            if file_path:
                # Update database with file path
                filing.file_path = file_path
                filing.file_size = Path(file_path).stat().st_size
                success_count += 1
                
        except Exception as e:
            logger.error(f"  Failed to download {filing.accession_number}: {e}")
    
    return success_count


def main():
    parser = argparse.ArgumentParser(description='Re-download SEC filings on RunPod')
    parser.add_argument('--company-limit', type=int, 
                       help='Limit number of companies')
    parser.add_argument('--ticker', type=str,
                       help='Download for specific ticker only')
    parser.add_argument('--top-n', type=int, default=50,
                       help='Download top N companies by filing count')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be downloaded without downloading')
    parser.add_argument('--filing-types', nargs='+',
                       default=['10-K', '10-Q', '8-K'],
                       help='Filing types to download')
    
    args = parser.parse_args()
    
    # Initialize
    session = get_db_session()
    sec_client = SECClient()
    
    # Get companies to process
    if args.ticker:
        companies = session.query(Company).filter_by(ticker=args.ticker.upper()).all()
        if not companies:
            logger.error(f"Company {args.ticker} not found")
            return
    else:
        # Get top companies by filing count
        query = session.query(
            Company,
            func.count(SECFiling.id).label('filing_count')
        ).join(
            SECFiling
        ).group_by(
            Company.id
        ).order_by(
            func.count(SECFiling.id).desc()
        )
        
        if args.company_limit:
            limit = min(args.company_limit, args.top_n)
        else:
            limit = args.top_n
            
        results = query.limit(limit).all()
        companies = [r[0] for r in results]
    
    logger.info(f"Processing {len(companies)} companies")
    if args.dry_run:
        logger.info("DRY RUN - No files will be downloaded")
    
    # Process each company
    total_downloaded = 0
    total_to_download = 0
    start_time = time.time()
    
    for idx, company in enumerate(companies, 1):
        # Get filings for this company
        filings = session.query(SECFiling).filter(
            SECFiling.company_id == company.id,
            SECFiling.filing_type.in_(args.filing_types)
        ).all()
        
        # Count how many need downloading
        need_download = sum(1 for f in filings 
                          if not (f.file_path and Path(f.file_path).exists()))
        
        if need_download == 0:
            logger.info(f"[{idx}/{len(companies)}] {company.ticker}: All {len(filings)} filings already downloaded")
            continue
        
        logger.info(f"[{idx}/{len(companies)}] {company.ticker}: Downloading {need_download}/{len(filings)} filings")
        total_to_download += need_download
        
        # Download filings
        downloaded = download_company_filings(company, filings, sec_client, args.dry_run)
        total_downloaded += downloaded
        
        # Commit changes
        if not args.dry_run:
            session.commit()
        
        # Show progress
        if total_to_download > 0:
            elapsed = time.time() - start_time
            rate = total_downloaded / elapsed if elapsed > 0 else 0
            eta = (total_to_download - total_downloaded) / rate if rate > 0 else 0
            logger.info(f"  Progress: {total_downloaded}/{total_to_download} filings "
                       f"({rate:.1f} files/sec, ETA: {eta/60:.1f} min)")
    
    # Summary
    elapsed_total = time.time() - start_time
    logger.info(f"\nDownload complete!")
    logger.info(f"Total filings downloaded: {total_downloaded}")
    logger.info(f"Total time: {elapsed_total/60:.1f} minutes")
    
    if not args.dry_run:
        # Check total size
        total_size = 0
        for company in companies:
            company_dir = Path(f"data/sec_filings/{company.ticker}_{company.biopharma_id}")
            if company_dir.exists():
                size = sum(f.stat().st_size for f in company_dir.rglob("*.gz"))
                total_size += size
        
        logger.info(f"Total size: {total_size/1e9:.1f} GB (compressed)")
    
    session.close()


if __name__ == '__main__':
    main()