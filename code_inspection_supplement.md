# Code Inspection Supplement - Non-Python Files

## Web Assets to Review (7 files)

### JavaScript Files (4)
1. **webapp/static/script.js** - Main table functionality
   - Check for unused event handlers
   - Look for deprecated jQuery/library usage
   - Verify all API endpoints match backend

2. **webapp/static/detail.js** - Catalyst detail page
   - Check if all data fields are displayed
   - Look for duplicate code with script.js
   - Verify error handling

3. **webapp/static/range-slider.js** - Market cap slider
   - Check if component is actually used
   - Look for hardcoded min/max values
   - Verify accessibility

4. **webapp/static/stock-price-slider.js** - Price range slider
   - Check for code duplication with range-slider.js
   - Verify integration with main filters

### CSS Files (1)
5. **webapp/static/style.css** - Application styling
   - Check for unused CSS rules
   - Look for duplicate styles
   - Verify responsive design rules
   - Check for inline styles in HTML that should be moved here

### HTML Templates (2)
6. **webapp/templates/index.html** - Main catalyst table
   - Check for unused JavaScript includes
   - Verify all filter controls are wired up
   - Look for hardcoded text that should be dynamic

7. **webapp/templates/catalyst_detail.html** - Detail view
   - Check if all model fields are displayed
   - Look for unused sections
   - Verify back navigation

## Configuration Files to Review

### Project Configuration
- **.env** - Environment variables
  - Check for unused API keys
  - Verify all keys are documented
  - Look for development vs production settings

- **requirements.txt** - Python dependencies
  - Check for unused packages
  - Look for packages that can be consolidated
  - Verify version pins are appropriate
  - Check for security vulnerabilities

- **.gitignore** - Git ignore patterns
  - Verify all sensitive files are ignored
  - Check for missing patterns

### Documentation Files
- **CLAUDE.md** - Project documentation
  - Check if documentation matches current code
  - Look for outdated sections
  - Verify all features are documented

- **README.md** - If exists, check for accuracy

## Database Files
- **data/catalyst.db** or **data/database.db**
  - Note which one is actually used
  - Check if test databases exist
  - Verify backup strategy

## Quick Checks for Common Issues

### Across All JavaScript Files
```bash
# Find console.log statements (should be removed in production)
grep -n "console\." webapp/static/*.js

# Find hardcoded URLs (should use relative paths or config)
grep -n "http://\|https://" webapp/static/*.js

# Find TODO/FIXME comments
grep -n "TODO\|FIXME\|XXX\|HACK" webapp/static/*.js
```

### For CSS File
```bash
# Find !important declarations (code smell)
grep -n "!important" webapp/static/style.css

# Check for vendor prefixes that might not be needed
grep -n "-webkit-\|-moz-\|-ms-\|-o-" webapp/static/style.css
```

### For HTML Templates
```bash
# Find inline styles (should be in CSS)
grep -n "style=" webapp/templates/*.html

# Find hardcoded URLs
grep -n "http://\|https://" webapp/templates/*.html

# Find TODO comments
grep -n "TODO\|FIXME" webapp/templates/*.html
```

## Dependencies Analysis

### Check for Redundant Packages
Common redundancies to look for in requirements.txt:
- Multiple HTTP libraries (requests, urllib3, httpx)
- Multiple date handling (datetime, dateutil, arrow)
- Multiple config libraries (python-dotenv, configparser)
- Development dependencies in production requirements

### Security Audit
Run after inspection:
```bash
pip install safety
safety check -r requirements.txt
```

## File Size Check
Look for unusually large files that might contain:
- Hardcoded data that should be in database
- Concatenated/minified code that should be split
- Binary data that shouldn't be in repo

```bash
find . -type f -name "*.py" -o -name "*.js" -o -name "*.css" | xargs wc -l | sort -n
```

This supplement covers the non-Python files that should also be reviewed during your code inspection process.