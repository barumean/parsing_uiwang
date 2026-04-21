#!/usr/bin/env python3
"""
Uiwang City Government Announcement Checker
Monitors https://www.uiwang.go.kr/UWKORINFO0101 for new announcements
and sends Telegram notifications.
"""

import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
BASE_URL = "https://www.uiwang.go.kr"
TARGET_URL = "https://www.uiwang.go.kr/UWKORINFO0101"
STATE_FILE = Path(__file__).parent / "seen_announcements.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": "https://www.uiwang.go.kr/",
}

# eGovFrame / Korean gov board CSS selector strategies (tried in order)
TABLE_SELECTORS = [
    "table.board_list tbody tr",
    "table.tbl_list tbody tr",
    "table.bbs-list tbody tr",
    "table.list_table tbody tr",
    "table.board-list tbody tr",
    "#content table tbody tr",
    ".board_wrap table tbody tr",
    "table tbody tr",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# --- HTTP Session ---

def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


# --- Page Fetching ---

def fetch_page(session: requests.Session, url: str) -> Optional[str]:
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.exceptions.HTTPError as e:
        log.error("HTTP error fetching %s: %s", url, e)
    except requests.exceptions.ConnectionError as e:
        log.error("Connection error fetching %s: %s", url, e)
    except requests.exceptions.Timeout:
        log.error("Timeout fetching %s", url)
    except requests.exceptions.RequestException as e:
        log.error("Unexpected request error: %s", e)
    return None


# --- HTML Parsing ---

def extract_ntt_id(href: str) -> Optional[str]:
    if not href:
        return None
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    if "nttId" in params:
        return params["nttId"][0]
    match = re.search(r"/(\d{4,})", parsed.path)
    if match:
        return match.group(1)
    return None


def make_fallback_id(title: str, date: str) -> str:
    raw = f"{title}|{date}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def resolve_link(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def parse_announcements(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    announcements = []

    rows = []
    for selector in TABLE_SELECTORS:
        candidates = soup.select(selector)
        data_rows = [r for r in candidates if r.find("td")]
        if data_rows:
            rows = data_rows
            log.info("Matched selector: %s (%d rows)", selector, len(rows))
            break

    if not rows:
        log.warning("No table rows found with any known selector.")
        log.debug(html[:3000])
        return []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        title_link = None
        for cell in cells:
            a_tag = cell.find("a")
            if a_tag and a_tag.get_text(strip=True):
                title_link = a_tag
                break

        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        raw_href = title_link.get("href", "")

        if not raw_href or raw_href == "#":
            onclick = title_link.get("onclick", "")
            match = re.search(r"[\"']+(\d{4,})[\"']+", onclick)
            if match:
                raw_href = f"?nttId={match.group(1)}"

        link = resolve_link(raw_href) if raw_href else TARGET_URL
        ann_id = extract_ntt_id(raw_href)

        date = ""
        for cell in reversed(cells):
            text = cell.get_text(strip=True)
            if re.match(r"\d{4}[-./]\d{2}[-./]\d{2}", text):
                date = text
                break

        number = cells[0].get_text(strip=True)
        if number in ("번호", "No", "NO", "순번"):
            continue

        if not ann_id:
            ann_id = make_fallback_id(title, date)

        announcements.append({
            "id": ann_id,
            "number": number,
            "title": title,
            "link": link,
            "date": date,
        })

    log.info("Parsed %d announcements", len(announcements))
    return announcements


# --- State Management ---

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to load state file, starting fresh: %s", e)
    return {"last_seen_ids": [], "last_check": None}


def save_state(state: dict) -> None:
    try:
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        log.info("State saved to %s", STATE_FILE)
    except OSError as e:
        log.error("Failed to save state file: %s", e)


# --- Telegram Notifications ---

def send_telegram_message(session: requests.Session, text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not set; skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = session.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("Telegram notification sent.")
        return True
    except requests.exceptions.RequestException as e:
        log.error("Failed to send Telegram message: %s", e)
        return False


def format_announcement_message(ann: dict) -> str:
    lines = [
        "📢 <b>의왕시 새 공고</b>",
        "",
        f"📋 <b>{ann['title']}</b>",
    ]
    if ann.get("number"):
        lines.append(f"번호: {ann['number']}")
    if ann.get("date"):
        lines.append(f"날짜: {ann['date']}")
    lines.append("")
    lines.append(f'🔗 <a href="{ann["link"]}">공고 보기</a>')
    return "\n".join(lines)


# --- Main Logic ---

def main() -> int:
    log.info("=== Uiwang Announcement Checker started ===")

    session = make_session()

    html = fetch_page(session, TARGET_URL)
    if html is None:
        log.error("Could not fetch the announcement page. Exiting.")
        return 1

    announcements = parse_announcements(html)
    if not announcements:
        log.warning("No announcements parsed. Possible page structure change.")
        return 1

    state = load_state()
    seen_ids = set(state.get("last_seen_ids", []))
    is_first_run = len(seen_ids) == 0

    new_announcements = [a for a in announcements if a["id"] not in seen_ids]

    if is_first_run:
        log.info(
            "First run detected. Seeding database with %d announcements. "
            "No notifications will be sent.",
            len(announcements),
        )
    else:
        log.info(
            "Found %d new announcement(s) out of %d total.",
            len(new_announcements),
            len(announcements),
        )

    if not is_first_run:
        for ann in new_announcements:
            message = format_announcement_message(ann)
            send_telegram_message(session, message)

    all_ids = [a["id"] for a in announcements]
    state["last_seen_ids"] = all_ids
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    log.info("=== Checker finished successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
