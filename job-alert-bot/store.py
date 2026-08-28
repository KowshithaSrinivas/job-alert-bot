"""
Tiny JSON-backed "seen jobs" store used to dedupe postings between runs.
Kept as plain JSON (rather than SQLite) on purpose: GitHub Actions commits
this file back to the repo after every run, and JSON diffs are human
readable in the commit history -- itself a nice thing to show off on a
resume/portfolio ("you can literally see the bot discovering jobs over
time in the git log").
"""
import json
import os

STORE_PATH = os.path.join(os.path.dirname(__file__), "db", "seen_jobs.json")


def load() -> dict:
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
