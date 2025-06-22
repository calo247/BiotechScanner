#!/usr/bin/env python3
"""
Index SEC filings into FAISS for RAG search.
"""
import argparse
import logging
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Company, SECFiling
from sqlalchemy import func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def index_all_companies(engine: RAGSearchEngine, 
                       filing_types: list = None,
                       limit_per_company: int = None,
                       company_limit: int = None):
    """Index filings for all companies."""
    session = get_db_session()
    
    # Get companies with filings
    query = session.query(Company).join(SECFiling).distinct()
    
    if company_limit:
        query = query.limit(company_limit)
    
    companies = query.all()
    logger.info(f"Found {len(companies)} companies with filings")
    
    total_stats = {
        'companies_processed': 0,
        'total_filings': 0,
        'total_chunks': 0,
        'failed_companies': []
    }
    
    for company in companies:
        logger.info(f"\nProcessing {company.ticker} ({company.name})")
        
        try:
            stats = engine.index_company_filings(
                company.id,
                filing_types=filing_types,
                limit=limit_per_company
            )
            
            total_stats['companies_processed'] += 1
            total_stats['total_filings'] += stats['indexed_filings']
            total_stats['total_chunks'] += stats['total_chunks']
            
            logger.info(f"  Indexed {stats['indexed_filings']}/{stats['total_filings']} filings, "
                       f"{stats['total_chunks']} chunks")
            
            if stats['failed_filings']:
                logger.warning(f"  Failed filings: {stats['failed_filings']}")
                
        except Exception as e:
            logger.error(f"Error processing {company.ticker}: {e}")
            total_stats['failed_companies'].append(company.ticker)
    
    session.close()
    return total_stats


def index_single_company(engine: RAGSearchEngine, ticker: str,
                        filing_types: list = None,
                        limit: int = None):
    """Index filings for a single company."""
    session = get_db_session()
    
    company = session.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        logger.error(f"Company {ticker} not found")
        return None
    
    stats = engine.index_company_filings(
        company.id,
        filing_types=filing_types,
        limit=limit
    )
    
    session.close()
    return stats


def test_search(engine: RAGSearchEngine):
    """Run some test searches."""
    test_queries = [
        "Phase 3 clinical trial results",
        "cash runway burn rate",
        "FDA approval PDUFA date",
        "adverse events safety",
        "revenue drug sales milestone payments"
    ]
    
    logger.info("\nRunning test searches...")
    
    for query in test_queries:
        logger.info(f"\nQuery: {query}")
        results = engine.search(query, k=3)
        
        for i, result in enumerate(results):
            logger.info(f"\n  Result {i+1}:")
            logger.info(f"    Company: {result.get('company_ticker', 'N/A')}")
            logger.info(f"    Filing: {result.get('filing_type', 'N/A')} - {result.get('filing_date', 'N/A')}")
            logger.info(f"    Section: {result.get('section', 'N/A')}")
            logger.info(f"    Score: {result.get('score', 'N/A'):.4f}")
            logger.info(f"    Text: {result.get('text', '')[:200]}...")


def main():
    parser = argparse.ArgumentParser(description='Index SEC filings for RAG search')
    parser.add_argument('--ticker', type=str, help='Index specific company by ticker')
    parser.add_argument('--all', action='store_true', help='Index all companies')
    parser.add_argument('--filing-types', nargs='+', 
                       default=['10-K', '10-Q', '8-K'],
                       help='Filing types to index')
    parser.add_argument('--limit-per-company', type=int, 
                       help='Maximum filings per company')
    parser.add_argument('--company-limit', type=int,
                       help='Maximum number of companies to process')
    parser.add_argument('--model', type=str, default='general-fast',
                       choices=['general-fast', 'general-best', 'biomedical', 'retrieval-optimized'],
                       help='Embedding model to use')
    parser.add_argument('--hybrid', action='store_true',
                       help='Use hybrid embedder for mixed content')
    parser.add_argument('--test', action='store_true',
                       help='Run test searches after indexing')
    parser.add_argument('--stats', action='store_true',
                       help='Show index statistics')
    
    args = parser.parse_args()
    
    # Initialize RAG engine
    logger.info(f"Initializing RAG engine with model: {args.model}")
    engine = RAGSearchEngine(
        model_type=args.model,
        use_hybrid=args.hybrid
    )
    
    # Show current stats
    if args.stats or not (args.ticker or args.all):
        stats = engine.get_stats()
        logger.info("\nCurrent index statistics:")
        logger.info(f"  Total vectors: {stats['total_vectors']:,}")
        logger.info(f"  Total chunks: {stats['total_chunks']:,}")
        logger.info(f"  Companies indexed: {stats['companies_indexed']}")
        logger.info(f"  Filing types: {stats.get('filing_types', {})}")
        
        if not (args.ticker or args.all):
            logger.info("\nUse --ticker SYMBOL or --all to index filings")
            return
    
    # Perform indexing
    if args.ticker:
        logger.info(f"\nIndexing filings for {args.ticker}")
        stats = index_single_company(
            engine,
            args.ticker,
            filing_types=args.filing_types,
            limit=args.limit_per_company
        )
        
        if stats:
            logger.info(f"\nIndexing complete:")
            logger.info(f"  Filings indexed: {stats['indexed_filings']}")
            logger.info(f"  Total chunks: {stats['total_chunks']}")
            
    elif args.all:
        logger.info("\nIndexing all companies...")
        stats = index_all_companies(
            engine,
            filing_types=args.filing_types,
            limit_per_company=args.limit_per_company,
            company_limit=args.company_limit
        )
        
        logger.info(f"\nIndexing complete:")
        logger.info(f"  Companies processed: {stats['companies_processed']}")
        logger.info(f"  Total filings: {stats['total_filings']}")
        logger.info(f"  Total chunks: {stats['total_chunks']}")
        
        if stats['failed_companies']:
            logger.warning(f"  Failed companies: {stats['failed_companies']}")
    
    # Run test searches
    if args.test:
        test_search(engine)
    
    # Clean up
    engine.close()
    logger.info("\nDone!")


if __name__ == '__main__':
    main()