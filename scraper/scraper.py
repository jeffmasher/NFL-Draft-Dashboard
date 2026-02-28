"""
Saints Football Encyclopedia - Pro Football Reference / StatHead Scraper
========================================================================
Scrapes all Saints players who have thrown a pass, rushed, or had a reception
by game, then outputs dashboard-ready JSON and CSV files.

Local usage:
    pip install -r requirements.txt
    playwright install chromium

    python scraper.py --login               # one-time: saves session.json + prints secret
    python scraper.py --full                # scrape all history (first run)
    python scraper.py --incremental         # scrape current season only, merge with existing data
    python scraper.py --year 2023           # scrape a specific year
    python scraper.py --start 2000 --end 2023

GitHub Actions usage (reads STATHEAD_SESSION env var):
    Scheduled runs use --incremental automatically.
    Manual runs can specify --full or a year range.

Incremental mode logic:
    1. Detect the current NFL season year
    2. Load existing saints_dashboard_latest.json
    3. Strip all records from the current season (they may be incomplete mid-season)
    4. Scrape only the current season from StatHead
    5. Merge fresh current-season data with untouched historical data
    6. Rebuild and save the dashboard JSON
"""

import asyncio
import json
import argparse
import os
import sys
import base64
from pathlib import Path
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL      = "https://www.sports-reference.com/stathead/football/player-game-finder.cgi"
TEAM_ID       = "nor"
STORAGE_STATE = Path("session.json")
OUTPUT_DIR    = Path(os.environ.get("OUTPUT_DIR", "docs/data"))
PAGE_LIMIT    = 200

RESULT_TIMEOUT = int(os.environ.get("RESULT_TIMEOUT", "60"))  # seconds
DEBUG_DIR      = Path(os.environ.get("DEBUG_DIR", "debug"))

STAT_TYPES = {
    "passing":   ("pass_att", "gt", "0"),
    "rushing":   ("rush_att", "gt", "0"),
    "receiving": ("rec",      "gt", "0"),
}


class ScrapeError(Exception):
    """Raised when scraping fails in a way that should abort the run."""


