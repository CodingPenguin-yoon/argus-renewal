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


def test_collect_once_cli_skips_market_on_holiday(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "argus-v2.db"))
    monkeypatch.setenv("ARGUS_NEWS_TRIGGERS_PROVIDER", "mock")
    monkeypatch.setenv("ARGUS_NEWS_FEED_PROVIDER", "mock")
    get_settings.cache_clear()

    exit_code = main(["collect-once", "--snapshot-time", "2026-05-16T03:00:00Z"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"provider_key": "market_session"' in captured.out
    assert '"reason": "market_holiday"' in captured.out
    assert '"provider_key": "v2_news_triggers"' in captured.out


def test_collect_loop_cli_honors_max_iterations(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "argus-v2.db"))
    monkeypatch.setenv("ARGUS_NEWS_TRIGGERS_PROVIDER", "mock")
    monkeypatch.setenv("ARGUS_NEWS_FEED_PROVIDER", "mock")
    get_settings.cache_clear()

    exit_code = main(["collect-loop", "--news-only", "--interval-seconds", "0", "--max-iterations", "2"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.count('"provider_key": "v2_news_feed"') == 2
