"""
Scraper for companies using Personio Recruiting -- extremely common among
German/DACH startups and SMEs (this list has a lot of them). Personio
exposes a free public XML job feed per company, no auth needed.

Career URL looks like:
  https://<company>.jobs.personio.de/   or   https://<company>.jobs.personio.com/

XML feed:
  https://<company>.jobs.personio.de/xml
"""
import re
import requests
from bs4 import BeautifulSoup

XML_URL_TEMPLATE = "https://{subdomain}.jobs.{domain}/xml"


def extract_subdomain(career_url: str):
    match = re.search(r"https?://([A-Za-z0-9-]+)\.jobs\.personio\.(de|com)", career_url)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def fetch_jobs(career_url: str, timeout: int = 20) -> list[dict]:
    subdomain, domain = extract_subdomain(career_url)
    if not subdomain:
        raise ValueError(f"Could not extract Personio subdomain from {career_url}")

    xml_url = XML_URL_TEMPLATE.format(subdomain=subdomain, domain=domain)
    resp = requests.get(xml_url, timeout=timeout)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "xml")
    jobs = []
    for position in soup.find_all("position"):
        job_id = position.find("id")
        name = position.find("name")
        office = position.find("office")
        url_el = position.find("createdAt")  # placeholder, real link built below
        job_id_val = job_id.text.strip() if job_id else name.text.strip()
        title = name.text.strip() if name else "Untitled role"
        office_val = f" ({office.text.strip()})" if office and office.text.strip() else ""
        jobs.append({
            "id": job_id_val,
            "title": f"{title}{office_val}",
            "url": f"https://{subdomain}.jobs.{domain}/job/{job_id_val}",
        })
    return jobs
