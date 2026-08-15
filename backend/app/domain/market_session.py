"""Iran TSE regular-hours session inference.

This completes the P3.25 MarketSession contract gap. It uses weekday + clock
in Asia/Tehran only. Official holiday calendars are NOT applied.

Session-open is NOT live market data.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models.schemas import MarketSession

TEHRAN = ZoneInfo("Asia/Tehran")
# Saturday–Wednesday (Python weekday: Mon=0 ... Sun=6)
TRADING_WEEKDAYS = {5, 6, 0, 1, 2}
PRE_OPEN = time(8, 45)
CONTINUOUS_OPEN = time(9, 0)
CONTINUOUS_CLOSE = time(12, 30)


def infer_iran_market_session(now: datetime | None = None) -> MarketSession:
    """Infer regular TSE hours. Holidays unknown. Does not affect data_trust."""
    if now is None:
        current = datetime.now(TEHRAN)
    elif now.tzinfo is None:
        current = now.replace(tzinfo=TEHRAN)
    else:
        current = now.astimezone(TEHRAN)

    session_date = current.date().isoformat()
    clock = time(current.hour, current.minute, current.second)

    if current.weekday() not in TRADING_WEEKDAYS:
        return MarketSession(
            timezone="Asia/Tehran",
            session_date=session_date,
            is_open=False,
            status="closed",
        )
    if PRE_OPEN <= clock < CONTINUOUS_OPEN:
        return MarketSession(
            timezone="Asia/Tehran",
            session_date=session_date,
            is_open=False,
            status="pre_open",
        )
    if CONTINUOUS_OPEN <= clock < CONTINUOUS_CLOSE:
        return MarketSession(
            timezone="Asia/Tehran",
            session_date=session_date,
            is_open=True,
            status="open",
        )
    return MarketSession(
        timezone="Asia/Tehran",
        session_date=session_date,
        is_open=False,
        status="closed",
    )
