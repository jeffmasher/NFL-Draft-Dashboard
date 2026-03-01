#!/usr/bin/env python3
"""
PFA Draft Scraper — Saints Encyclopedia

Scrapes New Orleans Saints draft picks from Pro Football Archives draft pages
and populates the draft_picks table.

PFA draft page URL pattern (Saints):
  https://www.profootballarchives.com/drafts/{YEAR}nflno.html
  e.g. https://www.profootballarchives.com/drafts/1967nflno.html

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
    """Return the PFA Saints draft page URL for a given year."""
    return f"{BASE_URL}/drafts/{year}nflno.html"


def _extract_player_id(href):
    """Extract PFA player ID from a player page URL like /players/m/mill18800.html"""
    if not href:
        return None
    m = re.search(r'/players/\w+/(\w+)\.html', href)
    return m.group(1) if m else None


def parse_draft_page(html, year):
    """
    Parse a PFA draft page for the Saints and return a list of pick dicts.

    Each dict: {season, round, pick, player_name, player_id, position, college}
    """
    soup = BeautifulSoup(html, "lxml")
    picks = []

    # PFA draft pages have a table with columns like:
    # Round | Pick | Player | Position | College | ...
    # Find the main draft table (contains "Round" header or similar)
    draft_table = None
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
        if not headers:
            # Some pages use the first row as headers with <td>
            first_row = table.find("tr")
            if first_row:
                headers = [td.get_text(strip=True).upper() for td in first_row.find_all("td")]
        if any(h in ("ROUND", "RD", "PICK", "PLAYER") for h in headers):
            draft_table = table
            break

    if not draft_table:
        # Fallback: try to parse any table with numeric first column (round numbers)
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) > 3:
                # Check if first data cell looks like a round number
                first_cells = rows[1].find_all("td") if len(rows) > 1 else []
                if first_cells and first_cells[0].get_text(strip=True).isdigit():
                    draft_table = table
                    break

    if not draft_table:
        return picks

    rows = draft_table.find_all("tr")
    if not rows:
        return picks

    # Determine header row and column positions
    header_row = rows[0]
    headers = [cell.get_text(strip=True).upper() for cell in header_row.find_all(["th", "td"])]

    def find_col(names):
        for name in names:
            for i, h in enumerate(headers):
                if name in h:
                    return i
        return None

    round_idx = find_col(["ROUND", "RD"])
    pick_idx = find_col(["PICK", "PK", "OVERALL"])
    player_idx = find_col(["PLAYER", "NAME"])
    pos_idx = find_col(["POS", "POSITION"])
    college_idx = find_col(["COLLEGE", "SCHOOL"])

    # If we couldn't find headers, assume positional defaults
    if round_idx is None:
        round_idx = 0
    if pick_idx is None:
        pick_idx = 1
    if player_idx is None:
        player_idx = 2
    if pos_idx is None:
        pos_idx = 3
    if college_idx is None:
        college_idx = 4

    current_round = None

    for tr in rows[1:]:
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue

        # Some pages use bold/header rows to indicate round breaks
        if len(cells) == 1:
            text = cells[0].get_text(strip=True)
            round_m = re.match(r'(\d+)(?:st|nd|rd|th)?\s*Round', text, re.IGNORECASE)
            if round_m:
                current_round = int(round_m.group(1))
            continue

        if len(cells) < 3:
            continue

        def cell_text(idx):
            if idx < len(cells):
                return cells[idx].get_text(strip=True)
            return ""

        def cell_link(idx):
            if idx < len(cells):
                a = cells[idx].find("a", href=True)
                return a["href"] if a else None
            return None

        # Round
        round_text = cell_text(round_idx)
        round_num = None
        if round_text.isdigit():
            round_num = int(round_text)
        elif current_round is not None:
            round_num = current_round
        else:
            continue  # Can't determine round

        # Pick (overall)
        pick_text = cell_text(pick_idx)
        pick_num = None
        if pick_text.isdigit():
            pick_num = int(pick_text)
        else:
            # Some pages only have pick-within-round; use position in list
            pick_num = len(picks) + 1

        # Player name and optional player_id from link
        player_name = cell_text(player_idx)
        if not player_name or player_name.upper() in ("PLAYER", "NAME", ""):
            continue
        player_href = cell_link(player_idx)
        player_id = _extract_player_id(player_href)

        position = cell_text(pos_idx) if pos_idx < len(cells) else None
        college = cell_text(college_idx) if college_idx < len(cells) else None

        picks.append({
            "season": year,
            "round": round_num,
            "pick": pick_num,
            "player_name": player_name,
            "player_id": player_id,
            "position": position or None,
            "college": college or None,
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
