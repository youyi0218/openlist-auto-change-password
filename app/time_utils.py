from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter

MAX_SLEEP_SECONDS = 3600


def now_in_timezone(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def get_next_rotation_time(schedule, from_time: datetime | None = None) -> datetime | None:
    if not schedule.enabled:
        return None
    base = from_time or now_in_timezone(schedule.timezone)
    if base.tzinfo is None:
        base = base.replace(tzinfo=ZoneInfo(schedule.timezone))
    else:
        base = base.astimezone(ZoneInfo(schedule.timezone))
    return croniter(schedule.cron, base).get_next(datetime)


def format_datetime(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return "???"
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")


def sleep_until(target_time: datetime) -> None:
    while True:
        remaining = target_time.timestamp() - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, MAX_SLEEP_SECONDS))
