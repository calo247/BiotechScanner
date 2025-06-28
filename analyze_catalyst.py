#!/usr/bin/env python3
"""
Command-line interface for analyzing specific catalysts using the AI Research Agent.
"""
import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import and_
import logging

from src.database.database import get_db_session
from src.database.models import Drug, Company
from src.ai_agent.catalyst_agent import CatalystResearchAgent


def setup_logging():
    """Set up logging to both console and file."""
    # Store all output in a list to save later
    class LogCapture:
        def __init__(self):
            self.terminal = sys.stdout
            self.log_content = []
            
        def write(self, message):
            self.terminal.write(message)
            self.terminal.flush()
            if message.strip():  # Store non-empty lines
                self.log_content.append(message.rstrip())
            
        def flush(self):
            self.terminal.flush()
            
        def get_content(self):
            return '\n'.join(self.log_content)
    
    # Replace stdout with our capture object
    log_capture = LogCapture()
    sys.stdout = log_capture
    
    return log_capture


def list_upcoming_catalysts(days: int = 30):
    """List upcoming catalysts to choose from."""
    session = get_db_session()
    
    cutoff_date = datetime.utcnow() + timedelta(days=days)
    today = datetime.utcnow()
    
    drugs = session.query(Drug).join(Company).filter(
        and_(
            Drug.has_catalyst == True,
            Drug.catalyst_date >= today,
            Drug.catalyst_date <= cutoff_date
        )
    ).order_by(Drug.catalyst_date).limit(20).all()
    
    print(f"\nUpcoming Catalysts (Next {days} days):\n")
    print(f"{'ID':<6} {'Date':<12} {'Ticker':<8} {'Company':<30} {'Drug':<30} {'Stage':<15}")
    print("-" * 120)
    
    for drug in drugs:
        date_str = drug.catalyst_date.strftime('%Y-%m-%d') if drug.catalyst_date else 'Unknown'
        company_name = drug.company.name[:28] + '..' if len(drug.company.name) > 30 else drug.company.name
        drug_name = drug.drug_name[:28] + '..' if len(drug.drug_name) > 30 else drug.drug_name
        stage = drug.stage[:13] + '..' if len(drug.stage) > 15 else drug.stage
        
        print(f"{drug.id:<6} {date_str:<12} {drug.company.ticker:<8} {company_name:<30} {drug_name:<30} {stage:<15}")
    
    session.close()
    return len(drugs) > 0


