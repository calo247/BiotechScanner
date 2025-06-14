"""Data synchronization module for updating database with API data."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dateutil import parser as date_parser
from tqdm import tqdm

from .api_clients.biopharma_client import biopharma_client
from .database.database import get_db
from .database.models import Company, Drug, APICache
from .config import config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataSynchronizer:
    """Handles synchronization of data from APIs to database."""
    
    def __init__(self):
        self.biopharma_client = biopharma_client
    
    def _parse_catalyst_date(self, date_value: Any) -> Optional[datetime]:
        """
        Parse catalyst date from API response.
        
        The API can return dates in various formats:
        - ISO format: "2024-03-15T00:00:00Z"
        - Date only: "2024-03-15"
        - None/null for TBA dates
        
        Args:
            date_value: Date value from API
            
        Returns:
            Parsed datetime or None
        """
        if not date_value:
            return None
            
        try:
            if isinstance(date_value, str):
                return date_parser.parse(date_value)
            return None
        except Exception as e:
            logger.warning(f"Could not parse date '{date_value}': {e}")
            return None
    
    def _get_or_create_company(self, db, company_data: Dict[str, Any]) -> Company:
        """
        Get existing company or create new one.
        
        Args:
            db: Database session
            company_data: Company data from API
            
        Returns:
            Company instance
        """
        if not company_data:
            logger.warning("No company data provided")
            return None
            
        biopharma_company_id = company_data.get('id')
        ticker = company_data.get('ticker', '').upper()
        
        if not biopharma_company_id:
            logger.error(f"Company missing BiopharmIQ ID: {company_data}")
            return None
            
        if not ticker:
            logger.error(f"Company missing ticker: {company_data}")
            return None
        
        # Check if company exists by BiopharmIQ ID (the only way we match)
        company = db.query(Company).filter(
            Company.biopharma_id == biopharma_company_id
        ).first()
        
        if not company:
            # Create new company
            company = Company(
                biopharma_id=biopharma_company_id,
                ticker=ticker,
                name=company_data.get('name', ticker),
                sector='Biotechnology'  # Default sector, can be updated later
            )
            db.add(company)
            logger.debug(f"Created new company: {ticker} (BiopharmIQ ID: {biopharma_company_id})")
        
        return company
    
    def sync_drugs(self, force_refresh: bool = False, limit: Optional[int] = None):
        """
        Synchronize drug data from BiopharmIQ API to database.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            limit: If set, only sync this many drugs (for testing)
        """
        logger.info("Starting drug data synchronization...")
        
        # Test API connection first
        if not self.biopharma_client.test_connection():
            logger.error("Cannot connect to BiopharmIQ API. Check your API key.")
            return
        
        # Fetch all drugs
        try:
            drugs_data = self.biopharma_client.get_all_drugs(
                use_cache=not force_refresh,
                limit=limit
            )
                
        except Exception as e:
            logger.error(f"Failed to fetch drugs: {e}")
            return
        
        logger.info(f"Processing {len(drugs_data)} drugs...")
        
        # Process drugs in batches
        with get_db() as db:
            stats = {
                'created': 0,
                'updated': 0,
                'errors': 0,
                'companies_created': 0
            }
            
            # Keep track of existing companies to avoid repeated queries
            company_cache = {}
            
            for drug_data in tqdm(drugs_data, desc="Processing drugs"):
                try:
                    # Get or create company
                    company_data = drug_data.get('company', {})
                    ticker = company_data.get('ticker', '').upper()
                    
                    # Check cache first
                    if ticker in company_cache:
                        company = company_cache[ticker]
                    else:
                        company = self._get_or_create_company(db, company_data)
                        if company:
                            company_cache[ticker] = company
                    
                    if not company:
                        stats['errors'] += 1
                        continue
                    
                    # Check if drug exists
                    biopharma_id = drug_data.get('id')
                    drug = db.query(Drug).filter(
                        Drug.biopharma_id == biopharma_id
                    ).first()
                    
                    # Parse stage information
                    stage_event = drug_data.get('stage_event', {})
                    stage = stage_event.get('stage_label', '')
                    
                    # Prepare drug data
                    drug_attrs = {
                        'company': company,  # Use relationship instead of company_id
                        'drug_name': drug_data.get('drug_name', ''),
                        'mechanism_of_action': drug_data.get('mechanism_of_action', ''),
                        'indications': drug_data.get('indications', []),
                        'indications_text': drug_data.get('indications_text', ''),
                        'stage': stage,
                        'stage_event_label': stage_event.get('label', ''),
                        'event_score': stage_event.get('score'),
                        'catalyst_date': self._parse_catalyst_date(drug_data.get('catalyst_date')),
                        'catalyst_date_text': drug_data.get('catalyst_date_text', ''),
                        'has_catalyst': drug_data.get('has_catalyst', False),
                        'catalyst_source': drug_data.get('catalyst_source', ''),
                        'is_big_mover': drug_data.get('is_big_mover', False),
                        'is_suspected_mover': drug_data.get('is_suspected_mover', False),
                        'note': drug_data.get('note', ''),
                        'market_info': drug_data.get('market', ''),
                        'last_update_name': drug_data.get('last_name_updated', ''),
                        'api_last_updated': datetime.utcnow()
                    }
                    
                    if drug:
                        # Update existing drug
                        for key, value in drug_attrs.items():
                            setattr(drug, key, value)
                        stats['updated'] += 1
                    else:
                        # Create new drug
                        drug = Drug(biopharma_id=biopharma_id, **drug_attrs)
                        db.add(drug)
                        stats['created'] += 1
                    
                    # Commit every 100 drugs to avoid memory issues
                    if (stats['created'] + stats['updated']) % 100 == 0:
                        db.commit()
                        
                except Exception as e:
                    logger.error(f"Error processing drug {drug_data.get('id')}: {e}")
                    stats['errors'] += 1
                    # Don't rollback the entire transaction, just skip this drug
                    continue
            
            # Final commit for any remaining drugs
            try:
                db.commit()
                logger.info("Database commit successful")
            except Exception as e:
                logger.error(f"Error during final commit: {e}")
                db.rollback()
                raise
            
        # Log summary
        logger.info(f"\nSynchronization complete:")
        logger.info(f"  - Drugs created: {stats['created']}")
        logger.info(f"  - Drugs updated: {stats['updated']}")
        logger.info(f"  - Errors: {stats['errors']}")
        logger.info(f"  - Total drugs in database: {stats['created'] + stats['updated']}")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        with get_db() as db:
            drug_count = db.query(Drug).count()
            company_count = db.query(Company).count()
            
            # Get last sync time from cache
            cache = db.query(APICache).filter(
                APICache.endpoint == "/drugs/"
            ).first()
            
            last_sync = cache.last_fetched if cache else None
            
            # Count drugs with catalysts
            catalyst_count = db.query(Drug).filter(
                Drug.has_catalyst == True
            ).count()
            
            return {
                'total_drugs': drug_count,
                'total_companies': company_count,
                'drugs_with_catalysts': catalyst_count,
                'last_sync': last_sync,
                'cache_expires': last_sync + config.get_cache_expiry() if last_sync else None
            }


# Create singleton instance
data_synchronizer = DataSynchronizer()