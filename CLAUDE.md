# BiotechScanner Project Documentation

## Project Overview

BiotechScanner is a Python-based tool designed to automate the process of searching through biotech stock catalysts for trading opportunities. The tool collects data from multiple sources, stores it in a structured database, and will eventually provide AI-powered analysis of potential catalyst events.

## Current Project Status

### Completed Components

#### 1. Database Infrastructure (SQLAlchemy + SQLite)
- Designed for future PostgreSQL migration
- Models: Company, Drug, StockData, SECFiling, FinancialMetric, HistoricalCatalyst, APICache
- Proper relationship handling
- Timezone-naive UTC datetime management throughout
- Removed redundant fields for cleaner schema

#### 2. BiopharmIQ Integration
- Fetches all drug and catalyst data via API
- Implements 12-hour caching to respect rate limits (1-2 calls/day max)
- Stores complete drug information including clinical trial phases, catalyst dates, and indications
- Premium API: Historical catalyst endpoint for past events
- Graceful interrupt handling (Ctrl+C)
- Removed opaque scoring fields (is_big_mover, is_suspected_mover, event_score)

#### 3. Polygon.io Integration (Replaced Yahoo Finance)
- Downloads historical stock prices with adjusted close values
- Premium API: No rate limiting
- Smart incremental updates:
  - Initial load: 5 years of historical data
  - Updates: Only fetches days since last sync (always refetches last day)
- Batch processing with progress bars
- Graceful interrupt handling

#### 4. SEC EDGAR Integration
- Dual-API approach:
  - Company Facts API: All historical financial metrics in one call
  - Submissions API: Filing metadata and document URLs
- Downloads and compresses full filing text (10-K, 10-Q, 8-K, etc.)
- Stores financial metrics in structured format
- File organization: `data/sec_filings/TICKER_CIK/filing_type/date_accession.txt.gz`

#### 5. Web Application Interface
- Flask-based web application for catalyst viewing and analysis
- Professional table-based interface with sorting and search functionality
- Detailed catalyst view pages with comprehensive drug and market information
- Real-time search with backend API integration
- Clickable catalyst rows for drill-down navigation
- Clean, responsive design optimized for biotech catalyst analysis

## Data Collection Commands

```bash
# Check status
python3 sync_data.py --status

# Sync drug data (respects cache)
python3 sync_data.py --drugs
python3 sync_data.py --drugs --force # Force refresh

# Sync stock data
python3 sync_data.py --stocks --initial # Initial 5-year load
python3 sync_data.py --stocks # Incremental update
python3 sync_data.py --stocks --ticker MRNA # Single ticker

# Sync historical catalysts (premium API)
python3 sync_data.py --historical
python3 sync_data.py --historical --force
python3 sync_data.py --historical --limit 100 # For testing

# Sync SEC filings
python3 sync_data.py --sec
python3 sync_data.py --sec --ticker MRNA # Single ticker

# Sync everything
python3 sync_data.py --all
python3 sync_data.py --all --force # Force refresh drugs
```

## Database Schema

### Company
- `id`: Primary key
- `biopharma_id`: BiopharmIQ's company ID (unique, indexed)
- `ticker`: Stock symbol (unique, indexed)
- `name`: Company name
- `created_at`: Timestamp
- `updated_at`: Timestamp
- **Relationships**: drugs, stock_data, sec_filings, financial_metrics, historical_catalysts

### Drug
- `id`: Primary key
- `biopharma_id`: BiopharmIQ's drug ID (unique)
- `company_id`: Foreign key to Company
- `drug_name`: Full drug name
- `mechanism_of_action`: How the drug works
- `indications`: JSON array of conditions treated
- `indications_text`: Text representation
- `stage`: Development stage (Phase 1/2/3, Approved, etc.)
- `stage_event_label`: Full event description
- `catalyst_date`: Expected catalyst event date
- `catalyst_date_text`: Text representation
- `has_catalyst`: Boolean
- `catalyst_source`: URL
- `note`: Additional notes
- `market_info`: Market information
- `last_update_name`: Last update info
- `api_last_updated`: Last API sync
- `created_at`, `updated_at`: Timestamps

### StockData
- `id`: Primary key
- `company_id`: Foreign key to Company
- `date`: Trading date
- `open`, `high`, `low`, `close`: OHLC prices (adjusted)
- `volume`: Trading volume
- `market_cap`: Market capitalization
- `pe_ratio`: P/E ratio (when available)
- `week_52_high`, `week_52_low`: 52-week range
- `source`: Data source ('polygon')
- `created_at`: Timestamp
- **Unique constraint** on (company_id, date)

