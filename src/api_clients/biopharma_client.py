"""BiopharmIQ API client for fetching drug and catalyst data."""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from urllib.parse import urlparse, parse_qs
import json
import os

from ..config import config
from ..database.database import get_db
from ..database.models import APICache

# Set up logging
logger = logging.getLogger(__name__)


class BiopharmIQClient:
    """Client for interacting with the BiopharmIQ API."""
    
    def __init__(self):
        self.base_url = config.BIOPHARMA_BASE_URL
        self.api_key = config.BIOPHARMA_API_KEY
        self.headers = {
            "Authorization": f"Token {self.api_key}"
        }
        self.timeout = config.REQUEST_TIMEOUT
        
        # Create directory for API responses
        self.api_response_dir = "data/api_responses"
        os.makedirs(self.api_response_dir, exist_ok=True)
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a request to the BiopharmIQ API.
        
        Args:
            endpoint: API endpoint (e.g., '/drugs/')
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            requests.exceptions.RequestException: On API errors
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
            
        # Build full URL - don't use urljoin as it can strip parts of the base path
        url = self.base_url + endpoint
        
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:
                logger.error("Authentication failed. Check your API key.")
            elif response.status_code == 404:
                logger.error(f"Endpoint not found: {endpoint}")
            else:
                logger.error(f"HTTP error: {e}")
            raise
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def _check_cache(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Check if we have cached data for this endpoint.
        
        Args:
            endpoint: API endpoint
            
        Returns:
            Cached data if valid, None otherwise
        """
        with get_db() as db:
            cache_entry = db.query(APICache).filter(
                APICache.endpoint == endpoint
            ).first()
            
            if cache_entry:
                # Check if cache is still valid
                cache_age = datetime.utcnow() - cache_entry.last_fetched
                if cache_age < config.get_cache_expiry():
                    logger.info(f"Using cached data for {endpoint} (age: {cache_age})")
                    return cache_entry.response_data
                else:
                    logger.info(f"Cache expired for {endpoint} (age: {cache_age})")
                    
        return None
    
    def _save_response_to_file(self, endpoint: str, data: Any):
        """
        Save API response to a JSON file for manual inspection.
        
        Args:
            endpoint: API endpoint
            data: Response data to save
        """
        # Create filename based on endpoint and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        endpoint_safe = endpoint.replace('/', '_').strip('_')
        filename = f"{endpoint_safe}_{timestamp}.json"
        filepath = os.path.join(self.api_response_dir, filename)
        
        # Save with pretty formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved API response to: {filepath}")
    
    def _update_cache(self, endpoint: str, data: Dict[str, Any]):
        """Update cache with new data."""
        with get_db() as db:
            cache_entry = db.query(APICache).filter(
                APICache.endpoint == endpoint
            ).first()
            
            if cache_entry:
                cache_entry.response_data = data
                cache_entry.last_fetched = datetime.utcnow()
            else:
                cache_entry = APICache(
                    endpoint=endpoint,
                    response_data=data,
                    last_fetched=datetime.utcnow()
                )
                db.add(cache_entry)
            
            db.commit()
            logger.info(f"Cache updated for {endpoint}")
        
        # Also save to file for manual inspection
        self._save_response_to_file(endpoint, data)
    
    def get_all_drugs(self, use_cache: bool = True, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch all drugs from the API.
        
        This handles pagination automatically and returns all results.
        
        Args:
            use_cache: Whether to use cached data if available
            limit: Maximum number of drugs to fetch (None for all)
            
        Returns:
            List of all drug records
        """
        endpoint = "/drugs/"
        
        # Check cache first (only if we're getting all drugs)
        if use_cache and limit is None:
            cached_data = self._check_cache(endpoint)
            if cached_data and 'all_results' in cached_data:
                return cached_data['all_results']
        
        all_drugs = []
        next_url = endpoint
        page = 1
        
        # Determine page size
        page_size = min(100, limit) if limit and limit < 100 else 100
        
        logger.info(f"Fetching drugs from BiopharmIQ API{f' (limit: {limit})' if limit else ''}...")
        
        while next_url:
            # Make request
            if page == 1:
                # First page - set limit
                response = self._make_request(next_url, params={'limit': page_size})
            else:
                # For pagination, we need to use the full URL
                # Extract the offset from the next URL
                parsed_url = urlparse(next_url)
                query_params = parse_qs(parsed_url.query)
                params = {k: v[0] for k, v in query_params.items()}
                response = self._make_request(endpoint, params)
            
            # Add results to our list
            drugs = response.get('results', [])
            all_drugs.extend(drugs)
            
            logger.info(f"Fetched page {page}: {len(drugs)} drugs (total: {len(all_drugs)})")
            
            # Check if we've reached our limit
            if limit and len(all_drugs) >= limit:
                all_drugs = all_drugs[:limit]  # Trim to exact limit
                logger.info(f"Reached limit of {limit} drugs")
                break
            
            # Check for next page
            next_url = response.get('next')
            if next_url:
                # Extract just the path and query from the full URL
                parsed_url = urlparse(next_url)
                next_url = parsed_url.path + ('?' + parsed_url.query if parsed_url.query else '')
            
            page += 1
        
        logger.info(f"Fetched total of {len(all_drugs)} drugs")
        
        # Save the complete response to file
        if all_drugs:  # Only save if we got data
            complete_response = {
                'all_results': all_drugs,
                'fetched_at': datetime.utcnow().isoformat(),
                'total_count': len(all_drugs)
            }
            self._save_response_to_file(endpoint, complete_response)
        
        # Cache all results only if we fetched everything
        if use_cache and limit is None:
            self._update_cache(endpoint, {'all_results': all_drugs})
        
        return all_drugs
    
    def get_drug_by_id(self, drug_id: int) -> Dict[str, Any]:
        """
        Fetch a specific drug by ID.
        
        Args:
            drug_id: BiopharmIQ drug ID
            
        Returns:
            Drug data
        """
        endpoint = f"/drugs/{drug_id}/"
        
        # Check cache
        cached_data = self._check_cache(endpoint)
        if cached_data:
            return cached_data
        
        # Fetch from API
        data = self._make_request(endpoint)
        
        # Update cache
        self._update_cache(endpoint, data)
        
        return data
    
    def test_connection(self) -> bool:
        """
        Test the API connection and authentication.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to fetch first page with limit of 1
            response = self._make_request("/drugs/", params={"limit": 1})
            
            if 'results' in response:
                logger.info("API connection successful!")
                return True
            else:
                logger.error("Unexpected API response format")
                return False
                
        except Exception as e:
            logger.error(f"API connection failed: {e}")
            return False


# Create a singleton instance
biopharma_client = BiopharmIQClient()