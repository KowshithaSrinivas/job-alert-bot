"""
Entry point: reads data/companies.csv, scrapes each company's career page
with the scraper matching its `ats` column, diffs against db/seen_jobs.json
to find newly-posted roles, sends alerts for anything new, then updates
the seen-jobs store.

Designed to be run on a schedule by .github/workflows/check_jobs.yml, but
works the same way run locally: `python main.py`.
"""
import csv
import sys
import traceback

import store
import notify
from scrapers import greenhouse, lever, workday, personio, smartrecruiters, generic

COMPANIES_CSV = "data/companies.csv"

SCRAPER_MAP = {
    "greenhouse": greenhouse,
    "lever": lever,
    "workday": workday,
    "personio": personio,
    "smartrecruiters": smartrecruiters,
    "generic": generic,
}


def load_companies() -> list[dict]:
    with open(COMPANIES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Only companies that have a career_url set (discover.py fills this in)
    return [r for r in rows if r.get("career_url")]


def main():
    companies = load_companies()
    if not companies:
        print(
            "No companies with a career_url in data/companies.csv yet.\n"
            "Run `python discover.py` first (see README), or fill in URLs by hand."
        )
        return

    seen = store.load()
    new_jobs = []
    errors = []

    print(f"Checking {len(companies)} companies...")

    for row in companies:
        name = row["company"]
        url = row["career_url"]
        ats = (row.get("ats") or "generic").strip().lower()

        scraper = SCRAPER_MAP.get(ats, generic)

        try:
            jobs = scraper.fetch_jobs(url)
        except Exception as e:
            errors.append((name, str(e)))
            print(f"  [FAIL] {name} ({ats}): {e}")
            continue

        # A company we've never scraped before has no baseline to diff
        # against. Without this check, the very first run would treat
        # every currently-open role at every company as "new" and fire
        # an alert for all of them at once. Instead, the first sighting
        # just establishes the baseline silently -- alerts start from
        # the *next* run, for roles that appear after that.
        is_first_sighting = name not in seen

        seen_ids = set(seen.get(name, []))
        current_ids = {job["id"] for job in jobs}

        newly_posted = [] if is_first_sighting else [
            job for job in jobs if job["id"] not in seen_ids
        ]
        for job in newly_posted:
            job["company"] = name
            new_jobs.append(job)

        seen[name] = sorted(current_ids)
        if is_first_sighting:
            status = f"baseline set ({len(jobs)} roles, no alert)"
        else:
            status = f"{len(newly_posted)} new" if newly_posted else "no change"
        print(f"  [OK] {name} ({ats}): {len(jobs)} open roles, {status}")

    store.save(seen)

    print(f"\nTotal new postings found: {len(new_jobs)}")
    if errors:
        print(f"Companies that failed to scrape: {len(errors)}")

    notify.send_all(new_jobs)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