async def save_debug_snapshot(page, label):
    """Save a screenshot and HTML dump for post-mortem debugging."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_{label}"
    try:
        await page.screenshot(path=str(DEBUG_DIR / f"{stem}.png"), full_page=True)
    except Exception as e:
        print(f"    ⚠️  Could not save screenshot: {e}")
    try:
        html = await page.content()
        (DEBUG_DIR / f"{stem}.html").write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"    ⚠️  Could not save HTML dump: {e}")
    print(f"    📸  Debug snapshot saved: {DEBUG_DIR / stem}.*")

PASS_COLS = ["player","player_id","game_date","season","week_num","game_location",
             "opp","game_result","team","pass_cmp","pass_att","pass_yds",
             "pass_td","pass_int","pass_rating","pass_sacked","pass_sacked_yds"]
RUSH_COLS = ["player","player_id","game_date","season","week_num","game_location",
             "opp","game_result","team","rush_att","rush_yds","rush_td",
             "rush_yds_per_att","rush_long"]
REC_COLS  = ["player","player_id","game_date","season","week_num","game_location",
             "opp","game_result","team","rec","rec_yds","rec_td",
             "rec_yds_per_rec","rec_long","targets"]

# ─────────────────────────────────────────────────────────────────────────────
# NFL SEASON DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def current_nfl_season() -> int:
    """
    Return the current NFL season year.
    The NFL season starts in September. Games in Jan/Feb belong to the
    previous calendar year's season (e.g. Super Bowl in Feb 2025 = 2024 season).
    So: if month <= 7 (July), season = last year; else season = this year.
    """
    now = datetime.now()
    return now.year if now.month >= 8 else now.year - 1


# ─────────────────────────────────────────────────────────────────────────────
# SESSION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def load_session_from_env():
    """Load Playwright storage state from STATHEAD_SESSION env var (base64 JSON)."""
    raw = os.environ.get("STATHEAD_SESSION")
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        return json.loads(decoded)
    except Exception as e:
        print(f"⚠️  Could not parse STATHEAD_SESSION: {e}")
        return None


def session_to_secret(path: Path) -> str:
    """Convert a session.json file to a base64 string for a GitHub Secret."""
    return base64.b64encode(path.read_text().encode()).decode()


async def login_and_save(playwright):
    """Interactive login — opens browser for user, saves session."""
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page    = await context.new_page()

    print("\n🔐  Opening StatHead login page...")
    print("    Sign in with your Sports Reference / StatHead account.")
    print("    Press ENTER here once you are fully logged in.\n")
    await page.goto("https://stathead.com/users/login.cgi")
    input("    >>> Press ENTER after logging in: ")

    await context.storage_state(path=str(STORAGE_STATE))
    await browser.close()

    secret = session_to_secret(STORAGE_STATE)
    print(f"\n✅  Session saved to {STORAGE_STATE}")
    print("\n" + "─"*60)
    print("  GitHub Secret value (copy everything between the lines):\n")
    print(f"  Secret name:  STATHEAD_SESSION")
    print(f"  Secret value: {secret}")
    print("─"*60)
    print("\n  Add it at: Settings → Secrets → Actions → New repository secret\n")


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING DATA LOADING (for incremental mode)
# ─────────────────────────────────────────────────────────────────────────────

def load_existing_data() -> pd.DataFrame | None:
    """
    Load the existing dashboard JSON and return a flat DataFrame of all game rows,
    or None if no existing data is found or data is a stub (total_records == 0).
    """
    latest = OUTPUT_DIR / "saints_dashboard_latest.json"
    if not latest.exists():
        print("  ℹ️  No existing data file found — will do a full scrape instead.")
        return None

    with open(latest) as f:
        data = json.load(f)

    if not data.get("meta", {}).get("total_records"):
        print("  ℹ️  Existing data file is a stub — will do a full scrape instead.")
        return None

    rows = data.get("games_flat", [])
    if not rows:
        print("  ℹ️  games_flat is empty — will do a full scrape instead.")
        return None

    df = pd.DataFrame(rows)
    seasons = sorted(df["season"].dropna().unique().tolist()) if "season" in df.columns else []
    print(f"  📂  Loaded {len(df):,} existing rows covering seasons: {seasons}")
    return df


def strip_season(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """Remove all rows for a given season from the DataFrame."""
    if "season" not in df.columns:
        return df
    before = len(df)
    df = df[df["season"] != season].copy()
    dropped = before - len(df)
    print(f"  🗑️  Stripped {dropped:,} existing rows for season {season} (will be replaced with fresh data)")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────────────────────────────────────

async def validate_session(browser, storage_state):
    """Check that the StatHead session is still valid before scraping."""
    ctx_kwargs = {"storage_state": storage_state} if storage_state else {}
    context = await browser.new_context(**ctx_kwargs)
    page = await context.new_page()
    try:
        await page.goto("https://stathead.com/football/", wait_until="domcontentloaded", timeout=RESULT_TIMEOUT * 1000)
        # Check for common login/paywall indicators
        login_el = await page.query_selector("a[href*='login'], .login-required, .paywall-content, .sr_paywall")
        if login_el:
            await save_debug_snapshot(page, "session_expired")
            raise ScrapeError("Session appears expired — login/paywall element detected on StatHead")
        print("  ✔  Session validated — StatHead access confirmed.")
    except PlaywrightTimeout:
        await save_debug_snapshot(page, "session_validate_timeout")
        raise ScrapeError("Timed out navigating to StatHead for session validation")
    finally:
        await context.close()


def build_url(stat_key, offset=0, start_year=None, end_year=None):
    cstat, ccomp, cval = STAT_TYPES[stat_key]
    params = [
        "request=1",
        f"order_by={cstat}",
        "timeframe=seasons",
        f"ccomp%5B1%5D={ccomp}",
        f"cval%5B1%5D={cval}",
        f"cstat%5B1%5D={cstat}",
        f"team_id={TEAM_ID}",
        f"offset={offset}",
        f"per_page={PAGE_LIMIT}",
    ]
    if start_year: params.append(f"year_min={start_year}")
    if end_year:   params.append(f"year_max={end_year}")
    return f"{BASE_URL}?" + "&".join(params)


async def parse_table(page):
    try:
        await page.wait_for_selector("#results, .stathead-message", timeout=RESULT_TIMEOUT * 1000)
    except PlaywrightTimeout:
        await save_debug_snapshot(page, "parse_table_timeout")
        raise ScrapeError(f"Timed out waiting for results after {RESULT_TIMEOUT}s")

    no_results = await page.query_selector(".stathead-message")
    if no_results:
        msg = await no_results.inner_text()
        if "no results" in msg.lower():
            return None

    html = await page.content()
    try:
        tables = pd.read_html(html, flavor="lxml")
    except Exception as e:
        await save_debug_snapshot(page, "parse_table_read_html_fail")
        raise ScrapeError(f"pd.read_html failed: {e}")

    for t in tables:
        if "player" in [c.lower() for c in t.columns]:
            t.columns = [c.lower().replace(" ", "_").replace("/", "_") for c in t.columns]
            if "player" in t.columns:
                t = t[t["player"] != "Player"]
            return t
    return None


async def scrape_stat(browser, stat_key, start_year=None, end_year=None, storage_state=None):
    ctx_kwargs = {"storage_state": storage_state} if storage_state else {}
    context = await browser.new_context(**ctx_kwargs)
    page    = await context.new_page()
    frames  = []
    offset  = 0

    print(f"\n  📊  Scraping {stat_key.upper()}  ({start_year or 'all'}–{end_year or 'all'})...")

    try:
        while True:
            url = build_url(stat_key, offset, start_year, end_year)
            print(f"      offset={offset}  →  {url[:80]}...")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=RESULT_TIMEOUT * 1000)
            except PlaywrightTimeout:
                print("      ⚠️  Timeout, retrying...")
                await asyncio.sleep(3)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=RESULT_TIMEOUT * 1000)
                except PlaywrightTimeout:
                    await save_debug_snapshot(page, f"scrape_{stat_key}_nav_timeout")
                    raise ScrapeError(f"Double navigation timeout for {stat_key} at offset {offset}")

            df = await parse_table(page)
            if df is None or df.empty:
                print(f"      ✔  No more results.")
                break

            frames.append(df)
            print(f"      ✔  {len(df)} rows")
            if len(df) < PAGE_LIMIT:
                break

            offset += PAGE_LIMIT
            await asyncio.sleep(1.5)
    finally:
        await context.close()

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# POST-PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def post_process(raw, stat_key):
    if raw.empty:
        return raw

    desired  = {"passing": PASS_COLS, "rushing": RUSH_COLS, "receiving": REC_COLS}[stat_key]
    existing = [c for c in desired if c in raw.columns]
    df       = raw[existing].copy()
    df.insert(0, "stat_type", stat_key)

    if "game_location" in df.columns:
        df["game_location"] = df["game_location"].apply(
            lambda v: "Away" if str(v).strip() == "@" else "Home"
        )

    skip = {"player","player_id","game_date","game_location","opp","game_result","team","stat_type"}
    for col in df.columns:
        if col not in skip:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "season" not in df.columns and "game_date" in df.columns:
        df["season"] = pd.to_datetime(df["game_date"], errors="coerce").dt.year

    return df


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard_json(combined: pd.DataFrame) -> dict:
    if combined.empty:
        return {"meta": {"generated": datetime.now().isoformat(), "total_records": 0},
                "players": [], "games_flat": [], "season_summary": []}

    games_flat = json.loads(combined.to_json(orient="records", date_format="iso"))

    players_out = []
    group_col   = "player_id" if "player_id" in combined.columns else "player"
    for pid, grp in combined.groupby(group_col):
        player_name = grp["player"].iloc[0] if "player" in grp.columns else pid
        seasons     = sorted(grp["season"].dropna().unique().tolist()) if "season" in grp.columns else []
        career      = {}
        for st, sg in grp.groupby("stat_type"):
            num_cols   = sg.select_dtypes("number").columns.tolist()
            career[st] = {c: round(float(sg[c].sum()), 2) for c in num_cols if c != "week_num"}
            career[st]["games_played"] = len(sg)

        players_out.append({
            "player":       player_name,
            "player_id":    pid,
            "seasons":      seasons,
            "career_stats": career,
            "games":        json.loads(grp.to_json(orient="records", date_format="iso")),
        })

    players_out.sort(key=lambda p: p["player"].split()[-1])

    season_summary = []
    if "season" in combined.columns:
        for season, sg in combined.groupby("season"):
            entry = {"season": int(season), "stat_types": {}}
            for st, stg in sg.groupby("stat_type"):
                num_cols = stg.select_dtypes("number").columns.tolist()
                entry["stat_types"][st] = {
                    c: round(float(stg[c].sum()), 2) for c in num_cols if c not in ("season","week_num")
                }
                entry["stat_types"][st]["unique_players"] = int(stg["player"].nunique())
            season_summary.append(entry)
        season_summary.sort(key=lambda x: x["season"])

    seasons_covered = sorted(combined["season"].dropna().unique().tolist()) if "season" in combined.columns else []

    return {
        "meta": {
            "generated":       datetime.now().isoformat(),
            "team":            "New Orleans Saints",
            "total_records":   len(combined),
            "total_players":   len(players_out),
            "seasons_covered": [int(s) for s in seasons_covered],
        },
        "players":        players_out,
        "games_flat":     games_flat,
        "season_summary": season_summary,
    }


def save_outputs(combined: pd.DataFrame):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dashboard = build_dashboard_json(combined)

    latest = OUTPUT_DIR / "saints_dashboard_latest.json"
    with open(latest, "w") as f:
        json.dump(dashboard, f, separators=(",", ":"), default=str)
    print(f"  💾  {latest}  ({dashboard['meta']['total_records']:,} total records)")

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = OUTPUT_DIR / f"saints_dashboard_{ts}.json"
    with open(archive, "w") as f:
        json.dump(dashboard, f, separators=(",", ":"), default=str)
    print(f"  💾  {archive}  (archive copy)")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Saints Football Encyclopedia Scraper")
    parser.add_argument("--login",       action="store_true", help="Interactive login flow")
    parser.add_argument("--incremental", action="store_true",
                        help="Scrape current season only and merge with existing data")
    parser.add_argument("--full",        action="store_true", help="Scrape all seasons from scratch")
    parser.add_argument("--year",        type=int, help="Scrape a specific season year")
    parser.add_argument("--start",       type=int, help="Start year for range")
    parser.add_argument("--end",         type=int, help="End year for range")
    args = parser.parse_args()

    async with async_playwright() as pw:

        # ── Login flow ────────────────────────────────────────────────────────
        if args.login or (not STORAGE_STATE.exists() and not os.environ.get("STATHEAD_SESSION")):
            await login_and_save(pw)
            if args.login:
                return

        # ── Resolve session ───────────────────────────────────────────────────
        session_data = load_session_from_env()
        if session_data:
            print("🔑  Using STATHEAD_SESSION from environment.")
            storage_state = session_data
        elif STORAGE_STATE.exists():
            print(f"🔑  Using local {STORAGE_STATE}.")
            storage_state = str(STORAGE_STATE)
        else:
            print("❌  No session found. Run with --login first.")
            return

        # ── Determine scrape mode ─────────────────────────────────────────────
        historical_df = None   # existing rows we keep untouched

        if args.incremental:
            season      = current_nfl_season()
            start_year  = season
            end_year    = season
            print(f"\n🏈  Saints Encyclopedia Scraper  [INCREMENTAL — season {season}]")

            existing = load_existing_data()
            if existing is not None:
                historical_df = strip_season(existing, season)
            else:
                # No existing data — fall back to full scrape
                print("  ↩️  Falling back to full scrape.\n")
                start_year = end_year = None

        elif args.full:
            start_year = end_year = None
            print(f"\n🏈  Saints Encyclopedia Scraper  [FULL SCRAPE — all seasons]")

        else:
            start_year = args.year or args.start
            end_year   = args.year or args.end
            print(f"\n🏈  Saints Encyclopedia Scraper  [years: {start_year or 'ALL'} → {end_year or 'ALL'}]")

        # ── Scrape ────────────────────────────────────────────────────────────
        browser = await pw.chromium.launch(headless=True)

        try:
            await validate_session(browser, storage_state)

            pass_raw = await scrape_stat(browser, "passing",   start_year, end_year, storage_state)
            rush_raw = await scrape_stat(browser, "rushing",   start_year, end_year, storage_state)
            rec_raw  = await scrape_stat(browser, "receiving", start_year, end_year, storage_state)
        except ScrapeError as exc:
            print(f"\n❌  Scrape failed: {exc}")
            await browser.close()
            sys.exit(1)

        await browser.close()

        # ── Post-process freshly scraped data ─────────────────────────────────
        print("\n🔧  Post-processing fresh data...")
        pass_df = post_process(pass_raw, "passing")
        rush_df = post_process(rush_raw, "rushing")
        rec_df  = post_process(rec_raw,  "receiving")

        fresh_df = pd.concat([pass_df, rush_df, rec_df], ignore_index=True)
        print(f"  ✔  {len(fresh_df):,} fresh rows scraped")

        # ── Guard: fail loudly if full scrape produced nothing ────────────────
        if len(fresh_df) == 0:
            if args.incremental:
                print("  ℹ️  0 rows scraped — normal during offseason.")
            else:
                print("\n❌  0 rows scraped in non-incremental mode — aborting.")
                sys.exit(1)

        # ── Merge with historical if incremental ──────────────────────────────
        if historical_df is not None:
            combined = pd.concat([historical_df, fresh_df], ignore_index=True)
            print(f"  🔀  Merged: {len(historical_df):,} historical + {len(fresh_df):,} fresh = {len(combined):,} total rows")
        else:
            combined = fresh_df

        # ── Save ──────────────────────────────────────────────────────────────
        print("\n💾  Saving outputs...")
        save_outputs(combined)
        print("\n✅  Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
