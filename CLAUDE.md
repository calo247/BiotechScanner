# BiotechScanner Project Documentation

## Project Overview

BiotechScanner is a Python-based tool designed to automate the process of searching through biotech stock catalysts for trading opportunities. The tool collects data from multiple sources, stores it in a structured database, and provides AI-powered analysis of potential catalyst events using RAG search and LLM-driven research.

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
- Calculates 3-day price changes for historical catalysts:
  - Uses 3 trading days (not calendar days) after catalyst date
  - Formula: (Price at T+3 close - Price at T+0 close) / Price at T+0 close * 100
  - Stored in `price_change_3d` field (nullable for missing data)
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

#### 5. Web Application Interface (COMPLETED)
- Flask-based web application for catalyst viewing and analysis
- Professional table-based interface with sorting and search functionality
- Detailed catalyst view pages with comprehensive drug and market information
- Real-time search with backend API integration
- Advanced filtering: market cap ranges, stock price ranges, custom date ranges, stage filters
- Clickable catalyst rows for drill-down navigation
- Clean, responsive design optimized for biotech catalyst analysis

#### 6. AI-Powered Catalyst Analysis (COMPLETED)
- LLM-driven research using Claude Sonnet 4 via OpenRouter
- Dynamic SEC filing and press release search
- RAG pipeline with FAISS for searching 8.5M+ document chunks
- Historical catalyst analysis across ALL development stages
- Company track record analysis
- Financial health assessment (cash position, market cap)
- Competitive landscape analysis
- Automated report generation with success probability estimates

#### 7. RAG Search Pipeline (COMPLETED)
- FAISS vector similarity search with Product Quantization compression
- 32x memory reduction through PQ (48 subquantizers, 8 bits)
- On-demand text loading from compressed SEC filings
- Multiple embedding models (all-MiniLM-L6-v2, S-PubMedBert-MS-MARCO)
- Company-specific filtering for targeted searches
- Integrated with AI agent for dynamic research

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
python3 sync_data.py --historical --recalc-prices # Recalculate 3-day price changes

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
- `price_change_3d`: 3-day price change percentage (Float, nullable)
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

