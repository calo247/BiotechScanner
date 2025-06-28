"""
Convenience methods for ticker-based RAG search.
"""
from typing import List, Dict, Optional
from src.database.models import Company


def search_by_ticker(engine, session, query: str, ticker: str, 
                    k: int = 10, filing_types: Optional[List[str]] = None) -> List[Dict]:
    """
    Search within a specific company's filings using ticker symbol.
    
    Args:
        engine: RAGSearchEngine instance
        session: Database session
        query: Search query
        ticker: Company ticker symbol (e.g., 'MRNA')
        k: Number of results to return
        filing_types: Optional list of filing types to filter (e.g., ['10-K', '10-Q'])
    
    Returns:
        List of search results
    
    Example:
        results = search_by_ticker(engine, session, "vaccine clinical trial", "MRNA", k=5)
    """
    # Look up company by ticker
    company = session.query(Company).filter_by(ticker=ticker.upper()).first()
    
    if not company:
        print(f"Warning: Company '{ticker}' not found in database")
        return []
    
    # Use the engine's search with company_id filter
    return engine.search(
        query=query,
        company_id=company.id,
        k=k,
        filing_types=filing_types
    )


def search_multiple_tickers(engine, session, query: str, tickers: List[str], 
                           k_per_company: int = 5) -> Dict[str, List[Dict]]:
    """
    Search across multiple companies, returning results grouped by ticker.
    
    Args:
        engine: RAGSearchEngine instance
        session: Database session
        query: Search query
        tickers: List of ticker symbols
        k_per_company: Results per company
    
    Returns:
        Dictionary mapping ticker -> list of results
    
    Example:
        results = search_multiple_tickers(
            engine, session, 
            "Phase 3 results", 
            ["MRNA", "BNTX", "NVAX"], 
            k_per_company=3
        )
    """
    results_by_ticker = {}
    
    for ticker in tickers:
        results = search_by_ticker(engine, session, query, ticker, k=k_per_company)
        results_by_ticker[ticker] = results
    
    return results_by_ticker


def compare_company_searches(engine, session, query: str, tickers: List[str], 
                            k: int = 5) -> None:
    """
    Print a comparison of search results across multiple companies.
    
    Example:
        compare_company_searches(
            engine, session,
            "clinical trial primary endpoint",
            ["MRNA", "BNTX", "PFE"]
        )
    """
    print(f"\nQuery: '{query}'")
    print("="*60)
    
    for ticker in tickers:
        results = search_by_ticker(engine, session, query, ticker, k=k)
        
        print(f"\n{ticker}:")
        print(f"  Found {len(results)} results")
        
        if results:
            # Get score range
            scores = [r.get('score', 999) for r in results]
            print(f"  Score range: {min(scores):.4f} - {max(scores):.4f}")
            
            # Show filing types
            filing_types = {}
            for r in results:
                ftype = r.get('filing_type', 'Unknown')
                filing_types[ftype] = filing_types.get(ftype, 0) + 1
            print(f"  Filing types: {filing_types}")
            
            # Show top result
            top = results[0]
            print(f"  Top result: {top.get('filing_type')} ({top.get('filing_date')})")
            print(f"  Preview: {top.get('text', '')[:100]}...")
        else:
            print("  No results found (company may not be indexed)")


# Usage example:
if __name__ == "__main__":
    from src.rag.rag_search import RAGSearchEngine
    from src.database.database import get_db_session
    
    # Initialize
    engine = RAGSearchEngine()
    session = get_db_session()
    
    # Example 1: Search single company
    print("Example 1: Single company search")
    results = search_by_ticker(engine, session, "vaccine development", "MRNA", k=3)
    print(f"Found {len(results)} results for MRNA")
    
    # Example 2: Compare multiple companies
    print("\nExample 2: Compare multiple companies")
    compare_company_searches(
        engine, session,
        "Phase 3 clinical trial", 
        ["MRNA", "BNTX", "NVAX"],
        k=3
    )
    
    # Cleanup
    engine.close()
    session.close()