#!/usr/bin/env python3
"""
Pondicherry University — Telegram Notification Bot
Monitors https://www.pondiuni.edu.in/all-notifications/
Sends new notifications to Telegram with PDF attachment.
"""

import os
import re
import json
import time
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID        = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL       = "https://www.pondiuni.edu.in"
NOTIF_URL      = f"{BASE_URL}/all-notifications/"
SEEN_FILE      = "seen.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TAB_SLUGS = {
    "Circulars":           ("Circulars",           "📋"),
    "News":                ("News & Announcements", "📰"),
    "PhD":                 ("Ph.D Notifications",  "🎓"),
    "Events":              ("Events",              "🗓️"),
    "Admission":           ("Admission",           "🏫"),
    "Careers":             ("Careers",             "💼"),
    "Tenders":             ("Tenders",             "📝"),
}

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ─────────────────────────────────────────────────────────────
# SEEN-STORE  (persisted in seen.json → committed to Git)
# ─────────────────────────────────────────────────────────────
def load_seen() -> dict:
    try:
        return json.loads(Path(SEEN_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_seen(seen: dict):
    Path(SEEN_FILE).write_text(
        json.dumps(seen, indent=2, ensure_ascii=False), encoding="utf-8"
    )

# ─────────────────────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────────────────────
def fetch_all_notifications() -> list[dict]:
    """
    Strategy 1 → WordPress REST API (fastest, cleanest)
    Strategy 2 → Direct HTML scrape (fallback)
    """
    results = _try_wp_rest_api()
    if results:
        print(f"  [API]  Retrieved {len(results)} notifications via WP REST API")
        return results

    results = _scrape_html()
    print(f"  [HTML] Retrieved {len(results)} notifications via HTML scrape")
    return results


def _try_wp_rest_api() -> list[dict]:
    """WordPress REST API — works if site exposes /wp-json/"""
    all_items = []
    for page in range(1, 6):          # up to 5 pages × 50 = 250 items
        url = (
            f"{BASE_URL}/wp-json/wp/v2/university_news"
            f"?per_page=50&page={page}&orderby=date&order=desc&_embed=true"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 400:    # page out of range
                break
            if r.status_code != 200:
                return []
            items = r.json()
            if not items:
                break
            for item in items:
                # Try to get category name from embedded terms
                cat_name = "General"
                cat_emoji = "🔔"
                try:
                    terms = item["_embedded"]["wp:term"][0]
                    if terms:
                        raw = terms[0]["name"]
                        for key, (name, emoji) in TAB_SLUGS.items():
                            if key.lower() in raw.lower() or name.lower() in raw.lower():
                                cat_name, cat_emoji = name, emoji
                                break
                        else:
                            cat_name = raw
                except Exception:
                    pass

                issued_by = ""
                try:
                    # Sometimes stored in meta or excerpt
                    excerpt = BeautifulSoup(
                        item.get("excerpt", {}).get("rendered", ""), "html.parser"
                    ).get_text()
                    issued_by = excerpt.strip()[:120]
                except Exception:
                    pass

                all_items.append({
                    "id":        str(item["id"]),
                    "title":     BeautifulSoup(
                                     item["title"]["rendered"], "html.parser"
                                 ).get_text(strip=True),
                    "link":      item["link"],
                    "category":  f"{cat_name} {cat_emoji}",
                    "issued_by": issued_by,
                    "date":      _fmt_wp_date(item.get("date", "")),
                })
        except Exception as e:
            print(f"  WP API page {page} error: {e}")
            break
    return all_items


def _scrape_html() -> list[dict]:
    """Direct HTML scrape — iterates over all tab sections."""
    try:
        r = requests.get(NOTIF_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"  Failed to fetch notifications page: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # Many PU-style sites: <div id="Circulars"> ... <table> ...
    for tab_id, (cat_name, cat_emoji) in TAB_SLUGS.items():
        container = (
            soup.find(id=tab_id) or
            soup.find(id=tab_id.lower()) or
            soup.find("div", {"data-id": tab_id})
        )
        if container is None:
            continue
        _extract_rows(container, f"{cat_name} {cat_emoji}", results)

    # Fallback: parse whole page if no tab containers found
    if not results:
        _extract_rows(soup, "General 🔔", results)

    # Deduplicate by link
    seen_links = set()
    deduped = []
    for n in results:
        if n["link"] not in seen_links:
            seen_links.add(n["link"])
            deduped.append(n)
    return deduped


def _extract_rows(container, category: str, out: list):
    for row in container.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 1:
            continue
        link_tag = cells[0].find("a", href=True)
        if not link_tag:
            continue
        href  = _abs(link_tag["href"])
        title = link_tag.get_text(strip=True)
        if not title:
            continue
        issued_by = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        date_str  = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        out.append({
            "id":        href,
            "title":     title,
            "link":      href,
            "category":  category,
            "issued_by": issued_by,
            "date":      date_str,
        })

# ─────────────────────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────────────────────
def get_pdf_url(detail_url: str) -> str | None:
    """Scrape notification detail page and find the PDF URL."""
    try:
        r = requests.get(detail_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # 1. Direct <a href="*.pdf">
        for a in soup.find_all("a", href=True):
            if re.search(r"\.pdf(\?|$)", a["href"], re.I):
                return _abs(a["href"])

        # 2. <embed>, <iframe>, <object> src
        for tag in soup.find_all(["embed", "iframe", "object"]):
            src = tag.get("src") or tag.get("data") or ""
            if re.search(r"\.pdf", src, re.I):
                return _abs(src)

        # 3. ViewerJS / PDFObject / Google Viewer patterns in raw HTML
        raw = r.text
        for pat in [
            r'ViewerJS/#(?:https?:)?([^\s"\'<]+\.pdf[^\s"\'<]*)',
            r'["\']([^"\']*?\.pdf)["\']',
            r'file=([^\s&"\'<]+\.pdf[^\s&"\'<]*)',
        ]:
            m = re.search(pat, raw, re.I)
            if m:
                candidate = m.group(1)
                # Skip tiny icon/logo PDFs
                if len(candidate) > 8:
                    return _abs(candidate)

    except Exception as e:
        print(f"    PDF extraction error: {e}")
    return None


def download_pdf(pdf_url: str) -> str | None:
    """Download PDF → /tmp/pu_<hash>.pdf. Returns path or None."""
    try:
        uid = hashlib.md5(pdf_url.encode()).hexdigest()[:10]
        local = f"/tmp/pu_{uid}.pdf"
        with requests.get(pdf_url, headers=HEADERS, timeout=60, stream=True) as r:
            if r.status_code != 200:
                return None
            ct = r.headers.get("content-type", "")
            if "pdf" not in ct.lower() and not re.search(r"\.pdf", pdf_url, re.I):
                return None
            size = 0
            with open(local, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    size += len(chunk)
                    if size > 49 * 1024 * 1024:   # Telegram 50 MB limit
                        break
        if Path(local).stat().st_size < 512:
            return None
        return local
    except Exception as e:
        print(f"    PDF download error: {e}")
        return None

# ─────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────
def _tg_post(endpoint: str, **kwargs) -> bool:
    for attempt in range(3):
        try:
            r = requests.post(f"{TG_API}/{endpoint}", timeout=60, **kwargs)
            if r.ok:
                return True
            err = r.json().get("description", r.text)
            print(f"    Telegram {endpoint} attempt {attempt+1} failed: {err}")
            if "Too Many Requests" in err:
                time.sleep(int(re.search(r"\d+", err).group()) + 1)
            elif "file" in err.lower() or "document" in err.lower():
                return False   # don't retry file errors
            else:
                time.sleep(2)
        except Exception as e:
            print(f"    Telegram error: {e}")
            time.sleep(3)
    return False


def tg_text(text: str) -> bool:
    return _tg_post("sendMessage", json={
        "chat_id":                  CHAT_ID,
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": True,
    })


def tg_document_file(path: str, caption: str) -> bool:
    with open(path, "rb") as f:
        return _tg_post("sendDocument",
            data={"chat_id": CHAT_ID, "caption": caption[:1024], "parse_mode": "HTML"},
            files={"document": (Path(path).name, f, "application/pdf")},
        )


def tg_document_url(pdf_url: str, caption: str) -> bool:
    return _tg_post("sendDocument", data={
        "chat_id":    CHAT_ID,
        "document":   pdf_url,
        "caption":    caption[:1024],
        "parse_mode": "HTML",
    })


def build_caption(n: dict) -> str:
    return (
        f"🔔 <b>NEW NOTIFICATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏛 <b>Pondicherry University</b>\n\n"
        f"📁 <b>Category :</b> {n.get('category', 'General')}\n"
        f"📄 <b>Title    :</b> {n['title']}\n"
        f"🏢 <b>Issued by:</b> {n.get('issued_by') or '—'}\n"
        f"📅 <b>Date     :</b> {n.get('date') or '—'}\n\n"
        f"🔗 <a href=\"{n['link']}\">Open on Website ↗</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


def deliver(n: dict):
    caption = build_caption(n)
    pdf_url  = get_pdf_url(n["link"])

    if pdf_url:
        print(f"    PDF → {pdf_url[:80]}")
        local = download_pdf(pdf_url)
        if local:
            print("    Sending PDF as file upload …")
            ok = tg_document_file(local, caption)
            Path(local).unlink(missing_ok=True)
            if ok:
                return
        # Fallback: send URL directly (Telegram fetches it)
        print("    Sending PDF by URL …")
        ok = tg_document_url(pdf_url, caption)
        if ok:
            return

    # Last resort: text only with link
    print("    Sending text-only message …")
    tg_text(caption)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _abs(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):   return "https:" + url
    if url.startswith("/"):    return BASE_URL + url
    if not url.startswith("http"): return BASE_URL + "/" + url
    return url

def _fmt_wp_date(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").strftime("%d %B %Y")
    except Exception:
        return s

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"  PU Notification Bot  —  {ts}")
    print(f"{'='*55}")

    seen = load_seen()
    is_first_run = len(seen) == 0

    if is_first_run:
        print("  ⚡ First run detected — seeding seen.json without sending alerts.")
        print("     Future runs will send only NEW notifications.")

    notifications = fetch_all_notifications()
    new_count = 0

    for n in notifications:
        nid = n["id"]
        if nid in seen:
            continue

        if is_first_run:
            # Just mark as known — don't spam user with old notifications
            seen[nid] = {
                "title":    n["title"],
                "date":     n.get("date", ""),
                "category": n.get("category", ""),
                "notified": "seeded",
            }
            continue

        print(f"\n  🆕 {n['title'][:70]}")
        print(f"     {n.get('category','')}  |  {n.get('date','')}")
        deliver(n)

        seen[nid] = {
            "title":    n["title"],
            "date":     n.get("date", ""),
            "category": n.get("category", ""),
            "notified": datetime.now().isoformat(),
        }
        new_count += 1
        time.sleep(3)      # respect Telegram rate limits

    save_seen(seen)

    if is_first_run:
        print(f"\n  ✅ Seeded {len(seen)} existing notifications. Bot is now active!")
        tg_text(
            "✅ <b>PU Notification Bot is now active!</b>\n\n"
            f"I've catalogued <b>{len(seen)}</b> existing notifications.\n"
            "You'll get alerts for every <b>new</b> one from now on — with PDF! 🎉\n\n"
            "🏛 <i>Pondicherry University</i>"
        )
    else:
        print(f"\n  ✅ Done. {new_count} new notification(s) sent.")

if __name__ == "__main__":
    main()
