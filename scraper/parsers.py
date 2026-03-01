"""HTML parsers for Pro Football Archives season pages and box scores."""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.profootballarchives.com/"

# ---------------------------------------------------------------------------
# Season page parsing
# ---------------------------------------------------------------------------

def parse_season_page(html: str, season: int) -> list[dict]:
    """Parse a PFA season page and return a list of game dicts.

    Each dict has keys: game_id, season, game_date, day_of_week, game_type,
    opponent, opponent_abbr, home_away, saints_score, opponent_score, result,
    overtime, location, venue, attendance, boxscore_url.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find the SCORES table — first row text is "SCORES"
    scores_table = None
    for table in soup.find_all("table"):
        first_row = table.find("tr")
        if first_row and first_row.get_text(strip=True) == "SCORES":
            scores_table = table
            break

    if scores_table is None:
        return []

    games = []
    game_type = "preseason"  # default; switches to regular once we see boxscore links
    regular_started = False

    for row in scores_table.find_all("tr")[1:]:  # skip the "SCORES" header row
        cells = row.find_all("td")

        # Bold single-cell row = playoff round header
        if len(cells) == 1:
            cell = cells[0]
            if cell.find("b"):
                game_type = "playoff"
            continue

        # Game rows have 11 cells:
        # 0:day, 1:date, 2:H/A, 3:opponent, 4:saints_score, 5:opp_score,
        # 6:result, 7:OT marker, 8:location, 9:venue, 10:attendance
        if len(cells) < 10:
            continue

        day = _text(cells[0])
        date_cell = cells[1]
        home_away_raw = _text(cells[2])
        opponent_cell = cells[3]
        saints_score_raw = _text(cells[4])
        opp_score_raw = _text(cells[5])
        result_raw = _text(cells[6])
        ot_marker = _text(cells[7]) if len(cells) > 7 else ""
        location = _text(cells[8]) if len(cells) > 8 else ""
        venue = _text(cells[9]) if len(cells) > 9 else ""
        attendance_raw = _text(cells[10]) if len(cells) > 10 else ""

        # Determine if this game has a box score link
        date_link = date_cell.find("a")
        boxscore_url = None
        game_id = None

        if date_link:
            href = date_link["href"]
            boxscore_url = urljoin(BASE_URL, href)
            # Extract game_id from URL: /nflboxscores2/2024nfl058.html -> 2024nfl058
            match = re.search(r"(\d{4}nfl\d+)\.html", href)
            if match:
                game_id = match.group(1)
            # First linked game means regular season has started
            if not regular_started:
                regular_started = True
                if game_type != "playoff":
                    game_type = "regular"
        else:
            # No link = preseason (or cancelled game)
            if not regular_started:
                game_type = "preseason"

        # Parse date: M/D/YYYY -> YYYY-MM-DD
        date_text = date_cell.get_text(strip=True)
        game_date = _parse_date(date_text)

        # Generate a game_id for preseason games that don't have one
        if game_id is None:
            game_id = f"{season}pre{game_date.replace('-', '')}"

        # Opponent
        opp_link = opponent_cell.find("a")
        opponent_name = opponent_cell.get_text(strip=True)
        opponent_abbr = None
        if opp_link:
            # Extract abbr from href: 2024nflcar.html -> car
            opp_match = re.search(r"\d{4}nfl(\w+)\.html", opp_link["href"])
            if opp_match:
                opponent_abbr = opp_match.group(1).upper()

        # Home/Away
        home_away = {"H": "home", "A": "away", "N": "neutral"}.get(home_away_raw, home_away_raw)

        # Parse scores
        saints_score = _safe_int(saints_score_raw)
        opponent_score = _safe_int(opp_score_raw)

        # Result — handle OT
        result = result_raw  # W, L, T
        overtime = ot_marker.upper() == "OT"

        games.append({
            "game_id": game_id,
            "season": season,
            "game_date": game_date,
            "day_of_week": day,
            "game_type": game_type if date_link or not regular_started else "regular",
            "opponent": opponent_name,
            "opponent_abbr": opponent_abbr,
            "home_away": home_away,
            "saints_score": saints_score,
            "opponent_score": opponent_score,
            "result": result,
            "location": location,
            "venue": venue,
            "attendance": _safe_int(attendance_raw),
            "boxscore_url": boxscore_url,
        })

        # After first linked game, all subsequent non-playoff games are regular
        if regular_started and game_type != "playoff":
            game_type = "regular"

    return games


# ---------------------------------------------------------------------------
# Box score parsing
# ---------------------------------------------------------------------------

# Map of stat section name -> (db table, column mapping)
# Column mapping: list of (html_col_name, db_col_name) pairs
# The first column (player name) is handled specially.
STAT_SECTIONS = {
    "RUSHING": {
        "table": "player_rushing",
        "cols": [("ATT", "att"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td")],
    },
    "PASSING": {
        "table": "player_passing",
        "cols": [
            ("ATT", "att"), ("COM", "com"), ("PCT", "pct"), ("INT", "int_thrown"),
            ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td"),
            ("TS", "sacked"), ("YL", "sacked_yds"), ("RTG", "rtg"),
        ],
    },
    "RECEIVING": {
        "table": "player_receiving",
        # Modern: TAR, REC, YDS, AVG, LG, TD
        # Older:  NO, YDS, AVG, LG, TD (NO = receptions)
        "cols_modern": [("TAR", "tar"), ("REC", "rec"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td")],
        "cols_legacy": [("NO", "rec"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td")],
    },
    "INTERCEPTIONS": {
        "table": "player_interceptions",
        "cols": [("NO", "int_count"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td")],
    },
    "PUNTING": {
        "table": "player_punting",
        "cols": [("NO", "punts"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("BL", "bl")],
    },
    "PUNT RETURNS": {
        "table": "player_punt_returns",
        "cols": [("NO", "ret"), ("FC", "fc"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td")],
    },
    "KICKOFF RETURNS": {
        "table": "player_kick_returns",
        "cols": [("NO", "ret"), ("FC", "fc"), ("YDS", "yds"), ("AVG", "avg"), ("LG", "lg"), ("TD", "td")],
    },
    "KICKOFFS": {
        "table": "player_kickoffs",
        "cols": [("NO", "kickoffs"), ("YDS", "yds"), ("AVG", "avg"), ("TB", "tb")],
    },
    "SACKS": {
        "table": "player_sacks",
        # Modern: NO, YDS.  Older: NO only.
        "cols_modern": [("NO", "sacks"), ("YDS", "yds")],
        "cols_legacy": [("NO", "sacks")],
    },
    "DEFENSE": {
        "table": "player_defense",
        "cols": [("TKL", "tkl"), ("TFL", "tfl"), ("QH", "qh"), ("PD", "pd"), ("FF", "ff"), ("BL", "bl")],
    },
}


def parse_boxscore(html: str, game_id: str) -> dict:
    """Parse a PFA box score page.

    Returns a dict with:
        - teams: (away_team, home_team)
        - metadata: {date, location, venue, attendance}
        - scoring_plays: list of dicts
        - stats: {table_name: [row_dicts]}  where each row_dict has game_id, player_id, team, ...
        - players: {player_id: {name, url}}
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")

    result = {
        "teams": (None, None),
        "metadata": {},
        "scoring_plays": [],
        "stats": {},
        "players": {},
    }

    if len(tables) < 5:
        return result

    # --- Table 0: Game header ---
    header_text = tables[0].get_text(strip=True)
    # "Carolina Panthers at New Orleans Saints" -> (away, home)
    match = re.match(r"(.+?)\s+at\s+(.+?)(?:Game Statistics|$)", header_text)
    if match:
        result["teams"] = (match.group(1).strip(), match.group(2).strip())

    # --- Table 1: Metadata ---
    meta_text = tables[1].get_text()
    for pattern, key in [
        (r"Date:\s*(.+?)(?=Location:|$)", "date"),
        (r"Location:\s*(.+?)(?=Venue:|$)", "location"),
        (r"Venue:\s*(.+?)(?=Attendance:|$)", "venue"),
        (r"Attendance:\s*([\d,]+)", "attendance"),
    ]:
        m = re.search(pattern, meta_text)
        if m:
            val = m.group(1).strip()
            if key == "attendance":
                val = int(val.replace(",", ""))
            result["metadata"][key] = val

    # --- Table 4 (usually): Scoring plays ---
    scoring_table = _find_table_by_header(tables, "Qtr")
    if scoring_table:
        result["scoring_plays"] = _parse_scoring_plays(scoring_table, game_id, result["teams"])

    # --- Stat tables ---
    for section_name, config in STAT_SECTIONS.items():
        stat_table = _find_table_by_header(tables, section_name)
        if stat_table is None:
            continue

        table_name = config["table"]
        rows = stat_table.find_all("tr")
        if not rows:
            continue

        # Determine column mapping from header row
        header_cells = rows[0].find_all(["th", "td"])
        header_texts = [c.get_text(strip=True) for c in header_cells]

        col_map = _get_col_map(section_name, config, header_texts)
        if not col_map:
            continue

        # Parse player rows using a two-pass approach.
        # Team separators can appear BEFORE (header) or AFTER (footer) each
        # team's players, and sometimes there's only 1 separator for 2 teams
        # (e.g. DEFENSE). We collect all entries first, then assign teams.

        entries = []  # list of ("separator", team_name) or ("player", stat_row)

        for row in rows[1:]:  # skip header
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            first_cell = cells[0]
            first_text = first_cell.get_text(strip=True)

            if _is_team_separator(cells):
                entries.append(("separator", first_text))
                continue

            player_link = first_cell.find("a")
            if player_link:
                player_name = first_text
                player_href = player_link.get("href", "")
                player_id = _extract_player_id(player_href)

                if player_id:
                    result["players"][player_id] = {
                        "name": player_name,
                        "url": urljoin(BASE_URL, player_href),
                    }

                    stat_row = {
                        "game_id": game_id,
                        "player_id": player_id,
                        "team": None,
                    }

                    for i, (html_col, db_col) in enumerate(col_map):
                        cell_idx = i + 1
                        if cell_idx < len(cells):
                            stat_row[db_col] = _parse_stat_value(
                                cells[cell_idx].get_text(strip=True), db_col
                            )
                        else:
                            stat_row[db_col] = None

                    entries.append(("player", stat_row))

        # Assign teams to player rows
        stat_rows = _assign_teams(entries, result["teams"])

        if stat_rows:
            result["stats"][table_name] = stat_rows

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _text(cell) -> str:
    return cell.get_text(strip=True)


