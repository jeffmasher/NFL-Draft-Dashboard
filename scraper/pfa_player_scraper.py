#!/usr/bin/env python3
"""
PFA Player Scraper — Saints Encyclopedia

Scrapes full bio data, GP/GS participation (with jersey number), and
career defensive stats (sacks, fumbles) from Pro Football Archives
player pages.

Usage:
    python pfa_player_scraper.py --full            # All players with PFA URLs
    python pfa_player_scraper.py --missing         # Only players without bio data yet
    python pfa_player_scraper.py --player mill18800  # Single player by ID
"""

import argparse
import os
import re
import sys
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from db import init_db, upsert_player, upsert_participation, upsert_page_sacks, upsert_page_fumbles

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUEST_DELAY = 1.0  # seconds between requests
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

def _parse_int(text):
    """Parse an integer from text, return None if not valid."""
    text = text.strip()
    try:
        return int(text)
    except (ValueError, AttributeError):
        return None


def _parse_float(text):
    """Parse a float from text, return None if not valid."""
    text = text.strip()
    try:
        return float(text)
    except (ValueError, AttributeError):
        return None


def _is_game_log_page(soup):
    """Return True if this is a PFA game-log page rather than a career stats page."""
    title = soup.find("title")
    if title and "Game Log" in title.get_text():
        return True
    # Also check for an h1/h2 with "Game Log"
    for tag in soup.find_all(["h1", "h2"]):
        if "Game Log" in tag.get_text():
            return True
    return False


def parse_player_page(html):
    """
    Parse a PFA player page and extract bio, participation, and career defensive stats.

    PFA has two page formats:
    - "Pro Football Stats" pages: bio header + season-level GP/GS table + career stat tables
    - "NFL Game Logs" pages: individual game rows only, no bio

    Returns a dict with any fields that could be extracted.
    """
    soup = BeautifulSoup(html, "lxml")
    result = {}

    if _is_game_log_page(soup):
        # Game log pages have no bio — extract GP by counting Saints game rows per season
        result["participation"] = _parse_game_log_participation(soup)
        if result["participation"]:
            result["position"] = result["participation"][-1].get("position") or result["participation"][0].get("position")
        result["sacks_by_season"] = []
        result["fumbles_by_season"] = []
        return result

    # ── Bio fields ────────────────────────────────────────────────────────────
    # PFA pages typically list bio info in a table or paragraph near the top.
    # Look for patterns like "Height: 6-4", "Weight: 235", "Born: ...", "Draft: ..."
    full_text = soup.get_text(" ", strip=True)

    # Height (e.g. "6-4" or "6'4"")
    ht_match = re.search(r'Height[:\s]+(\d-\d+)', full_text)
    if ht_match:
        result["height"] = ht_match.group(1)

    # Weight (e.g. "235")
    wt_match = re.search(r'Weight[:\s]+(\d{2,3})', full_text)
    if wt_match:
        result["weight"] = int(wt_match.group(1))

    # Born date and city — "Born: March 26, 1951 in Chicago, IL"
    born_match = re.search(
        r'Born[:\s]+((?:January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+\d{1,2},\s+\d{4})',
        full_text,
    )
    if born_match:
        result["birth_date"] = born_match.group(1)

    # City follows immediately after the date: "Born: September 20, 1935 Baton Rouge, LA"
    # Match "City, ST" pattern specifically; stops before Died/High School/end
    born_city_match = re.search(
        r'Born:\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+\d{1,2},\s+\d{4}\s+([A-Za-z][A-Za-z\s\.]+,\s+[A-Z]{2})'
        r'(?=\s|$)',
        full_text,
    )
    if born_city_match:
        result["birth_city"] = born_city_match.group(1).strip()

    # Draft info — "Draft: 2nd round (51st overall) 1973 New Orleans Saints"
    # or "Draft: Xnd round (Nth overall) YEAR New Orleans Saints"
    draft_match = re.search(
        r'Draft[:\s]+(\d+)(?:st|nd|rd|th)\s+round\s+\((\d+)(?:st|nd|rd|th)\s+overall\)\s+(\d{4})\s+New Orleans Saints',
        full_text,
        re.IGNORECASE,
    )
    if draft_match:
        result["draft_round"] = int(draft_match.group(1))
        result["draft_pick"] = int(draft_match.group(2))
        result["draft_year"] = int(draft_match.group(3))

    # College — look for a college table or text. Prefer a row with "Lettered".
    # PFA has a section "College" with a table listing year, college, status.
    college = _parse_college(soup)
    if college:
        result["college"] = college

    # ── GP/GS participation table ─────────────────────────────────────────────
    participation = _parse_participation(soup)
    result["participation"] = participation

    # Position from most recent Saints participation row
    if participation:
        result["position"] = participation[-1].get("position") or participation[0].get("position")

    # ── Career sacks table ────────────────────────────────────────────────────
    result["sacks_by_season"] = _parse_career_sacks(soup)

    # ── Career fumbles table ──────────────────────────────────────────────────
    result["fumbles_by_season"] = _parse_career_fumbles(soup)

    return result


