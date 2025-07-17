# BiotechScanner Code Inspection Plan

## Overview
This document provides a systematic approach to inspect all 49 Python files in the BiotechScanner project for unused and old code. Files are organized by inspection priority and logical groupings.

## Inspection Checklist for Each File

### General Checklist Items:
- [ ] Check for unused imports
- [ ] Identify unused functions/classes
- [ ] Look for commented-out code blocks
- [ ] Check for TODO/FIXME/HACK comments
- [ ] Verify if file is still needed
- [ ] Check for duplicate functionality
- [ ] Review code style consistency
- [ ] Check for hardcoded values that should be config
- [ ] Identify deprecated patterns/libraries
- [ ] Check for proper error handling

### Additional Items by File Type:
- **API Clients**: Check if all endpoints are used
- **Database Models**: Check for unused fields/relationships
- **Scripts**: Verify if still needed/working
- **Tests**: Check if tests still pass and cover current code
- **Utils**: Check if utilities are actually used

---

## Inspection Order by Priority

### Phase 1: Entry Points and Main Scripts (4 files)
These are the main entry points - inspect first to understand current usage patterns.

1. **sync_data.py** - Main data synchronization script
   - Check which sync options are actually used
   - Verify all command-line arguments are documented

2. **analyze_catalyst.py** - AI catalyst analysis interface
   - Check if all analysis features are used
   - Review report generation logic

3. **fetch_raw_data.py** - Raw data fetching utility
   - Determine if this duplicates sync_data.py functionality
   - Check if still needed

4. **view_reports.py** - Report viewing utility
   - Check if this is used given the web interface exists

### Phase 2: Core Database Layer (3 files)
Critical for understanding data structure and dependencies.

5. **src/database/models.py** - All SQLAlchemy models
   - Check for unused fields in each model
   - Look for deprecated models
   - Verify all relationships are used

6. **src/database/database.py** - Database initialization
   - Check connection handling
   - Look for unused utility functions

7. **src/database/__init__.py** - Package initialization
   - Verify exports are correct

### Phase 3: Data Collection & APIs (8 files)
Review API integrations for unused endpoints and outdated code.

8. **src/data_sync.py** - Core synchronization logic
   - Check for unused sync methods
   - Look for duplicate functionality with scripts

9. **src/api_clients/biopharma_client.py** - BiopharmIQ API
   - Check for unused endpoints
   - Verify rate limiting logic

10. **src/api_clients/polygon_client.py** - Stock data API
    - Check if all data fields are used
    - Look for Yahoo Finance remnants

11. **src/api_clients/sec_client.py** - SEC EDGAR API
    - Check for unused filing types
    - Verify parsing logic is current

12. **src/api_clients/__init__.py** - Package initialization

13. **src/config.py** - Configuration management
    - Check for unused config variables
    - Look for hardcoded values elsewhere

14. **src/__init__.py** - Package initialization

15. **src/models/__init__.py** - Legacy models package?
    - Check if this entire directory is obsolete

### Phase 4: Web Application (1 file)
Review the Flask application for unused routes and features.

16. **webapp/app.py** - Flask web application
    - Check for unused API endpoints
    - Verify all routes are documented
    - Look for deprecated features

### Phase 5: Query Builders (4 files)
Review query logic for unused filters and methods.

17. **src/queries/catalyst_queries.py** - Catalyst queries
    - Check for unused query methods
    - Look for duplicate query logic

18. **src/queries/company_queries.py** - Company queries
    - Verify all methods are used
    - Check for overlap with catalyst queries

19. **src/queries/filters.py** - Query filters
    - Check which filters are actually used
    - Look for deprecated filter types

20. **src/queries/__init__.py** - Package initialization

### Phase 6: AI Agent & RAG (12 files)
Review AI components for unused features and old implementations.

21. **src/ai_agent/catalyst_agent.py** - Main AI agent
    - Check for unused analysis methods
    - Review report generation logic

22. **src/ai_agent/llm_client.py** - LLM integration
    - Check for unused models/endpoints
    - Verify error handling

