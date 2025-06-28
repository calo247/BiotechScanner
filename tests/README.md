# BiotechScanner Tests

This directory contains all test files for the BiotechScanner project.

## Test Files

### Database Tests
- `test_database.py` - Basic database connectivity and model tests
- `test_queries.py` - Query module tests (catalyst and company queries)

### RAG/FAISS Tests
- `test_faiss_index.py` - Tests for FAISS index with PQ compression
  - Index statistics
  - Memory usage verification
  - Search functionality
  - Index structure validation

- `test_rag_company_filtering.py` - Company-specific search filtering tests
  - Verifies filtering by company_id works correctly
  - Tests the search_by_ticker convenience method
  - Confirms all results are from the specified company

- `test_rag_catalyst_search.py` - Catalyst-specific search tests
  - Tests various biotech-related queries
  - Validates search quality for different categories:
    - Clinical trial endpoints
    - Regulatory milestones
    - Safety and efficacy
    - Financial metrics
    - Disease-specific searches

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python tests/test_rag_company_filtering.py

# Run with verbose output
python -m pytest tests/ -v
```

## Notes

- All tests have been updated to work from the tests/ directory
- Import paths have been fixed to use parent.parent for accessing src modules
- Tests that were timing out or broken have been removed
- The FAISS index must be properly loaded for RAG tests to work