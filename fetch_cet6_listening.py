#!/usr/bin/env python3
"""
Fetch CET-6 Listening Comprehension transcripts (2016-2025) from web sources.
Saves each exam's transcript as a text file in the listening_transcripts/ folder.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent / "listening_transcripts"
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Known URLs for CET-6 listening transcripts
# Format: (exam_date, set_number, url, source_site)
TRANSCRIPT_URLS = [
    # 2024.12
    ("2024.12", 1, "https://cet6.koolearn.com/20241214/893923.html", "koolearn"),
    # 2024.06
    ("2024.06", 1, "https://cet6.koolearn.com/20240615/887631.html", "koolearn"),
    ("2024.06", 2, "https://cet6.koolearn.com/20240615/887635.html", "koolearn"),
    # 2023.06
    ("2023.06", 1, "https://cet6.koolearn.com/20230617/873428.html", "koolearn"),
    # 2023.03
    ("2023.03", 1, "https://cet6.koolearn.com/20230310/870265.html", "koolearn"),
    # 2022.12
    ("2022.12", 1, "https://cet6.koolearn.com/20221210/866720.html", "koolearn"),
    # 2022.06
    ("2022.06", 1, "https://cet6.koolearn.com/20220611/860152.html", "koolearn"),
    # 2021.12
    ("2021.12", 1, "https://cet6.koolearn.com/20220117/851202.html", "koolearn"),
    ("2021.12", 2, "https://cet6.koolearn.com/20220117/851203.html", "koolearn"),
    # 2019.12
    ("2019.12", 1, "http://m.hujiang.com/en/p1310562/", "hujiang"),
    # 2019.06
    ("2019.06", 1, "http://m.hujiang.com/en/p1278880/", "hujiang"),
    # 2018.06
    ("2018.06", 1, "https://m.hujiang.com/en/p1243234/", "hujiang"),
    # 2017.06
    ("2017.06", 1, "https://www.hujiang.com/c/wx/p1208279/", "hujiang"),
    # 2016.06
    ("2016.06", 1, "https://m.hujiang.com/en/p787874/", "hujiang"),
    ("2016.06", 2, "https://m.hujiang.com/en/p787872/", "hujiang"),
    # 2016.12
    ("2016.12", 1, "https://m.hujiang.com/en/p978411/", "hujiang"),
]

def fetch_page(url: str, retries: int = 3) -> str | None:
    """Fetch a URL and return the HTML content."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"  [FAIL] {url}: {e}", file=sys.stderr)
                return None
    return None


def extract_english_text(html: str, source: str) -> str:
    """Extract English listening transcript text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav elements
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Try to find the main content area
    content = None
    if source == "koolearn":
        content = soup.find("div", class_="con-body") or soup.find("div", class_="article-con")
        if not content:
            content = soup.find("div", id="artContent") or soup.find("article")
    elif source == "hujiang":
        content = soup.find("div", class_="article-body") or soup.find("div", class_="content")
        if not content:
            content = soup.find("div", id="content") or soup.find("article")

    if not content:
        # Fallback: use body
        content = soup.find("body")

    if not content:
        return ""

    # Get all text
    text = content.get_text(separator="\n")

    # Clean up and extract English content
    lines = text.split("\n")
    result_lines = []
    in_transcript = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_transcript:
                result_lines.append("")
            continue

        # Detect section markers
        if re.match(r"^(Section [ABC]|Conversation (One|Two|1|2)|Passage (One|Two|Three|1|2|3)|Recording (One|Two|Three|1|2|3)|Directions)", line, re.IGNORECASE):
            in_transcript = True
            result_lines.append(line)
            continue

        # Keep lines that are mostly English (listening transcript content)
        english_chars = len(re.findall(r"[a-zA-Z]", line))
        total_chars = len(line)
        if total_chars > 0 and english_chars / total_chars > 0.5:
            in_transcript = True
            result_lines.append(line)
        elif in_transcript and re.match(r"^(Q|Question|[MW]\s*[:：]|\d+\.)", line):
            result_lines.append(line)

    # Clean up multiple blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(result_lines))
    return cleaned.strip()


def extract_koolearn_transcript(html: str) -> str:
    """Specialized extractor for koolearn.com pages."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    # koolearn uses various content div classes
    content = (
        soup.find("div", class_="con-body")
        or soup.find("div", class_="article-con")
        or soup.find("div", class_="content")
        or soup.find("div", id="artContent")
        or soup.find("article")
        or soup.find("body")
    )

    if not content:
        return ""

    # Get paragraphs
    paragraphs = content.find_all(["p", "div", "span"])
    lines = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if text:
            lines.append(text)

    if not lines:
        text = content.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Filter for English content related to listening
    result = []
    capture = False
    for line in lines:
        # Start capturing at section markers
        if re.search(r"(Section [ABC]|Conversation|Passage|Recording|Directions)", line, re.IGNORECASE):
            capture = True

        if not capture:
            # Also start if line is mostly English
            eng = len(re.findall(r"[a-zA-Z]", line))
            if len(line) > 20 and eng / max(len(line), 1) > 0.7:
                capture = True

        if capture:
            eng = len(re.findall(r"[a-zA-Z]", line))
            if len(line) > 5 and eng / max(len(line), 1) > 0.4:
                result.append(line)
            elif re.match(r"^(Section|Conversation|Passage|Recording|Question)", line, re.IGNORECASE):
                result.append(line)
            elif line == "":
                result.append("")

    return "\n".join(result).strip()


def save_transcript(exam_date: str, set_num: int, text: str) -> Path:
    """Save transcript to file."""
    filename = f"CET6_{exam_date}_set{set_num}_listening.txt"
    filepath = OUTPUT_DIR / filename
    filepath.write_text(text, encoding="utf-8")
    return filepath


def main():
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Total URLs to fetch: {len(TRANSCRIPT_URLS)}")
    print("=" * 60)

    success = 0
    failed = 0

    for exam_date, set_num, url, source in TRANSCRIPT_URLS:
        print(f"\n[{exam_date} Set {set_num}] Fetching from {source}...")
        html = fetch_page(url)
        if not html:
            failed += 1
            continue

        if source == "koolearn":
            text = extract_koolearn_transcript(html)
        else:
            text = extract_english_text(html, source)

        if not text or len(text) < 100:
            print(f"  [WARN] Extracted text too short ({len(text)} chars), trying fallback...")
            text = extract_english_text(html, source)

        if text and len(text) > 100:
            filepath = save_transcript(exam_date, set_num, text)
            print(f"  [OK] Saved {len(text)} chars -> {filepath.name}")
            success += 1
        else:
            print(f"  [FAIL] Could not extract meaningful transcript ({len(text or '')} chars)")
            failed += 1

        time.sleep(1.5)

    print("\n" + "=" * 60)
    print(f"Done! Success: {success}, Failed: {failed}")
    print(f"Files saved to: {OUTPUT_DIR}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