def _parse_game_log_participation(soup):
    """
    For game-log format pages, count unique game dates per season for Saints rows.
    Returns list of dicts: [{season, gp, gs, jersey, position}, ...]
    """
    from collections import defaultdict
    games_by_season = defaultdict(set)

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            # First cell should be a date (MM/DD/YYYY)
            date_text = cells[0].get_text(strip=True)
            if not re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_text):
                continue
            # Second cell should contain the team name
            team_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            if "New Orleans Saints" not in team_text and "NO NFL" not in team_text:
                continue
            year_match = re.match(r'(\d{4})', team_text)
            if not year_match:
                continue
            season = int(year_match.group(1))
            games_by_season[season].add(date_text)

    rows = []
    for season in sorted(games_by_season):
        rows.append({
            "season": season,
            "gp": len(games_by_season[season]),
            "gs": 0,
            "jersey": None,
            "position": None,
        })
    return rows


def _parse_college(soup):
    """Extract college name from PFA player page. Prefers 'Lettered' rows; falls back to last listed."""
    # Look for a section heading containing "College" then a table
    college_section = None
    for tag in soup.find_all(["h2", "h3", "b", "strong"]):
        if "college" in tag.get_text(strip=True).lower():
            college_section = tag
            break

    if college_section:
        table = college_section.find_next("table")
        if table:
            lettered_college = None
            last_college = None
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) >= 2:
                    college_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    status = cells[-1].get_text(strip=True) if len(cells) > 2 else ""
                    if college_name:
                        last_college = college_name
                        if "letter" in status.lower():
                            lettered_college = college_name
            return lettered_college or last_college

    # Fallback: look for "College:" label in page text
    full_text = soup.get_text(" ", strip=True)
    col_match = re.search(r'College[:\s]+([A-Z][^\d\n|]{2,40}?)(?:\s{2,}|\||\n|$)', full_text)
    if col_match:
        return col_match.group(1).strip()

    return None


def _parse_participation(soup):
    """
    Parse Saints GP/GS rows from the year-by-year table.
    Returns list of dicts: [{season, gp, gs, jersey, position}, ...]
    """
    rows = []

    # Find the GP/GS table — first header must be "YEAR TEAM" to exclude
    # the college participation table (which also has GP/GS columns).
    gp_table = None
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if headers and headers[0].upper() == "YEAR TEAM" and "GP" in headers and "GS" in headers:
            gp_table = table
            break

    if not gp_table:
        return rows

    # Figure out column indices from headers
    headers = [th.get_text(strip=True) for th in gp_table.find_all("th")]
    # Typical columns: Year/Team | Jersey | Pos | GP | GS  (indices vary)
    def col_idx(names):
        for name in names:
            for i, h in enumerate(headers):
                if name.upper() == h.upper():
                    return i
        return None

    gp_idx = col_idx(["GP"])
    gs_idx = col_idx(["GS"])
    jersey_idx = col_idx(["No", "#", "Jersey"])
    pos_idx = col_idx(["Pos", "Position"])
    # Year+Team is almost always column 0

    for tr in gp_table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        year_team_text = cells[0].get_text(strip=True)

        # Only Saints rows
        if "New Orleans Saints" not in year_team_text and "NO NFL" not in year_team_text:
            continue

        year_match = re.match(r"(\d{4})", year_team_text)
        if not year_match:
            continue
        season = int(year_match.group(1))

        def cell_text(idx):
            if idx is not None and idx < len(cells):
                return cells[idx].get_text(strip=True)
            return ""

        # Fallback indices when headers are missing
        gp_text = cell_text(gp_idx if gp_idx is not None else 3)
        gs_text = cell_text(gs_idx if gs_idx is not None else 4)
        jersey = cell_text(jersey_idx) if jersey_idx is not None else ""
        position = cell_text(pos_idx) if pos_idx is not None else ""

        gp = int(gp_text) if gp_text.isdigit() else 0
        gs = int(gs_text) if gs_text.isdigit() else 0

        rows.append({
            "season": season,
            "gp": gp,
            "gs": gs,
            "jersey": jersey or None,
            "position": position or None,
        })

    return rows


def _find_table_by_header(soup, keyword):
    """Find a table whose first <th> cell matches keyword (case-insensitive)."""
    for table in soup.find_all("table"):
        ths = table.find_all("th")
        if ths and ths[0].get_text(strip=True).upper() == keyword.upper():
            return table
    return None


