# AI Model Deprecations RSS Feed

[![Daily Update](https://github.com/leblancfg/deprecations-rss/actions/workflows/daily-update.yml/badge.svg)](https://github.com/leblancfg/deprecations-rss/actions/workflows/daily-update.yml)
[![RSS Valid](https://img.shields.io/badge/RSS-Valid-orange)](https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml)

A daily-updated RSS feed tracking AI model deprecations across major providers. Enterprise-grade reliability for production systems that depend on AI models.

## 🔗 Quick Links

- **RSS Feed**: https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml
- **Web Dashboard**: https://leblancfg.github.io/deprecations-rss/
- **Subscribe**: [Add to your RSS reader](#subscribing-to-the-feed)

## 📊 Coverage

### Tier 1 Providers (Priority)
- **OpenAI** - GPT models, API deprecations
- **Anthropic** - Claude model retirements

### Tier 2 Providers
- **Google Vertex AI** - Gemini, Imagen, MedLM deprecations
- **AWS Bedrock** - Model lifecycle and EOL dates
- **Cohere** - Command and Embed model deprecations
- **Azure OpenAI** - Service-specific retirement schedules

## 🚀 Features

- **Daily Updates**: Automated scraping runs every 24 hours
- **Historical Tracking**: Maintains past deprecation notices for future dates
- **Reliability**: Graceful degradation if individual providers are unavailable
- **Speed**: Complete update cycle in <60 seconds
- **Static Hosting**: No backend required, served via GitHub Pages
- **Versioned API**: RSS feed at `/rss/v1/feed.xml` for stability

## 📖 Subscribing to the Feed

Add this URL to your RSS reader:
```
https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml
```

### Popular RSS Readers
- **Feedly**: Click the "+" button and paste the URL
- **Inoreader**: Add subscription → Enter RSS feed URL
- **NewsBlur**: Add Site → Enter URL
- **Slack**: `/feed subscribe https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml`
- **Microsoft Teams**: Use the RSS connector in Power Automate

### Programmatic Access
```python
import feedparser
feed = feedparser.parse('https://leblancfg.github.io/deprecations-rss/rss/v1/feed.xml')
for entry in feed.entries:
    print(f"{entry.title} - {entry.published}")
```

## 🏗️ Architecture

- **Scraping**: Parallel collection from all providers
- **Caching**: 23-hour cache to minimize requests
- **Storage**: Historical data in JSON format
- **Generation**: Static site rebuilt after each update
- **Hosting**: GitHub Pages with automatic deployment

## 🧪 Development

### Prerequisites
- Python 3.13+
- GitHub account with Pages enabled

### Setup
```bash
# Clone the repository
git clone https://github.com/leblancfg/deprecations-rss.git
cd deprecations-rss

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run scrapers locally
python -m src.scrapers.run_all
```

### Testing
We use pytest with pytest-describe for BDD-style testing:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_openai_scraper.py
```

## 📊 Data Format

Each deprecation entry contains:
- **provider**: Source of the deprecation (e.g., "OpenAI", "Anthropic")
- **model**: Affected model name
- **deprecation_date**: When the deprecation was announced
- **retirement_date**: When the model stops working
- **replacement**: Suggested alternative model
- **notes**: Additional context or migration information

## 🔄 Update Schedule

- **Frequency**: Daily at 00:00 UTC
- **Duration**: <60 seconds total
- **Fallback**: Uses cached data if scraping fails
- **Monitoring**: Failed scrapes trigger maintainer notifications

## ⚠️ Error Handling

- Individual provider failures don't affect others
- URL changes are detected and reported via GitHub Issues
- Cached data serves as fallback during outages
- Comprehensive logging for debugging

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Key areas:
- Adding new providers
- Improving scraping reliability
- Enhancing data extraction
- Documentation improvements

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

## 🔮 Roadmap

- [x] Core scraping infrastructure
- [x] RSS feed generation
- [x] GitHub Pages hosting
- [ ] Data enrichment and structured parsing
- [ ] API endpoint for JSON data
- [ ] Webhook notifications for critical deprecations
- [ ] Browser extension for developers

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/leblancfg/deprecations-rss/issues)
- **Discussions**: [GitHub Discussions](https://github.com/leblancfg/deprecations-rss/discussions)

## 🙏 Acknowledgments

This project helps developers and organizations stay informed about AI model deprecations, preventing production outages and ensuring smooth migrations.

---

*Last updated: Check the [live dashboard](https://leblancfg.github.io/deprecations-rss/) for real-time status*
