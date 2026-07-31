"""
db/supabase_client.py
---------------------
Provides Supabase and asyncpg connection helpers for the hedge-fund AI backend.

Functions
---------
get_supabase_client()  — returns a supabase-py client using the service role key
get_db_connection()    — returns a single asyncpg connection to Supabase Postgres
get_db_pool()          — returns an asyncpg connection pool to Supabase Postgres

Usage::

    from db.supabase_client import get_supabase_client, get_db_pool

    # Supabase REST / realtime
    sb = get_supabase_client()
    result = sb.table("trade_proposals").select("*").execute()

    # Direct Postgres (asyncpg)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM trades WHERE status = 'open'")
    await pool.close()
"""
from __future__ import annotations

import functools
import os
from typing import Optional

import asyncpg  # type: ignore
from supabase import create_client, Client  # type: ignore

# ---------------------------------------------------------------------------
# Configuration — read from environment variables (or fall back to defaults)
# ---------------------------------------------------------------------------

_SUPABASE_URL: str = os.environ.get(
    "SUPABASE_URL",
    "https://hugpspsssckbepyofcnt.supabase.co",
)
_SUPABASE_SERVICE_KEY: str = os.environ.get(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTQyOTk5MywiZXhwIjoyMTAxMDA1OTkzfQ"
    ".Yx0Mg2JgRjM98GKhuVJGSM9HB4rHdi50aWXIYuGM-j4",
)
_SUPABASE_ANON_KEY: str = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0Mjk5OTMsImV4cCI6MjEwMTAwNTk5M30"
    ".DF3DCBllgTpQ9XCy4V_N0UiTljq-GDaJkoyu0TEsUhY",
)
_DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:"
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTQyOTk5MywiZXhwIjoyMTAxMDA1OTkzfQ"
    ".Yx0Mg2JgRjM98GKhuVJGSM9HB4rHdi50aWXIYuGM-j4"
    "@db.hugpspsssckbepyofcnt.supabase.co:5432/postgres",
)

# ---------------------------------------------------------------------------
# Supabase REST client (singleton, service-role key for backend)
# ---------------------------------------------------------------------------

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Return a cached supabase-py client authenticated with the service role key.

    The service role key bypasses Row Level Security — use it only in trusted
    backend code, never expose it to the browser.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)
    return _supabase_client


# ---------------------------------------------------------------------------
# asyncpg helpers — direct Postgres connections
# ---------------------------------------------------------------------------

async def get_db_connection() -> asyncpg.Connection:
    """
    Open and return a single asyncpg connection to the Supabase Postgres database.

    The caller is responsible for closing it::

        conn = await get_db_connection()
        try:
            rows = await conn.fetch("SELECT 1")
        finally:
            await conn.close()
    """
    return await asyncpg.connect(_DATABASE_URL)


async def get_db_pool(
    min_size: int = 2,
    max_size: int = 10,
) -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool to the Supabase Postgres database.

    The caller is responsible for closing the pool when done::

        pool = await get_db_pool()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT 1")
        finally:
            await pool.close()

    Args:
        min_size: Minimum number of connections kept alive.
        max_size: Maximum number of connections in the pool.

    Returns:
        An open asyncpg.Pool ready for use.
    """
    return await asyncpg.create_pool(
        _DATABASE_URL,
        min_size=min_size,
        max_size=max_size,
    )