def _header_col(headers, *names):
    """Return the index of the first header matching any of the given names."""
    for name in names:
        for i, h in enumerate(headers):
            if h.upper() == name.upper():
                return i
    return None


def _saints_rows(table):
    """Yield (season, cells) for Saints rows in a stat table."""
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        year_team = cells[0].get_text(strip=True)
        if "New Orleans Saints" not in year_team and "NO NFL" not in year_team:
            continue
        m = re.match(r"(\d{4})", year_team)
        if not m:
            continue
        yield int(m.group(1)), cells


def _parse_career_sacks(soup):
    """Parse season-level sacks from the SACKS table on a stats page."""
    table = _find_table_by_header(soup, "SACKS")
    if not table:
        return []
    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
    no_idx = _header_col(headers, "NO")
    yds_idx = _header_col(headers, "YDS")
    rows = []
    for season, cells in _saints_rows(table):
        def cv(idx):
            return cells[idx].get_text(strip=True) if idx is not None and idx < len(cells) else ""
        rows.append({"season": season, "sacks": _parse_float(cv(no_idx)), "yds": _parse_int(cv(yds_idx))})
    return rows


def _parse_career_fumbles(soup):
    """Parse season-level fumbles from the FUMBLES table on a stats page."""
    table = _find_table_by_header(soup, "FUMBLES")
    if not table:
        return []
    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
    opp_idx = _header_col(headers, "OPP")
    yds_idx = _header_col(headers, "YDS")
    td_idx = _header_col(headers, "TD")
    rows = []
    for season, cells in _saints_rows(table):
        def cv(idx):
            return cells[idx].get_text(strip=True) if idx is not None and idx < len(cells) else ""
        rows.append({"season": season, "opp_rec": _parse_int(cv(opp_idx)), "opp_yds": _parse_int(cv(yds_idx)), "td": _parse_int(cv(td_idx))})
    return rows


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def save_player_data(conn, player_id, data):
    """Persist all parsed data for a single player."""
    bio = {k: data.get(k) for k in ("height", "weight", "birth_date", "birth_city", "position", "college")}
    upsert_player(conn, player_id, "", bio=bio)

    if data.get("participation"):
        upsert_participation(conn, player_id, data["participation"])

    if data.get("sacks_by_season"):
        upsert_page_sacks(conn, player_id, data["sacks_by_season"])

    if data.get("fumbles_by_season"):
        upsert_page_fumbles(conn, player_id, data["fumbles_by_season"])

    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_player(session, conn, player_id, pfa_url):
    """Scrape a single player's full page data."""
    html = fetch(session, pfa_url)
    if not html:
        return False

    data = parse_player_page(html)
    save_player_data(conn, player_id, data)
    return True


def main():
    parser = argparse.ArgumentParser(description="Scrape bio + GP/GS from PFA player pages")
    parser.add_argument("--full", action="store_true", help="Scrape all players with PFA URLs")
    parser.add_argument("--missing", action="store_true", help="Only players without bio data yet")
    parser.add_argument("--player", type=str, help="Scrape a single player by ID")
    args = parser.parse_args()

    conn = init_db(DB_PATH)
    session = make_session()

    if args.player:
        row = conn.execute(
            "SELECT player_id, pfa_url FROM players WHERE player_id = ? AND pfa_url IS NOT NULL",
            (args.player,),
        ).fetchone()
        if not row:
            print(f"Player {args.player} not found or has no PFA URL")
            sys.exit(1)
        pid, url = row
        ok = scrape_player(session, conn, pid, url)
        print(f"  {pid}: {'ok' if ok else 'failed'}")

    elif args.full or args.missing:
        if args.missing:
            players = conn.execute("""
                SELECT p.player_id, p.pfa_url FROM players p
                WHERE p.pfa_url IS NOT NULL
                  AND p.height IS NULL
                ORDER BY p.player_name
            """).fetchall()
        else:
            players = conn.execute(
                "SELECT player_id, pfa_url FROM players WHERE pfa_url IS NOT NULL ORDER BY player_name"
            ).fetchall()

        total = len(players)
        print(f"Scraping player pages for {total} players...")
        success = 0
        failed = 0

        for i, (pid, url) in enumerate(players):
            ok = scrape_player(session, conn, pid, url)
            if ok:
                success += 1
                if (i + 1) % 50 == 0 or (i + 1) == total:
                    print(f"  [{i+1}/{total}] {pid}: ok")
            else:
                failed += 1
                print(f"  [{i+1}/{total}] {pid}: FAILED", file=sys.stderr)

            time.sleep(REQUEST_DELAY)

        print(f"\nDone! {success} ok, {failed} failed.")

    else:
        parser.print_help()
        sys.exit(1)

    conn.close()


if __name__ == "__main__":
    main()
