from __future__ import annotations

from src.argus_v2.cli import main
from src.config.env import get_settings


def test_smoke_news_ai_cli_handles_missing_ai_key(capsys, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_NEWS_AI_PROVIDER", "disabled")
    monkeypatch.delenv("ARGUS_NEWS_AI_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(["smoke-news-ai"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"status": "failed"' in captured.out
    assert "news_ai_disabled" in captured.out
