"""
Scraper for companies using Greenhouse (job-boards.greenhouse.io or
boards.greenhouse.io). Greenhouse exposes a free public JSON API per
company board, so no HTML scraping is needed here -- this is the most
reliable source in the whole project.

Board token = the last path segment of the careers URL, e.g.
  https://job-boards.greenhouse.io/notion  ->  token = "notion"
"""
import re
import requests

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def extract_token(career_url: str) -> str | None:
    match = re.search(r"greenhouse\.io/([A-Za-z0-9_-]+)", career_url)
    return match.group(1) if match else None


def fetch_jobs(career_url: str, timeout: int = 20) -> list[dict]:
    """Returns a list of {id, title, url} dicts for open roles."""
    token = extract_token(career_url)
    if not token:
        raise ValueError(f"Could not extract Greenhouse board token from {career_url}")

    resp = requests.get(API_URL.format(token=token), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "id": str(job["id"]),
            "title": job.get("title", "Untitled role"),
            "url": job.get("absolute_url", career_url),
        })
    return jobs
