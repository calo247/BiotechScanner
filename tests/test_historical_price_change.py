#!/usr/bin/env python3
"""Test script to verify historical catalyst price changes are working."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.database import get_db_session
from src.database.models import HistoricalCatalyst, Company
from src.ai_agent.tools import CatalystAnalysisTools

def test_historical_catalyst(catalyst_id: int):
    """Test historical catalyst price change retrieval."""
    session = get_db_session()
    
    # Get the historical catalyst
    catalyst = session.query(HistoricalCatalyst).filter(
        HistoricalCatalyst.id == catalyst_id
    ).first()
    
    if not catalyst:
        print(f"Historical catalyst {catalyst_id} not found")
        return
    
    print(f"\n=== Historical Catalyst {catalyst_id} ===")
    print(f"Ticker: {catalyst.ticker}")
    print(f"Drug: {catalyst.drug_name}")
    print(f"Date: {catalyst.catalyst_date}")
    print(f"Outcome: {catalyst.catalyst_text}")
    print(f"3-Day Price Change: {catalyst.price_change_3d}%")
    
    # Test the tools module
    print("\n=== Testing CatalystAnalysisTools ===")
    tools = CatalystAnalysisTools()
    
    # Get historical catalysts for the stage
    print(f"\nGetting historical catalysts for stage: {catalyst.stage}")
    historical_data = tools.get_historical_catalysts(
        stage=catalyst.stage,
        indication=catalyst.drug_indication
    )
    
    print(f"Total events found: {historical_data['total_events']}")
    print(f"Note: {historical_data.get('note', '')}")
    
    # Check if our catalyst is in the results
    if historical_data['catalyst_details']:
        print(f"\nFirst few catalyst details:")
        for i, cat in enumerate(historical_data['catalyst_details'][:3]):
            print(f"\n{i+1}. {cat['date']} - {cat['company']} - {cat['drug']}")
            print(f"   Outcome: {cat['outcome'][:100]}...")
            print(f"   3-Day Price Change: {cat.get('price_change_3d', 'N/A')}")
    
    # Test company track record
    print(f"\n=== Testing Company Track Record ===")
    track_record = tools.get_company_track_record(
        company_id=catalyst.company_id,
        drug_name=catalyst.drug_name
    )
    
    print(f"Total company events: {track_record['total_events']}")
    if track_record['recent_catalysts']:
        print(f"\nCompany catalyst history:")
        for i, cat in enumerate(track_record['recent_catalysts'][:3]):
            print(f"\n{i+1}. {cat['date']} - {cat['drug']}")
            print(f"   Outcome: {cat['outcome'][:100]}...")
            print(f"   3-Day Price Change: {cat.get('price_change_3d', 'N/A')}")
    
    tools.close()
    session.close()

if __name__ == "__main__":
    # Test with catalyst 3025
    test_historical_catalyst(3025)