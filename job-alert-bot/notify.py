"""
Sends alerts about newly found jobs via Email and/or Telegram.
Credentials are read from environment variables (set via .env locally,
or GitHub Actions Secrets in production) -- never hardcoded.
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText

import requests


def _group_by_company(new_jobs: list[dict]) -> dict:
    grouped = {}
    for job in new_jobs:
        grouped.setdefault(job["company"], []).append(job)
    return grouped


def format_message(new_jobs: list[dict]) -> str:
    lines = [f"🔔 {len(new_jobs)} new job posting(s) found:\n"]
    for company, jobs in _group_by_company(new_jobs).items():
        lines.append(f"\n**{company}**")
        for job in jobs:
            lines.append(f"  • {job['title']}\n    {job['url']}")
    return "\n".join(lines)


def send_email(new_jobs: list[dict]) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addr = os.environ.get("EMAIL_TO")

    if not all([host, user, password, to_addr]):
        print("[notify] Email not configured, skipping.")
        return

    body = format_message(new_jobs)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[Job Alert Bot] {len(new_jobs)} new posting(s)"
    msg["From"] = user
    msg["To"] = to_addr

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
    print(f"[notify] Email sent to {to_addr}")


def send_telegram(new_jobs: list[dict]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not all([token, chat_id]):
        print("[notify] Telegram not configured, skipping.")
        return

    text = format_message(new_jobs)
    # Telegram caps messages at 4096 chars; split into chunks if needed
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] or [text]

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in chunks:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        if not resp.ok:
            print(f"[notify] Telegram send failed: {resp.status_code} {resp.text}")
    print(f"[notify] Telegram message sent to chat {chat_id}")


def send_all(new_jobs: list[dict]) -> None:
    if not new_jobs:
        print("[notify] No new jobs, nothing to send.")
        return
    send_email(new_jobs)
    send_telegram(new_jobs)