### CatalystReport
- `id`: Primary key
- `drug_id`: Foreign key to Drug
- `company_id`: Foreign key to Company
- `report_type`: Type of analysis (default: 'full_analysis')
- `model_used`: LLM model used (default: 'anthropic/claude-sonnet-4')
- `report_markdown`: Full markdown report
- `report_summary`: Brief summary
- `success_probability`: Extracted probability (0-1)
- `price_target_upside`: Upside potential (e.g., "200-400%")
- `price_target_downside`: Downside risk (e.g., "50-80%")
- `recommendation`: Investment recommendation
- `risk_level`: Risk assessment (High/Moderate/Low)
- `analysis_data`: JSON of raw analysis data
- `tokens_used`: Token usage tracking
- `generation_time_ms`: Report generation time
- `created_at`: Timestamp

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
│   ├── ai_agent/
│   │   ├── __init__.py
│   │   ├── catalyst_agent.py
│   │   ├── llm_client.py
│   │   └── tools.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── chunk_sec_filings.py
│   │   ├── embedding_model.py
│   │   ├── faiss_index.py
│   │   └── rag_search.py
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
├── scripts/
│   ├── runpod_index_all.py
│   ├── migrate_historical_catalysts_price_change.py
│   └── migrate_remove_last_update_name.py
├── data/
│   ├── catalyst.db
│   ├── api_responses/
│   │   └── drugs_TIMESTAMP.json
│   ├── sec_filings/
│   │   └── TICKER_CIK/
│   │       ├── 10-K/
│   │       ├── 10-Q/
│   │       └── 8-K/
│   ├── faiss_index/
│   │   ├── faiss_general-fast_pq.index
│   │   └── metadata_general-fast_pq.pkl
│   └── ai_reports/
│       └── {ticker}_{company_id}/
│           └── {catalyst_id}/
│               ├── {timestamp}_report.md
│               ├── {timestamp}_analysis_data.json
│               └── {timestamp}_terminal_log.txt
├── sync_data.py
├── analyze_catalyst.py
├── requirements.txt
└── .env
```

### Key Technical Decisions

#### 1. Database Design
- SQLAlchemy ORM for portability
- Timezone-naive UTC datetimes throughout
- Removed redundant fields for cleaner schema (e.g., last_update_name, revenue metrics)
- JSON columns for flexible data storage
- Added CatalystReport table for AI-generated analyses

#### 2. API Integration
- BiopharmIQ: 12-hour cache, premium historical endpoint
- Polygon.io: Premium tier with no rate limits
- SEC: 100ms delay between requests, dual API approach
- OpenRouter: LLM access for AI analysis with Claude Sonnet 4
- Google Search: Free press release search (no API key required)

#### 3. Data Management
- Smart incremental updates for stock data
- 5-year initial load, then daily updates
- Always refetch last day for complete data
- Compressed SEC filing storage
- 3-day price change calculation for historical catalysts (trading days only)

#### 4. Error Handling
- Graceful interrupt handling (Ctrl+C)
- Transaction management
- Proper logging throughout
- Fallback for companies with non-standard financial reporting

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

#### 7. AI Agent Architecture
- LLM-driven dynamic research with up to 10 iterative searches
- Dual search capability: SEC filings (via FAISS RAG) and press releases (via Google)
- Historical catalyst analysis across ALL development stages (not just matching stages)
- Intelligent search query generation based on context and previous findings
- Comprehensive report generation with success probability estimation

#### 8. RAG Pipeline Design
- FAISS with Product Quantization (PQ) for 32x compression
- On-demand text loading to minimize memory usage (~6GB total)
- Multi-model embeddings (general-purpose vs biomedical)
- Company-specific filtering for targeted searches
- Deferred index training for optimal PQ performance

## Environment Setup

### Required Environment Variables (.env)

```bash
# Required API Keys
BIOPHARMA_API_KEY=your_api_key_here
POLYGON_API_KEY=your_polygon_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Database
DATABASE_URL=sqlite:///data/catalyst.db

# SEC Configuration
SEC_USER_AGENT=BiotechScanner/1.0 (your.email@example.com)

# Optional: SerpAPI for press releases (falls back to free Google search if not set)
SERPAPI_KEY=your_serpapi_key_here
```

### Python Dependencies

```bash
# Core dependencies
sqlalchemy>=2.0.23
python-dotenv>=1.0.0
requests>=2.31.0
polygon-api-client>=1.12.0
pandas>=2.1.4
openai>=1.0.0  # For OpenRouter LLM access
beautifulsoup4>=4.12.0
lxml>=4.9.0

# RAG/FAISS dependencies
faiss-cpu>=1.7.4
sentence-transformers>=2.2.2
numpy>=1.24.0
scikit-learn>=1.3.0

# Web application dependencies
flask>=2.3.3
flask-cors>=4.0.0

# Press release search
googlesearch-python>=1.2.3

# Additional utilities
python-dateutil>=2.8.2
tqdm>=4.66.1
tabulate>=0.9.0
typing-extensions>=4.9.0

