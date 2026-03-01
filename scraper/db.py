"""SQLite database layer for Saints Encyclopedia."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id         TEXT PRIMARY KEY,
    season          INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    day_of_week     TEXT,
    game_type       TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    opponent_abbr   TEXT,
    home_away       TEXT NOT NULL,
    saints_score    INTEGER,
    opponent_score  INTEGER,
    result          TEXT,
    location        TEXT,
    venue           TEXT,
    attendance      INTEGER,
    boxscore_url    TEXT
);

CREATE TABLE IF NOT EXISTS players (
    player_id       TEXT PRIMARY KEY,
    player_name     TEXT NOT NULL,
    pfa_url         TEXT
);

CREATE TABLE IF NOT EXISTS player_passing (
    game_id TEXT, player_id TEXT, team TEXT,
    att INT, com INT, pct REAL, int_thrown INT,
    yds INT, avg REAL, lg INT, td INT,
    sacked INT, sacked_yds INT, rtg REAL,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_rushing (
    game_id TEXT, player_id TEXT, team TEXT,
    att INT, yds INT, avg REAL, lg INT, td INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_receiving (
    game_id TEXT, player_id TEXT, team TEXT,
    tar INT, rec INT, yds INT, avg REAL, lg INT, td INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_defense (
    game_id TEXT, player_id TEXT, team TEXT,
    tkl INT, tfl INT, qh INT, pd INT, ff INT, bl INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_sacks (
    game_id TEXT, player_id TEXT, team TEXT,
    sacks REAL, yds INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_interceptions (
    game_id TEXT, player_id TEXT, team TEXT,
    int_count INT, yds INT, avg REAL, lg INT, td INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_punting (
    game_id TEXT, player_id TEXT, team TEXT,
    punts INT, yds INT, avg REAL, lg INT, bl INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_punt_returns (
    game_id TEXT, player_id TEXT, team TEXT,
    ret INT, fc INT, yds INT, avg REAL, lg INT, td INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_kick_returns (
    game_id TEXT, player_id TEXT, team TEXT,
    ret INT, fc INT, yds INT, avg REAL, lg INT, td INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS player_kickoffs (
    game_id TEXT, player_id TEXT, team TEXT,
    kickoffs INT, yds INT, avg REAL, tb INT,
    PRIMARY KEY (game_id, player_id, team)
);

CREATE TABLE IF NOT EXISTS team_game_stats (
    game_id TEXT, team TEXT,
    rush_att INT, rush_yds INT, rush_td INT,
    pass_att INT, pass_com INT, pass_yds INT, pass_td INT, pass_int INT,
    times_sacked INT, sack_yds_lost INT,
    sacks REAL, interceptions INT,
    punt_count INT, punt_yds INT,
    total_points INT,
    PRIMARY KEY (game_id, team)
);

CREATE TABLE IF NOT EXISTS scoring_plays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT, quarter INT, team TEXT,
    description TEXT, saints_score INT, opp_score INT
);

CREATE TABLE IF NOT EXISTS player_participation (
    player_id TEXT NOT NULL,
    season INTEGER NOT NULL,
    gp INTEGER NOT NULL DEFAULT 0,
    gs INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, season)
);

CREATE TABLE IF NOT EXISTS player_page_sacks (
    player_id TEXT NOT NULL,
    season INTEGER NOT NULL,
    sacks REAL,
    yds INTEGER,
    PRIMARY KEY (player_id, season)
);

CREATE TABLE IF NOT EXISTS player_page_fumbles (
    player_id TEXT NOT NULL,
    season INTEGER NOT NULL,
    opp_rec INTEGER,
    opp_yds INTEGER,
    td INTEGER,
    PRIMARY KEY (player_id, season)
);

CREATE TABLE IF NOT EXISTS draft_picks (
    season INTEGER NOT NULL,
    round INTEGER NOT NULL,
    pick INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    player_id TEXT,
    position TEXT,
    college TEXT,
    PRIMARY KEY (season, round, pick)
);

CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_scoring_game ON scoring_plays(game_id);
CREATE INDEX IF NOT EXISTS idx_participation_player ON player_participation(player_id);
"""

