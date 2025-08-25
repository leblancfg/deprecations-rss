# LLM Integration Architecture

This document explains the LLM integration added to the deprecations scraper to improve content quality while minimizing API costs.

## Overview

The system uses Anthropic's Claude API to enhance scraped deprecation notices, making them more readable and informative for RSS feed consumers.

## Key Design Principles

1. **Simplicity**: Minimal code changes to existing workflow
2. **Token Efficiency**: Only call LLM when scraped content actually changes
3. **Fail-Fast**: Required API key - fails immediately if missing/invalid
4. **Git-Based State**: Uses git history instead of cache files

## Architecture Components

### 1. Change Detection (`change_detector.py`)

- **Purpose**: Minimize LLM API calls by detecting content changes
- **Mechanism**: SHA-256 hashing of scraped content fields (before LLM enhancement)
- **State Storage**: Compares with `git show main:data.json` 
- **Benefits**: Avoids redundant API calls, no extra files needed

### 2. LLM Analysis (`llm_analyzer.py`)

- **Model**: Claude 3 Haiku (fast, cost-effective)
- **API Validation**: Tests key with minimal token usage at startup
- **Batch Size**: 3 items per batch to optimize token usage
- **Fail-Fast**: Exits immediately on invalid API key

### 3. Integration (`main.py`)

- **Environment**: **Requires** `ANTHROPIC_API_KEY` or `ANTHROPIC_API_TOKEN`
- **Workflow**: Scrape → Detect Changes → Validate API → Analyze → Save Data
- **No Degradation**: Fails completely if API key missing/invalid

## Configuration

### Environment Variables

**Required** - one of:
- `ANTHROPIC_API_KEY` 
- `ANTHROPIC_API_TOKEN`

Load from `~/.env` file:
```bash
ANTHROPIC_API_TOKEN=sk-ant-api03-...
```

### State Management

- **Previous state**: Retrieved via `git show main:data.json`
- **Current state**: `data.json` with enhanced content
- **No cache files**: Uses git as the "database"

## Token Usage Optimization

1. **Hash-Based Detection**: Only analyze items with changed scraped content
2. **Git Comparison**: No need for separate cache files
3. **Batch Processing**: Process up to 3 items per API call
4. **Content Limiting**: Truncate input content to 800 characters
5. **Upfront Validation**: 1 token test to validate API key

## Example Enhancement

**Before (scraped)**:
```
Title: "OpenAI: gpt-4o-realtime-preview-2024-10-01"
Content: "On June 10th, 2025, we notified developers using gpt-4o-realtime-preview-2024-10-01 of its deprecation and removal from the API in three months. SHUTDOWN DATE	MODEL / SYSTEM	RECOMMENDED REPLACEMENT 2025-09-10	gpt-4o-realtime-preview-2024-10-01	gpt-4o-realtime-preview"
```

**After (LLM enhanced)**:
```
Title: "OpenAI to deprecate gpt-4o-realtime-preview-2024-10-01"
Content: "OpenAI will deprecate the gpt-4o-realtime-preview-2024-10-01 model and replace it with the gpt-4o-realtime-preview model. Shutdown date: 2025-09-10."
```

## Error Handling

- **Missing API Key**: Process exits immediately with clear error message
- **Invalid API Key**: Fails fast during initialization with 1-token test
- **API Failures**: Process exits - no degraded state
- **Git Errors**: First run treats as "all items changed"

## Cost Estimation

With 50-60 deprecation notices and typical change rates:

- **First run**: ~$0.10-0.20 (all items analyzed) + 1 token validation
- **Subsequent runs**: ~$0.01-0.05 (only changed items)  
- **Daily cost**: Usually under $0.05 due to hash-based change detection

## Testing

Run complete workflow (requires API key):
```bash
uv run python main.py
```

Test API key validation:
```bash
export ANTHROPIC_API_TOKEN=invalid_key
uv run python main.py  # Should fail immediately
```

## Benefits

1. **Improved UX**: More readable titles and content in RSS feeds
2. **Cost Efficient**: Hash-based change detection minimizes API calls  
3. **Reliable**: Fail-fast behavior - either works properly or fails clearly
4. **Simple**: Git-based state, no cache files
5. **Maintainable**: Clear separation of concerns, minimal complexity