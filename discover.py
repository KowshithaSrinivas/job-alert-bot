"""
One-time (or occasional) enrichment pass: for every company in
data/companies.csv that doesn't have a career_url yet, guess likely
domains, probe them over HTTP, and try to detect which ATS (Greenhouse /
Lever / Personio / SmartRecruiters / Workday) they use, or fall back to a
generic career-page guess.

This is a heuristic, best-effort pass -- expect it to resolve maybe
40-70% of companies automatically. Anything it can't resolve is left
blank in career_url and flagged in the `ats` column as "needs_review" so
you can fill it in by hand (open the company's site, find Careers, copy
the URL).

IMPORTANT: run this somewhere with normal internet access (your own
machine, or as a one-off GitHub Actions job) -- NOT from a network-
restricted sandbox.

Usage:
    python discover.py                  # process all companies missing a career_url
    python discover.py --limit 20       # just the first 20 (useful for testing)
    python discover.py --workers 30     # tune concurrency
"""
import argparse
import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

COMPANIES_CSV = "data/companies.csv"
TIMEOUT = 6
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 JobAlertBotDiscovery/1.0"
    )
}

# Known ATS hostnames -> ats tag used by scrapers/*.py
ATS_HOST_MAP = [
    (r"greenhouse\.io", "greenhouse"),
    (r"lever\.co", "lever"),
    (r"jobs\.personio\.(de|com)", "personio"),
    (r"smartrecruiters\.com", "smartrecruiters"),
    (r"myworkdayjobs\.com", "workday"),
]

CAREER_PATHS = [
    "/careers", "/en/careers", "/career", "/jobs", "/en/jobs",
    "/karriere", "/de/karriere", "/unternehmen/karriere",
    "/about/careers", "/company/careers",
]

SUFFIX_STRIP_RE = re.compile(
    r"\b(GmbH|AG|SE|Group|Germany|Deutschland|Inc\.?|Ltd\.?|Co\.?|KG|mbH|"
    r"& Co\.? KG|Digital|Tech Innovation|Technologies)\b",
    re.IGNORECASE,
)
PAREN_RE = re.compile(r"\(.*?\)")


def candidate_domains(company: str) -> list[str]:
    name = PAREN_RE.sub("", company)
    name = SUFFIX_STRIP_RE.sub("", name)
    name = name.strip()

    concat = re.sub(r"[^a-zA-Z0-9]+", "", name).lower()
    hyphen = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()

    candidates = []
    for base in dict.fromkeys([concat, hyphen]):  # dedupe, keep order
        if not base:
            continue
        candidates.append(f"https://{base}.com")
        candidates.append(f"https://{base}.de")
    return candidates


def detect_ats(url: str) -> str | None:
    for pattern, tag in ATS_HOST_MAP:
        if re.search(pattern, url, re.IGNORECASE):
            return tag
    return None


def probe(session: requests.Session, url: str):
    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return resp
    except requests.RequestException:
        return None


def resolve_company(company: str) -> dict:
    """Returns {'career_url': str, 'ats': str} best-effort."""
    session = requests.Session()

    # 1. find a live homepage domain
    homepage = None
    for domain_url in candidate_domains(company):
        resp = probe(session, domain_url)
        if resp is not None and resp.status_code < 400:
            homepage = resp.url  # follow redirects to final URL
            ats = detect_ats(homepage)
            if ats:
                return {"career_url": homepage, "ats": ats}
            break

    if not homepage:
        return {"career_url": "", "ats": "needs_review"}

    # 2. try common career paths on that domain
    base = homepage.rstrip("/")
    for path in CAREER_PATHS:
        resp = probe(session, base + path)
        if resp is not None and resp.status_code < 400:
            final_url = resp.url
            ats = detect_ats(final_url)
            return {"career_url": final_url, "ats": ats or "generic"}

    # homepage resolved but no career path found -- still useful, flag for review
    return {"career_url": homepage, "ats": "needs_review"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=25)
    args = parser.parse_args()

    with open(COMPANIES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    todo = [r for r in rows if not r.get("career_url")]
    if args.limit:
        todo = todo[: args.limit]

    print(f"Resolving {len(todo)} of {len(rows)} companies (workers={args.workers})...")

    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_to_company = {
            pool.submit(resolve_company, r["company"]): r["no"] for r in todo
        }
        done = 0
        for future in as_completed(future_to_company):
            no = future_to_company[future]
            try:
                results[no] = future.result()
            except Exception as e:
                results[no] = {"career_url": "", "ats": "needs_review"}
                print(f"  [{no}] error: {e}", file=sys.stderr)
            done += 1
            if done % 25 == 0:
                print(f"  ...{done}/{len(todo)}")

    resolved = 0
    for r in rows:
        if r["no"] in results:
            r["career_url"] = results[r["no"]]["career_url"]
            r["ats"] = results[r["no"]]["ats"]
            if r["ats"] not in ("needs_review", ""):
                resolved += 1

    with open(COMPANIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Auto-resolved {resolved}/{len(todo)} companies with a confident ATS match.")
    print("Everything else is tagged 'needs_review' in data/companies.csv -- fill those in by hand.")


if __name__ == "__main__":
    main()
