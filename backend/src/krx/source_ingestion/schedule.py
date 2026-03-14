from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


MARKET_OPEN_PHASE = "MARKET_OPEN"
POST_CLOSE_PHASE = "POST_CLOSE"
OFF_HOURS_PHASE = "OFF_HOURS"


@dataclass(frozen=True)
class NewsAutomationCadenceDecision:
    phase: str
    cadence_minutes: int
    should_run: bool
    timezone_name: str
    local_now: datetime
    next_due_at: datetime


def resolve_news_automation_cadence(
    *,
    now: datetime,
    timezone_name: str,
    market_open_time: str,
    market_close_time: str,
    post_close_end_time: str,
    weekdays: str,
    market_open_interval_minutes: int,
    post_close_interval_minutes: int,
    off_hours_interval_minutes: int,
) -> NewsAutomationCadenceDecision:
    timezone = ZoneInfo(timezone_name)
    local_now = now.astimezone(timezone) if now.tzinfo else now.replace(tzinfo=timezone)
    active_weekdays = _parse_weekdays(weekdays)
    open_at = _parse_time(market_open_time)
    close_at = _parse_time(market_close_time)
    post_close_end_at = _parse_time(post_close_end_time)

    if local_now.weekday() in active_weekdays and open_at <= local_now.time() < close_at:
        phase = MARKET_OPEN_PHASE
        cadence_minutes = market_open_interval_minutes
    elif local_now.weekday() in active_weekdays and close_at <= local_now.time() < post_close_end_at:
        phase = POST_CLOSE_PHASE
        cadence_minutes = post_close_interval_minutes
    else:
        phase = OFF_HOURS_PHASE
        cadence_minutes = off_hours_interval_minutes

    minute_tick = local_now.replace(second=0, microsecond=0)
    remainder = minute_tick.minute % max(1, cadence_minutes)
    should_run = cadence_minutes <= 1 or remainder == 0
    next_due_at = minute_tick if should_run else minute_tick + timedelta(minutes=cadence_minutes - remainder)

    return NewsAutomationCadenceDecision(
        phase=phase,
        cadence_minutes=max(1, cadence_minutes),
        should_run=should_run,
        timezone_name=timezone_name,
        local_now=local_now,
        next_due_at=next_due_at,
    )


def _parse_time(value: str) -> time:
    hour_text, minute_text = value.split(":", maxsplit=1)
    return time(hour=int(hour_text), minute=int(minute_text))


def _parse_weekdays(value: str) -> set[int]:
    items = {int(item.strip()) for item in value.split(",") if item.strip()}
    return items or {0, 1, 2, 3, 4}