### HistoricalCatalyst
- `id`: Primary key
- `biopharma_id`: BiopharmIQ ID (indexed, not unique)
- `company_id`: Foreign key to Company
- `ticker`: Company ticker
- `drug_name`: Drug name
- `drug_indication`: Indication
- `stage`: Development stage
- `catalyst_date`: Event date
- `catalyst_text`: Outcome description
- `catalyst_source`: URL
- `updated_at`: Timestamp

### SECFiling
- `id`: Primary key
- `company_id`: Foreign key to Company
- `filing_type`: 10-K, 10-Q, 8-K, etc.
- `filing_date`: Filing date
- `accession_number`: Unique filing ID
- `filing_url`: SEC URL
- `file_path`: Local compressed file path
- `file_size`: Bytes
- `word_count`: Word count
- `mentions_clinical_trial`: Boolean
- `parsed_content`: JSON with section previews
- `created_at`: Timestamp

### FinancialMetric
- `id`: Primary key
- `company_id`: Foreign key to Company
- `concept`: XBRL concept name
- `label`: Human-readable label
- `value`: Metric value
- `unit`: Currency or unit
- `fiscal_year`: Year
- `fiscal_period`: FY, Q1, Q2, Q3, Q4
- `form`: Source form (10-K, 10-Q)
- `filed_date`: Filing date
- `accession_number`: Source filing
- `updated_at`: Last updated timestamp
- **Unique constraint** on (company_id, concept, fiscal_year, fiscal_period, form)

### APICache
- `id`: Primary key
- `endpoint`: API endpoint (unique)
- `response_data`: JSON response
- `last_fetched`: Timestamp

## Technical Architecture

### File Structure

```
BiotechScanner/
├── src/
│   ├── api_clients/
│   │   ├── biopharma_client.py
│   │   ├── polygon_client.py
│   │   └── sec_client.py
│   ├── database/
│   │   ├── database.py
│   │   └── models.py
│   ├── queries/
│   │   ├── __init__.py
│   │   ├── filters.py
│   │   ├── catalyst_queries.py
│   │   └── company_queries.py
│   ├── data_sync.py
│   └── config.py
├── webapp/
│   ├── app.py
│   ├── templates/
│   │   ├── index.html
│   │   └── catalyst_detail.html
│   └── static/
│       ├── script.js
│       ├── catalyst_detail.js
│       ├── style.css
│       ├── range-slider.js
│       └── stock-price-slider.js
├── data/
│   ├── catalyst.db
│   ├── api_responses/
│   │   └── drugs_TIMESTAMP.json
│   └── sec_filings/
│       └── TICKER_CIK/
│           ├── 10-K/
│           ├── 10-Q/
│           └── 8-K/
├── sync_data.py
├── requirements.txt
└── .env
```

### Key Technical Decisions

#### 1. Database Design
- SQLAlchemy ORM for portability
- Timezone-naive UTC datetimes throughout
- Removed redundant fields for cleaner schema
- JSON columns for flexible data storage

#### 2. API Integration
- BiopharmIQ: 12-hour cache, premium historical endpoint
- Polygon.io: Premium tier with no rate limits
- SEC: 100ms delay between requests, dual API approach

#### 3. Data Management
- Smart incremental updates for stock data
- 5-year initial load, then daily updates
- Always refetch last day for complete data
- Compressed SEC filing storage

#### 4. Error Handling
- Graceful interrupt handling (Ctrl+C)
- Transaction management
- Proper logging throughout

#### 5. Web Application Architecture
- Flask backend with CORS support for API access
- Separate JavaScript modules for main table and detail pages
- RESTful API endpoints for catalyst data and individual catalyst details
- SQLAlchemy joins for efficient sorting across multiple tables
- Rich text parsing for mechanism of action fields
- Responsive CSS grid layout for optimal mobile and desktop viewing

#### 6. Query Module Architecture
- Separate query module (`src/queries/`) for clean separation of business logic from Flask routes
- Chainable query builder pattern for flexible catalyst and company queries
- Filter classes for stage normalization, date ranges, and market cap categories
- Support for complex filters including market cap ranges, stock price ranges, and custom date ranges

## Environment Setup

### Required Environment Variables (.env)

```bash
BIOPHARMA_API_KEY=your_api_key_here
POLYGON_API_KEY=your_polygon_api_key_here
DATABASE_URL=sqlite:///data/catalyst.db
SEC_USER_AGENT=BiotechScanner/1.0 (your.email@example.com)
```

### Python Dependencies

```bash
# Core dependencies
sqlalchemy>=2.0.23
python-dotenv>=1.0.0
requests>=2.31.0
polygon-api-client>=1.12.0
pandas>=2.1.4

# Development dependencies
pytest>=7.4.3
black>=23.12.0
flake8>=6.1.0

# Additional utilities
python-dateutil>=2.8.2
tqdm>=4.66.1
tabulate>=0.9.0
typing-extensions>=4.9.0

# Web application dependencies
flask>=2.3.3
flask-cors>=4.0.0
```

