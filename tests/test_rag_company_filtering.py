#!/usr/bin/env python3
"""
Simple test of company-specific filtering in FAISS search.
"""
import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Company

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_company():
    """Test searching within a single company's filings."""
    logger.info("Testing company-specific filtering...")
    
    engine = RAGSearchEngine()
    session = get_db_session()
    
    # Test with a well-known biotech company
    test_ticker = "MRNA"
    company = session.query(Company).filter_by(ticker=test_ticker).first()
    
    if not company:
        logger.error(f"Company {test_ticker} not found!")
        # Try another company
        company = session.query(Company).first()
        if company:
            logger.info(f"Using {company.ticker} instead")
        else:
            logger.error("No companies found in database!")
            return
    
    logger.info(f"\nTesting with {company.ticker} - {company.name}")
    logger.info(f"Company ID: {company.id}")
    
    # Test query
    query = "clinical trial results vaccine"
    
    # Search without filtering
    logger.info(f"\n1. General search for: '{query}'")
    general_results = engine.search(query, k=5)
    logger.info(f"   Found {len(general_results)} results across all companies")
    
    if general_results:
        # Check how many different companies in results
        companies_in_results = set()
        for r in general_results:
            companies_in_results.add(r.get('company_ticker', 'Unknown'))
        logger.info(f"   Results from {len(companies_in_results)} different companies: {companies_in_results}")
    
    # Search with company filter
    logger.info(f"\n2. Company-filtered search for: '{query}'")
    logger.info(f"   Filtering to company_id={company.id} ({company.ticker})")
    
    filtered_results = engine.search(
        query, 
        company_id=company.id,
        k=5
    )
    
    logger.info(f"   Found {len(filtered_results)} results for {company.ticker} only")
    
    # Verify filtering worked
    if filtered_results:
        logger.info("\n   Verifying all results are from the correct company:")
        for i, r in enumerate(filtered_results):
            result_ticker = r.get('company_ticker', 'Unknown')
            result_company_id = r.get('company_id', -1)
            
            if result_company_id != company.id:
                logger.error(f"   Result {i+1}: WRONG COMPANY! Expected {company.ticker} (ID:{company.id}), got {result_ticker} (ID:{result_company_id})")
            else:
                logger.info(f"   Result {i+1}: ✓ {result_ticker} - {r.get('filing_type')} ({r.get('filing_date')})")
                logger.info(f"            Score: {r.get('score', 999):.4f}")
                logger.info(f"            Preview: {r.get('text', '')[:80]}...")
    else:
        logger.info(f"   No results found for {company.ticker}")
        logger.info("   This could mean:")
        logger.info("   - This company's filings haven't been indexed yet")
        logger.info("   - The search terms don't match any content in their filings")
    
    # Compare filtering effectiveness
    logger.info(f"\n3. Filtering Summary:")
    logger.info(f"   General search: {len(general_results)} results")
    logger.info(f"   {company.ticker}-only: {len(filtered_results)} results")
    
    if general_results:
        effectiveness = (len(filtered_results) / len(general_results)) * 100
        logger.info(f"   Filter captured {effectiveness:.1f}% of general results")
    
    session.close()
    engine.close()
    logger.info("\nTest completed!")


if __name__ == '__main__':
    test_single_company()