#!/usr/bin/env python3
"""
Draft History Scraper — Saints Encyclopedia

Scrapes the complete New Orleans Saints draft history from
footballdb.com (1967–present).

Usage:
    python draft_scraper.py --full              # All drafts 1967-present
    python draft_scraper.py --year 2024         # Single year
    python draft_scraper.py --start 2020        # 2020 to present
    python draft_scraper.py --start 1967 --end 1980   # Custom range
"""

import argparse
import os
import sys
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from db import init_db

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.footballdb.com/teams/nfl/new-orleans-saints/draft"
FIRST_SEASON = 1967
REQUEST_DELAY = 1.5  # seconds between requests (polite rate limiting)

DB_PATH = os.environ.get("DB_PATH", "saints_encyclopedia.db")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

DRAFT_SCHEMA = """
CREATE TABLE IF NOT EXISTS draft_picks (
    season      INTEGER NOT NULL,
    round       INTEGER NOT NULL,
    pick        INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    player_id   TEXT,
    position    TEXT,
    college     TEXT,
    PRIMARY KEY (season, round, pick)
);

CREATE INDEX IF NOT EXISTS idx_draft_season ON draft_picks(season);
"""


def init_draft_table(conn):
    """Create the draft_picks table if it doesn't exist."""
    conn.executescript(DRAFT_SCHEMA)
    conn.commit()


def upsert_draft_pick(conn, pick):
    """Insert or replace a draft pick."""
    conn.execute(
        "INSERT OR REPLACE INTO draft_picks "
        "(season, round, pick, player_name, player_id, position, college) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (pick["season"], pick["round"], pick["pick"],
         pick["player_name"], pick.get("player_id"),
         pick.get("position"), pick.get("college")),
    )


def draft_year_exists(conn, season):
    """Check if we already have draft picks for a season."""
    row = conn.execute(
        "SELECT COUNT(*) FROM draft_picks WHERE season = ?", (season,)
    ).fetchone()
    return row[0] > 0


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def make_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    return session


def fetch(session, url):
    """Fetch a URL and return the HTML text, or None on failure."""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_draft_page(html, season):
    """Parse a footballdb.com draft page and return a list of pick dicts."""
    soup = BeautifulSoup(html, "lxml")

    # Find the statistics table
    table = soup.find("table", class_="statistics")
    if not table:
        print(f"  WARNING: No draft table found for {season}", file=sys.stderr)
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    picks = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        # Round — inside <a><b>N</b></a> or just text
        round_text = cells[0].get_text(strip=True)
        try:
            round_num = int(round_text)
        except ValueError:
            continue

        # Pick (overall)
        pick_text = cells[1].get_text(strip=True)
        try:
            pick_num = int(pick_text)
        except ValueError:
            continue

        # Player name — may have <a> link or be plain text
        player_name = cells[2].get_text(strip=True)
        player_link = cells[2].find("a")
        player_id = None
        if player_link and player_link.get("href"):
            # Extract ID from href like /players/taliese-fuaga-fuagata01
            href = player_link["href"]
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            # Extract the ID portion (last segment after the last dash group)
            # e.g. "taliese-fuaga-fuagata01" -> "fdb_fuagata01"
            parts = slug.rsplit("-", 1)
            if len(parts) == 2 and len(parts[1]) >= 4:
                player_id = f"fdb_{parts[1]}"
            else:
                player_id = f"fdb_{slug}"

        # Position
        position = cells[3].get_text(strip=True)

        # College
        college = cells[4].get_text(strip=True)

        picks.append({
            "season": season,
            "round": round_num,
            "pick": pick_num,
            "player_name": player_name,
            "player_id": player_id,
            "position": position,
            "college": college,
        })

    return picks


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------

def scrape_draft_year(session, conn, year, force=False):
    """Scrape a single draft year."""
    if not force and draft_year_exists(conn, year):
        print(f"  {year}: already scraped ({draft_year_exists(conn, year)} picks), skipping")
        return 0

    # Build URL — latest year uses base URL, others use /draft/{YEAR}
    current_year = datetime.now().year
    if year == current_year or year == current_year + 1:
        url = BASE_URL
    else:
        url = f"{BASE_URL}/{year}"

    print(f"  {year}: fetching {url}")
    html = fetch(session, url)
    if not html:
        print(f"  {year}: FAILED to fetch", file=sys.stderr)
        return 0

    picks = parse_draft_page(html, year)
    if not picks:
        print(f"  {year}: no picks found")
        return 0

    # Delete existing picks for this year (if force re-scraping)
    conn.execute("DELETE FROM draft_picks WHERE season = ?", (year,))

    for pick in picks:
        upsert_draft_pick(conn, pick)

    conn.commit()
    print(f"  {year}: saved {len(picks)} picks (Rd 1-{picks[-1]['round']})")
    return len(picks)


def main():
    parser = argparse.ArgumentParser(description="Scrape Saints draft history from footballdb.com")
    parser.add_argument("--full", action="store_true", help="Scrape all drafts 1967-present")
    parser.add_argument("--year", type=int, help="Scrape a single draft year")
    parser.add_argument("--start", type=int, help="Start year (inclusive)")
    parser.add_argument("--end", type=int, help="End year (inclusive)")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if data exists")
    args = parser.parse_args()

    current_year = datetime.now().year

    if args.year:
        years = [args.year]
    elif args.full:
        years = list(range(FIRST_SEASON, current_year + 1))
    elif args.start:
        end = args.end or current_year
        years = list(range(args.start, end + 1))
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Saints Draft Scraper")
    print(f"  Database: {DB_PATH}")
    print(f"  Years: {years[0]}-{years[-1]} ({len(years)} drafts)")
    print()

    conn = init_db(DB_PATH)
    init_draft_table(conn)
    session = make_session()

    total_picks = 0
    for year in years:
        count = scrape_draft_year(session, conn, year, force=args.force)
        total_picks += count
        if count > 0:
            time.sleep(REQUEST_DELAY)

    conn.close()
    print(f"\nDone! {total_picks} total picks saved.")


if __name__ == "__main__":
    main()
