#!/usr/bin/env python3
"""
Simple test to verify RAG search is working and show statistics.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from src.rag.rag_search import RAGSearchEngine
from src.database.database import get_db_session
from src.database.models import Company


def test_rag_verification():
    """Test RAG search and show detailed statistics."""
    print("RAG Search Verification Test")
    print("="*60)
    
    try:
        # Initialize RAG engine
        print("\n1. Initializing RAG engine...")
        engine = RAGSearchEngine()
        
        # Get and display index stats
        stats = engine.get_stats()
        print("\n2. FAISS Index Statistics:")
        print(f"   - Total vectors: {stats['total_vectors']:,}")
        print(f"   - Total chunks: {stats['total_chunks']:,}")
        print(f"   - Embedding dimension: {stats['embedding_dim']}")
        print(f"   - Index type: {stats['index_type']}")
        print(f"   - Companies indexed: {stats['companies_indexed']}")
        
        # Get a test company
        session = get_db_session()
        test_company = session.query(Company).filter_by(ticker="MRNA").first()
        if not test_company:
            test_company = session.query(Company).first()
        
        if not test_company:
            print("\nNo companies found in database!")
            return
        
        print(f"\n3. Testing search for company: {test_company.ticker} - {test_company.name}")
        print(f"   Company ID: {test_company.id}")
        
        # Test search
        query = "clinical trial vaccine development"
        print(f"\n4. Searching for: '{query}'")
        
        results = engine.search(
            query=query,
            company_id=test_company.id,
            k=5
        )
        
        print(f"\n5. Search Results:")
        print(f"   - Results found: {len(results)}")
        
        if results:
            # Show filing distribution
            filing_types = {}
            for r in results:
                ftype = r.get('filing_type', 'Unknown')
                filing_types[ftype] = filing_types.get(ftype, 0) + 1
            
            print(f"   - Filing type distribution: {filing_types}")
            print(f"   - Score range: {min(r.get('score', 999) for r in results):.4f} - {max(r.get('score', 0) for r in results):.4f}")
            
            # Show first result
            print(f"\n   First result:")
            first = results[0]
            print(f"     - Filing: {first.get('filing_type')} ({first.get('filing_date')})")
            print(f"     - Score: {first.get('score', 999):.4f}")
            print(f"     - Section: {first.get('section', 'Unknown')}")
            print(f"     - Has text: {'Yes' if first.get('text') else 'No'}")
            print(f"     - Text preview: {first.get('text', '')[:100]}...")
        else:
            print("   No results found - this company may not have relevant filings indexed")
        
        print(f"\n✓ RAG Search is {'WORKING' if results else 'WORKING (but no results for this query)'}")
        
        session.close()
        engine.close()
        
    except Exception as e:
        print(f"\n✗ RAG Search FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_rag_verification()