## Data Volume Expectations

- **Drugs**: ~4,500 entries from BiopharmIQ
- **Companies**: ~2,000 biotech companies
- **Stock Data**: 5 years × 250 trading days × 2,000 companies = ~2.5M records
- **Historical Catalysts**: Variable (depends on API data)
- **SEC Filings**: ~20 filings × 2,000 companies = ~40,000 documents
- **Financial Metrics**: ~200 metrics × 10 years × 2,000 companies = ~4M records
- **Storage**: ~10-20GB for full SEC document storage (compressed)

## Future Development Plan

### Phase 1: Query Tools (Next Step)
- Build flexible filtering system for catalysts
- Examples:
  - "Phase 3 catalysts in next 30 days"
  - "FDA approvals with market cap < $500M"
  - "Oncology drugs with upcoming data"
- Sort by date, potential impact, market cap

### Phase 2: AI Research Agent
- Implement tool-calling paradigm
- Tools for:
  - SEC document search
  - Stock price analysis
  - Clinical trial database
  - News search
- RAG pipeline for document retrieval
- Use OpenRouter for LLM flexibility

### Phase 3: Conversational Interface
- Chat interface for follow-up questions
- Context persistence across conversations
- Citation tracking for transparency
- Ability to dive deeper into specific catalysts

### Phase 4: Enhanced Web Interface (COMPLETED)
- ✅ Flask backend with RESTful API endpoints
- ✅ Professional catalyst table interface with search and sorting
- ✅ Detailed catalyst pages with comprehensive information display
- ✅ Responsive design for desktop and mobile viewing

## Migration Notes

### Recent Changes

#### 1. Migrated from Yahoo Finance to Polygon.io
- Better data quality and reliability
- Premium API with no rate limits
- Adjusted close prices by default

#### 2. Removed Opaque Fields
- Removed `is_big_mover`, `is_suspected_mover`, `event_score`
- Removed sector from companies (all biotech)
- Focus on factual data only

#### 3. Timezone Handling
- Switched to timezone-naive UTC throughout
- Prevents SQLite timezone issues
- Simpler datetime comparisons

#### 4. Schema Optimizations
- Removed adjusted_close (using close for adjusted prices)
- Changed created_at to updated_at where appropriate
- Removed redundant timestamp fields

#### 5. Web Application Implementation (COMPLETED)
- Built Flask-based web interface for catalyst viewing
- Implemented professional table layout with search and sort functionality
- Created detailed catalyst view pages with comprehensive drug and market information
- Added rich text parsing for mechanism of action fields
- Implemented clickable navigation between main table and detail pages
- Optimized responsive design for mobile and desktop viewing

#### 6. Advanced Filtering System (COMPLETED)
- Implemented modular query architecture with chainable query builders
- Added market cap range filter with double-ended slider (logarithmic scale)
- Added stock price range filter with double-ended slider (linear scale)
- Implemented custom date range picker with calendar inputs
- Added PDUFA stage filter for FDA action dates
- Created "Reset All Filters" functionality with dynamic enable/disable
- Combined drug name and indication display in single column for cleaner layout

## Web Application Usage

### Starting the Web Application

```bash
# Navigate to webapp directory
cd webapp

# Start the Flask development server
python app.py

# Access the application
# Open browser to: http://127.0.0.1:5678
```

### Web Application Features

#### Main Catalyst Table
- **Search Functionality**: Real-time search across all catalyst fields
- **Column Sorting**: Click column headers to sort by date, ticker, company, market cap, or price
- **Stage Filtering**: Filter catalysts by development stage (Phase 1/2/3, Approved, NDA, PDUFA)
- **Market Cap Filter**: Double-ended slider with custom input boxes for precise range selection
- **Stock Price Filter**: Double-ended slider for filtering by stock price ranges ($0-$1000)
- **Time Range Filter**: Preset options (7/30/60/90/180/365 days) or custom date range picker
- **Combined Drug & Indication Display**: Drug names with indications shown in italics below
- **Reset All Filters**: Button to clear all active filters at once
- **Pagination**: Navigate through large datasets with 25 catalysts per page
- **Clickable Rows**: Click any catalyst row to view detailed information

#### Detail Pages
- **Comprehensive Drug Information**: Name, mechanism of action, development stage, indications
- **Catalyst Event Details**: Date, formatted notes with bold dates, source links
- **Market Information**: Current stock price, market cap, volume, P/E ratio, 52-week range
- **Rich Text Processing**: Clean display of mechanism of action with HTML tag removal
- **Navigation**: Back button to return to main catalyst list