def _parse_date(date_str: str) -> str:
    """Convert M/D/YYYY to YYYY-MM-DD."""
    match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
    if match:
        m, d, y = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return date_str


def _safe_int(s: str) -> int | None:
    s = s.replace(",", "").strip()
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_stat_value(text: str, col_name: str):
    """Parse a stat cell value. Handles trailing 't' on long plays (e.g. '59t' = TD)."""
    if not text or text == "-" or text == "":
        return None

    # Strip trailing 't' (indicates the long play was a touchdown)
    text = text.rstrip("t").strip()

    # Real-valued columns
    if col_name in ("avg", "pct", "rtg", "sacks"):
        try:
            return float(text)
        except ValueError:
            return None

    # Integer columns
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def _find_table_by_header(tables: list, header_text: str):
    """Find a table whose first row's first cell matches header_text."""
    for table in tables:
        first_row = table.find("tr")
        if first_row:
            first_cell = first_row.find(["th", "td"])
            if first_cell and first_cell.get_text(strip=True) == header_text:
                return table
    return None


def _assign_teams(entries: list, game_teams: tuple) -> list[dict]:
    """Assign team names to player stat rows based on separator positions.

    Handles three patterns:
    - Header: sep → players → sep → players (separator names following players)
    - Footer: players → sep → players → sep (separator names preceding players)
    - Single: players → sep → players (separator divides two teams)
    """
    away_team, home_team = game_teams

    # Find separator positions and team names
    separators = [(i, name) for i, (kind, name) in enumerate(entries) if kind == "separator"]
    player_indices = [i for i, (kind, _) in enumerate(entries) if kind == "player"]

    if not player_indices:
        return []

    # Determine mode from separator positions relative to players
    if not separators:
        # No separators — assign all to away team (best guess)
        for i in player_indices:
            entries[i][1]["team"] = away_team or "Unknown"
    elif len(separators) == 1:
        # Single separator — divides away (before) and home (after)
        sep_idx, sep_team = separators[0]
        other_team = home_team if sep_team == away_team else away_team
        for i in player_indices:
            if i < sep_idx:
                entries[i][1]["team"] = other_team or "Unknown"
            else:
                entries[i][1]["team"] = sep_team
    elif len(separators) >= 2:
        # Two+ separators — determine if header or footer style
        first_sep_idx = separators[0][0]
        first_player_idx = player_indices[0] if player_indices else 999

        if first_sep_idx < first_player_idx:
            # Header mode: separators come before their players
            current_team = None
            for kind, data in entries:
                if kind == "separator":
                    current_team = data
                elif kind == "player":
                    data["team"] = current_team or "Unknown"
        else:
            # Footer mode: separators come after their players
            # Work backwards from each separator
            prev_end = 0
            for sep_idx, sep_team in separators:
                for i in player_indices:
                    if prev_end <= i < sep_idx:
                        entries[i][1]["team"] = sep_team
                prev_end = sep_idx + 1
            # Any remaining players after the last separator
            last_sep_idx = separators[-1][0]
            for i in player_indices:
                if i > last_sep_idx and entries[i][1]["team"] is None:
                    entries[i][1]["team"] = "Unknown"

    return [data for kind, data in entries if kind == "player"]