# Column lists for each stat table (used for inserts)
STAT_TABLE_COLS = {
    "player_passing": [
        "game_id", "player_id", "team",
        "att", "com", "pct", "int_thrown", "yds", "avg", "lg", "td",
        "sacked", "sacked_yds", "rtg",
    ],
    "player_rushing": [
        "game_id", "player_id", "team",
        "att", "yds", "avg", "lg", "td",
    ],
    "player_receiving": [
        "game_id", "player_id", "team",
        "tar", "rec", "yds", "avg", "lg", "td",
    ],
    "player_defense": [
        "game_id", "player_id", "team",
        "tkl", "tfl", "qh", "pd", "ff", "bl",
    ],
    "player_sacks": [
        "game_id", "player_id", "team",
        "sacks", "yds",
    ],
    "player_interceptions": [
        "game_id", "player_id", "team",
        "int_count", "yds", "avg", "lg", "td",
    ],
    "player_punting": [
        "game_id", "player_id", "team",
        "punts", "yds", "avg", "lg", "bl",
    ],
    "player_punt_returns": [
        "game_id", "player_id", "team",
        "ret", "fc", "yds", "avg", "lg", "td",
    ],
    "player_kick_returns": [
        "game_id", "player_id", "team",
        "ret", "fc", "yds", "avg", "lg", "td",
    ],
    "player_kickoffs": [
        "game_id", "player_id", "team",
        "kickoffs", "yds", "avg", "tb",
    ],
}


