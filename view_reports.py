#!/usr/bin/env python3
"""
View saved catalyst analysis reports from the database.
"""
import argparse
from datetime import datetime, timedelta
from sqlalchemy import desc, and_

from src.database.database import get_db_session
from src.database.models import CatalystReport, Drug, Company


def list_reports(days: int = 7):
    """List recent catalyst reports."""
    session = get_db_session()
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    reports = session.query(CatalystReport).join(Drug).join(Company).filter(
        CatalystReport.created_at >= cutoff_date
    ).order_by(desc(CatalystReport.created_at)).all()
    
    if not reports:
        print(f"No reports found in the last {days} days.")
        session.close()
        return
    
    print(f"\nCatalyst Reports (Last {days} days):\n")
    print(f"{'ID':<6} {'Created':<20} {'Ticker':<8} {'Drug':<30} {'Recommendation':<20} {'Success %':<10}")
    print("-" * 105)
    
    for report in reports:
        created = report.created_at.strftime('%Y-%m-%d %H:%M') if report.created_at else 'Unknown'
        drug_name = report.drug.drug_name[:28] + '..' if len(report.drug.drug_name) > 30 else report.drug.drug_name
        rec = report.recommendation[:18] + '..' if report.recommendation and len(report.recommendation) > 20 else report.recommendation or 'N/A'
        success = f"{report.success_probability*100:.0f}%" if report.success_probability else 'N/A'
        
        print(f"{report.id:<6} {created:<20} {report.company.ticker:<8} {drug_name:<30} {rec:<20} {success:<10}")
    
    session.close()


def view_report(report_id: int):
    """View a specific report."""
    session = get_db_session()
    
    report = session.query(CatalystReport).filter(CatalystReport.id == report_id).first()
    
    if not report:
        print(f"Report with ID {report_id} not found.")
        session.close()
        return
    
    print("\n" + "="*80)
    print(f"Report ID: {report.id}")
    print(f"Created: {report.created_at}")
    print(f"Model: {report.model_used}")
    print(f"Generation time: {report.generation_time_ms}ms")
    print("="*80 + "\n")
    
    print(report.report_markdown)
    
    print("\n" + "="*80)
    print("EXTRACTED METRICS:")
    print(f"Success Probability: {report.success_probability*100:.1f}%" if report.success_probability else "Success Probability: N/A")
    print(f"Recommendation: {report.recommendation}" if report.recommendation else "Recommendation: N/A")
    print(f"Upside Target: {report.price_target_upside}" if report.price_target_upside else "Upside Target: N/A")
    print(f"Downside Risk: {report.price_target_downside}" if report.price_target_downside else "Downside Risk: N/A")
    print(f"Risk Level: {report.risk_level}" if report.risk_level else "Risk Level: N/A")
    print("="*80)
    
    session.close()


def search_reports(ticker: str = None, drug_name: str = None):
    """Search for reports by ticker or drug name."""
    session = get_db_session()
    
    query = session.query(CatalystReport).join(Drug).join(Company)
    
    if ticker:
        query = query.filter(Company.ticker == ticker.upper())
    
    if drug_name:
        query = query.filter(Drug.drug_name.ilike(f'%{drug_name}%'))
    
    reports = query.order_by(desc(CatalystReport.created_at)).all()
    
    if not reports:
        print("No reports found matching your criteria.")
        session.close()
        return
    
    print(f"\nFound {len(reports)} report(s):\n")
    print(f"{'ID':<6} {'Created':<20} {'Ticker':<8} {'Drug':<40}")
    print("-" * 80)
    
    for report in reports:
        created = report.created_at.strftime('%Y-%m-%d %H:%M') if report.created_at else 'Unknown'
        drug_name_display = report.drug.drug_name[:38] + '..' if len(report.drug.drug_name) > 40 else report.drug.drug_name
        
        print(f"{report.id:<6} {created:<20} {report.company.ticker:<8} {drug_name_display:<40}")
    
    session.close()


def main():
    parser = argparse.ArgumentParser(description='View saved catalyst analysis reports')
    parser.add_argument('--list', action='store_true', help='List recent reports')
    parser.add_argument('--days', type=int, default=7, help='Days to look back for reports (default: 7)')
    parser.add_argument('--id', type=int, help='View specific report by ID')
    parser.add_argument('--ticker', type=str, help='Search reports by ticker')
    parser.add_argument('--drug', type=str, help='Search reports by drug name')
    
    args = parser.parse_args()
    
    if args.list:
        list_reports(args.days)
    elif args.id:
        view_report(args.id)
    elif args.ticker or args.drug:
        search_reports(ticker=args.ticker, drug_name=args.drug)
    else:
        # Default to listing recent reports
        list_reports(args.days)


if __name__ == "__main__":
    main()