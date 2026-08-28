"""
Fallback scraper for any career page that isn't on a recognized ATS
platform (Greenhouse/Lever/Workday). There's no universal structure for
custom career pages, so instead of trying to fully parse each one, this
takes a pragmatic heuristic approach:

  1. Fetch the page HTML.
  2. Pull every <a> link whose href or visible text looks job-related
     (contains words like "job", "career", "req", "position", "opening",
     or matches a /jobs/<id> - style path).
  3. Treat each unique href as a "posting". New hrefs since last run =
     new postings.

This will occasionally produce false positives (e.g. a nav link) or miss
postings rendered client-side by JavaScript (many modern career pages are
React/Vue SPAs that fetch jobs via their own internal API -- for those,
open browser devtools -> Network tab, find the JSON endpoint they call,
and write a small dedicated scraper for it, following the same pattern as
greenhouse.py/lever.py). It's intentionally simple so the project stays
easy to extend company-by-company.
"""
import re
import hashlib
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

JOB_KEYWORDS = re.compile(
    r"(job|career|req|position|opening|vacanc|apply)", re.IGNORECASE
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JobAlertBot/1.0; "
        "+https://github.com/YOUR_USERNAME/job-alert-bot)"
    )
}


def fetch_jobs(career_url: str, timeout: int = 20) -> list[dict]:
    resp = requests.get(career_url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    jobs = []
    seen_hrefs = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)

        if not JOB_KEYWORDS.search(href) and not JOB_KEYWORDS.search(text):
            continue
        if len(text) < 3:
            continue

        full_url = urljoin(career_url, href)
        if full_url in seen_hrefs:
            continue
        seen_hrefs.add(full_url)

        # Stable id derived from the URL so re-runs dedupe correctly
        job_id = hashlib.sha1(full_url.encode()).hexdigest()[:16]
        jobs.append({
            "id": job_id,
            "title": text or full_url,
            "url": full_url,
        })

    return jobs
