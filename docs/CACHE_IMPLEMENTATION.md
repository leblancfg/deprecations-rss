# Cache Implementation Documentation

## Overview

The caching system provides persistent storage for deprecation data with automatic fallback support when scraping fails. It includes both local filesystem storage for development and GitHub Actions cache integration for CI/CD.

## Architecture

### Storage Backends

#### 1. FileSystemStorage
- **Purpose**: Local development and testing
- **Location**: `.cache/deprecations/` directory
- **Features**:
  - TTL-based expiration
  - Metadata tracking
  - Atomic operations
  - Pattern-based key listing

#### 2. GitHubActionsStorage
- **Purpose**: CI/CD persistence between workflow runs
- **Location**: `.github-cache/deprecations/` in GitHub workspace
- **Features**:
  - Extends FileSystemStorage
  - State file tracking
  - GitHub Actions cache key generation
  - Cache restoration across workflow runs

### Cache Manager

The `CacheManager` class provides high-level caching operations:
- Automatic storage backend selection based on environment
- Fallback to stale data when fresh data fetching fails
- Provider-specific deprecation data management
- Historical data retrieval with configurable max age

## Usage

### Basic Cache Operations

```python
from src.cache import CacheManager

# Initialize with automatic backend selection
manager = CacheManager()

# Save deprecation data
data = {"models": ["gpt-3", "davinci"], "deprecation_date": "2024-01-04"}
await manager.save_deprecation_data("openai", data)

# Retrieve deprecation data
cached_data = await manager.get_deprecation_data("openai")

# Get all providers' data
all_data = await manager.get_all_providers_data()
```

### Cache with Fallback

```python
async def fetch_fresh_data():
    # Scraper logic here
    return scraper.fetch_deprecations()

# Get data with automatic fallback to cache if scraping fails
data = await manager.get_with_fallback(
    key="deprecations:openai:2024-01-15",
    fetch_func=fetch_fresh_data,
    ttl=86400,  # 24 hours
    use_stale_on_error=True
)
```

### CLI Commands

```bash
# Update deprecation data with cache support
python -m src.cache.cli update

# Load cached data when scraping fails
python -m src.cache.cli fallback

# Check cache status
python -m src.cache.cli status

# Clear cache (with confirmation)
python -m src.cache.cli clear --confirm
```

## GitHub Actions Integration

### Workflow Configuration

The `daily-update.yml` workflow includes:

1. **Cache Restoration**:
   - Attempts to restore cache from previous runs
   - Uses date-based keys with fallback to older caches

2. **Scraping with Fallback**:
   - Runs scrapers to fetch fresh data
   - Falls back to cached data if scraping fails

3. **Cache Saving**:
   - Saves updated cache for next run
   - Maintains cache across workflow executions

### Cache Keys

Cache keys follow this pattern:
```
deprecations-cache-v1-YYYY-MM-DD
```

With restore keys for fallback:
```
deprecations-cache-v1-YYYY-MM-
deprecations-cache-v1-YYYY-
deprecations-cache-v1-
```

## Storage Format

### Cache Entry Structure

```json
{
    "data": {...},
    "created_at": "2024-01-15T10:00:00Z",
    "ttl": 86400
}
```

### Deprecation Data Structure

```json
{
    "provider": "openai",
    "date": "2024-01-15T00:00:00Z",
    "data": {
        "models": ["gpt-3", "davinci"],
        "deprecation_date": "2024-01-04"
    },
    "scraped_at": "2024-01-15T10:00:00Z"
}
```

### GitHub Actions State File

```json
{
    "version": "1.0.0",
    "created_at": "2024-01-15T00:00:00Z",
    "last_updated": "2024-01-15T10:00:00Z",
    "entries": {
        "deprecations:openai:2024-01-15": {
            "added_at": "2024-01-15T10:00:00Z",
            "status": "active"
        }
    }
}
```

## Testing

### Unit Tests

```bash
# Run storage backend tests
pytest tests/unit/cache/test_storage_backends.py

# Run cache manager tests  
pytest tests/unit/cache/test_cache_manager.py
```

### Integration Tests

```bash
# Run complete cache workflow tests
pytest tests/integration/test_cache_integration.py
```

## Configuration

### Environment Variables

- `GITHUB_ACTIONS`: Set to "true" in GitHub Actions environment
- `GITHUB_WORKSPACE`: GitHub workspace directory path
- `CACHE_FALLBACK`: Enable fallback to cached data

### Cache Settings

- **Default TTL**: 24 hours (86400 seconds)
- **Deprecation Data TTL**: 48 hours (172800 seconds)
- **Max Age for Historical Data**: 7 days
- **Cache Directory**: `.cache/deprecations/` (local) or `.github-cache/deprecations/` (CI)

## Error Handling

The cache system handles failures gracefully:

1. **Scraping Failures**: Automatically falls back to cached data
2. **Cache Miss**: Returns None, allowing scraper to fetch fresh data
3. **Expired Data**: Automatically cleaned up on access
4. **Storage Errors**: Logged but don't break the application

## Performance Considerations

- **Async I/O**: All operations are async for non-blocking execution
- **File-based Storage**: Suitable for moderate data volumes
- **Metadata Caching**: Separate metadata files for quick lookups
- **Pattern Matching**: Efficient key listing with glob patterns

## Future Enhancements

Potential improvements for the caching system:

1. **Redis Backend**: Add Redis storage for production deployments
2. **Compression**: Compress cached data to reduce storage size
3. **Metrics**: Add cache hit/miss ratio tracking
4. **Partial Updates**: Support incremental cache updates
5. **S3 Backend**: Add AWS S3 storage for cloud deployments