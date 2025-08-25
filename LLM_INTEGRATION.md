# LLM Integration Architecture

This document explains the LLM integration added to the deprecations scraper to improve content quality while minimizing API costs.

## Overview

The system now uses Anthropic's Claude API to enhance scraped deprecation notices, making them more readable and informative for RSS feed consumers.

## Key Design Principles

1. **Simplicity**: Minimal code changes to existing workflow
2. **Token Efficiency**: Only call LLM when content actually changes
3. **Fail-Safe**: Falls back to original scraped content if LLM fails
4. **Cost Control**: Uses efficient Claude Haiku model and batching

## Architecture Components

### 1. Change Detection (`change_detector.py`)

- **Purpose**: Minimize LLM API calls by detecting content changes
- **Mechanism**: SHA-256 hashing of key content fields
- **Cache**: Stores content hashes and LLM analysis results
- **Benefits**: Avoids redundant API calls, saves costs

### 2. LLM Analysis (`llm_analyzer.py`)

- **Model**: Claude 3 Haiku (fast, cost-effective)
- **Batch Size**: 3 items per batch to optimize token usage
- **Timeout**: 30 seconds with proper error handling
- **Output**: Improved titles, cleaner content, standardized dates

### 3. Integration (`main.py`)

- **Environment**: Requires `ANTHROPIC_API_KEY` or `ANTHROPIC_API_TOKEN`
- **Workflow**: Scrape → Detect Changes → Analyze with LLM → Cache Results → Save Data
- **Graceful Degradation**: Works without API key, just skips enhancement

## Configuration

### Environment Variables

The system looks for either:
- `ANTHROPIC_API_KEY` 
- `ANTHROPIC_API_TOKEN`

Load from `~/.env` file:
```bash
ANTHROPIC_API_TOKEN=sk-ant-api03-...
```

### Files Generated

- `data_cache.json`: Content hashes and LLM analysis cache (gitignored)
- `data.json`: Enhanced deprecation data with `llm_enhanced` flags

## Token Usage Optimization

1. **Change Detection**: Only analyze changed content
2. **Batch Processing**: Process up to 3 items per API call
3. **Content Limiting**: Truncate input content to 800 characters
4. **Token Limits**: Conservative 1000 token response limit
5. **Efficient Model**: Claude Haiku for speed and cost

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

- **Missing API Key**: Gracefully skips LLM enhancement
- **API Failures**: Falls back to original scraped content
- **Malformed Responses**: Uses original content, logs error
- **Network Issues**: Continues with cached or original content

## Cost Estimation

With 50-60 deprecation notices and typical change rates:

- **First run**: ~$0.10-0.20 (all items analyzed)
- **Subsequent runs**: ~$0.01-0.05 (only changed items)
- **Daily cost**: Usually under $0.05 due to change detection

## Testing

Run complete workflow:
```bash
uv run python main.py
```

Test without API key:
```bash
unset ANTHROPIC_API_KEY ANTHROPIC_API_TOKEN
uv run python main.py
```

## Benefits

1. **Improved UX**: More readable titles and content in RSS feeds
2. **Cost Efficient**: Change detection minimizes API calls
3. **Reliable**: Graceful fallbacks ensure system always works
4. **Simple**: Minimal changes to existing codebase
5. **Maintainable**: Clear separation of concerns