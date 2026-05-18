from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone


KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class MarketSessionState:
    session_type: str
    trading_date: date
    local_time: datetime
    is_trading_day: bool
    is_market_open: bool
    reason: str
    session_id: str

    def to_dict(self) -> dict[str, str | bool]:
        payload = asdict(self)
        payload["trading_date"] = self.trading_date.isoformat()
        payload["local_time"] = self.local_time.replace(microsecond=0).isoformat()
        return payload


def resolve_market_session(
    *,
    now: datetime | None = None,
    holiday_dates: str = "",
    regular_start: str = "08:40",
    regular_end: str = "15:50",
    night_start: str = "17:50",
    night_end: str = "06:05",
    night_enabled: bool = False,
) -> MarketSessionState:
    local_now = (now or datetime.now(timezone.utc)).astimezone(KST).replace(microsecond=0)
    local_date = local_now.date()
    holidays = parse_holiday_dates(holiday_dates)
    regular_start_time = parse_hhmm(regular_start)
    regular_end_time = parse_hhmm(regular_end)
    night_start_time = parse_hhmm(night_start)
    night_end_time = parse_hhmm(night_end)

    if is_trading_day(local_date, holidays):
        if regular_start_time <= local_now.time() <= regular_end_time:
            return _state(
                session_type="regular",
                trading_date=local_date,
                local_time=local_now,
                is_trading_day=True,
                is_market_open=True,
                reason="regular_session_open",
            )
        if night_enabled and local_now.time() >= night_start_time:
            trading_date = next_trading_day(local_date, holidays)
            return _state(
                session_type="night",
                trading_date=trading_date,
                local_time=local_now,
                is_trading_day=True,
                is_market_open=True,
                reason="night_session_open",
            )

    previous_date = local_date - timedelta(days=1)
    if night_enabled and is_trading_day(previous_date, holidays) and local_now.time() <= night_end_time:
        trading_date = next_trading_day(previous_date, holidays)
        return _state(
            session_type="night",
            trading_date=trading_date,
            local_time=local_now,
            is_trading_day=is_trading_day(local_date, holidays),
            is_market_open=True,
            reason="night_session_open",
        )

    reason = "market_closed"
    if not is_trading_day(local_date, holidays):
        reason = "market_holiday"
    elif local_now.time() < regular_start_time:
        reason = "before_regular_session"
    elif local_now.time() > regular_end_time:
        reason = "after_regular_session"

    return _state(
        session_type="closed",
        trading_date=local_date,
        local_time=local_now,
        is_trading_day=is_trading_day(local_date, holidays),
        is_market_open=False,
        reason=reason,
    )


def parse_holiday_dates(value: str | None) -> set[date]:
    dates: set[date] = set()
    for item in (value or "").split(","):
        item = item.strip()
        if not item:
            continue
        dates.add(date.fromisoformat(item))
    return dates


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(hour=int(hour), minute=int(minute))


def is_trading_day(day: date, holiday_dates: set[date] | None = None) -> bool:
    if day.weekday() >= 5:
        return False
    if day.month == 5 and day.day == 1:
        return False
    if day.month == 12 and day.day == 31:
        return False
    return day not in (holiday_dates or set())


def next_trading_day(day: date, holiday_dates: set[date] | None = None) -> date:
    candidate = day + timedelta(days=1)
    while not is_trading_day(candidate, holiday_dates):
        candidate += timedelta(days=1)
    return candidate


def next_regular_session_start(
    *,
    now: datetime | None = None,
    holiday_dates: str = "",
    regular_start: str = "08:40",
) -> datetime:
    local_now = (now or datetime.now(timezone.utc)).astimezone(KST).replace(microsecond=0)
    holidays = parse_holiday_dates(holiday_dates)
    start_time = parse_hhmm(regular_start)
    candidate = local_now.date()
    if not is_trading_day(candidate, holidays) or local_now.time() > start_time:
        candidate = next_trading_day(candidate, holidays)
    return datetime.combine(candidate, start_time, tzinfo=KST)


def _state(
    *,
    session_type: str,
    trading_date: date,
    local_time: datetime,
    is_trading_day: bool,
    is_market_open: bool,
    reason: str,
) -> MarketSessionState:
    return MarketSessionState(
        session_type=session_type,
        trading_date=trading_date,
        local_time=local_time,
        is_trading_day=is_trading_day,
        is_market_open=is_market_open,
        reason=reason,
        session_id=f"KRX-DERIVATIVES-{session_type.upper()}-{trading_date.isoformat()}",
    )