def init_db(path: str) -> sqlite3.Connection:
    """Create all tables and indexes. Returns a connection."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    # Add player bio columns (idempotent — ignore if already present)
    player_columns = [
        ("position", "TEXT"),
        ("college", "TEXT"),
        ("height", "TEXT"),
        ("weight", "INTEGER"),
        ("birth_date", "TEXT"),
        ("birth_city", "TEXT"),
        ("fdb_id", "TEXT"),
        ("fdb_url", "TEXT"),
        ("seasons_text", "TEXT"),
    ]
    for col_name, col_type in player_columns:
        try:
            conn.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass  # column already exists

    # Add jersey_number to player_participation (idempotent)
    try:
        conn.execute("ALTER TABLE player_participation ADD COLUMN jersey_number TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return conn


def upsert_game(conn: sqlite3.Connection, game: dict) -> None:
    """Insert or replace a game record."""
    cols = [
        "game_id", "season", "game_date", "day_of_week", "game_type",
        "opponent", "opponent_abbr", "home_away", "saints_score",
        "opponent_score", "result", "location", "venue", "attendance",
        "boxscore_url",
    ]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    vals = [game.get(c) for c in cols]
    conn.execute(
        f"INSERT OR REPLACE INTO games ({col_str}) VALUES ({placeholders})",
        vals,
    )


def upsert_player(conn: sqlite3.Connection, player_id: str, name: str, url: str | None = None, bio: dict | None = None) -> None:
    """Insert a player if not already present, optionally updating bio fields."""
    conn.execute(
        "INSERT OR IGNORE INTO players (player_id, player_name, pfa_url) VALUES (?, ?, ?)",
        (player_id, name, url),
    )
    if bio:
        fields = ["height", "weight", "birth_date", "birth_city", "position", "college"]
        updates = {f: bio[f] for f in fields if f in bio and bio[f] is not None}
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [player_id]
            conn.execute(f"UPDATE players SET {set_clause} WHERE player_id = ?", vals)


def upsert_participation(conn: sqlite3.Connection, player_id: str, rows: list) -> None:
    """Insert or replace participation rows for a player."""
    for row in rows:
        conn.execute(
            "INSERT OR REPLACE INTO player_participation (player_id, season, gp, gs, jersey_number) "
            "VALUES (?, ?, ?, ?, ?)",
            (player_id, row["season"], row.get("gp", 0), row.get("gs", 0), row.get("jersey")),
        )


def upsert_page_sacks(conn: sqlite3.Connection, player_id: str, rows: list) -> None:
    """Insert or replace season-level sack data from player pages."""
    for row in rows:
        conn.execute(
            "INSERT OR REPLACE INTO player_page_sacks (player_id, season, sacks, yds) VALUES (?, ?, ?, ?)",
            (player_id, row["season"], row.get("sacks"), row.get("yds")),
        )


def upsert_page_fumbles(conn: sqlite3.Connection, player_id: str, rows: list) -> None:
    """Insert or replace season-level fumble data from player pages."""
    for row in rows:
        conn.execute(
            "INSERT OR REPLACE INTO player_page_fumbles (player_id, season, opp_rec, opp_yds, td) VALUES (?, ?, ?, ?, ?)",
            (player_id, row["season"], row.get("opp_rec"), row.get("opp_yds"), row.get("td")),
        )


def upsert_draft_pick(conn: sqlite3.Connection, pick: dict) -> None:
    """Insert or replace a draft pick."""
    conn.execute(
        "INSERT OR REPLACE INTO draft_picks (season, round, pick, player_name, player_id, position, college) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (pick["season"], pick["round"], pick["pick"], pick["player_name"],
         pick.get("player_id"), pick.get("position"), pick.get("college")),
    )


def insert_stat_row(conn: sqlite3.Connection, table: str, row: dict) -> None:
    """Insert a stat row into the given table. Uses INSERT OR REPLACE."""
    cols = STAT_TABLE_COLS[table]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    vals = [row.get(c) for c in cols]
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})",
        vals,
    )


def insert_scoring_play(conn: sqlite3.Connection, play: dict) -> None:
    """Insert a scoring play."""
    conn.execute(
        "INSERT INTO scoring_plays (game_id, quarter, team, description, saints_score, opp_score) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (play["game_id"], play.get("quarter"), play.get("team"),
         play.get("description"), play.get("saints_score"), play.get("opp_score")),
    )


def clear_game_stats(conn: sqlite3.Connection, game_id: str) -> None:
    """Remove all stat rows for a game (used before re-scraping)."""
    for table in STAT_TABLE_COLS:
        conn.execute(f"DELETE FROM {table} WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM scoring_plays WHERE game_id = ?", (game_id,))
    conn.execute("DELETE FROM team_game_stats WHERE game_id = ?", (game_id,))


def compute_team_totals(conn: sqlite3.Connection, game_id: str) -> None:
    """Aggregate player stats into team_game_stats for a given game."""
    # Get distinct teams in this game from rushing (most reliable — nearly every game has rushers)
    teams = [r[0] for r in conn.execute(
        "SELECT DISTINCT team FROM player_rushing WHERE game_id = ? "
        "UNION SELECT DISTINCT team FROM player_passing WHERE game_id = ?",
        (game_id, game_id),
    ).fetchall()]

    for team in teams:
        rush = conn.execute(
            "SELECT COALESCE(SUM(att),0), COALESCE(SUM(yds),0), COALESCE(SUM(td),0) "
            "FROM player_rushing WHERE game_id=? AND team=?", (game_id, team)
        ).fetchone()
        passing = conn.execute(
            "SELECT COALESCE(SUM(att),0), COALESCE(SUM(com),0), COALESCE(SUM(yds),0), "
            "COALESCE(SUM(td),0), COALESCE(SUM(int_thrown),0), "
            "COALESCE(SUM(sacked),0), COALESCE(SUM(sacked_yds),0) "
            "FROM player_passing WHERE game_id=? AND team=?", (game_id, team)
        ).fetchone()
        sacks = conn.execute(
            "SELECT COALESCE(SUM(sacks),0) FROM player_sacks WHERE game_id=? AND team=?",
            (game_id, team),
        ).fetchone()
        ints = conn.execute(
            "SELECT COALESCE(SUM(int_count),0) FROM player_interceptions WHERE game_id=? AND team=?",
            (game_id, team),
        ).fetchone()
        punting = conn.execute(
            "SELECT COALESCE(SUM(punts),0), COALESCE(SUM(yds),0) "
            "FROM player_punting WHERE game_id=? AND team=?", (game_id, team)
        ).fetchone()

        # Get total points from the games table
        game = conn.execute(
            "SELECT saints_score, opponent_score, home_away, opponent FROM games WHERE game_id=?",
            (game_id,),
        ).fetchone()
        total_points = None
        if game:
            saints_score, opp_score, home_away, opponent = game
            # Determine if this team is Saints or opponent
            # We use "New Orleans Saints" as the Saints identifier
            if team in ("New Orleans Saints", "NO", "Saints"):
                total_points = saints_score
            else:
                total_points = opp_score

        conn.execute(
            "INSERT OR REPLACE INTO team_game_stats "
            "(game_id, team, rush_att, rush_yds, rush_td, "
            "pass_att, pass_com, pass_yds, pass_td, pass_int, "
            "times_sacked, sack_yds_lost, sacks, interceptions, "
            "punt_count, punt_yds, total_points) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (game_id, team,
             rush[0], rush[1], rush[2],
             passing[0], passing[1], passing[2], passing[3], passing[4],
             passing[5], passing[6],
             sacks[0], ints[0],
             punting[0], punting[1],
             total_points),
        )


def game_exists(conn: sqlite3.Connection, game_id: str) -> bool:
    """Check if a game's box score stats have already been scraped."""
    row = conn.execute(
        "SELECT COUNT(*) FROM player_rushing WHERE game_id = ?", (game_id,)
    ).fetchone()
    return row[0] > 0
