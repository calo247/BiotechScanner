#!/usr/bin/env python3
"""
GPU-accelerated indexing script for RunPod.
Indexes all SEC filings with progress tracking and error recovery.
"""
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Company, SECFiling
from sqlalchemy import func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/indexing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IndexingProgress:
    """Track indexing progress for resume capability."""
    
    def __init__(self, progress_file='logs/indexing_progress.json'):
        self.progress_file = progress_file
        self.data = self._load_progress()
    
    def _load_progress(self):
        """Load existing progress or create new."""
        if Path(self.progress_file).exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'indexed_companies': [],
            'failed_companies': {},
            'stats': {
                'total_companies': 0,
                'total_filings': 0,
                'total_chunks': 0,
                'start_time': datetime.utcnow().isoformat(),
                'last_updated': datetime.utcnow().isoformat()
            }
        }
    
    def save(self):
        """Save progress to disk."""
        self.data['stats']['last_updated'] = datetime.utcnow().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def is_indexed(self, ticker):
        """Check if company is already indexed."""
        return ticker in self.data['indexed_companies']
    
    def mark_indexed(self, ticker, stats):
        """Mark company as indexed."""
        self.data['indexed_companies'].append(ticker)
        self.data['stats']['total_filings'] += stats.get('indexed_filings', 0)
        self.data['stats']['total_chunks'] += stats.get('total_chunks', 0)
        self.save()
    
    def mark_failed(self, ticker, error):
        """Mark company as failed."""
        self.data['failed_companies'][ticker] = str(error)
        self.save()


def get_companies_to_index(session, limit=None, min_filings=5):
    """Get companies with SEC filings to index."""
    # Query companies with filing counts
    query = session.query(
        Company,
        func.count(SECFiling.id).label('filing_count')
    ).join(
        SECFiling
    ).group_by(
        Company.id
    ).having(
        func.count(SECFiling.id) >= min_filings
    ).order_by(
        func.count(SECFiling.id).desc()
    )
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def index_with_gpu(resume=False, company_limit=None, filing_types=None):
    """Main indexing function with GPU acceleration."""
    # Initialize components
    logger.info("Initializing RAG engine with GPU...")
    engine = RAGSearchEngine(model_type='general-fast')
    session = get_db_session()
    progress = IndexingProgress()
    
    # Get model info
    model_info = engine.get_stats()['embedding_model']
    logger.info(f"Using model: {model_info['model_name']}")
    logger.info(f"Device: {model_info['device']}")
    
    # Get companies to index
    companies = get_companies_to_index(session, limit=company_limit)
    total_companies = len(companies)
    logger.info(f"Found {total_companies} companies to index")
    
    # Update total in progress
    progress.data['stats']['total_companies'] = total_companies
    
    # Start indexing
    start_time = time.time()
    
    for idx, (company, filing_count) in enumerate(companies, 1):
        # Skip if already indexed (for resume)
        if resume and progress.is_indexed(company.ticker):
            logger.info(f"[{idx}/{total_companies}] Skipping {company.ticker} - already indexed")
            continue
        
        logger.info(f"\n[{idx}/{total_companies}] Indexing {company.ticker} ({company.name}) - {filing_count} filings")
        
        try:
            # Index company filings
            stats = engine.index_company_filings(
                company.id,
                filing_types=filing_types,
                limit=None  # Index all filings
            )
            
            # Update progress
            progress.mark_indexed(company.ticker, stats)
            
            # Log results
            logger.info(f"  ✓ Indexed {stats['indexed_filings']}/{filing_count} filings")
            logger.info(f"  ✓ Created {stats['total_chunks']} chunks")
            
            if stats['failed_filings']:
                logger.warning(f"  ⚠ Failed filings: {len(stats['failed_filings'])}")
            
            # Estimate remaining time
            elapsed = time.time() - start_time
            companies_done = idx - (len(progress.data['indexed_companies']) - 1 if resume else 0)
            if companies_done > 0:
                avg_time_per_company = elapsed / companies_done
                remaining_companies = total_companies - idx
                eta_seconds = avg_time_per_company * remaining_companies
                eta_hours = eta_seconds / 3600
                logger.info(f"  ⏱ ETA: {eta_hours:.1f} hours")
            
        except Exception as e:
            logger.error(f"  ✗ Failed to index {company.ticker}: {e}")
            progress.mark_failed(company.ticker, e)
            continue
        
        # Save index periodically (every 10 companies)
        if idx % 10 == 0:
            logger.info("Saving FAISS index...")
            engine.index.save_index()
    
    # Final save
    engine.index.save_index()
    
    # Summary statistics
    elapsed_total = time.time() - start_time
    logger.info("\n" + "="*60)
    logger.info("INDEXING COMPLETE")
    logger.info("="*60)
    logger.info(f"Total time: {elapsed_total/3600:.1f} hours")
    logger.info(f"Companies indexed: {len(progress.data['indexed_companies'])}")
    logger.info(f"Total filings: {progress.data['stats']['total_filings']}")
    logger.info(f"Total chunks: {progress.data['stats']['total_chunks']:,}")
    logger.info(f"Failed companies: {len(progress.data['failed_companies'])}")
    
    if progress.data['failed_companies']:
        logger.info("\nFailed companies:")
        for ticker, error in progress.data['failed_companies'].items():
            logger.info(f"  - {ticker}: {error}")
    
    # Get final index stats
    final_stats = engine.get_stats()
    logger.info(f"\nFinal index size: {final_stats['total_vectors']:,} vectors")
    
    # Cleanup
    engine.close()
    session.close()


def main():
    parser = argparse.ArgumentParser(description='GPU-accelerated SEC filing indexing')
    parser.add_argument('--resume', action='store_true', 
                       help='Resume from previous progress')
    parser.add_argument('--company-limit', type=int,
                       help='Limit number of companies to index')
    parser.add_argument('--filing-types', nargs='+',
                       default=['10-K', '10-Q', '8-K'],
                       help='Filing types to index')
    parser.add_argument('--test', action='store_true',
                       help='Test mode - index only 5 companies')
    
    args = parser.parse_args()
    
    if args.test:
        args.company_limit = 5
        logger.info("TEST MODE: Indexing only 5 companies")
    
    # Create logs directory
    Path('logs').mkdir(exist_ok=True)
    
    # Start indexing
    index_with_gpu(
        resume=args.resume,
        company_limit=args.company_limit,
        filing_types=args.filing_types
    )


if __name__ == '__main__':
    main()