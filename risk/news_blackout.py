"""
risk/news_blackout.py
=====================
NewsBlackoutManager — prevents trade entry around high-impact macro events.

Blackout windows are defined by PRE_EVENT_BLACKOUT_MINUTES and
POST_EVENT_BLACKOUT_MINUTES from risk/limits.py.

The manager fetches its economic calendar from the Financial Modelling Prep
(FMP) free API (https://financialmodelingprep.com/api/v3/economic_calendar).
If the API is unavailable the last cached result is used.  If no cache
exists at all, the manager conservatively returns is_blackout_active=True
to prevent trading without a calendar.

Usage
-----
    mgr = NewsBlackoutManager()
    if await mgr.is_blackout_active():
        # do not place orders
        ...

    # Manual override for known events
    await mgr.add_manual_event("Fed Powell Speech", datetime(2026, 7, 30, 14, 0, tzinfo=timezone.utc))
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from risk.limits import POST_EVENT_BLACKOUT_MINUTES, PRE_EVENT_BLACKOUT_MINUTES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# High-impact event names (case-insensitive substring matching)
# ---------------------------------------------------------------------------

CRITICAL_EVENTS: frozenset[str] = frozenset(
    {
        "fomc rate decision",
        "federal funds rate",
        "interest rate decision",
        "non-farm payrolls",
        "nonfarm payrolls",
        "nfp",
        "cpi",
        "consumer price index",
        "pce price index",
        "personal consumption expenditures",
        "gdp",
        "gross domestic product",
        "fed chair speech",
        "powell speech",
        "fed chair powell",
        "jackson hole",
        "ecb rate decision",
        "ecb interest rate",
        "european central bank",
        "boe rate decision",
        "bank of england",
        "boe interest rate",
        "boj rate decision",
        "bank of japan",
        "rba rate decision",
        "reserve bank of australia",
        "unemployment rate",
        "initial jobless claims",
        "retail sales",
        "ism manufacturing",
        "ism services",
        "pmi",
        "purchasing managers index",
        "producer price index",
        "ppi",
        "trade balance",
        "durable goods orders",
        "michigan consumer sentiment",
        "conference board consumer confidence",
        "treasury auction",
        "fed minutes",
        "fomc minutes",
        "beige book",
        "earnings",  # major company earnings (broad catch)
    }
)

# ---------------------------------------------------------------------------
# FMP API
# ---------------------------------------------------------------------------

_FMP_BASE_URL = "https://financialmodelingprep.com/api/v3/economic_calendar"
_CALENDAR_REFRESH_HOURS = 1
_HTTP_TIMEOUT_SECONDS = 10.0


class NewsBlackoutManager:
    """
    Manages pre- and post-event trading blackout windows.

    Thread-safe for async use; uses an asyncio.Lock to serialise calendar
    refreshes.

    Parameters
    ----------
    fmp_api_key:
        FMP API key.  Falls back to the environment variable
        ``FMP_API_KEY`` if not supplied.
    pre_blackout_minutes:
        Minutes before an event to suspend trading.
    post_blackout_minutes:
        Minutes after an event to suspend trading.
    """

    def __init__(
        self,
        fmp_api_key: str | None = None,
        pre_blackout_minutes: int = PRE_EVENT_BLACKOUT_MINUTES,
        post_blackout_minutes: int = POST_EVENT_BLACKOUT_MINUTES,
    ) -> None:
        self._fmp_api_key: str = fmp_api_key or os.getenv("FMP_API_KEY", "")
        self._pre_minutes = pre_blackout_minutes
        self._post_minutes = post_blackout_minutes

        # Cached high-impact events: list of (name, event_datetime_utc)
        self._events: list[tuple[str, datetime]] = []
        self._last_refresh: datetime | None = None
        self._refresh_lock = asyncio.Lock()

        # Manual overrides (always merged with calendar events)
        self._manual_events: list[tuple[str, datetime]] = []

        # Whether the initial fetch has ever succeeded
        self._ever_fetched: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_blackout_active(self, symbol: str | None = None) -> bool:
        """
        Return True if trading should be suspended right now.

        Parameters
        ----------
        symbol:
            Reserved for future instrument-specific blackout rules.
            Currently unused (all blackouts are global).

        Returns
        -------
        bool
            True  → trading is blocked.
            False → trading is permitted.
        """
        await self._refresh_if_stale()

        if not self._ever_fetched and not self._events and not self._manual_events:
            # Conservative: if we have no data at all, block trading.
            logger.warning(
                "news_blackout: no calendar data available — conservatively blocking."
            )
            return True

        now = datetime.now(timezone.utc)
        all_events = self._events + self._manual_events

        for event_name, event_time in all_events:
            window_start = event_time - timedelta(minutes=self._pre_minutes)
            window_end = event_time + timedelta(minutes=self._post_minutes)

            if window_start <= now <= window_end:
                logger.info(
                    "news_blackout ACTIVE: event='%s' at %s | window=[%s, %s]",
                    event_name,
                    event_time.isoformat(),
                    window_start.isoformat(),
                    window_end.isoformat(),
                )
                return True

        return False

    def add_manual_event(self, name: str, event_time: datetime) -> None:
        """
        Manually register a high-impact event.

        The event will be included in blackout calculations alongside
        the automatically fetched calendar.

        Parameters
        ----------
        name:
            Human-readable event name.
        event_time:
            UTC datetime of the event.  Timezone-naive values are assumed
            to be UTC and will be made timezone-aware.
        """
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        self._manual_events.append((name, event_time))
        logger.info("news_blackout: manual event added: '%s' at %s", name, event_time.isoformat())

    async def get_upcoming_events(self, hours: int = 24) -> list[dict[str, Any]]:
        """
        Return high-impact events scheduled in the next *hours* hours.

        Useful for dashboard display and pre-flight checks.
        """
        await self._refresh_if_stale()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)

        all_events = self._events + self._manual_events
        result = []
        for name, dt in sorted(all_events, key=lambda x: x[1]):
            if now <= dt <= cutoff:
                window_start = dt - timedelta(minutes=self._pre_minutes)
                window_end = dt + timedelta(minutes=self._post_minutes)
                result.append(
                    {
                        "name": name,
                        "event_time": dt.isoformat(),
                        "blackout_start": window_start.isoformat(),
                        "blackout_end": window_end.isoformat(),
                        "source": "manual" if (name, dt) in self._manual_events else "calendar",
                    }
                )
        return result

    # ------------------------------------------------------------------
    # Internal: refresh logic
    # ------------------------------------------------------------------

    async def _refresh_if_stale(self) -> None:
        """
        Trigger a calendar refresh if the cache is older than one hour.

        Uses an asyncio.Lock so that concurrent callers do not all fire
        simultaneous HTTP requests.
        """
        now = datetime.now(timezone.utc)

        if (
            self._last_refresh is not None
            and (now - self._last_refresh) < timedelta(hours=_CALENDAR_REFRESH_HOURS)
        ):
            return  # Cache is fresh

        async with self._refresh_lock:
            # Double-check after acquiring lock
            now = datetime.now(timezone.utc)
            if (
                self._last_refresh is not None
                and (now - self._last_refresh) < timedelta(hours=_CALENDAR_REFRESH_HOURS)
            ):
                return

            await self._fetch_and_cache()

    async def _fetch_and_cache(self) -> None:
        """Fetch the economic calendar from FMP and cache parsed events."""
        try:
            raw_data = await self._fetch_calendar()
            new_events = self._parse_events(raw_data)

            # Prune stale manual events (more than post-blackout hours old)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            self._manual_events = [
                (n, t) for n, t in self._manual_events if t > cutoff
            ]

            self._events = new_events
            self._last_refresh = datetime.now(timezone.utc)
            self._ever_fetched = True

            logger.info(
                "news_blackout: calendar refreshed — %d high-impact events loaded.",
                len(new_events),
            )

        except Exception as exc:
            logger.warning(
                "news_blackout: calendar fetch failed (%s) — using cached data (%d events).",
                exc,
                len(self._events),
            )
            # Update timestamp so we back-off and don't hammer the API
            self._last_refresh = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Internal: HTTP fetch
    # ------------------------------------------------------------------

    async def _fetch_calendar(self) -> list[dict[str, Any]]:
        """
        Fetch the upcoming economic calendar from FMP API.

        Returns raw list of event dicts.  Raises on network / API errors.
        """
        now = datetime.now(timezone.utc)
        from_date = now.strftime("%Y-%m-%d")
        to_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")

        params: dict[str, str] = {
            "from": from_date,
            "to": to_date,
        }
        if self._fmp_api_key:
            params["apikey"] = self._fmp_api_key

        url = _FMP_BASE_URL
        logger.debug("news_blackout: fetching calendar from %s params=%s", url, {k: v for k, v in params.items() if k != "apikey"})

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, list):
            raise ValueError(f"Unexpected FMP response format: {type(data)}")

        return data

    # ------------------------------------------------------------------
    # Internal: parsing
    # ------------------------------------------------------------------

    def _parse_events(self, data: list[dict[str, Any]]) -> list[tuple[str, datetime]]:
        """
        Filter raw calendar data for high-impact events.

        FMP event dicts typically contain:
          event     — str name
          date      — "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD"
          impact    — "High" | "Medium" | "Low"
          country   — ISO country code

        We keep events where:
          1. impact == "High", OR
          2. The event name contains a substring from CRITICAL_EVENTS.

        Returns
        -------
        list of (name, utc_datetime) tuples
        """
        results: list[tuple[str, datetime]] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            name: str = item.get("event", "") or item.get("name", "") or ""
            impact: str = (item.get("impact") or item.get("importance") or "").strip()
            date_str: str = item.get("date") or item.get("time") or ""

            if not name or not date_str:
                continue

            # Parse datetime (FMP uses various formats)
            event_time = self._parse_event_datetime(date_str)
            if event_time is None:
                continue

            # Skip past events (older than post-blackout window)
            if event_time < datetime.now(timezone.utc) - timedelta(minutes=self._post_minutes + 1):
                continue

            # Check if high-impact by FMP's own flag
            is_high_impact = impact.lower() in {"high", "3", "critical"}

            # Check if matches our critical event keywords
            name_lower = name.lower()
            is_critical_keyword = any(kw in name_lower for kw in CRITICAL_EVENTS)

            if is_high_impact or is_critical_keyword:
                results.append((name.strip(), event_time))
                logger.debug(
                    "news_blackout: tracked event '%s' at %s (impact=%s)",
                    name, event_time.isoformat(), impact,
                )

        # Sort chronologically
        results.sort(key=lambda x: x[1])
        return results

    def _parse_event_datetime(self, date_str: str) -> datetime | None:
        """
        Parse FMP's date string into a timezone-aware UTC datetime.

        FMP uses several formats:
          "2026-07-30 14:00:00"
          "2026-07-30T14:00:00"
          "2026-07-30"
        """
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                # FMP economic calendar is in UTC
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        logger.debug("news_blackout: could not parse date string '%s'", date_str)
        return None