# Development dependencies
pytest>=7.4.3
black>=23.12.0
flake8>=6.1.0
```

## Data Volume Expectations

- **Drugs**: ~4,500 entries from BiopharmIQ
- **Companies**: ~2,000 biotech companies
- **Stock Data**: 5 years × 250 trading days × 2,000 companies = ~2.5M records
- **Historical Catalysts**: Variable (depends on API data)
- **SEC Filings**: ~20 filings × 2,000 companies = ~40,000 documents
- **Financial Metrics**: ~200 metrics × 10 years × 2,000 companies = ~4M records
- **Storage**: ~10-20GB for full SEC document storage (compressed)

## Completed Features

### Phase 1: Query Tools (COMPLETED)
- ✅ Advanced filtering system with market cap/price ranges, date filters, stage filters
- ✅ Real-time search across all catalyst fields
- ✅ Flexible sorting by date, ticker, company, market cap, price
- ✅ Clean API integration with web interface

### Phase 2: AI Research Agent (COMPLETED)
- ✅ LLM-driven analysis using Claude Sonnet 4 via OpenRouter
- ✅ Dynamic SEC filing search with FAISS RAG pipeline
- ✅ Press release search via Google (free, no API key required)
- ✅ Historical catalyst analysis with 3-day price changes
- ✅ Comprehensive report generation with success probability
- ✅ Automated report storage in structured folders

### Phase 3: Web Interface (COMPLETED)
- ✅ Professional catalyst table with advanced filtering
- ✅ Detailed catalyst view pages
- ✅ Responsive design for all devices
- ✅ RESTful API for data access

## Future Development Ideas

### Enhanced Analytics
- Portfolio-level catalyst tracking
- Email/SMS alerts for upcoming catalysts
- Historical success rate visualization
- Machine learning for outcome prediction

### Additional Data Sources
- Clinical trial databases (ClinicalTrials.gov)
- FDA calendar integration
- Patent expiration tracking
- Insider trading analysis

### Conversational Interface
- Chat interface for natural language queries
- Follow-up question handling
- Multi-catalyst comparison reports
- Export to PDF/Word formats

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

#### 7. Historical Catalyst Price Analysis
- Replaced announcement timing extraction with 3-day price change calculation
- Removed `announcement_time` and `announcement_timing` columns
- Added `price_change_3d` column to track post-catalyst stock performance
- Calculates percentage change using 3 trading days (not calendar days)
- Added `--recalc-prices` command to recalculate price changes for existing catalysts
- Handles missing stock data gracefully (nullable field)

#### 8. AI Agent Implementation (NEW)
- Built comprehensive catalyst analysis system using LLM
- Dynamic research with up to 10 iterative searches
- Searches both SEC filings (FAISS RAG) and press releases (Google)
- Historical catalyst analysis now includes ALL development stages
- Generates detailed reports with success probability estimates
- Saves reports in structured folder: `data/ai_reports/{ticker}_{company_id}/{catalyst_id}/`

#### 9. Financial Analysis Updates (NEW)
- Removed revenue metrics (misleading for biotech due to grants/milestones)
- Enhanced cash detection for companies with non-standard XBRL reporting
- Better handling of distressed companies with limited financial data
- Focus on cash position and burn rate as key metrics

#### 10. Database Schema Cleanup (NEW)
- Removed `last_update_name` field from Drug model
- Added CatalystReport model for storing AI-generated analyses
- Simplified function names (e.g., `get_historical_success_rate` → `get_historical_catalysts`)

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
The AI agent now uses **LLM-driven dynamic search** with both SEC filings and press releases:

1. **Intelligent Search Loop**: The LLM decides what to search for based on:
   - Initial catalyst context (drug, stage, indication)
   - Previous search findings
   - What information is still missing
   - Whether to search SEC filings or press releases

2. **Adaptive Research**: Each search iteration:
   - LLM generates targeted search query with reasoning
   - LLM chooses search type: "sec" for filings or "press_release" for news
   - For SEC: RAG search finds relevant filing excerpts
   - For Press Releases: Google search finds company announcements
   - LLM analyzes findings and decides next steps
   - Continues until sufficient information gathered (typically 4-6 searches)

3. **Key Features**:
   - **Dual search capability**: SEC filings AND press releases
   - Press releases often have catalyst data before SEC filings
   - Uses semantic RAG search for SEC documents
   - Google search for press releases (with SerpAPI option)
   - Loads text on-demand from compressed filings
   - Company-specific filtering for targeted research
   - Returns expanded context windows
   - **Requires RAG to be available** (no fallback - fails fast if index not loaded)

4. **Press Release Search**:
   - Uses **googlesearch-python** library (FREE - no API key needed)
   - No site restrictions - searches ALL sources including:
     - Company investor relations pages (often the primary source)
     - Traditional PR wire services (GlobeNewswire, PR Newswire, BusinessWire)
     - Biotech news sites (BioSpace, FierceBiotech)
     - Financial news sites (Yahoo Finance, Seeking Alpha)
     - General news outlets
   - Extracts titles, URLs, snippets, and dates
   - Fails fast if library not installed - no fallbacks
   - Broader coverage ensures finding the most recent and detailed information

**Setup (FREE - No API Keys Required)**:
```bash
# Already included in requirements.txt:
pip install googlesearch-python
```

That's it! No configuration needed.

Example search progression:
- Search 1: "OST-HER2 topline results" (press_release) → Find recent announcement
- Search 2: "[Drug name] clinical trial design" (sec) → Get trial details from filings
- Search 3: "primary endpoint efficacy data" (sec) → Get detailed results
- Search 4: "adverse events safety discontinuation" (sec) → Assess safety profile
- Search 5: "FDA feedback regulatory correspondence" (sec) → Check regulatory status
- Search 6: "partnership licensing agreement" (press_release) → Recent deals

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

## AI Catalyst Analysis

### Running Catalyst Analysis

```bash
# List upcoming catalysts
python analyze_catalyst.py --list --days 30