23. **src/ai_agent/llm_driven_search.py** - Dynamic search
    - Check if all search strategies are used
    - Look for duplicate search logic

24. **src/ai_agent/tools.py** - Agent tools
    - Check which tools are actually used
    - Look for deprecated tools

25. **src/ai_agent/enhanced_search_tools.py** - Enhanced tools
    - Determine overlap with tools.py
    - Check if consolidation needed

26. **src/ai_agent/__init__.py** - Package initialization

27. **src/rag/rag_search.py** - Main RAG search
    - Check for unused search methods
    - Verify index compatibility

28. **src/rag/faiss_index.py** - FAISS index management
    - Check for unused index operations
    - Look for deprecated methods

29. **src/rag/embeddings.py** - Embedding models
    - Check which models are actually used
    - Look for unused embedding methods

30. **src/rag/document_processor.py** - Document processing
    - Check for unused processors
    - Verify chunking logic

31. **src/rag/ticker_search.py** - Ticker-specific search
    - Check overlap with main search
    - Determine if needed

32. **src/rag/__init__.py** - Package initialization

### Phase 7: Utility Scripts (4 files)
Review standalone scripts for current relevance.

33. **scripts/runpod_index_all.py** - GPU indexing script
    - Check if still compatible with current index
    - Verify RunPod integration

34. **scripts/download_all_sec_filings.py** - SEC download script
    - Check overlap with sync_data.py
    - Determine if still needed

35. **scripts/test_gpu_indexing.py** - GPU testing script
    - Check if tests are current
    - Verify GPU detection logic

36. **scripts/drop_old_indication_columns.py** - Migration script
    - Check if migration already completed
    - Can likely be archived/removed

### Phase 8: Utils Package (1 file)
Check utility functions usage.

37. **src/utils/__init__.py** - Utils package
    - Check if utils package has any actual utilities
    - May be completely unused

### Phase 9: Test Suite (12 files)
Review tests for coverage and relevance.

38. **tests/__init__.py** - Test package initialization

39. **tests/test_database.py** - Database tests
    - Check if tests still pass
    - Look for missing model tests

40. **tests/test_queries.py** - Query tests
    - Verify query coverage
    - Check for deprecated queries

41. **tests/test_faiss_index.py** - FAISS tests
    - Check index compatibility
    - Verify test data

42. **tests/test_rag_company_filtering.py** - RAG filtering tests
    - Check coverage of filters
    - Verify test scenarios

43. **tests/test_rag_catalyst_search.py** - Catalyst search tests
    - Check search scenarios
    - Verify expected results

44. **tests/test_historical_price_change.py** - Price analysis tests
    - Check calculation accuracy
    - Verify data sources

45. **tests/test_press_releases.py** - Press release tests
    - Check if search still works
    - Verify test companies

46. **tests/test_rag_verification.py** - RAG verification tests
    - Check what this verifies
    - Determine if redundant

47. **tests/test_polygon_data.py** - Polygon API tests
    - Check API compatibility
    - Verify test coverage

48. **tests/test_create_report.py** - Report generation tests
    - Check report format
    - Verify all sections tested

49. **tests/test_llm_integration.py** - LLM integration tests
    - Check API compatibility
    - Verify mock responses

---

## Tracking Template

Create a tracking document with this format for each file:

```
File: [filename]
Status: [ ] Not Started [ ] In Progress [ ] Complete
Still Needed: [ ] Yes [ ] No [ ] Partially
Unused Imports: 
Unused Functions/Classes:
Commented Code Blocks:
TODOs/FIXMEs:
Recommended Actions:
Notes:
```

---

## Summary Statistics

- **Total Files**: 49
- **Entry Points**: 4
- **Core Source**: 15
- **Web App**: 1
- **AI/RAG**: 12
- **Scripts**: 4
- **Tests**: 12
- **Init Files**: 9

## Next Steps

1. Start with Phase 1 (entry points) to understand current usage
2. Use findings from each phase to inform inspection of related files
3. Create a summary document listing:
   - Files that can be deleted
   - Functions/classes that can be removed
   - Code that needs refactoring
   - Dependencies that can be updated
4. Plan refactoring in stages to maintain functionality