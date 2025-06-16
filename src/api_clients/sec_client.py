"""SEC EDGAR API client for fetching company filings."""

import requests
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
import time
import json
import os
import gzip
from urllib.parse import urljoin
import re

from ..config import config
from ..database.database import get_db
from ..database.models import Company, SECFiling, FinancialMetric

# Set up logging
logger = logging.getLogger(__name__)


class SECClient:
    """Client for fetching SEC filings from EDGAR API."""
    
    def __init__(self):
        self.base_url = "https://data.sec.gov"
        self.archives_url = "https://www.sec.gov/Archives/edgar"
        
        # SEC requires a user agent with contact info
        self.headers = {
            "User-Agent": config.SEC_USER_AGENT,
            "Accept": "application/json"
        }
        
        # Rate limiting: 10 requests per second
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        
        # Create base directory for SEC filings
        self.filings_dir = "data/sec_filings"
        os.makedirs(self.filings_dir, exist_ok=True)
    
    def _rate_limit(self):
        """Ensure we don't exceed SEC rate limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a rate-limited request to the SEC API.
        
        Args:
            url: Full URL to request
            params: Query parameters
            
        Returns:
            JSON response data or None if failed
        """
        self._rate_limit()
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=config.REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                logger.debug(f"Request to {url} returned status {response.status_code}")
                
            response.raise_for_status()
            
            # SEC API returns JSON for submissions endpoint
            if response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            else:
                return {"text": response.text}
                
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                logger.debug(f"404 Not Found for URL: {url}")
            else:
                logger.error(f"SEC API HTTP error: {e}")
            return None
            
        except Exception as e:
            logger.error(f"SEC API request failed: {e}")
            return None
    
    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Get a company's CIK (Central Index Key) from ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            10-digit CIK as string or None
        """
        # SEC provides a ticker to CIK mapping
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        
        data = self._make_request(tickers_url)
        if not data:
            return None
        
        # Search for the ticker
        ticker_upper = ticker.upper()
        for item in data.values():
            if item.get('ticker') == ticker_upper:
                # CIK needs to be 10 digits with leading zeros
                cik = str(item.get('cik_str', '')).zfill(10)
                logger.debug(f"Found CIK {cik} for ticker {ticker}")
                return cik
        
        logger.warning(f"No CIK found for ticker {ticker}")
        return None
    
    def get_company_facts(self, cik: str) -> Optional[Dict]:
        """
        Get all XBRL financial facts for a company.
        This includes all historical financial data in structured format.
        
        Args:
            cik: Company's CIK (Central Index Key)
            
        Returns:
            Dictionary with all company financial facts or None
        """
        cik = cik.zfill(10)
        url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik}.json"
        
        logger.info(f"Fetching company facts for CIK {cik}")
        data = self._make_request(url)
        
        if data:
            logger.info(f"Retrieved financial facts for {data.get('entityName', 'Unknown')}")
        
        return data
    
    def store_financial_metrics(self, company: Company, facts: Dict) -> int:
        """
        Store financial metrics from company facts API.
        
        Args:
            company: Company object
            facts: Company facts data from API
            
        Returns:
            Number of metrics stored
        """
        metrics_stored = 0
        metrics_updated = 0
        
        # Important metrics to extract
        important_concepts = {
            'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
            'ResearchAndDevelopmentExpense', 'CostOfGoodsAndServicesSold',
            'NetIncomeLoss', 'Assets', 'Liabilities', 'StockholdersEquity',
            'CashAndCashEquivalentsAtCarryingValue', 'OperatingIncomeLoss'
        }
        
        # Process in separate sessions to handle duplicates
        for concept, concept_data in facts.get('facts', {}).get('us-gaap', {}).items():
            if concept not in important_concepts:
                continue
                
            label = concept_data.get('label', concept)
            
            # Process each unit type (usually USD)
            for unit, values in concept_data.get('units', {}).items():
                for value_data in values:
                    with get_db() as db:
                        try:
                            # Check if metric exists
                            existing = db.query(FinancialMetric).filter(
                                FinancialMetric.company_id == company.id,
                                FinancialMetric.concept == concept,
                                FinancialMetric.fiscal_year == value_data.get('fy'),
                                FinancialMetric.fiscal_period == value_data.get('fp'),
                                FinancialMetric.form == value_data.get('form')
                            ).first()
                            
                            # Parse filed date
                            filed_date = None
                            if value_data.get('filed'):
                                filed_date = datetime.strptime(value_data['filed'], '%Y-%m-%d')
                                filed_date = filed_date.replace(tzinfo=timezone.utc)
                            
                            if existing:
                                # Update if the filed date is newer
                                existing_filed_date = existing.filed_date
                                # Make sure both dates are timezone-aware for comparison
                                if existing_filed_date and existing_filed_date.tzinfo is None:
                                    existing_filed_date = existing_filed_date.replace(tzinfo=timezone.utc)
                                
                                if filed_date and (not existing_filed_date or filed_date > existing_filed_date):
                                    existing.value = value_data.get('val')
                                    existing.filed_date = filed_date
                                    existing.accession_number = value_data.get('accn')
                                    db.commit()
                                    metrics_updated += 1
                            else:
                                # Create new metric
                                metric = FinancialMetric(
                                    company_id=company.id,
                                    concept=concept,
                                    label=label,
                                    value=value_data.get('val'),
                                    unit=unit,
                                    fiscal_year=value_data.get('fy'),
                                    fiscal_period=value_data.get('fp'),
                                    form=value_data.get('form'),
                                    filed_date=filed_date,
                                    accession_number=value_data.get('accn')
                                )
                                
                                db.add(metric)
                                db.commit()
                                metrics_stored += 1
                                
                        except Exception as e:
                            if "UNIQUE constraint failed" not in str(e):
                                logger.error(f"Error storing metric {concept}: {e}")
        
        logger.info(f"Stored {metrics_stored} new and updated {metrics_updated} financial metrics for {company.ticker}")
        return metrics_stored + metrics_updated
    
    def get_recent_filings(self, cik: str, filing_types: List[str] = None) -> List[Dict]:
        """
        Get recent filings for a company.
        
        Args:
            cik: Company's CIK (Central Index Key)
            filing_types: List of filing types to filter (e.g., ['10-K', '10-Q', '8-K'])
            
        Returns:
            List of filing metadata
        """
        if filing_types is None:
            filing_types = ['10-K', '10-Q', '8-K', 'DEF 14A']  # Common filing types
        
        # Ensure CIK is 10 digits
        cik = cik.zfill(10)
        
        # Get company submissions
        url = f"{self.base_url}/submissions/CIK{cik}.json"
        
        data = self._make_request(url)
        if not data:
            return []
        
        filings = []
        recent_filings = data.get('filings', {}).get('recent', {})
        
        # Extract filing data
        forms = recent_filings.get('form', [])
        filing_dates = recent_filings.get('filingDate', [])
        accession_numbers = recent_filings.get('accessionNumber', [])
        primary_documents = recent_filings.get('primaryDocument', [])
        
        # Process each filing
        for i in range(min(len(forms), 100)):  # Limit to recent 100
            if forms[i] in filing_types:
                # Format accession number (remove hyphens for URL)
                accession = accession_numbers[i]
                accession_clean = accession.replace('-', '')
                
                filing = {
                    'form': forms[i],
                    'filing_date': filing_dates[i],
                    'accession_number': accession,
                    'primary_document': primary_documents[i],
                    # Remove leading zeros from CIK for the URL
                    'url': f"{self.archives_url}/data/{int(cik)}/{accession_clean}/{primary_documents[i]}",
                    'cik': cik
                }
                filings.append(filing)
        
        logger.info(f"Found {len(filings)} filings for CIK {cik}")
        return filings
    
    def download_filing_text(self, filing_url: str, accession_number: str = None) -> Optional[str]:
        """
        Download the text version of a filing.
        
        Args:
            filing_url: URL to the filing document
            accession_number: Accession number (with hyphens)
            
        Returns:
            Filing text or None
        """
        # Extract parts from the URL to build the correct text URL
        if '/data/' in filing_url and accession_number:
            parts = filing_url.split('/')
            cik_idx = parts.index('data') + 1
            
            if len(parts) > cik_idx:
                cik = parts[cik_idx]
                accession_clean = accession_number.replace('-', '')
                
                # Build the correct text file URL using the accession number
                txt_url = f"{self.archives_url}/data/{cik}/{accession_clean}/{accession_number}.txt"
                logger.debug(f"Downloading filing from {txt_url}")
                
                response = self._make_request(txt_url)
                if response and 'text' in response:
                    text = response['text']
                    # Clean up common SGML tags and formatting
                    text = self._clean_filing_text(text)
                    return text
                else:
                    logger.debug(f"Failed to download from {txt_url}")
        
        return None
    
    def _clean_filing_text(self, text: str) -> str:
        """Clean up SEC filing text."""
        # Remove SGML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Fix common encoding issues
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def save_filing_text(self, company: Company, filing: Dict, text: str) -> str:
        """
        Save filing text to disk with compression.
        
        Args:
            company: Company object
            filing: Filing metadata
            text: Filing text content
            
        Returns:
            Path to saved file
        """
        # Create directory structure: ticker_cik/filing_type/
        # Get CIK from parsed_content or filing data
        cik = filing.get('cik') or filing.get('parsed_content', {}).get('cik', 'unknown')
        ticker_cik = f"{company.ticker}_{cik}"
        filing_type = filing['form'].replace('/', '-')  # Handle 10-K/A etc
        
        dir_path = os.path.join(self.filings_dir, ticker_cik, filing_type)
        os.makedirs(dir_path, exist_ok=True)
        
        # Filename: date_accession.txt.gz
        filing_date = filing['filing_date']
        accession = filing['accession_number']
        filename = f"{filing_date}_{accession}.txt.gz"
        file_path = os.path.join(dir_path, filename)
        
        # Compress and save
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            f.write(text)
        
        logger.debug(f"Saved filing to {file_path}")
        return file_path
    
    def load_filing_text(self, file_path: str) -> Optional[str]:
        """Load filing text from disk."""
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading filing from {file_path}: {e}")
            return None
    
    def update_company_filings(self, company: Company, days_back: int = 90) -> Tuple[int, int]:
        """
        Update SEC filings and financial data for a company.
        
        Args:
            company: Company object
            days_back: Number of days of history to fetch
            
        Returns:
            Tuple of (filings_added, metrics_added)
        """
        # First, get the company's CIK
        cik = self.get_company_cik(company.ticker)
        if not cik:
            logger.warning(f"Could not find CIK for {company.ticker}")
            return 0, 0
        
        # Update financial metrics via company facts API
        metrics_added = 0
        facts = self.get_company_facts(cik)
        if facts:
            metrics_added = self.store_financial_metrics(company, facts)
        
        # Then, get recent filings via submissions API
        filings = self.get_recent_filings(cik)
        
        # Filter by date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        recent_filings = []
        
        for filing in filings:
            filing_date = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
            filing_date = filing_date.replace(tzinfo=timezone.utc)
            
            if filing_date >= cutoff_date:
                recent_filings.append(filing)
        
        logger.info(f"Processing {len(recent_filings)} recent filings for {company.ticker}")
        
        filings_added = 0
        
        with get_db() as db:
            for filing in recent_filings:
                # Check if filing already exists
                existing = db.query(SECFiling).filter(
                    SECFiling.accession_number == filing['accession_number']
                ).first()
                
                if existing:
                    continue
                
                # Download filing text
                logger.info(f"Processing {filing['form']} filing {filing['accession_number']}")
                text = self.download_filing_text(filing['url'], filing['accession_number'])
                if not text:
                    logger.warning(f"Could not download text for {filing['accession_number']}")
                    continue
                
                # Save to disk
                file_path = self.save_filing_text(company, filing, text)
                
                # Extract metadata
                word_count = len(text.split())
                mentions_clinical = bool(re.search(r'clinical trial|phase [123]|FDA approval', text, re.IGNORECASE))
                
                # Extract first 1000 chars of key sections for preview
                business_section = self._extract_section(text, "BUSINESS")[:1000]
                risk_section = self._extract_section(text, "RISK FACTORS")[:1000]
                
                # Create filing record
                filing_date = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
                filing_date = filing_date.replace(tzinfo=timezone.utc)
                
                sec_filing = SECFiling(
                    company=company,
                    filing_type=filing['form'],
                    filing_date=filing_date,
                    accession_number=filing['accession_number'],
                    filing_url=filing['url'],
                    file_path=file_path,
                    file_size=os.path.getsize(file_path),
                    word_count=word_count,
                    mentions_clinical_trial=mentions_clinical,
                    parsed_content={
                        'primary_document': filing['primary_document'],
                        'business_preview': business_section,
                        'risk_preview': risk_section,
                        'cik': cik
                    }
                )
                
                db.add(sec_filing)
                filings_added += 1
            
            if filings_added > 0:
                db.commit()
                logger.info(f"Added {filings_added} new filings for {company.ticker}")
        
        return filings_added, metrics_added
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from filing text."""
        patterns = [
            rf"ITEM\s+\d+[A-Z]?\.\s*{section_name}",
            rf"{section_name}"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = match.end()
                # Find next section
                next_match = re.search(r'ITEM\s+\d+[A-Z]?\.', text[start:], re.IGNORECASE)
                if next_match:
                    end = start + next_match.start()
                else:
                    end = min(start + 50000, len(text))  # Max 50k chars
                
                return text[start:end].strip()
        
        return ""
    
    def update_all_companies_filings(self, days_back: int = 90) -> Dict[str, int]:
        """
        Update SEC filings for all companies.
        
        Args:
            days_back: Number of days of history to fetch
            
        Returns:
            Dictionary with statistics
        """
        stats = {
            'companies_processed': 0,
            'companies_skipped': 0,
            'filings_added': 0,
            'metrics_added': 0,
            'errors': 0
        }
        
        with get_db() as db:
            companies = db.query(Company).all()
            total = len(companies)
            
        logger.info(f"Updating SEC filings for {total} companies...")
        
        for i, company in enumerate(companies):
            try:
                filings, metrics = self.update_company_filings(company, days_back)
                
                if filings > 0 or metrics > 0:
                    stats['filings_added'] += filings
                    stats['metrics_added'] += metrics
                    stats['companies_processed'] += 1
                else:
                    stats['companies_skipped'] += 1
                
                # Progress update
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i + 1}/{total} companies")
                    
            except Exception as e:
                logger.error(f"Error processing {company.ticker}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Get a company's CIK (Central Index Key) from ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            10-digit CIK as string or None
        """
        # SEC provides a ticker to CIK mapping
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        
        data = self._make_request(tickers_url)
        if not data:
            return None
        
        # Search for the ticker
        ticker_upper = ticker.upper()
        for item in data.values():
            if item.get('ticker') == ticker_upper:
                # CIK needs to be 10 digits with leading zeros
                cik = str(item.get('cik_str', '')).zfill(10)
                logger.debug(f"Found CIK {cik} for ticker {ticker}")
                return cik
        
        logger.warning(f"No CIK found for ticker {ticker}")
        return None


# Create singleton instance
sec_client = SECClient()