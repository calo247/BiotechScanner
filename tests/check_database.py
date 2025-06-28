"""Quick script to check database contents."""

from src.database.database import init_db, get_db
from src.database.models import Company, Drug
from sqlalchemy import func

def check_database():
    """Check what's in the database."""
    init_db()
    
    with get_db() as db:
        # Count records
        drug_count = db.query(Drug).count()
        company_count = db.query(Company).count()
        
        print(f"\nDatabase Contents:")
        print(f"Total drugs: {drug_count}")
        print(f"Total companies: {company_count}")
        
        if drug_count > 0:
            # Show some sample drugs
            print("\nSample drugs:")
            drugs = db.query(Drug).limit(5).all()
            for drug in drugs:
                print(f"  - {drug.drug_name} ({drug.company.ticker if drug.company else 'No company'})")
            
            # Count drugs with catalysts
            catalyst_count = db.query(Drug).filter(Drug.has_catalyst == True).count()
            print(f"\nDrugs with catalysts: {catalyst_count}")
            
            # Show stage distribution
            print("\nDrugs by stage:")
            stages = db.query(
                Drug.stage, 
                func.count(Drug.id)
            ).group_by(Drug.stage).all()
            
            for stage, count in sorted(stages, key=lambda x: x[1], reverse=True)[:10]:
                print(f"  - {stage}: {count}")

if __name__ == "__main__":
    check_database()