#### API Endpoints
- `GET /`: Main catalyst table interface
- `GET /catalyst/<id>`: Individual catalyst detail page
- `GET /api/catalysts/upcoming`: JSON API for catalyst data with search/sort/pagination
- `GET /api/catalysts/<id>`: JSON API for individual catalyst details
- `GET /api/stats`: Database statistics (currently unused)

## RAG Pipeline for SEC Document Search (COMPLETED)

### Architecture
- **FAISS**: Vector similarity search for 8.5M+ document chunks
- **Product Quantization (PQ)**: 32x compression for memory efficiency
- **On-Demand Text Loading**: Stores file references instead of full text to save memory
- **Sentence-Transformers**: Multiple embedding model options
- **Smart Chunking**: Preserves SEC document structure and context
- **Company-Specific Filtering**: Efficient search within single company's filings

### Key Optimizations
- **Memory Usage**: Reduced from ~15-20GB to ~6GB through:
  - Product Quantization compression (48 subquantizers, 8 bits)
  - Storing file paths + character positions instead of full text
  - On-demand text loading from compressed files
- **Deferred Training**: Accumulates vectors until 40k minimum for optimal index training
- **Company Filtering**: Built-in support for searching specific company filings

### Embedding Models
- **all-MiniLM-L6-v2** (384 dims): Fast general-purpose, good for prototyping
- **S-PubMedBert-MS-MARCO** (768 dims): Biomedical domain specialist
- **Hybrid Approach**: Auto-detects content type for optimal embeddings

### Indexing on RunPod
```bash
# GPU-accelerated indexing with PQ compression
python scripts/runpod_index_all.py --company-limit 500 --pq-bits 8

# Test mode (5 companies)
python scripts/runpod_index_all.py --test

# Resume from previous progress
python scripts/runpod_index_all.py --resume
```

### Search API Usage
```python
from src.rag.rag_search import RAGSearchEngine

engine = RAGSearchEngine()

# General search across all companies
results = engine.search("Phase 3 clinical trial", k=10)

# Company-specific search by ID
results = engine.search("vaccine development", company_id=450, k=10)

# Company-specific search by ticker (new convenience method)
results = engine.search_by_ticker("FDA approval", ticker="MRNA", k=10)

# Combined filters
results = engine.search_by_ticker(
    "revenue guidance",
    ticker="MRNA",
    filing_types=["10-K", "10-Q"],
    k=5
)
```

### Integration with AI Agent
The AI agent's `search_sec_filings` method now:
1. Uses RAG search for semantic understanding
2. Loads text on-demand from compressed filings
3. Supports company-specific filtering for targeted research
4. Returns expanded context windows
5. Falls back to basic search if RAG unavailable

## Next Immediate Steps

1. **Index Existing SEC Filings**
   - Run indexing for top biotech companies
   - Validate search quality with test queries
   - Fine-tune chunking parameters if needed

2. **Performance Optimizations**
   - Add database indexing for frequently queried fields
   - Implement caching for expensive queries
   - Optimize frontend rendering for large datasets

3. **Interactive Chat Interface**
   - Build on existing AI agent architecture
   - Add conversation memory and context
   - Enable follow-up questions about catalysts

## Usage Examples

### Initial Setup

```bash
# Clone repository
git clone [repository]
cd BiotechScanner

# Create virtual environment
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python sync_data.py --status
```

### Daily Workflow

```bash
# Morning sync
python sync_data.py --drugs # Check for new drugs/catalysts
python sync_data.py --stocks # Update stock prices
python sync_data.py --historical # Update historical catalysts

# Query upcoming catalysts (to be implemented)
python query_catalysts.py --days 30 --stage "Phase 3"
```

## Test Suite

All tests are located in the `tests/` directory. The test suite covers database operations, query functionality, and the RAG search pipeline.

### Available Tests

#### Database Tests
- `test_database.py` - Basic database connectivity and model tests
- `test_queries.py` - Query module tests for catalyst and company queries

#### RAG/FAISS Tests
- `test_faiss_index.py` - FAISS index validation including:
  - Index statistics and memory usage
  - PQ compression verification
  - Search functionality
  - Index structure validation

- `test_rag_company_filtering.py` - Company-specific search filtering:
  - Verifies filtering by company_id
  - Tests search_by_ticker convenience method
  - Confirms results isolation to specified company

- `test_rag_catalyst_search.py` - Biotech-specific search validation:
  - Clinical trial endpoints (OS, PFS, ORR)
  - Regulatory milestones (PDUFA, NDA, BLA)
  - Safety and efficacy queries
  - Financial and commercial searches
  - Disease-specific searches

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python tests/test_rag_company_filtering.py

# Run with verbose output
python -m pytest tests/ -v
```

---

This documentation represents the complete current state of the BiotechScanner project with all recent updates and improvements.