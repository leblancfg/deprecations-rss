"""Mock data generator for testing and development."""

from datetime import UTC, datetime, timedelta

from src.models.deprecation import DeprecationEntry, FeedData, ProviderStatus


def generate_mock_feed_data() -> FeedData:
    """Generate realistic mock deprecation feed data for testing.

    Returns:
        FeedData object with sample deprecations and provider statuses.
    """
    now = datetime.now(UTC)

    deprecations = [
        # OpenAI deprecations
        DeprecationEntry(
            provider="OpenAI",
            model="gpt-3.5-turbo-0301",
            deprecation_date=datetime(2024, 6, 13, tzinfo=UTC),
            retirement_date=datetime(2024, 9, 13, tzinfo=UTC),
            replacement="gpt-3.5-turbo",
            notes="This model snapshot will be retired 3 months after deprecation",
            source_url="https://platform.openai.com/docs/deprecations",
        ),
        DeprecationEntry(
            provider="OpenAI",
            model="text-davinci-003",
            deprecation_date=datetime(2024, 1, 4, tzinfo=UTC),
            retirement_date=datetime(2024, 6, 4, tzinfo=UTC),
            replacement="gpt-3.5-turbo or gpt-4",
            notes="Legacy completion model being retired",
            source_url="https://platform.openai.com/docs/deprecations",
        ),
        DeprecationEntry(
            provider="OpenAI",
            model="text-embedding-ada-002-v2",
            deprecation_date=datetime(2025, 1, 15, tzinfo=UTC),
            retirement_date=datetime(2025, 4, 15, tzinfo=UTC),
            replacement="text-embedding-3-small",
            notes="Upgrading to new embedding models with better performance",
            source_url="https://platform.openai.com/docs/guides/embeddings",
        ),
        # Anthropic deprecations
        DeprecationEntry(
            provider="Anthropic",
            model="claude-instant-1",
            deprecation_date=datetime(2024, 9, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 12, 1, tzinfo=UTC),
            replacement="claude-3-haiku",
            notes="Moving to Claude 3 family for improved capabilities",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models",
        ),
        DeprecationEntry(
            provider="Anthropic",
            model="claude-2.0",
            deprecation_date=datetime(2024, 7, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 10, 1, tzinfo=UTC),
            replacement="claude-3-sonnet",
            notes="Claude 2 models superseded by Claude 3 family",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models",
        ),
        DeprecationEntry(
            provider="Anthropic",
            model="claude-2.1",
            deprecation_date=datetime(2024, 7, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 10, 1, tzinfo=UTC),
            replacement="claude-3-opus",
            notes="Upgrading to Claude 3 for enhanced performance",
            source_url="https://docs.anthropic.com/en/docs/about-claude/models",
        ),
        # Google Vertex AI deprecations
        DeprecationEntry(
            provider="Google Vertex AI",
            model="text-bison@001",
            deprecation_date=datetime(2024, 10, 9, tzinfo=UTC),
            retirement_date=datetime(2025, 4, 9, tzinfo=UTC),
            replacement="text-bison@002 or gemini-pro",
            notes="PaLM 2 text-bison-001 being retired after 6 months",
            source_url="https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text",
        ),
        DeprecationEntry(
            provider="Google Vertex AI",
            model="chat-bison@001",
            deprecation_date=datetime(2024, 10, 9, tzinfo=UTC),
            retirement_date=datetime(2025, 4, 9, tzinfo=UTC),
            replacement="chat-bison@002 or gemini-pro",
            notes="PaLM 2 chat model being upgraded",
            source_url="https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-chat",
        ),
        DeprecationEntry(
            provider="Google Vertex AI",
            model="code-bison@001",
            deprecation_date=datetime(2024, 12, 1, tzinfo=UTC),
            retirement_date=datetime(2025, 6, 1, tzinfo=UTC),
            replacement="code-bison@002 or gemini-code",
            notes="Code generation model update",
            source_url="https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/code-generation",
        ),
        # AWS Bedrock deprecations
        DeprecationEntry(
            provider="AWS Bedrock",
            model="anthropic.claude-v1",
            deprecation_date=datetime(2024, 3, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 6, 1, tzinfo=UTC),
            replacement="anthropic.claude-v2 or anthropic.claude-3-sonnet",
            notes="First generation Claude model on Bedrock",
            source_url="https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html",
        ),
        DeprecationEntry(
            provider="AWS Bedrock",
            model="amazon.titan-text-lite-v1",
            deprecation_date=datetime(2024, 11, 15, tzinfo=UTC),
            retirement_date=datetime(2025, 2, 15, tzinfo=UTC),
            replacement="amazon.titan-text-express-v1",
            notes="Titan Lite model being consolidated",
            source_url="https://docs.aws.amazon.com/bedrock/latest/userguide/titan-models.html",
        ),
        DeprecationEntry(
            provider="AWS Bedrock",
            model="ai21.j2-mid-v1",
            deprecation_date=datetime(2025, 1, 1, tzinfo=UTC),
            retirement_date=datetime(2025, 4, 1, tzinfo=UTC),
            replacement="ai21.j2-ultra-v1",
            notes="Jurassic-2 mid tier being deprecated",
            source_url="https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-jurassic2.html",
        ),
        # Cohere deprecations
        DeprecationEntry(
            provider="Cohere",
            model="command-medium-nightly",
            deprecation_date=datetime(2024, 8, 1, tzinfo=UTC),
            retirement_date=datetime(2024, 11, 1, tzinfo=UTC),
            replacement="command-r",
            notes="Nightly models being replaced with stable versions",
            source_url="https://docs.cohere.com/docs/models",
        ),
        DeprecationEntry(
            provider="Cohere",
            model="command-xlarge-20221108",
            deprecation_date=datetime(2024, 9, 15, tzinfo=UTC),
            retirement_date=datetime(2024, 12, 15, tzinfo=UTC),
            replacement="command-r-plus",
            notes="Older command model snapshot being retired",
            source_url="https://docs.cohere.com/docs/models",
        ),
        DeprecationEntry(
            provider="Cohere",
            model="embed-english-v2.0",
            deprecation_date=datetime(2025, 2, 1, tzinfo=UTC),
            retirement_date=datetime(2025, 5, 1, tzinfo=UTC),
            replacement="embed-english-v3.0",
            notes="Upgrading to v3.0 embeddings with improved multilingual support",
            source_url="https://docs.cohere.com/docs/embed-api",
        ),
    ]

    provider_statuses = [
        ProviderStatus(
            name="OpenAI",
            last_checked=now - timedelta(minutes=5),
            is_healthy=True,
            error_message=None,
        ),
        ProviderStatus(
            name="Anthropic",
            last_checked=now - timedelta(minutes=10),
            is_healthy=True,
            error_message=None,
        ),
        ProviderStatus(
            name="Google Vertex AI",
            last_checked=now - timedelta(minutes=7),
            is_healthy=True,
            error_message=None,
        ),
        ProviderStatus(
            name="AWS Bedrock",
            last_checked=now - timedelta(minutes=3),
            is_healthy=False,
            error_message="Rate limit exceeded - retry after 60 seconds",
        ),
        ProviderStatus(
            name="Cohere",
            last_checked=now - timedelta(minutes=8),
            is_healthy=True,
            error_message=None,
        ),
    ]

    return FeedData(
        deprecations=deprecations,
        provider_statuses=provider_statuses,
        last_updated=now,
    )
