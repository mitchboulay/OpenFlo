"""In-process nightly jobs (FR-16): the address check at 03:00 in ``TZ``, feeding ``/healthz.degraded``."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import Settings
from ..db import Database
from . import address_check

logger = logging.getLogger(__name__)

NIGHTLY_AT = time(3, 0)
NIGHTLY_ACTOR = "system:nightly"


def zone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("TZ %r is not a known time zone; nightly jobs use UTC", name)
        return ZoneInfo("UTC")


def seconds_until(at: time, now: datetime) -> float:
    """Seconds from ``now`` (aware) to the next wall-clock ``at`` in ``now``'s zone; never zero."""
    target = datetime.combine(now.date(), at, tzinfo=now.tzinfo)
    if target <= now:
        target = datetime.combine(now.date() + timedelta(days=1), at, tzinfo=now.tzinfo)
    # Subtract in UTC so a DST change between now and the target is counted correctly.
    return (target.astimezone(ZoneInfo("UTC")) - now.astimezone(ZoneInfo("UTC"))).total_seconds()


async def run_address_check_nightly(db: Database, settings: Settings) -> None:
    """Forever: sleep until 03:00 local, then check the server address. Errors are logged, never fatal."""
    tz = zone(settings.default_timezone)
    while True:
        await asyncio.sleep(seconds_until(NIGHTLY_AT, datetime.now(tz)))
        try:
            await address_check.check_and_store(db, settings, NIGHTLY_ACTOR)
        except Exception:  # a failed night must not stop the next one
            logger.exception("nightly address check failed")
