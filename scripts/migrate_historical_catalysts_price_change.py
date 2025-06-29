#!/usr/bin/env python3
"""
Migration script to update historical_catalysts table:
- Remove announcement_time and announcement_timing columns
- Add price_change_3d column
- Recalculate all price changes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.database.database import get_db, engine
from src.data_sync import data_synchronizer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_historical_catalysts():
    """Migrate the historical_catalysts table to new schema."""
    
    print("=== Historical Catalysts Migration ===")
    print("This will:")
    print("1. Add price_change_3d column")
    print("2. Remove announcement timing columns")
    print("3. Recalculate all price changes")
    print()
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    try:
        with engine.connect() as conn:
            # Check if migration is needed
            result = conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='historical_catalysts'"
            ))
            table_def = result.fetchone()
            
            if not table_def:
                print("Table historical_catalysts not found!")
                return
            
            table_sql = table_def[0]
            
            # Check current schema
            has_price_change = 'price_change_3d' in table_sql
            has_timing = 'announcement_time' in table_sql
            
            if has_price_change and not has_timing:
                print("Migration already completed!")
                return
            
            # Start migration
            print("\n1. Adding price_change_3d column...")
            if not has_price_change:
                conn.execute(text(
                    "ALTER TABLE historical_catalysts ADD COLUMN price_change_3d REAL"
                ))
                conn.commit()
                print("   ✓ Column added")
            else:
                print("   ✓ Column already exists")
            
            print("\n2. Removing announcement timing columns...")
            if has_timing:
                # SQLite doesn't support DROP COLUMN directly, need to recreate table
                conn.execute(text("""
                    CREATE TABLE historical_catalysts_new (
                        id INTEGER PRIMARY KEY,
                        biopharma_id INTEGER,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        ticker VARCHAR(10),
                        drug_name TEXT,
                        drug_indication TEXT,
                        stage VARCHAR(100),
                        catalyst_date DATETIME,
                        catalyst_text TEXT,
                        catalyst_source TEXT,
                        price_change_3d REAL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Copy data
                conn.execute(text("""
                    INSERT INTO historical_catalysts_new 
                    (id, biopharma_id, company_id, ticker, drug_name, drug_indication, 
                     stage, catalyst_date, catalyst_text, catalyst_source, price_change_3d, updated_at)
                    SELECT id, biopharma_id, company_id, ticker, drug_name, drug_indication,
                           stage, catalyst_date, catalyst_text, catalyst_source, price_change_3d, updated_at
                    FROM historical_catalysts
                """))
                
                # Drop old table and rename new one
                conn.execute(text("DROP TABLE historical_catalysts"))
                conn.execute(text("ALTER TABLE historical_catalysts_new RENAME TO historical_catalysts"))
                
                # Recreate indexes
                conn.execute(text("CREATE INDEX idx_hist_catalyst_date ON historical_catalysts(catalyst_date)"))
                conn.execute(text("CREATE INDEX idx_hist_stage ON historical_catalysts(stage)"))
                conn.execute(text("CREATE INDEX idx_hist_ticker ON historical_catalysts(ticker)"))
                conn.execute(text("CREATE INDEX ix_historical_catalysts_biopharma_id ON historical_catalysts(biopharma_id)"))
                
                conn.commit()
                print("   ✓ Timing columns removed")
            else:
                print("   ✓ Timing columns already removed")
        
        print("\n3. Recalculating price changes...")
        print("   This may take a few minutes...\n")
        
        # Use the data synchronizer to recalculate all price changes
        data_synchronizer.recalculate_historical_price_changes()
        
        print("\n✓ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate_historical_catalysts()