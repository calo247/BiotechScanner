"""Test script to verify database setup."""

from datetime import datetime
from src.database.database import init_db, get_db
from src.database.models import Company, Drug

def test_database():
    """Test basic database operations."""
    print("Initializing database...")
    init_db()
    
    print("\nTesting database operations...")
    
    with get_db() as db:
        # Create a test company
        test_company = Company(
            ticker="TEST",
            name="Test Biotech Company",
            sector="Biotechnology"
        )
        db.add(test_company)
        db.commit()
        
        print(f"Created company: {test_company}")
        
        # Create a test drug
        test_drug = Drug(
            biopharma_id=99999,
            company_id=test_company.id,
            drug_name="Test Drug (TEST-001)",
            indications_text="Test Indication",
            stage="Phase 2",
            stage_event_label="Phase 2 Results",
            catalyst_date_text="Q1 2024",
            has_catalyst=True,
            is_big_mover=True
        )
        db.add(test_drug)
        db.commit()
        
        print(f"Created drug: {test_drug}")
        
        # Query the data
        companies = db.query(Company).all()
        print(f"\nTotal companies in database: {len(companies)}")
        
        drugs = db.query(Drug).all()
        print(f"Total drugs in database: {len(drugs)}")
        
        # Clean up test data
        db.delete(test_drug)
        db.delete(test_company)
        db.commit()
        
        print("\nTest completed successfully! Database is working.")


if __name__ == "__main__":
    test_database()