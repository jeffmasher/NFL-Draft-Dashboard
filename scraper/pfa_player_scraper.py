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


def parse_player_page(html):
    """
    Parse a PFA player page and extract bio, participation, and career defensive stats.

    Returns a dict:
    {
      "height": "6-7",
      "weight": 245,
      "birth_date": "March 26, 1951",
      "birth_city": "Chicago, IL",
      "college": "Purdue",
      "position": "DE",
      "draft_round": 2,
      "draft_pick": 51,
      "draft_year": 1973,
      "participation": [{"season": 1973, "gp": 14, "gs": 0, "jersey": "63", "position": "DE"}, ...],
      "sacks_by_season": [{"season": 1973, "sacks": 1.0, "yds": None}, ...],
      "fumbles_by_season": [{"season": 1974, "opp_rec": 1, "opp_yds": 0, "td": 0}, ...],
    }
    """
    soup = BeautifulSoup(html, "lxml")
    result = {}

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

    born_city_match = re.search(
        r'Born[^<\n]+(?:January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+\d{1,2},\s+\d{4}\s+in\s+([^<\n]+?)(?:\s{2,}|\||\n|$)',
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
    result["sacks_by_season"] = _parse_career_table(soup, "SACKS", ["season", "sacks", "yds"])

    # ── Career fumbles table ──────────────────────────────────────────────────
    result["fumbles_by_season"] = _parse_career_table(soup, "FUMBLES", ["season", "opp_rec", "opp_yds", "td"])

    return result


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

    # Find the table with GP/GS headers
    gp_table = None
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        header_str = " ".join(headers)
        if "GP" in header_str and "GS" in header_str:
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


def _parse_career_table(soup, section_keyword, field_names):
    """
    Generic parser for career stat tables (SACKS, FUMBLES) that list Saints rows.

    section_keyword: string to find the section heading (e.g. "SACKS")
    field_names: list of keys for the data columns (not counting year/team col)
    Returns list of dicts with "season" plus the named fields.
    """
    # Find section heading
    section = None
    for tag in soup.find_all(["h2", "h3", "b", "strong", "caption"]):
        if section_keyword.lower() in tag.get_text(strip=True).lower():
            section = tag
            break

    if not section:
        return []

    table = section.find_next("table")
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        year_team_text = cells[0].get_text(strip=True)
        if "New Orleans Saints" not in year_team_text and "NO NFL" not in year_team_text:
            continue

        year_match = re.match(r"(\d{4})", year_team_text)
        if not year_match:
            continue
        season = int(year_match.group(1))

        row = {"season": season}
        for i, field in enumerate(field_names):
            if field == "season":
                continue
            cell_idx = i + 1  # offset by 1 because col 0 is year/team
            raw = cells[cell_idx].get_text(strip=True) if cell_idx < len(cells) else ""
            if field == "sacks":
                row[field] = _parse_float(raw)
            else:
                row[field] = _parse_int(raw)
        rows.append(row)

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
