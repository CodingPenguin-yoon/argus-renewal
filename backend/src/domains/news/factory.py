from .provider import NewsProvider
from .providers.mock_provider import MockNewsProvider


def create_news_provider(provider_name: str) -> NewsProvider:
    if provider_name == "mock":
        return MockNewsProvider()

    raise ValueError(f"Unsupported news provider: {provider_name}")
