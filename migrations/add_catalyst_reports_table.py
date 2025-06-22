#!/usr/bin/env python3
"""
Add CatalystReport table to the database.

Run this script to update your existing database with the new table.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.database import engine
from src.database.models import CatalystReport

def main():
    """Create the catalyst_reports table."""
    print("Creating catalyst_reports table...")
    
    # Create only the new table
    CatalystReport.__table__.create(engine, checkfirst=True)
    
    print("✓ catalyst_reports table created successfully!")
    print("\nYou can now store AI-generated catalyst analysis reports.")

if __name__ == "__main__":
    main()