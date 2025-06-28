#!/usr/bin/env python3
"""
Example of company-specific filtering in RAG search.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Company


def main():
    """Demonstrate company-specific search filtering."""
    engine = RAGSearchEngine()
    session = get_db_session()
    
    print("Company-Specific RAG Search Examples")
    print("="*50)
    
    # Example 1: Using company_id directly
    print("\n1. Search using company_id:")
    company = session.query(Company).filter_by(ticker="MRNA").first()
    if company:
        results = engine.search(
            "mRNA vaccine clinical trial", 
            company_id=company.id,
            k=3
        )
        print(f"   Found {len(results)} results for {company.ticker}")
    
    # Example 2: Using the new search_by_ticker method
    print("\n2. Search using ticker (convenience method):")
    results = engine.search_by_ticker(
        "Phase 3 primary endpoint", 
        ticker="MRNA",
        k=3
    )
    print(f"   Found {len(results)} results for MRNA")
    
    # Example 3: Filter by both company and filing type
    print("\n3. Search with company + filing type filters:")
    results = engine.search_by_ticker(
        "financial results revenue", 
        ticker="MRNA",
        filing_types=["10-K", "10-Q"],
        k=3
    )
    print(f"   Found {len(results)} results in 10-K/10-Q filings")
    
    # Example 4: Compare results across companies
    print("\n4. Compare search results across companies:")
    query = "vaccine efficacy safety"
    tickers = ["MRNA", "BNTX", "NVAX"]
    
    for ticker in tickers:
        results = engine.search_by_ticker(query, ticker, k=2)
        print(f"\n   {ticker}: {len(results)} results")
        if results:
            print(f"   Best score: {results[0].get('score', 999):.4f}")
            print(f"   Filing types: {[r.get('filing_type') for r in results]}")
    
    # Example 5: Search non-existent company
    print("\n5. Handling non-existent ticker:")
    results = engine.search_by_ticker("test query", "FAKE", k=5)
    print(f"   Results for 'FAKE': {len(results)} (should be 0)")
    
    engine.close()
    session.close()
    print("\nDone!")


if __name__ == "__main__":
    main()