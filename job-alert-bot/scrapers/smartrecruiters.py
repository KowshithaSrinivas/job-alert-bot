"""
Scraper for companies using SmartRecruiters. They expose a free public
JSON API per company identifier, no auth needed.

Career URL looks like:
  https://careers.smartrecruiters.com/<CompanyIdentifier>

API:
  https://api.smartrecruiters.com/v1/companies/<CompanyIdentifier>/postings
"""
import re
import requests

API_URL = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"


def extract_company_id(career_url: str) -> str | None:
    match = re.search(r"smartrecruiters\.com/([A-Za-z0-9_.-]+)", career_url)
    return match.group(1) if match else None


def fetch_jobs(career_url: str, timeout: int = 20) -> list[dict]:
    company_id = extract_company_id(career_url)
    if not company_id:
        raise ValueError(f"Could not extract SmartRecruiters company id from {career_url}")

    jobs = []
    offset = 0
    limit = 100
    while True:
        resp = requests.get(
            API_URL.format(company_id=company_id),
            params={"limit": limit, "offset": offset},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        if not content:
            break

        for job in content:
            jobs.append({
                "id": job.get("id"),
                "title": job.get("name", "Untitled role"),
                "url": f"https://jobs.smartrecruiters.com/{company_id}/{job.get('id')}",
            })

        offset += limit
        if offset >= data.get("totalFound", 0):
            break

    return jobs
