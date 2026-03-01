#!/usr/bin/env python3
"""
PFA Box Score Scraper — Saints Encyclopedia

Scrapes historical box scores for the New Orleans Saints from
Pro Football Archives (profootballarchives.com).

Usage:
    python pfa_scraper.py --full              # All seasons 1967-present
    python pfa_scraper.py --season 2024       # Single season
    python pfa_scraper.py --start 2020        # 2020 to present
    python pfa_scraper.py --start 2010 --end 2019   # Custom range
    python pfa_scraper.py --incremental       # Current season only
    python pfa_scraper.py --export-only       # Just regenerate JSON
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from db import init_db, upsert_game, upsert_player, insert_stat_row, \
    insert_scoring_play, clear_game_stats, compute_team_totals, game_exists
from parsers import parse_season_page, parse_boxscore
from export import export_json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.profootballarchives.com"
FIRST_SEASON = 1967   # Saints' inaugural season
REQUEST_DELAY = 1.0   # seconds between requests (polite rate limiting)

DB_PATH = os.environ.get("DB_PATH", "saints_encyclopedia.db")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join("..", "docs", "data"))


# ---------------------------------------------------------------------------
# HTTP session with retry
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
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
        "User-Agent": "SaintsEncyclopedia/1.0 (historical research project)",
    })
    return session


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch(session: requests.Session, url: str) -> str | None:
    """Fetch a URL and return the HTML text, or None on failure."""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Season URL
# ---------------------------------------------------------------------------

def season_url(year: int) -> str:
    return f"{BASE_URL}/{year}nflno.html"


# ---------------------------------------------------------------------------
# Current NFL season
# ---------------------------------------------------------------------------

def current_season() -> int:
    """Return the current NFL season year. Season starts in August."""
    now = datetime.now()
    return now.year if now.month >= 8 else now.year - 1


# ---------------------------------------------------------------------------
# Main scrape logic
# ---------------------------------------------------------------------------

def _insert_boxscore(conn, game_id: str, box: dict, force: bool = False) -> None:
    """Insert parsed box score data into the database."""
    if force:
        clear_game_stats(conn, game_id)

    for pid, pinfo in box["players"].items():
        upsert_player(conn, pid, pinfo["name"], pinfo.get("url"))

    for table_name, rows in box["stats"].items():
        for row in rows:
            insert_stat_row(conn, table_name, row)

    for play in box.get("scoring_plays", []):
        insert_scoring_play(conn, play)

    compute_team_totals(conn, game_id)
    conn.commit()


def scrape_season(session, conn, year: int, force: bool = False) -> dict:
    """Scrape a single season. Returns a summary dict."""
    print(f"\n{'='*60}")
    print(f"Season {year}")
    print(f"{'='*60}")

    # Fetch season page
    url = season_url(year)
    html = fetch(session, url)
    if html is None:
        print(f"  SKIP: could not fetch season page for {year}")
        return {"season": year, "games": 0, "boxscores": 0, "skipped": 0, "errors": 0}

    # Parse game list
    games = parse_season_page(html, year)
    print(f"  Found {len(games)} games ({sum(1 for g in games if g['boxscore_url'])} with box scores)")

    # Upsert all games
    for game in games:
        upsert_game(conn, game)
    conn.commit()

    # Scrape box scores
    boxscore_count = 0
    skipped = 0
    errors = 0

    games_with_boxscores = [g for g in games if g["boxscore_url"]]
    total = len(games_with_boxscores)

    for i, game in enumerate(games_with_boxscores, 1):
        game_id = game["game_id"]
        boxscore_url = game["boxscore_url"]

        # Skip if already scraped (unless --force)
        if not force and game_exists(conn, game_id):
            skipped += 1
            continue

        # Rate limit
        time.sleep(REQUEST_DELAY)

        # Fetch box score
        box_html = fetch(session, boxscore_url)
        if box_html is None:
            errors += 1
            print(f"  [{i}/{total}] ERROR: {game_id}")
            continue

        # Parse
        box = parse_boxscore(box_html, game_id)

        _insert_boxscore(conn, game_id, box, force=force)
        boxscore_count += 1

        print(f"  [{i}/{total}] {game_id}: {game['game_date']} vs {game['opponent']} "
              f"({game['saints_score']}-{game['opponent_score']} {game['result']})")

    print(f"\n  Season {year} complete: {boxscore_count} scraped, "
          f"{skipped} skipped, {errors} errors")

    return {
        "season": year,
        "games": len(games),
        "boxscores": boxscore_count,
        "skipped": skipped,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape Saints box scores from Pro Football Archives"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--full", action="store_true",
                      help="Scrape all seasons 1967-present")
    mode.add_argument("--season", type=int, metavar="YYYY",
                      help="Scrape a single season")
    mode.add_argument("--incremental", action="store_true",
                      help="Scrape current season only")
    mode.add_argument("--export-only", action="store_true",
                      help="Only regenerate JSON from existing DB")

    parser.add_argument("--start", type=int, metavar="YYYY",
                        help="Start year (use with --full to override 1967)")
    parser.add_argument("--end", type=int, metavar="YYYY",
                        help="End year (default: current season)")
    parser.add_argument("--force", action="store_true",
                        help="Re-scrape even if data exists")
    parser.add_argument("--db", type=str, default=DB_PATH,
                        help=f"Database path (default: {DB_PATH})")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR,
                        help=f"JSON output directory (default: {OUTPUT_DIR})")
    return parser.parse_args()


def main():
    args = parse_args()

    # Resolve paths
    db_path = args.db
    output_dir = args.output_dir

    # Init database
    conn = init_db(db_path)
    print(f"Database: {os.path.abspath(db_path)}")

    if not args.export_only:
        # Determine season range
        cur = current_season()

        if args.season:
            start_year = args.season
            end_year = args.season
        elif args.incremental:
            start_year = cur
            end_year = cur
        else:  # --full
            start_year = args.start or FIRST_SEASON
            end_year = args.end or cur

        print(f"Scraping seasons {start_year} to {end_year}")
        print(f"Force re-scrape: {args.force}")

        session = make_session()
        summaries = []

        for year in range(start_year, end_year + 1):
            summary = scrape_season(session, conn, year, force=args.force)
            summaries.append(summary)

        # Print overall summary
        total_games = sum(s["games"] for s in summaries)
        total_box = sum(s["boxscores"] for s in summaries)
        total_skip = sum(s["skipped"] for s in summaries)
        total_err = sum(s["errors"] for s in summaries)

        print(f"\n{'='*60}")
        print(f"SCRAPE COMPLETE")
        print(f"{'='*60}")
        print(f"Seasons: {len(summaries)}")
        print(f"Total games: {total_games}")
        print(f"Box scores scraped: {total_box}")
        print(f"Skipped (already in DB): {total_skip}")
        print(f"Errors: {total_err}")

    # DB stats
    game_count = conn.execute("SELECT COUNT(*) FROM games WHERE boxscore_url IS NOT NULL").fetchone()[0]
    player_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    print(f"\nDB totals: {game_count} games with box scores, {player_count} players")

    # Export JSON
    print(f"\nExporting JSON to {os.path.abspath(output_dir)}...")
    export_json(db_path, output_dir)
    print("JSON export complete.")

    conn.close()


if __name__ == "__main__":
    main()
