# AI Deprecations RSS

Never miss an AI model shutdown again. This is a simple RSS feed that tracks deprecation announcements from major AI providers.

## The Feed

```
https://leblancfg.com/deprecations-rss/rss/v1/feed.xml
```

Add this to your RSS reader and you'll get notified when OpenAI, Anthropic, Google, AWS, or Cohere announce they're shutting down a model.

## How to Use It

### With Feedly
1. Open Feedly and click the "+" button
2. Paste the RSS feed URL
3. Click "Follow"

### Get Email Alerts
Use [Blogtrottr](https://blogtrottr.com) or [FeedRabbit](https://feedrabbit.com):
1. Sign up
2. Add our RSS feed URL
3. Choose how often you want emails

### Slack Notifications
```
/feed subscribe https://leblancfg.com/deprecations-rss/rss/v1/feed.xml
```

### In Your Code
```python
import feedparser
feed = feedparser.parse('https://leblancfg.com/deprecations-rss/rss/v1/feed.xml')
for entry in feed.entries:
    print(f"{entry.title}: {entry.description}")
```

## What We Track

We check these pages daily:
- [OpenAI Deprecations](https://platform.openai.com/docs/deprecations)
- [Anthropic Model Deprecations](https://docs.anthropic.com/en/docs/about-claude/model-deprecations)
- [Google Vertex AI Deprecations](https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations)
- [AWS Bedrock Model Lifecycle](https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html)
- [Cohere Deprecations](https://docs.cohere.com/docs/deprecations)

## Why This Exists

AI providers deprecate models regularly, sometimes with just a few months notice. If you're not checking their docs constantly, you might miss an announcement and have your app break. This feed does the checking for you.

## How It Works

1. GitHub Actions runs daily at 2 AM UTC
2. Scrapes each provider's deprecation page
3. Extracts individual deprecation notices
4. Updates the RSS feed
5. You get notified in your RSS reader

Simple as that. No authentication needed, no API keys, just an RSS feed.

## Development

It's ~250 lines of Python that scrapes deprecation pages and generates an RSS feed.

```bash
# Install dependencies
uv sync

# Run the scraper
uv run python main.py

# Generate RSS
uv run python rss_gen.py
```

## Contributing

Found a bug? Provider changed their page format? Open an issue or PR.

## License

MIT