# Analyze specific catalyst by ID
python analyze_catalyst.py --id 3115

# Analyze catalysts for specific company
python analyze_catalyst.py --ticker SAVA

# Interactive mode (default)
python analyze_catalyst.py
```

### Analysis Process

The AI agent performs comprehensive research:

1. **Historical Analysis**: Searches for similar catalysts across ALL development stages
2. **Company Track Record**: Analyzes company's previous catalyst outcomes
3. **Financial Health**: Assesses cash position and burn rate
4. **SEC Filing Research**: Dynamic LLM-driven search through indexed filings
5. **Press Release Search**: Finds recent announcements via Google
6. **Competitive Landscape**: Identifies competing drugs in same indication
7. **Report Generation**: Creates detailed analysis with success probability

### Report Storage

The `analyze_catalyst.py` script automatically saves all outputs in a structured folder format:

```
data/
  ai_reports/
    {ticker}_{company_id}/
      {catalyst_id}/
        {YYYYMMDD_HHMMSS}_report.md           # The full markdown report (public)
        {YYYYMMDD_HHMMSS}_analysis_data.json  # Raw analysis data and stats
        {YYYYMMDD_HHMMSS}_terminal_log.txt    # Complete terminal output
```

Example:
```
data/
  ai_reports/
    OSTX_511/
      3025/
        20250627_143052_report.md         # Clean public report
        20250627_143052_analysis_data.json # Structured data
        20250627_143052_terminal_log.txt  # Full workflow log
```

This structure allows you to:
- Keep all related files together in one location
- Track all analyses for a specific company
- Compare multiple analyses of the same catalyst over time
- Access the clean public report, raw data, and complete workflow
- Maintain a complete audit trail of all catalyst analyses

### Report Contents

- **report.md**: Clean, professional catalyst analysis including:
  - Executive summary with success probability
  - Historical precedent analysis
  - Company track record assessment
  - Financial runway analysis
  - Key risks and opportunities
  - Investment recommendation with rationale
  
- **analysis_data.json**: Structured data including:
  - All historical catalysts analyzed
  - SEC filing search results
  - Press release findings
  - Search statistics and iterations
  - Financial metrics
  
- **terminal_log.txt**: Complete workflow including:
  - All search queries and reasoning
  - Full search results
  - LLM decision-making process
  - Performance statistics

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

### Press Release Search Testing

Test the press release search functionality with various scenarios:

```bash
# Test multiple companies with different search scenarios
python test_press_releases.py

# Test specific company with custom search terms
python test_press_releases.py ABBV pipeline update results
python test_press_releases.py MRNA vaccine efficacy data
python test_press_releases.py BIIB Alzheimer Leqembi approval
```

The test script shows:
- Number of results found
- Distribution of results by domain (company sites vs news sites vs PR wires)
- Top 5 results with titles, URLs, dates, and snippets
- Helps verify search coverage across different source types

---

This documentation represents the complete current state of the BiotechScanner project with all recent updates and improvements.