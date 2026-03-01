#!/usr/bin/env python3
"""
PFA Draft Scraper — Saints Encyclopedia

Scrapes New Orleans Saints draft picks from Pro Football Archives draft pages
and populates the draft_picks table.

PFA draft page URL pattern (full NFL draft):
  https://www.profootballarchives.com/drafts/{YEAR}nfldraft.html
  e.g. https://www.profootballarchives.com/drafts/2024nfldraft.html

Table columns: Round, Overall, Team, Player, Pos, College, Notes
We filter rows where Team == "New Orleans Saints".

Usage:
    python pfa_draft_scraper.py --full              # All years 1967-present
    python pfa_draft_scraper.py --year 1973         # Single year
    python pfa_draft_scraper.py --start 2020        # 2020 to present
    python pfa_draft_scraper.py --incremental       # Current year only
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from db import init_db, upsert_draft_pick

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.profootballarchives.com"
FIRST_DRAFT_YEAR = 1967   # Saints joined NFL in 1967
REQUEST_DELAY = 1.0

DB_PATH = os.environ.get("DB_PATH", "saints_encyclopedia.db")


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
        "User-Agent": "SaintsEncyclopedia/1.0 (historical research project)",
    })
    return session


def fetch(session, url):
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

def draft_page_url(year):
    """Return the PFA NFL draft page URL for a given year."""
    return f"{BASE_URL}/drafts/{year}nfldraft.html"


def _extract_player_id(href):
    """Extract PFA player ID from a player page URL like /players/m/mill18800.html"""
    if not href:
        return None
    m = re.search(r'/players/\w+/(\w+)\.html', href)
    return m.group(1) if m else None


def parse_draft_page(html, year):
    """
    Parse a PFA full NFL draft page and return Saints picks only.

    Table columns: Round, Overall, Team, Player, Pos, College, Notes
    Filters rows where Team == "New Orleans Saints".

    Each dict: {season, round, pick, player_name, player_id, position, college}
    """
    soup = BeautifulSoup(html, "lxml")
    picks = []

    # Find the table with Round/Overall/Team headers
    draft_table = None
    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if not first_row:
            continue
        headers = [cell.get_text(strip=True).upper() for cell in first_row.find_all(["th", "td"])]
        if "ROUND" in headers and "OVERALL" in headers and "TEAM" in headers:
            draft_table = table
            break

    if not draft_table:
        return picks

    rows = draft_table.find_all("tr")
    if not rows:
        return picks

    headers = [cell.get_text(strip=True).upper() for cell in rows[0].find_all(["th", "td"])]

    def col(name):
        for i, h in enumerate(headers):
            if name in h:
                return i
        return None

    round_idx   = col("ROUND")
    overall_idx = col("OVERALL")
    team_idx    = col("TEAM")
    player_idx  = col("PLAYER")
    pos_idx     = col("POS")
    college_idx = col("COLLEGE")

    if any(i is None for i in [round_idx, overall_idx, team_idx, player_idx]):
        return picks

    for tr in rows[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) <= team_idx:
            continue

        team = cells[team_idx].get_text(strip=True)
        if team != "New Orleans Saints":
            continue

        def cell_text(idx):
            return cells[idx].get_text(strip=True) if idx is not None and idx < len(cells) else ""

        round_text = cell_text(round_idx)
        overall_text = cell_text(overall_idx)
        player_name = cell_text(player_idx)

        if not round_text.isdigit() or not overall_text.isdigit():
            continue
        if not player_name or player_name.upper() in ("PLAYER", "NAME"):
            continue

        player_href = None
        if player_idx < len(cells):
            a = cells[player_idx].find("a", href=True)
            player_href = a["href"] if a else None

        picks.append({
            "season": year,
            "round": int(round_text),
            "pick": int(overall_text),
            "player_name": player_name,
            "player_id": _extract_player_id(player_href),
            "position": cell_text(pos_idx) or None,
            "college": cell_text(college_idx) or None,
        })

    return picks


# ---------------------------------------------------------------------------
# Scraping logic
# ---------------------------------------------------------------------------

def scrape_year(session, conn, year):
    """Scrape draft picks for a single year."""
    url = draft_page_url(year)
    html = fetch(session, url)
    if not html:
        return 0

    picks = parse_draft_page(html, year)
    for pick in picks:
        upsert_draft_pick(conn, pick)
    conn.commit()
    return len(picks)


def current_year():
    return datetime.now().year


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape Saints draft picks from PFA")
    parser.add_argument("--full", action="store_true", help="Scrape all years 1967-present")
    parser.add_argument("--year", type=int, help="Scrape a single year")
    parser.add_argument("--start", type=int, help="Start year (scrapes through present)")
    parser.add_argument("--incremental", action="store_true", help="Current year only")
    args = parser.parse_args()

    conn = init_db(DB_PATH)
    session = make_session()

    if args.year:
        years = [args.year]
    elif args.start:
        years = list(range(args.start, current_year() + 1))
    elif args.full:
        years = list(range(FIRST_DRAFT_YEAR, current_year() + 1))
    elif args.incremental:
        years = [current_year()]
    else:
        parser.print_help()
        sys.exit(1)

    total_picks = 0
    for year in years:
        n = scrape_year(session, conn, year)
        print(f"  {year}: {n} picks")
        total_picks += n
        if len(years) > 1:
            time.sleep(REQUEST_DELAY)

    print(f"\nDone! {total_picks} total picks across {len(years)} year(s).")
    conn.close()


if __name__ == "__main__":
    main()
