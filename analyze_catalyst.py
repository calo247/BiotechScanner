#!/usr/bin/env python3
"""
Command-line interface for analyzing specific catalysts using the AI Research Agent.
"""
import argparse
import sys
from datetime import datetime, timedelta
from sqlalchemy import and_

from src.database.database import get_db_session
from src.database.models import Drug, Company
from src.ai_agent.catalyst_agent import CatalystResearchAgent


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
        
        # Print the report
        print(result["report"])
        
        # Report is automatically saved to database
        print(f"\n✓ Report saved to database (ID: {result['report_id']})")
        
        # Optionally save to file
        save = input("\nAlso save report to file? (y/n): ")
        if save.lower() == 'y':
            drug_info = result["analysis_data"]["drug_info"]
            filename = f"catalyst_report_{drug_info['ticker']}_{drug_info['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(filename, 'w') as f:
                f.write(result["report"])
            print(f"Report saved to {filename}")
    
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
    finally:
        agent.close()


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