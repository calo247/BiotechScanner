# OpenRouter Setup Guide

## Overview

BiotechScanner uses OpenRouter with Claude Sonnet 4 for intelligent catalyst analysis. This model provides the best balance of capability, cost, and performance for analyzing biotech catalysts.

## Quick Start

1. **Sign up for OpenRouter**
   - Go to https://openrouter.ai/
   - Create an account (you can use Google/GitHub for quick signup)

2. **Get your API key**
   - Visit https://openrouter.ai/keys
   - Click "Create Key"
   - Copy the key (starts with `sk-or-v1-`)

3. **Add to your .env file**
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   ```

4. **Add credits**
   - Go to https://openrouter.ai/credits
   - Add at least $5 to get started
   - Claude Sonnet 4 costs ~$3 per million input tokens

## Model Details

**Claude Sonnet 4** 
- Claude's latest and most capable Sonnet model
- Excellent at understanding medical/scientific content
- Superior report writing and synthesis capabilities
- 200K context window - can analyze multiple SEC filings at once
- ~$3/1M input tokens, $15/1M output tokens

## Usage Examples

```bash
# Analyze a specific catalyst
python3 analyze_catalyst.py --id 231

# Analyze catalysts for a specific company
python3 analyze_catalyst.py --ticker BHVN

# List upcoming catalysts
python3 analyze_catalyst.py --list --days 60
```

## Cost Estimation

For a typical catalyst analysis:
- Input: ~2,000 tokens (all the gathered data)
- Output: ~1,000 tokens (the analysis report)
- **Cost per analysis: ~$0.02 (2 cents)**

With $5 in credits, you can analyze approximately 250 catalysts.

## Troubleshooting

### "No auth credentials found"
- Check that your API key is correctly set in `.env`
- Make sure the key starts with `sk-or-v1-`

### "Insufficient credits"
- Add credits at https://openrouter.ai/credits
- Minimum $5 recommended to start

### "Please replace the placeholder API key"
- You need to replace `your_openrouter_api_key_here` with your actual API key

## Privacy & Security

- Your API key is stored locally in `.env` (never committed to git)
- All analysis is done via API - no data is stored by OpenRouter
- Use environment variables or secure key management in production