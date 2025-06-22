#!/usr/bin/env python3
"""
Example of using the RAG search pipeline for SEC documents.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Company


def main():
    # Initialize RAG search engine
    print("Initializing RAG search engine...")
    rag_engine = RAGSearchEngine(model_type='general-fast')
    
    # Get current stats
    stats = rag_engine.get_stats()
    print(f"\nCurrent index stats:")
    print(f"  Total vectors: {stats['total_vectors']:,}")
    print(f"  Companies indexed: {stats['companies_indexed']}")
    
    # Example 1: Search across all companies
    print("\n" + "="*60)
    print("Example 1: Search across all companies")
    print("="*60)
    
    query = "Phase 3 clinical trial primary endpoint met positive results"
    print(f"\nSearching for: '{query}'")
    
    results = rag_engine.search(query, k=3)
    
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"  Company: {result.get('company_ticker')} - {result.get('company_name')}")
        print(f"  Filing: {result.get('filing_type')} dated {result.get('filing_date')}")
        print(f"  Section: {result.get('section')}")
        print(f"  Relevance score: {result.get('score'):.4f}")
        print(f"  Excerpt: {result.get('text', '')[:200]}...")
    
    # Example 2: Search for specific company
    print("\n" + "="*60)
    print("Example 2: Search for specific company")
    print("="*60)
    
    # Get a company ID (replace with actual ticker)
    session = get_db_session()
    company = session.query(Company).filter_by(ticker='MRNA').first()
    
    if company:
        query = "mRNA vaccine safety efficacy"
        print(f"\nSearching {company.ticker} filings for: '{query}'")
        
        results = rag_engine.search(query, company_id=company.id, k=3)
        
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Filing: {result.get('filing_type')} dated {result.get('filing_date')}")
            print(f"  Section: {result.get('section')}")
            print(f"  Relevance score: {result.get('score'):.4f}")
            print(f"  Excerpt: {result.get('text', '')[:200]}...")
    
    # Example 3: Search specific filing types
    print("\n" + "="*60)
    print("Example 3: Search only 10-K filings")
    print("="*60)
    
    query = "cash runway burn rate financial position"
    print(f"\nSearching 10-K filings for: '{query}'")
    
    results = rag_engine.search(query, filing_types=['10-K'], k=3)
    
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"  Company: {result.get('company_ticker')}")
        print(f"  Filing date: {result.get('filing_date')}")
        print(f"  Section: {result.get('section')}")
        print(f"  Relevance score: {result.get('score'):.4f}")
        print(f"  Excerpt: {result.get('text', '')[:200]}...")
    
    # Example 4: Get expanded context
    if results:
        print("\n" + "="*60)
        print("Example 4: Get expanded context for a result")
        print("="*60)
        
        first_result = results[0]
        context = rag_engine.get_context_window(first_result, window_size=1000)
        
        print(f"\nExpanded context for first result:")
        print(f"  Length: {len(context)} characters")
        print(f"  Preview: {context[:500]}...")
    
    # Clean up
    session.close()
    rag_engine.close()
    print("\n\nDone!")


if __name__ == '__main__':
    main()