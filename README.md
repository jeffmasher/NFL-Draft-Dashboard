# ⚜ Saints Football Encyclopedia

A searchable dashboard of every New Orleans Saints player who has thrown a pass, rushed, or caught a reception — by game — sourced from Pro Football Reference via StatHead.

**Live dashboard:** `https://YOUR-GITHUB-USERNAME.github.io/saints-encyclopedia/`

---

## Repo Structure

```
saints-encyclopedia/
├── .github/
│   └── workflows/
│       ├── scrape.yml      # Runs scraper on a schedule, commits data
│       └── deploy.yml      # Deploys docs/ to GitHub Pages on every push
├── scraper/
│   ├── scraper.py          # Playwright-based StatHead scraper
│   └── requirements.txt
├── docs/                   # GitHub Pages source
│   ├── index.html          # Dashboard
│   └── data/
│       └── saints_dashboard_latest.json   # Auto-updated by scraper
└── .gitignore
```

---

## One-Time Setup

### 1. Create the GitHub repo

```bash
git init
git remote add origin https://github.com/YOUR-USERNAME/saints-encyclopedia.git
git add .
git commit -m "initial commit"
git push -u origin main
```

### 2. Enable GitHub Pages

In your repo: **Settings → Pages → Source → GitHub Actions**

### 3. Get your StatHead session secret

You need a [StatHead subscription](https://stathead.com) (Sports Reference).

```bash
cd scraper
pip install -r requirements.txt
playwright install chromium
python scraper.py --login
```

This opens a browser. Log in, press ENTER, and the script prints your **base64 session value**.

### 4. Add the secret to GitHub

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `STATHEAD_SESSION` | *(the base64 string printed by --login)* |

### 5. First run — full historical scrape

Go to **Actions → Scrape Saints Data → Run workflow** and select **mode: full**.

This fetches all Saints history (~20–40 min). The workflow commits the JSON to docs/data/, which triggers the deploy workflow. Your dashboard will be live within minutes.

---

## Automatic Updates (incremental)

After the first full scrape, all subsequent **scheduled runs use incremental mode**:

1. Load the existing saints_dashboard_latest.json
2. Drop all rows for the current NFL season (they change week-to-week)
3. Scrape only the current season from StatHead (seconds, not 40 min)
4. Merge fresh current-season data back with untouched historical rows
5. Save and commit

The scraper runs **every Tuesday at 6am CT** (noon UTC). During the offseason it finds no new data and skips the commit — no wasted runs.

---

## Scraper modes

| Mode | Command | When to use |
|---|---|---|
| --full | python scraper.py --full | First run, or full data reset |
| --incremental | python scraper.py --incremental | Weekly updates (auto-detects current NFL season) |
| --year YYYY | python scraper.py --year 2023 | Re-scrape a specific season |
| --start/--end | python scraper.py --start 2010 --end 2019 | Custom range |

---

## Local Development

```bash
cd scraper
pip install -r requirements.txt
playwright install chromium

python scraper.py --login          # one-time login
python scraper.py --full           # first full scrape
python scraper.py --incremental    # current season only, merges with existing

# Must use a local server (not file://) for the dashboard fetch() to work
python -m http.server 8000 --directory docs
# then visit http://localhost:8000
```

---

## Dashboard Features

- **Player sidebar** — searchable, filterable by stat type (Pass / Rush / Rec)
- **Career totals** — yards, TDs, attempts by stat type
- **Game log table** — sortable by any column, filterable by season
- **Season chart** — stacked bar chart of yards by year (pass / rush / rec)
