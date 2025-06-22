#!/usr/bin/env python3
"""
Remove catalyst_date and updated_at columns from catalyst_reports table.

These columns are redundant:
- catalyst_date: Already available through drug.catalyst_date
- updated_at: Reports are immutable once created
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.database.database import engine

def main():
    """Remove unnecessary columns from catalyst_reports table."""
    print("Removing redundant columns from catalyst_reports table...")
    
    with engine.connect() as conn:
        # SQLite doesn't support ALTER TABLE DROP COLUMN directly
        # We need to check the database type
        if 'sqlite' in str(engine.url):
            print("SQLite detected. Creating new table without redundant columns...")
            
            # For SQLite, we need to:
            # 1. Create a new table with the desired schema
            # 2. Copy data from old table
            # 3. Drop old table
            # 4. Rename new table
            
            conn.execute(text("""
                CREATE TABLE catalyst_reports_new (
                    id INTEGER PRIMARY KEY,
                    drug_id INTEGER NOT NULL,
                    company_id INTEGER NOT NULL,
                    report_type VARCHAR(50) DEFAULT 'full_analysis',
                    model_used VARCHAR(100) DEFAULT 'anthropic/claude-sonnet-4',
                    report_markdown TEXT NOT NULL,
                    report_summary TEXT,
                    success_probability FLOAT,
                    price_target_upside VARCHAR(50),
                    price_target_downside VARCHAR(50),
                    recommendation VARCHAR(100),
                    risk_level VARCHAR(50),
                    analysis_data JSON,
                    tokens_used INTEGER,
                    generation_time_ms INTEGER,
                    created_at DATETIME,
                    FOREIGN KEY(drug_id) REFERENCES drugs(id),
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
            """))
            
            # Copy existing data (excluding the columns we're removing)
            conn.execute(text("""
                INSERT INTO catalyst_reports_new 
                SELECT id, drug_id, company_id, report_type, model_used, 
                       report_markdown, report_summary, success_probability,
                       price_target_upside, price_target_downside, recommendation,
                       risk_level, analysis_data, tokens_used, generation_time_ms,
                       created_at
                FROM catalyst_reports
            """))
            
            # Drop old table and rename new one
            conn.execute(text("DROP TABLE catalyst_reports"))
            conn.execute(text("ALTER TABLE catalyst_reports_new RENAME TO catalyst_reports"))
            
            # Recreate indexes
            conn.execute(text("CREATE INDEX idx_report_drug ON catalyst_reports(drug_id)"))
            conn.execute(text("CREATE INDEX idx_report_company ON catalyst_reports(company_id)"))
            conn.execute(text("CREATE INDEX idx_report_created ON catalyst_reports(created_at)"))
            
            conn.commit()
            
        else:
            # For other databases (PostgreSQL, MySQL, etc.)
            print("Non-SQLite database detected. Using ALTER TABLE...")
            conn.execute(text("ALTER TABLE catalyst_reports DROP COLUMN catalyst_date"))
            conn.execute(text("ALTER TABLE catalyst_reports DROP COLUMN updated_at"))
            # Drop the old index that references catalyst_date
            conn.execute(text("DROP INDEX IF EXISTS idx_report_catalyst_date"))
            conn.commit()
    
    print("✓ Successfully removed catalyst_date and updated_at columns")
    print("✓ Table schema is now cleaner with no redundant data")

if __name__ == "__main__":
    main()