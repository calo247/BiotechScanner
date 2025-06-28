#!/usr/bin/env python3
"""
Simple test script for press release searches.
Tests different search scenarios and shows what types of results we get.
"""
import sys
from src.database.database import get_db_session
from src.database.models import Company
from src.ai_agent.tools import CatalystAnalysisTools


def test_press_release_search(ticker: str, search_terms: list):
    """Test press release search for a specific company and terms."""
    session = get_db_session()
    company = session.query(Company).filter(Company.ticker == ticker.upper()).first()
    
    if not company:
        print(f"❌ Company {ticker} not found")
        session.close()
        return
    
    print(f"\n{'='*60}")
    print(f"🔍 Searching: {company.name} ({ticker})")
    print(f"📝 Terms: {', '.join(search_terms)}")
    print(f"{'='*60}")
    
    tools = CatalystAnalysisTools()
    
    try:
        results = tools.search_company_press_releases(
            company_name=company.name,
            ticker=company.ticker,
            search_terms=search_terms,
            days_back=90
        )
        
        print(f"\n✅ Found {len(results)} results\n")
        
        # Group results by domain
        domains = {}
        for result in results:
            url = result['url']
            domain = url.split('/')[2] if '/' in url else url
            domains[domain] = domains.get(domain, 0) + 1
        
        print("📊 Results by source:")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {domain}: {count}")
        
        print(f"\n📄 Top 5 results:")
        for i, result in enumerate(results[:5]):
            print(f"\n{i+1}. {result['title']}")
            print(f"   URL: {result['url']}")
            print(f"   Date: {result.get('date', 'Unknown')}")
            print(f"   Relevance: {result['relevance']}")
            if result.get('snippet'):
                print(f"   Preview: {result['snippet'][:150]}...")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    tools.close()
    session.close()


def main():
    """Run various test scenarios."""
    
    # Test scenarios
    test_cases = [
        # Recent catalyst results
        ("SGEN", ["PADCEV", "results", "bladder cancer"]),
        ("MRNA", ["vaccine", "efficacy", "data"]),
        ("BIIB", ["Alzheimer", "Leqembi", "approval"]),
        
        # FDA/regulatory news
        ("VRTX", ["FDA", "approval", "PDUFA"]),
        ("REGN", ["FDA", "clearance", "IND"]),
        
        # Partnership/business news  
        ("GILD", ["partnership", "collaboration", "agreement"]),
        ("ALNY", ["licensing", "deal", "milestone"]),
        
        # Earnings/financial
        ("AMGN", ["earnings", "revenue", "guidance"]),
        ("BMRN", ["financial", "results", "quarter"]),
        
        # Clinical trial updates
        ("INCY", ["Phase 3", "topline", "primary endpoint"]),
        ("EXEL", ["clinical", "trial", "enrollment"])
    ]
    
    # Allow testing specific case from command line
    if len(sys.argv) > 1:
        ticker = sys.argv[1]
        terms = sys.argv[2:] if len(sys.argv) > 2 else ["news", "update"]
        test_cases = [(ticker, terms)]
    
    for ticker, search_terms in test_cases:
        test_press_release_search(ticker, search_terms)
        print("\n" + "-"*60 + "\n")  # Just print separator instead


if __name__ == "__main__":
    main()