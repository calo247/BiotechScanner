# BiotechScanner Code Inspection Tracking

Use this template to track inspection progress for each file. Copy the template for each file you inspect.

## File Inspection Template

```markdown
### File: [Full Path]
- **Status**: ☐ Not Started | ☐ In Progress | ☐ Complete
- **Inspection Date**: 
- **Inspector**: 
- **File Size**: [lines of code]
- **Last Modified**: 

#### Assessment
- **Still Needed**: ☐ Yes | ☐ No | ☐ Partially
- **Reason**: 

#### Findings

**Unused Imports**: 
```python
# List unused imports here
```

**Unused Functions/Classes**:
```python
# List unused functions/classes with line numbers
```

**Commented/Dead Code**:
```python
# List blocks of commented code with line numbers
```

**TODOs/FIXMEs/HACKs**:
- Line X: TODO: [description]
- Line Y: FIXME: [description]

**Hardcoded Values**:
- Line X: [value] - should be in config
- Line Y: [value] - should be parameterized

**Deprecated Patterns**:
- [Pattern description and location]

**Duplicate Functionality**:
- Duplicates functionality in: [other file]
- Description: 

**Dependencies**:
- Uses deprecated library: [library name]
- Could use standard library instead of: [library name]

#### Recommended Actions
- [ ] Remove unused imports
- [ ] Delete unused functions: [list]
- [ ] Remove commented code blocks
- [ ] Address TODOs
- [ ] Move hardcoded values to config
- [ ] Refactor to remove duplication
- [ ] Update deprecated patterns
- [ ] Other: [specify]

#### Notes
[Any additional observations or context]

---
```

## Quick Reference Checklists by File Type

### Entry Point Scripts (sync_data.py, analyze_catalyst.py, etc.)
- [ ] All command-line arguments documented and used?
- [ ] Help text accurate and complete?
- [ ] All imported modules actually used?
- [ ] Error handling comprehensive?
- [ ] Logging appropriate?

### API Clients
- [ ] All API endpoints defined are actually called?
- [ ] Rate limiting logic still needed?
- [ ] Error handling for all API responses?
- [ ] Retry logic appropriate?
- [ ] API keys properly handled?
- [ ] Response caching working correctly?

### Database Models
- [ ] All model fields used in queries?
- [ ] All relationships utilized?
- [ ] Indexes appropriate for query patterns?
- [ ] Migration scripts needed for changes?
- [ ] Default values sensible?

### Query Builders
- [ ] All query methods called somewhere?
- [ ] Filters all accessible from API/CLI?
- [ ] Query optimization possible?
- [ ] Duplicate query logic?

### Web Application
- [ ] All routes documented?
- [ ] All endpoints used by frontend?
- [ ] Proper error responses?
- [ ] CORS configuration appropriate?
- [ ] Security headers present?

### AI/RAG Components
- [ ] All search methods utilized?
- [ ] Embedding models all needed?
- [ ] Index operations efficient?
- [ ] Memory usage optimized?
- [ ] Error handling for LLM failures?

### Tests
- [ ] Tests still pass?
- [ ] Test coverage adequate?
- [ ] Mock data up to date?
- [ ] Testing current functionality?
- [ ] Performance tests needed?

## Summary Tracking

### Files by Status
- **Not Started**: 49/49
- **In Progress**: 0/49
- **Complete**: 0/49

### Files Marked for Removal
1. [List files that can be deleted]

### Major Refactoring Needed
1. [List files needing significant work]

### Quick Wins (Easy Cleanup)
1. [List files with simple cleanup tasks]

## Action Items Summary

### Immediate Actions
- [ ] Remove files: [list]
- [ ] Delete unused functions in: [list]
- [ ] Update deprecated code in: [list]

### Medium-term Refactoring
- [ ] Consolidate duplicate functionality between: [files]
- [ ] Modernize patterns in: [files]
- [ ] Add missing tests for: [files]

### Long-term Improvements
- [ ] Architecture changes: [describe]
- [ ] Performance optimizations: [describe]
- [ ] Documentation updates: [describe]