def _is_team_separator(cells) -> bool:
    """Check if a row is a team separator (team name + colspan cells).

    Separator rows use <th> tags, have 2 cells, second has colspan,
    and the first cell does NOT contain a player link.
    """
    if len(cells) < 2:
        return False
    # Team separator: second cell has a colspan attribute and no player link in first
    if cells[1].get("colspan") and not cells[0].find("a"):
        return True
    return False


def _extract_player_id(href: str) -> str | None:
    """Extract player ID from a PFA player URL.

    /players/s/shah00050.html -> shah00050
    """
    match = re.search(r"/players/\w/(\w+)\.html", href)
    if match:
        return match.group(1)
    return None


def _get_col_map(section_name: str, config: dict, header_texts: list) -> list:
    """Get the column mapping for a stat section based on actual header columns."""
    if "cols" in config:
        return config["cols"]

    # Sections with era-dependent columns
    if "cols_modern" in config:
        modern_cols = config["cols_modern"]
        legacy_cols = config["cols_legacy"]
        # Check if the header matches modern or legacy
        if modern_cols[0][0] in header_texts:
            return modern_cols
        else:
            return legacy_cols

    return []


def _parse_scoring_plays(table, game_id: str, teams: tuple) -> list[dict]:
    """Parse the scoring plays table."""
    rows = table.find_all("tr")
    if not rows:
        return []

    # Header row tells us the team abbreviations
    header_cells = rows[0].find_all(["th", "td"])
    # Columns: Qtr, Team, Scoring Plays, AwayAbbr, HomeAbbr

    plays = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        qtr_text = _text(cells[0])
        team_text = _text(cells[1])
        description = cells[2].get_text(separator=" ", strip=True)
        away_score = _safe_int(_text(cells[3]))
        home_score = _safe_int(_text(cells[4]))

        qtr = _safe_int(qtr_text)

        # Determine if saints are home or away
        saints_team = teams[1] if teams[1] and "New Orleans" in teams[1] else teams[0]
        is_saints_home = teams[1] and "New Orleans" in teams[1]

        saints_score = home_score if is_saints_home else away_score
        opp_score = away_score if is_saints_home else home_score

        plays.append({
            "game_id": game_id,
            "quarter": qtr,
            "team": team_text,
            "description": description,
            "saints_score": saints_score,
            "opp_score": opp_score,
        })

    return plays