def analyze_by_id(drug_id: int):
    """Analyze a specific catalyst by drug ID."""
    # Set up logging
    log_capture = setup_logging()
    
    try:
        agent = CatalystResearchAgent()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print(f"\nAnalyzing catalyst ID {drug_id}...\n")
    
    try:
        result = agent.analyze_catalyst(drug_id)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        # Print RAG search statistics (for terminal/log only, not in the report)
        if "sec_search_stats" in result["analysis_data"]:
            stats = result["analysis_data"]["sec_search_stats"]
            print("\n" + "="*60)
            print("📈 RESEARCH STATISTICS (INTERNAL - NOT IN REPORT)")
            print("="*60)
            
            # Check if it was LLM-driven
            if stats.get('llm_driven', False):
                print(f"✓ Search Method: {stats['search_method']}")
                print(f"✓ Total Searches Performed: {stats['total_searches']}")
                print(f"✓ Total Results Found: {stats['total_results']}")
                print(f"✓ Unique SEC Filings Accessed: {stats.get('unique_filings_count', 0)}")
                print(f"✓ Press Releases Found: {stats.get('press_releases_found', 0)}")
                
                # Show search iterations
                if 'search_iterations' in stats:
                    print("\n📋 Detailed Search Log:")
                    for search in stats['search_iterations']:
                        source_type = "PRESS RELEASES" if search.get('search_type') == 'press_release' else "SEC FILINGS"
                        print(f"\n  🔍 Search {search['iteration']} ({source_type}):")
                        print(f"     Query: '{search['query']}'")
                        print(f"     Reasoning: {search['reasoning']}")
                        print(f"     Results Found: {search['results_found']}")
                        if search.get('key_findings'):
                            print(f"     AI Findings Summary:")
                            # Indent the findings for better readability
                            for line in search['key_findings'].split('\n'):
                                if line.strip():
                                    print(f"       {line.strip()}")
            else:
                # Fallback to old format
                print(f"✓ RAG Search Used: {stats.get('rag_search_used', True)}")
                print(f"✓ Total Index Chunks: {stats.get('total_index_chunks', 'N/A'):,}")
                print(f"✓ Query: '{stats.get('query', 'N/A')}'")
                print(f"✓ Results Found: {stats.get('results_found', 0)}")
                print(f"✓ Unique SEC Filings Matched: {stats.get('unique_filings_matched', 0)}")
            
            print("="*60)
            print("\n📊 CATALYST ANALYSIS REPORT")
            print("="*60)
            print()
        
        # Print the report
        print(result["report"])
        
        # Report is automatically saved to database
        print(f"\n✓ Report saved to database (ID: {result['report_id']})")
        
        # Automatically save report to structured folder
        drug_info = result["analysis_data"]["drug_info"]
        
        # Get company ID from the drug query
        session = get_db_session()
        drug = session.query(Drug).filter_by(id=drug_id).first()
        company_id = drug.company_id if drug else "unknown"
        session.close()
        
        # Create folder structure: data/ai_reports/{ticker}_{company_id}/{catalyst_id}/{datetime}
        ticker = drug_info['ticker']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = Path(f"data/ai_reports/{ticker}_{company_id}/{drug_id}")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # Save report with timestamp
        report_file = report_dir / f"{timestamp}_report.md"
        with open(report_file, 'w') as f:
            f.write(result["report"])
        
        # Also save the analysis data as JSON for reference
        import json
        data_file = report_dir / f"{timestamp}_analysis_data.json"
        with open(data_file, 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            analysis_data_json = result["analysis_data"].copy()
            if "drug_info" in analysis_data_json and "catalyst_date" in analysis_data_json["drug_info"]:
                if analysis_data_json["drug_info"]["catalyst_date"]:
                    analysis_data_json["drug_info"]["catalyst_date"] = str(analysis_data_json["drug_info"]["catalyst_date"])
            json.dump(analysis_data_json, f, indent=2, default=str)
        
        # Save the terminal log
        log_file = report_dir / f"{timestamp}_terminal_log.txt"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(log_capture.get_content())
        
        print(f"\n✓ Report automatically saved to: {report_file}")
        print(f"✓ Analysis data saved to: {data_file}")
        print(f"✓ Terminal log saved to: {log_file}")
    
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
    finally:
        agent.close()
        # Restore stdout
        if hasattr(sys.stdout, 'terminal'):
            sys.stdout = sys.stdout.terminal


def analyze_by_ticker(ticker: str):
    """Analyze catalysts for a specific company."""
    session = get_db_session()
    
    # Find company
    company = session.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        print(f"Company with ticker {ticker} not found.")
        session.close()
        return
    
    # Find upcoming catalysts
    today = datetime.utcnow()
    drugs = session.query(Drug).filter(
        and_(
            Drug.company_id == company.id,
            Drug.has_catalyst == True,
            Drug.catalyst_date >= today
        )
    ).order_by(Drug.catalyst_date).all()
    
    if not drugs:
        print(f"No upcoming catalysts found for {ticker}")
        session.close()
        return
    
    print(f"\nUpcoming catalysts for {company.name} ({ticker}):\n")
    for i, drug in enumerate(drugs):
        date_str = drug.catalyst_date.strftime('%Y-%m-%d') if drug.catalyst_date else 'Unknown'
        print(f"{i+1}. {drug.drug_name} - {drug.stage} - {date_str}")
    
    if len(drugs) == 1:
        choice = 1
    else:
        choice = input(f"\nSelect catalyst to analyze (1-{len(drugs)}): ")
        try:
            choice = int(choice)
        except:
            print("Invalid choice")
            session.close()
            return
    
    if 1 <= choice <= len(drugs):
        drug_id = drugs[choice-1].id
        session.close()
        analyze_by_id(drug_id)
    else:
        print("Invalid choice")
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Analyze biotech catalysts using AI Research Agent')
    parser.add_argument('--list', action='store_true', help='List upcoming catalysts')
    parser.add_argument('--days', type=int, default=30, help='Days ahead to look for catalysts (default: 30)')
    parser.add_argument('--id', type=int, help='Analyze specific catalyst by ID')
    parser.add_argument('--ticker', type=str, help='Analyze catalysts for specific ticker')
    
    args = parser.parse_args()
    
    if args.list:
        has_catalysts = list_upcoming_catalysts(args.days)
        if has_catalysts:
            print("\nUse --id <ID> to analyze a specific catalyst")
    elif args.id:
        analyze_by_id(args.id)
    elif args.ticker:
        analyze_by_ticker(args.ticker)
    else:
        # Interactive mode
        print("Biotech Catalyst Analyzer")
        print("=" * 50)
        
        has_catalysts = list_upcoming_catalysts(args.days)
        if has_catalysts:
            choice = input("\nEnter catalyst ID to analyze (or 'q' to quit): ")
            if choice.lower() != 'q':
                try:
                    drug_id = int(choice)
                    analyze_by_id(drug_id)
                except ValueError:
                    print("Invalid ID")


if __name__ == "__main__":
    main()