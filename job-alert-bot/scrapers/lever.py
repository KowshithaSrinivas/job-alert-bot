"""
Scraper for companies using Lever (jobs.lever.co). Lever also exposes a
free public JSON API per company, keyed by the same "site" slug that
appears in the careers URL.

Site slug = the last path segment, e.g.
  https://jobs.lever.co/netflix  ->  slug = "netflix"
"""
import re
import requests

API_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def extract_slug(career_url: str) -> str | None:
    match = re.search(r"lever\.co/([A-Za-z0-9_-]+)", career_url)
    return match.group(1) if match else None


def fetch_jobs(career_url: str, timeout: int = 20) -> list[dict]:
    slug = extract_slug(career_url)
    if not slug:
        raise ValueError(f"Could not extract Lever slug from {career_url}")

    resp = requests.get(API_URL.format(slug=slug), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for job in data:
        jobs.append({
            "id": str(job["id"]),
            "title": job.get("text", "Untitled role"),
            "url": job.get("hostedUrl", career_url),
        })
    return jobs
