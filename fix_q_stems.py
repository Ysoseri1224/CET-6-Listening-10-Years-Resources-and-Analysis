#!/usr/bin/env python3
"""
Fix q_stem files that are too long (didn't find Part III boundary)
or too short (answer-card-only PDFs with no real content).
Delete files that are just answer cards with no listening questions.
For oversized files, re-truncate at Part III boundary with broader patterns.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")

# Normal Part II is 5000-9000 chars
MIN_VALID = 1000
MAX_VALID = 15000


def fix_oversized(filepath: Path) -> bool:
    """Try to truncate oversized q_stem at Part III boundary."""
    text = filepath.read_text(encoding="utf-8")
    if len(text) <= MAX_VALID:
        return False

    # Broader patterns for Part III that OCR might produce
    patterns = [
        r"Part\s*(?:III|Ⅲ|II1|IIl|Il1)\s*(?:Reading|Ｒｅａｄｉｎｇ)",
        r"Part\s*(?:III|Ⅲ)\b",
        r"Part\s*III\b",
        r"Reading\s*Comprehension\s*\(40",
        r"Section\s*A\s*\n\s*Directions.*?In this section.*?(?:passage|article)",
    ]

    # Search after first 2000 chars (skip Part II header area)
    search_start = min(2000, len(text) // 4)

    for pat in patterns:
        m = re.search(pat, text[search_start:], re.IGNORECASE | re.DOTALL)
        if m:
            cut_point = search_start + m.start()
            truncated = text[:cut_point].strip()
            if MIN_VALID < len(truncated) < MAX_VALID:
                filepath.write_text(truncated, encoding="utf-8")
                return True

    # If no pattern matched, try finding question 25 and cut after it
    q25_patterns = [r"25\.\s*[A-D]\)", r"Q25", r"25\s*\.\s*A\s*\)"]
    for pat in q25_patterns:
        matches = list(re.finditer(pat, text))
        if matches:
            last_q25 = matches[-1]
            # Find end of that question's options (next blank line or next section)
            after_q25 = text[last_q25.start():]
            # Find the end of options for Q25
            end_match = re.search(r"\n\s*\n", after_q25[100:])
            if end_match:
                cut_point = last_q25.start() + 100 + end_match.end()
                truncated = text[:cut_point].strip()
                if len(truncated) > MIN_VALID:
                    filepath.write_text(truncated, encoding="utf-8")
                    return True

    return False


def fix_oversized_by_directions(filepath: Path) -> bool:
    """For OCR files where Part III marker is garbled, find where
    listening directions end and reading directions begin."""
    text = filepath.read_text(encoding="utf-8")
    if len(text) <= MAX_VALID:
        return False

    # Find Section B/C that has "read a passage" in its Directions (= Reading, not Listening)
    reading_patterns = [
        r"Section\s*[ABC]\s*\n\s*Directions.*?(?:read\s+a\s+passage|read\s+the\s+following)",
        r"Section\s*[A-C]\s*\n.*?(?:read\s+a\s+passage)",
    ]
    for pat in reading_patterns:
        m = re.search(pat, text[500:], re.IGNORECASE | re.DOTALL)
        if m:
            cut_point = 500 + m.start()
            truncated = text[:cut_point].strip()
            if MIN_VALID < len(truncated) < MAX_VALID:
                filepath.write_text(truncated, encoding="utf-8")
                return True
            elif len(truncated) >= MAX_VALID:
                # Still too long, try next match
                continue

    # Try finding "Part" followed by Translation/IV
    trans_pat = r"Part\s*\S{0,3}\s*Translation"
    m = re.search(trans_pat, text[2000:], re.IGNORECASE)
    if m:
        cut_point = 2000 + m.start()
        truncated = text[:cut_point].strip()
        if len(truncated) > MIN_VALID:
            filepath.write_text(truncated, encoding="utf-8")
            return True

    return False


def main():
    print("Fixing q_stem quality issues (pass 2)")
    print("=" * 60)

    fixed = 0
    deleted = 0
    still_bad = 0

    for exam_dir in sorted(BASE_DIR.iterdir()):
        if not exam_dir.is_dir() or not re.match(r"CET6_\d{4}\.\d{2}$", exam_dir.name):
            continue

        for f in sorted(exam_dir.glob("cet6_*_q_stem.txt")):
            text = f.read_text(encoding="utf-8")
            size = len(text)

            if MIN_VALID <= size <= MAX_VALID:
                continue

            if size < MIN_VALID:
                if "同第一套" in text or "同第二套" in text or "一致" in text or size < 300:
                    f.unlink()
                    print(f"  [DEL] {exam_dir.name}/{f.name} ({size} chars - answer card/placeholder)")
                    deleted += 1
                else:
                    print(f"  [BAD] {exam_dir.name}/{f.name} ({size} chars - too short)")
                    still_bad += 1
            else:
                if fix_oversized(f):
                    new_size = len(f.read_text(encoding="utf-8"))
                    print(f"  [FIX] {exam_dir.name}/{f.name} ({size} -> {new_size} chars)")
                    fixed += 1
                elif fix_oversized_by_directions(f):
                    new_size = len(f.read_text(encoding="utf-8"))
                    print(f"  [FIX2] {exam_dir.name}/{f.name} ({size} -> {new_size} chars)")
                    fixed += 1
                else:
                    print(f"  [BAD] {exam_dir.name}/{f.name} ({size} chars - can't truncate)")
                    still_bad += 1

    print(f"\nDone! Fixed={fixed}, Deleted={deleted}, Still bad={still_bad}")


if __name__ == "__main__":
    main()
