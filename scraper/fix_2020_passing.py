#!/usr/bin/env python3
"""Fix missing 2020 Saints passing data by fetching from FootballDB."""

import re
import sqlite3
import time

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DB_PATH = "saints_encyclopedia.db"
BASE_URL = "https://www.footballdb.com"
REQUEST_DELAY = 1.5


def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    return session


def extract_fdb_player_id(href):
    match = re.search(r"/players/[\w-]+-(\w+)$", href)
    if match:
        return f"fdb_{match.group(1)}"
    return None


def parse_stat_value(text, col_name):
    if not text or text == "-":
        return None
    text = text.rstrip("t").strip()
    if col_name in ("avg", "pct", "rtg"):
        try:
            return float(text)
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def find_fdb_boxscore_urls(session, season):
    """Get all FootballDB box score URLs for a Saints season."""
    url = f"https://www.footballdb.com/teams/nfl/new-orleans-saints/results/{season}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    games = {}
    for link in soup.find_all("a", href=re.compile(r"/games/boxscore/")):
        href = link["href"]
        date_match = re.search(r"(\d{8})\d{2}$", href)
        if date_match:
            date_str = date_match.group(1)
            game_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            games[game_date] = urljoin(BASE_URL, href)

    return games


def parse_passing_from_fdb(session, boxscore_url, game_id):
    """Fetch a FootballDB box score and extract Saints passing stats."""
    resp = session.get(boxscore_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    tables = soup.find_all("table")

    if len(tables) < 6:
        return [], {}

    # Identify teams from first stat table pair (indices 4,5 = passing)
    # Find passing tables by looking for "Att", "Cmp" headers
    passing_tables = []
    for i, tbl in enumerate(tables):
        first_row = tbl.find("tr")
        if first_row:
            headers = [c.get_text(strip=True) for c in first_row.find_all(["th", "td"])]
            if "Att" in headers and "Cmp" in headers and "Yds" in headers and "TD" in headers:
                passing_tables.append((i, tbl))

    if len(passing_tables) < 2:
        return [], {}

    col_map = {
        "Att": "att", "Cmp": "com", "Yds": "yds", "TD": "td",
        "Int": "int_thrown", "Lg": "lg", "Sack": "sacked",
        "Loss": "sacked_yds", "Rate": "rtg",
    }

    saints_rows = []
    players = {}

    for _, tbl in passing_tables:
        rows = tbl.find_all("tr")
        if len(rows) < 2:
            continue

        # Get team name from the row before the header or from table caption
        # FootballDB puts team name in a header row
        team_name = None
        prev = tbl.find_previous_sibling()
        while prev:
            text = prev.get_text(strip=True)
            if "Saints" in text or "New Orleans" in text:
                team_name = "New Orleans Saints"
                break
            if text and len(text) > 3:
                break
            prev = prev.find_previous_sibling()

        # Also check the table's own structure
        if not team_name:
            # Check all text in table for Saints
            table_text = tbl.get_text()
            if "Saints" in table_text or "New Orleans" in table_text:
                team_name = "New Orleans Saints"

        if team_name != "New Orleans Saints":
            continue

        # Parse header
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True) for c in header_cells]

        for row in rows[1:]:
            cells = row.find_all("td")
            if not cells:
                continue

            player_text = cells[0].get_text(strip=True)
            if player_text == "TOTAL" or not player_text:
                continue

            player_link = cells[0].find("a")
            if not player_link:
                continue

            # Clean player name
            player_name = player_text
            for j in range(len(player_name) - 1, 0, -1):
                if player_name[j] == "." and j >= 1:
                    k = j - 1
                    while k > 0 and player_name[k].isupper():
                        k -= 1
                    if k > 0 and k < j:
                        player_name = player_name[:k + 1].strip()
                        break
            player_name = player_name.replace("\xa0", " ")

            player_href = player_link.get("href", "")
            player_id = extract_fdb_player_id(player_href)
            if not player_id:
                continue

            players[player_id] = {"name": player_name, "url": urljoin(BASE_URL, player_href)}

            stat_row = {
                "game_id": game_id,
                "player_id": player_id,
                "team": "New Orleans Saints",
            }

            for i, hdr in enumerate(headers[1:], 1):
                db_col = col_map.get(hdr)
                if db_col and i < len(cells):
                    stat_row[db_col] = parse_stat_value(cells[i].get_text(strip=True), db_col)

            # Compute pct
            att = stat_row.get("att", 0) or 0
            com = stat_row.get("com", 0) or 0
            stat_row["pct"] = round(com / att * 100, 1) if att > 0 else 0.0
            stat_row["avg"] = round(stat_row.get("yds", 0) / att, 1) if att > 0 else 0.0

            saints_rows.append(stat_row)

    return saints_rows, players


def main():
    conn = sqlite3.connect(DB_PATH)

    # Get 2020 regular season games missing Saints passing
    games = conn.execute("""
        SELECT g.game_id, g.game_date, g.opponent
        FROM games g
        WHERE g.season = 2020 AND g.game_type = 'regular'
        AND NOT EXISTS (
            SELECT 1 FROM player_passing pp
            WHERE pp.game_id = g.game_id
            AND (pp.team LIKE '%Saints%' OR pp.team LIKE '%New Orleans%')
        )
        ORDER BY g.game_date
    """).fetchall()

    print(f"Found {len(games)} games missing Saints passing data")

    if not games:
        print("Nothing to fix!")
        conn.close()
        return

    session = make_session()

    # Get FootballDB URLs for 2020
    print("Fetching FootballDB game URLs for 2020...")
    fdb_urls = find_fdb_boxscore_urls(session, 2020)
    print(f"  Found {len(fdb_urls)} FootballDB box scores")
    time.sleep(REQUEST_DELAY)

    fixed = 0
    for game_id, game_date, opponent in games:
        fdb_url = fdb_urls.get(game_date)
        if not fdb_url:
            print(f"  {game_date} vs {opponent}: No FootballDB URL found")
            continue

        print(f"  {game_date} vs {opponent}: fetching {fdb_url}")
        try:
            passing_rows, players = parse_passing_from_fdb(session, fdb_url, game_id)
        except Exception as e:
            print(f"    ERROR: {e}")
            time.sleep(REQUEST_DELAY)
            continue

        if not passing_rows:
            print(f"    No Saints passing data found")
            time.sleep(REQUEST_DELAY)
            continue

        # Insert players
        for pid, pinfo in players.items():
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, player_name, pfa_url) VALUES (?, ?, ?)",
                (pid, pinfo["name"], pinfo["url"])
            )

        # Insert passing rows
        for row in passing_rows:
            conn.execute(
                """INSERT OR REPLACE INTO player_passing
                   (game_id, player_id, team, att, com, pct, int_thrown, yds, avg, lg, td, sacked, sacked_yds, rtg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["game_id"], row["player_id"], row["team"],
                 row.get("att"), row.get("com"), row.get("pct"),
                 row.get("int_thrown"), row.get("yds"), row.get("avg"),
                 row.get("lg"), row.get("td"), row.get("sacked"),
                 row.get("sacked_yds"), row.get("rtg"))
            )

        conn.commit()
        names = [r["player_id"] for r in passing_rows]
        print(f"    Inserted {len(passing_rows)} passing rows: {names}")
        fixed += 1
        time.sleep(REQUEST_DELAY)

    conn.close()
    print(f"\nDone! Fixed {fixed}/{len(games)} games")


if __name__ == "__main__":
    main()
