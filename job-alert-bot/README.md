# Job Alert Bot

Automatically checks 530 companies' career pages for new job postings and
sends an alert (Email + Telegram) the moment something new goes live —
no more manually refreshing 500 tabs.

Built as a small end-to-end data pipeline: **ingest → normalize → enrich
→ poll → diff → notify**, running on a schedule via GitHub Actions.

## How it works

```
data/companies.csv  ──►  discover.py  ──►  career_url + ats resolved per company
                                                    │
.github/workflows/check_jobs.yml (cron, every 3h)  │
                                                    ▼
                                    main.py orchestrates:
                                    for each company →
                                    scrapers/{greenhouse,lever,workday,
                                              personio,smartrecruiters,generic}.py
                                                    │
                                    diff against db/seen_jobs.json
                                                    │
                                        new postings found? ──► notify.py
                                                                 (Email + Telegram)
```

- **`data/companies.csv`** — the 530 companies (250 with confirmed
  official career pages + 280 additional research targets), extracted
  and cleaned from the sourced company directory. Columns: `company`,
  `location`, `sector`, `part`, `career_url`, `ats`.
- **`discover.py`** — one-off enrichment step. For any row missing a
  `career_url`, it guesses likely domains from the company name, probes
  them over HTTP, follows redirects, and detects whether the company
  runs on a known ATS (Greenhouse / Lever / Personio / SmartRecruiters /
  Workday) by inspecting the resolved URL. Best-effort — see
  [Known limitations](#known-limitations).
- **`scrapers/`** — one module per ATS platform. Greenhouse, Lever,
  Personio and SmartRecruiters all expose free public JSON/XML job
  APIs, so those are exact and reliable. Workday is scraped via its
  reverse-engineered but widely-used CXS endpoint. Anything else falls
  back to `generic.py`, which heuristically extracts job-looking links
  from the page HTML.
- **`db/seen_jobs.json`** — the dedupe store: which job IDs have already
  been seen per company. Committed back to the repo after every run, so
  the run history in `git log` literally shows new jobs being discovered
  over time.
- **`notify.py`** — sends a formatted alert by Email (SMTP) and/or
  Telegram (bot API) whenever `main.py` finds postings not already in
  the seen-jobs store.
- **`.github/workflows/check_jobs.yml`** — runs `main.py` every 3 hours
  on GitHub's free runners. No server to maintain.

## Setup

### 1. Push this to your own GitHub repo

```bash
cd job-alert-bot
git init
git add .
git commit -m "Initial commit: job alert bot"
gh repo create job-alert-bot --public --source=. --push
# (or create the repo on github.com and `git remote add origin ...` + push)
```

### 2. Set up notifications

**Telegram** (free, instant, recommended):
1. Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the prompts — you'll get a bot token.
2. Message your new bot once (anything), then visit
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser —
   your `chat_id` is in the JSON response.

**Email** (Gmail example):
1. Turn on 2FA on your Google account, then create an
   [App Password](https://myaccount.google.com/apppasswords).
2. Use that as `SMTP_PASSWORD` (not your real Gmail password).

Add these as **repo secrets** (Settings → Secrets and variables →
Actions → New repository secret): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD`, `EMAIL_TO`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
(See `.env.example` for local testing without secrets.)

### 3. Resolve career page URLs

`data/companies.csv` ships with company names, locations and sectors
filled in, but `career_url`/`ats` are blank — go to **Actions → Discover
career page URLs → Run workflow** in your repo. This runs `discover.py`
on GitHub's runners (which have normal internet access) and commits the
resolved URLs back. Re-run it any time; it only processes rows still
missing a `career_url`.

Afterwards, open `data/companies.csv` and manually fix/verify any row
tagged `needs_review` — this is expected for a meaningful chunk of
companies (see below).

### 4. Turn on the schedule

The `check_jobs.yml` workflow runs automatically once it's on your
default branch (every 3 hours, cron `0 */3 * * *`). You can also trigger
it manually from the Actions tab to test immediately.

### Run locally (optional, for testing)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your real credentials
python discover.py --limit 20   # try enrichment on a small batch first
python main.py
```

## Known limitations

- **`discover.py`'s domain-guessing is heuristic, not exhaustive.**
  Guessing a company's live domain from its name alone (`Datadog` →
  `datadog.com`, when the real domain is `datadoghq.com`) doesn't always
  work, especially for names with qualifiers like "Germany" or
  "Digital" appended. Expect a meaningful chunk of the 530 to land in
  `needs_review` — that's the honest baseline, and hand-fixing those
  is a legitimate and expected part of running this.
- **The PDF source for Part 2 (280 companies) explicitly calls those
  "research leads"**, not confirmed career pages — some may not have a
  single unified German career page at all (e.g. large multinationals
  hiring per-country).
- **The `generic.py` fallback scraper is heuristic**, not a true parser.
  It works well for simple server-rendered pages but can miss postings
  on JavaScript-heavy career pages (common with modern SPA-based sites)
  and can occasionally produce false positives. For any company you
  care about a lot, it's worth opening browser devtools → Network tab
  on their careers page, finding the JSON endpoint it calls internally,
  and writing a small dedicated scraper following the pattern in
  `scrapers/greenhouse.py`.
- **Career pages, and even domains, change.** This is a living project,
  not a one-time script — periodic maintenance (fixing broken scrapers,
  re-running discovery) is part of it, same as any real monitoring
  system.

## Possible extensions

- Add more ATS platforms (SAP SuccessFactors, Ashby, Recruitee, Teamtailor).
- A tiny dashboard (static HTML built by the Action) showing total jobs tracked / new this week.
- Filter/keyword matching (e.g. only alert for "Data Engineer" roles).
- Slack/Discord notifier alongside Email/Telegram.
- Swap `db/seen_jobs.json` for SQLite if the company list grows much larger.

## Tech stack

Python · `requests` · `BeautifulSoup` · GitHub Actions (cron + secrets)
· SMTP · Telegram Bot API · JSON as a lightweight datastore

---

*Source data: company list adapted from a 530-company Germany tech job
search directory (250 official career pages + 280 additional research
targets, compiled July 2026).*
