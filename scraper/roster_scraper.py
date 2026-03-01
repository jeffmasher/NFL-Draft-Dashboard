#!/usr/bin/env python3
"""
All-Time Roster Scraper — Saints Encyclopedia

Scrapes the complete New Orleans Saints all-time roster from
footballdb.com (paginated A-Z, ~1,700-2,000 players) and enriches
the players table with position, college, and seasons data.

Usage:
    python roster_scraper.py --full              # All letters A-Z
    python roster_scraper.py --letter B          # Single letter
    python roster_scraper.py --letter B --force  # Re-scrape even if data exists
"""

import argparse
import os
import sys
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from db import init_db

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.footballdb.com/teams/nfl/new-orleans-saints/alltime-roster"
REQUEST_DELAY = 1.5  # seconds between requests (polite rate limiting)

DB_PATH = os.environ.get("DB_PATH", "saints_encyclopedia.db")

LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)]


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

def parse_roster_page(html):
    """Parse a footballdb.com alltime-roster page and return a list of player dicts."""
    soup = BeautifulSoup(html, "lxml")

    table = soup.find("table", class_="statistics")
    if not table:
        print("  WARNING: No roster table found on page", file=sys.stderr)
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    players = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        # Player name and link
        player_name = cells[0].get_text(strip=True)
        player_link = cells[0].find("a")
        fdb_id = None
        fdb_url = None
        if player_link and player_link.get("href"):
            href = player_link["href"]
            fdb_url = f"https://www.footballdb.com{href}" if href.startswith("/") else href
            # Extract ID from href like /players/drew-brees-breesdr01
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            parts = slug.rsplit("-", 1)
            if len(parts) == 2 and len(parts[1]) >= 4:
                fdb_id = f"fdb_{parts[1]}"
            else:
                fdb_id = f"fdb_{slug}"

        # Position
        position = cells[1].get_text(strip=True) or None

        # Seasons
        seasons_text = cells[2].get_text(strip=True) or None

        # College
        college = cells[3].get_text(strip=True) or None

        if player_name:
            players.append({
                "player_name": player_name,
                "fdb_id": fdb_id,
                "fdb_url": fdb_url,
                "position": position,
                "seasons_text": seasons_text,
                "college": college,
            })

    return players


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def normalize_name(name):
    """Convert 'Last, First' to 'First Last'. Pass through if no comma."""
    if "," in name:
        parts = name.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}"
    return name.strip()


def resolve_and_upsert_player(conn, player):
    """
    Match an FDB player to an existing PFA player by case-insensitive name.
    FDB uses 'Last, First' format; PFA uses 'First Last'.
    If found, update that row with the new bio data.
    Otherwise, insert a new row using the fdb_id as the player_id.
    """
    raw_name = player["player_name"]
    normalized = normalize_name(raw_name)
    fdb_id = player["fdb_id"]

    # Try matching normalized name (First Last) against existing PFA players
    existing = conn.execute(
        "SELECT player_id FROM players WHERE LOWER(player_name) = LOWER(?)",
        (normalized,),
    ).fetchone()

    # Also try the raw FDB name format as fallback
    if not existing:
        existing = conn.execute(
            "SELECT player_id FROM players WHERE LOWER(player_name) = LOWER(?)",
            (raw_name,),
        ).fetchone()

    if existing:
        pid = existing[0]
        conn.execute(
            """UPDATE players SET
                position = COALESCE(?, position),
                college = COALESCE(?, college),
                fdb_id = COALESCE(?, fdb_id),
                fdb_url = COALESCE(?, fdb_url),
                seasons_text = COALESCE(?, seasons_text)
            WHERE player_id = ?""",
            (player["position"], player["college"],
             fdb_id, player["fdb_url"], player["seasons_text"],
             pid),
        )
        return pid, "updated"
    else:
        # Insert new player with fdb_id as player_id, using normalized name
        pid = fdb_id or f"fdb_{normalized.lower().replace(' ', '_')}"
        conn.execute(
            """INSERT OR IGNORE INTO players
                (player_id, player_name, position, college, fdb_id, fdb_url, seasons_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pid, normalized, player["position"], player["college"],
             fdb_id, player["fdb_url"], player["seasons_text"]),
        )
        return pid, "inserted"


def backfill_from_draft(conn):
    """
    Fill in position/college from draft_picks for any players still missing those fields.
    Matches by case-insensitive name.
    """
    updated = conn.execute("""
        UPDATE players SET
            position = COALESCE(players.position,
                (SELECT d.position FROM draft_picks d WHERE LOWER(d.player_name) = LOWER(players.player_name) LIMIT 1)),
            college = COALESCE(players.college,
                (SELECT d.college FROM draft_picks d WHERE LOWER(d.player_name) = LOWER(players.player_name) LIMIT 1))
        WHERE position IS NULL OR college IS NULL
    """).rowcount
    conn.commit()
    return updated


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------

def scrape_letter(session, conn, letter, force=False):
    """Scrape the roster page for a single letter."""
    url = f"{BASE_URL}?letter={letter}"
    print(f"  {letter}: fetching {url}")

    html = fetch(session, url)
    if not html:
        print(f"  {letter}: FAILED to fetch", file=sys.stderr)
        return 0, 0

    players = parse_roster_page(html)
    if not players:
        print(f"  {letter}: no players found")
        return 0, 0

    updated = 0
    inserted = 0
    for player in players:
        _, action = resolve_and_upsert_player(conn, player)
        if action == "updated":
            updated += 1
        else:
            inserted += 1

    conn.commit()
    print(f"  {letter}: {len(players)} players ({updated} updated, {inserted} new)")
    return updated, inserted


def main():
    parser = argparse.ArgumentParser(description="Scrape Saints all-time roster from footballdb.com")
    parser.add_argument("--full", action="store_true", help="Scrape all letters A-Z")
    parser.add_argument("--letter", type=str, help="Scrape a single letter (e.g. B)")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if data exists")
    args = parser.parse_args()

    if args.letter:
        letters = [args.letter.upper()]
    elif args.full:
        letters = LETTERS
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Saints All-Time Roster Scraper")
    print(f"  Database: {DB_PATH}")
    print(f"  Letters: {', '.join(letters)}")
    print()

    conn = init_db(DB_PATH)
    session = make_session()

    total_updated = 0
    total_inserted = 0
    for letter in letters:
        u, i = scrape_letter(session, conn, letter, force=args.force)
        total_updated += u
        total_inserted += i
        time.sleep(REQUEST_DELAY)

    # Backfill position/college from draft_picks table
    print("\nBackfilling from draft_picks...")
    backfilled = backfill_from_draft(conn)
    print(f"  Backfilled {backfilled} players with draft data")

    conn.close()
    print(f"\nDone! {total_updated} updated, {total_inserted} new players.")


if __name__ == "__main__":
    main()
