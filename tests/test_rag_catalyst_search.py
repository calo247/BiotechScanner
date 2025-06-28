#!/usr/bin/env python3
"""
Test catalyst-specific searches in the FAISS index.
"""
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Drug, Company

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_upcoming_catalysts(session, limit=5):
    """Get some upcoming catalysts from the database for targeted searches."""
    catalysts = session.query(Drug, Company).join(Company).filter(
        Drug.has_catalyst == True,
        Drug.catalyst_date >= datetime.utcnow()
    ).order_by(Drug.catalyst_date).limit(limit).all()
    
    return [(drug, company) for drug, company in catalysts]


def run_catalyst_searches():
    """Run various catalyst-specific searches."""
    logger.info("Initializing search engine...")
    engine = RAGSearchEngine()
    session = get_db_session()
    
    # Get some upcoming catalysts for context
    logger.info("\nFetching upcoming catalysts for targeted searches...")
    upcoming = get_upcoming_catalysts(session, limit=3)
    
    for drug, company in upcoming:
        logger.info(f"\nUpcoming catalyst: {company.ticker}")
        logger.info(f"  Drug: {drug.drug_name}")
        logger.info(f"  Stage: {drug.stage}")
        logger.info(f"  Date: {drug.catalyst_date}")
        logger.info(f"  Indication: {drug.indications_text}")
    
    # Test search categories
    test_categories = {
        "Clinical Trial Endpoints": [
            "primary endpoint overall survival",
            "progression free survival PFS endpoint",
            "objective response rate ORR",
            "complete response partial response",
            "time to progression TTP"
        ],
        
        "Regulatory Milestones": [
            "FDA approval PDUFA date action",
            "NDA submission new drug application",
            "BLA biologics license application",
            "breakthrough therapy designation",
            "fast track designation FDA"
        ],
        
        "Safety and Efficacy": [
            "serious adverse events SAE",
            "dose limiting toxicity DLT", 
            "maximum tolerated dose MTD",
            "treatment emergent adverse events TEAE",
            "safety run-in cohort"
        ],
        
        "Financial and Commercial": [
            "peak sales potential market opportunity",
            "cash runway burn rate quarters",
            "milestone payment royalty",
            "commercialization strategy launch",
            "market size addressable TAM"
        ],
        
        "Specific Disease Areas": [
            "metastatic castration resistant prostate cancer mCRPC",
            "non small cell lung cancer NSCLC",
            "acute myeloid leukemia AML",
            "diffuse large B cell lymphoma DLBCL",
            "solid tumors dose escalation"
        ],
        
        "Company-Specific Searches": []
    }
    
    # Add company-specific searches for the upcoming catalysts
    for drug, company in upcoming[:2]:  # Just use first 2
        drug_name_parts = drug.drug_name.split()[0] if drug.drug_name else ""
        test_categories["Company-Specific Searches"].extend([
            f"{company.ticker} {drug.stage}",
            f"{company.ticker} clinical trial results",
            f"{drug_name_parts} efficacy safety" if drug_name_parts else None
        ])
    
    # Remove None values
    test_categories["Company-Specific Searches"] = [
        q for q in test_categories["Company-Specific Searches"] if q
    ]
    
    # Run searches
    all_results = {}
    
    for category, queries in test_categories.items():
        if not queries:
            continue
            
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {category}")
        logger.info(f"{'='*60}")
        
        category_results = []
        
        for query in queries:
            logger.info(f"\nSearching: '{query}'")
            
            try:
                results = engine.search(query, k=3)
                
                if not results:
                    logger.warning("  No results found")
                    continue
                
                for i, result in enumerate(results):
                    score = result.get('score', 999)
                    company = result.get('company_ticker', 'N/A')
                    filing_type = result.get('filing_type', 'N/A')
                    filing_date = result.get('filing_date', 'N/A')
                    text_preview = result.get('text', '')[:150]
                    
                    if i == 0:  # Just show top result details
                        logger.info(f"  Top result:")
                        logger.info(f"    Score: {score:.4f}")
                        logger.info(f"    Company: {company}")
                        logger.info(f"    Filing: {filing_type} ({filing_date})")
                        logger.info(f"    Text: {text_preview}...")
                    
                    category_results.append({
                        'query': query,
                        'score': score,
                        'company': company,
                        'filing_type': filing_type
                    })
                    
            except Exception as e:
                logger.error(f"  Error: {e}")
        
        all_results[category] = category_results
    
    # Analyze results
    logger.info(f"\n{'='*60}")
    logger.info("SEARCH QUALITY ANALYSIS")
    logger.info(f"{'='*60}")
    
    for category, results in all_results.items():
        if not results:
            continue
            
        scores = [r['score'] for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        logger.info(f"\n{category}:")
        logger.info(f"  Total searches: {len(set(r['query'] for r in results))}")
        logger.info(f"  Results found: {len(results)}")
        logger.info(f"  Average score: {avg_score:.4f}")
        logger.info(f"  Best score: {min(scores):.4f}" if scores else "  No results")
        logger.info(f"  Worst score: {max(scores):.4f}" if scores else "  No results")
    
    # Test filtering by company
    if upcoming:
        logger.info(f"\n{'='*60}")
        logger.info("Testing Company-Specific Filtering")
        logger.info(f"{'='*60}")
        
        test_company = upcoming[0][1]
        logger.info(f"\nSearching for 'clinical trial' filtered to {test_company.ticker}")
        
        filtered_results = engine.search(
            "clinical trial primary endpoint", 
            company_id=test_company.id,
            k=3
        )
        
        if filtered_results:
            logger.info(f"Found {len(filtered_results)} results for {test_company.ticker}")
            for r in filtered_results:
                logger.info(f"  - {r.get('filing_type')} ({r.get('filing_date')})")
        else:
            logger.info(f"No results found for {test_company.ticker}")
    
    session.close()
    engine.close()


if __name__ == '__main__':
    run_catalyst_searches()