"""
Scraper for companies using Workday (*.myworkdayjobs.com). Workday is the
trickiest of the "structured" ATS platforms: there's no single documented
public API, but nearly every Workday careers site follows the same
reverse-engineered CXS (client experience service) pattern under the hood,
which is what this scrapes.

A Workday careers URL looks like:
  https://<tenant>.wd1.myworkdayjobs.com/en-US/<site>

  tenant = subdomain before ".wd#.myworkdayjobs.com"  (e.g. "robinhood")
  wd#    = the numbered Workday cluster (wd1, wd3, wd5 ...)
  site   = the last path segment                       (e.g. "External")

The matching CXS jobs endpoint is:
  https://<tenant>.wd#.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs

NOTE: because tenants sometimes customize their site slug or cluster
number, or block non-browser traffic, this scraper is best-effort. If a
company's Workday board fails here, add it to companies.csv with
ats=generic instead as a fallback (see generic.py).
"""
import re
import requests

WORKDAY_URL_RE = re.compile(
    r"https?://(?P<tenant>[A-Za-z0-9-]+)\.(?P<cluster>wd\d+)\.myworkdayjobs\.com"
    r"(?:/[A-Za-z-]+)?/(?P<site>[A-Za-z0-9_-]+)"
)


def parse_workday_url(career_url: str):
    match = WORKDAY_URL_RE.search(career_url)
    if not match:
        return None
    return match.group("tenant"), match.group("cluster"), match.group("site")


def fetch_jobs(career_url: str, timeout: int = 20) -> list[dict]:
    parsed = parse_workday_url(career_url)
    if not parsed:
        raise ValueError(
            f"Could not parse Workday tenant/cluster/site from {career_url}. "
            "Try ats=generic for this company instead."
        )
    tenant, cluster, site = parsed

    api_url = f"https://{tenant}.{cluster}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    headers = {"Content-Type": "application/json"}

    jobs = []
    offset = 0
    while True:
        payload["offset"] = offset
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            path = job.get("externalPath", "")
            jobs.append({
                "id": path or job.get("title", ""),
                "title": job.get("title", "Untitled role"),
                "url": f"https://{tenant}.{cluster}.myworkdayjobs.com{path}",
            })

        offset += len(postings)
        total = data.get("total", 0)
        if offset >= total:
            break

    return jobs
