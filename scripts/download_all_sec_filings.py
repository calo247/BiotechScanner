#!/usr/bin/env python3
"""
Simple script to download ALL SEC filings.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import gzip
import time
import logging
from src.database.database import get_db_session
from src.database.models import Company, SECFiling
from src.api_clients.sec_client import SECClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    session = get_db_session()
    sec_client = SECClient()
    
    # Get ALL companies with filings
    companies = session.query(Company).join(SECFiling).distinct().all()
    logger.info(f"Found {len(companies)} companies with filings")
    
    total_downloaded = 0
    total_skipped = 0
    
    for i, company in enumerate(companies, 1):
        # Get all filings for this company
        filings = session.query(SECFiling).filter_by(company_id=company.id).all()
        
        logger.info(f"[{i}/{len(companies)}] {company.ticker}: {len(filings)} filings")
        
        for filing in filings:
            # Skip if already downloaded
            if filing.file_path and Path(filing.file_path).exists():
                total_skipped += 1
                continue
            
            try:
                # Download filing
                filing_text = sec_client.download_filing_text(filing.filing_url, filing.accession_number)
                
                if filing_text:
                    # Match the exact file path from the database
                    if filing.file_path:
                        # Use the exact path from database
                        file_path = Path(filing.file_path)
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                    else:
                        # Fallback if no path in database
                        company_dir = Path(f"data/sec_filings/{company.ticker}_{company.biopharma_id}")
                        filing_type_dir = company_dir / filing.filing_type.replace('/', '-')
                        filing_type_dir.mkdir(parents=True, exist_ok=True)
                        
                        date_str = filing.filing_date.strftime('%Y-%m-%d')
                        filename = f"{date_str}_{filing.accession_number}.txt.gz"
                        file_path = filing_type_dir / filename
                    
                    with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                        f.write(filing_text)
                    
                    # Update database
                    filing.file_path = str(file_path)
                    filing.file_size = file_path.stat().st_size
                    session.commit()
                    
                    total_downloaded += 1
                    
                    if total_downloaded % 100 == 0:
                        logger.info(f"  Progress: {total_downloaded} downloaded, {total_skipped} skipped")
                        
            except Exception as e:
                logger.error(f"  Failed {filing.accession_number}: {e}")
    
    logger.info(f"\nDONE! Downloaded: {total_downloaded}, Skipped: {total_skipped}")
    session.close()

if __name__ == '__main__':
    main()