"""
Script to document the removal of old indication columns.
Note: SQLite doesn't support DROP COLUMN directly, so this script
provides instructions for manual cleanup if needed.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.database.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Document the column removal process."""
    logger.info("=== OLD COLUMN REMOVAL DOCUMENTATION ===")
    logger.info("")
    logger.info("The following columns have been removed from the Drug model:")
    logger.info("  - indications (replaced by indication_json)")
    logger.info("  - indications_text (replaced by indication_specific)")
    logger.info("  - indication_titles (replaced by indication_generic)")
    logger.info("")
    logger.info("SQLite Note: SQLite doesn't support DROP COLUMN directly.")
    logger.info("The old columns remain in the database but are no longer used by the code.")
    logger.info("")
    logger.info("For PostgreSQL migration, use these commands:")
    logger.info("  ALTER TABLE drugs DROP COLUMN indications;")
    logger.info("  ALTER TABLE drugs DROP COLUMN indications_text;")
    logger.info("  ALTER TABLE drugs DROP COLUMN indication_titles;")
    logger.info("")
    
    # Verify that new columns have data
    with engine.connect() as conn:
        # Check data migration status
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(indication_json) as has_json,
                COUNT(indication_specific) as has_specific,
                COUNT(indication_generic) as has_generic,
                COUNT(indication_nicknames) as has_nicknames
            FROM drugs
        """)).fetchone()
        
        logger.info("Current data status:")
        logger.info(f"  Total drugs: {result[0]}")
        logger.info(f"  With indication_json: {result[1]}")
        logger.info(f"  With indication_specific: {result[2]}")
        logger.info(f"  With indication_generic: {result[3]}")
        logger.info(f"  With indication_nicknames: {result[4]}")
        
        # Show column info
        logger.info("\nCurrent drugs table columns:")
        col_info = conn.execute(text("PRAGMA table_info(drugs)"))
        for col in col_info:
            col_name = col[1]
            if 'indication' in col_name:
                logger.info(f"  - {col_name}")


if __name__ == "__main__":
    main()