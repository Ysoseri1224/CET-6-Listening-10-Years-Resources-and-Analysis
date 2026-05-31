#!/usr/bin/env python3
"""
CET-6 Listening Resources Organizer
1. Match and copy MP3 audio files to corresponding exam directories
2. Extract Part II (Listening Comprehension) questions from exam PDFs using pdftotext
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")
AUDIO_DIR = BASE_DIR / "2015-2025年12月英语四六级真题"


def log(msg: str):
    print(msg)


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# TASK 1: Extract Part II from exam PDFs using pdftotext
# ============================================================

def find_exam_pdfs() -> list[Path]:
    """Find exam paper PDFs (真题/试题, not 答案/解析)."""
    results = []
    for exam_dir in sorted(BASE_DIR.iterdir()):
        if not exam_dir.is_dir() or not exam_dir.name.startswith("CET6_"):
            continue
        for pdf in exam_dir.rglob("*.pdf"):
            name = pdf.name
            is_exam = "真题" in name or "试题" in name
            is_answer = "解析" in name or "答案" in name or "详解" in name
            if is_exam and not is_answer:
                if pdf.stat().st_size > 50000:
                    results.append(pdf)
    return results


def extract_part2(pdf_path: Path) -> str | None:
    """Extract Part II Listening Comprehension from a PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, timeout=30, text=True, encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            return None
        text = result.stdout
    except Exception:
        return None

    if not text or len(text) < 200:
        return None

    # Find Part II start
    part2_start = -1
    for pattern in [r"Part\s*(?:II|Ⅱ)\s*Listening", r"Part\s*II\b"]:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            part2_start = m.start()
            break

    if part2_start < 0:
        m = re.search(r"Section\s*A\s*\n.*?Directions.*?hear", text, re.IGNORECASE | re.DOTALL)
        if m:
            part2_start = m.start()

    if part2_start < 0:
        return None

    # Find Part III start (end of Part II)
    part3_start = len(text)
    for pattern in [r"Part\s*(?:III|Ⅲ)\s*Reading", r"Part\s*(?:III|Ⅲ)\b",
                    r"Part\s*III\b"]:
        m = re.search(pattern, text[part2_start + 100:], re.IGNORECASE | re.MULTILINE)
        if m:
            part3_start = part2_start + 100 + m.start()
            break

    part2_text = text[part2_start:part3_start].strip()
    return part2_text if len(part2_text) > 100 else None


def extract_all_part2():
    """Extract Part II from all exam PDFs."""
    log("\n" + "=" * 60)
    log("TASK 1: Extracting Part II (Listening) from exam PDFs")
    log("=" * 60)

    pdfs = find_exam_pdfs()
    log(f"Found {len(pdfs)} exam PDFs")

    success = 0
    failed = 0

    for pdf_path in sorted(pdfs):
        # Output: q_stem.txt in same directory as the PDF
        # If multiple PDFs in same dir, use set-specific name
        parent = pdf_path.parent
        siblings = [p for p in pdfs if p.parent == parent]

        if len(siblings) <= 1:
            output_path = parent / "q_stem.txt"
        else:
            # Extract set number from filename
            set_match = re.search(r"第?(\d)套", pdf_path.name)
            if set_match:
                output_path = parent / f"q_stem_set{set_match.group(1)}.txt"
            else:
                output_path = parent / f"q_stem_{pdf_path.stem}.txt"

        part2 = extract_part2(pdf_path)
        if part2:
            output_path.write_text(part2, encoding="utf-8")
            rel = f"{pdf_path.parent.parent.name}/{pdf_path.parent.name}" if pdf_path.parent != parent else pdf_path.parent.name
            log(f"  [OK] .../{pdf_path.name} -> {output_path.name} ({len(part2)} chars)")
            success += 1
        else:
            log(f"  [FAIL] .../{pdf_path.name}")
            failed += 1

    log(f"\nPDF Summary: Success={success}, Failed={failed}")


# ============================================================
# TASK 2: Match and copy MP3 files
# ============================================================

def find_cet6_mp3s() -> list[tuple[Path, str, int]]:
    """Find CET-6 MP3 files and determine exam date + set number."""
    results = []
    if not AUDIO_DIR.exists():
        log(f"Audio directory not found: {AUDIO_DIR}")
        return results

    for mp3 in AUDIO_DIR.rglob("*.mp3"):
        rel = str(mp3.relative_to(AUDIO_DIR))
        fname = mp3.name
        parent_name = mp3.parent.name

        # Skip CET-4 files: check parent directory and filename
        if "四级" in parent_name and "六级" not in parent_name:
            continue
        if "CET4" in parent_name and "CET6" not in parent_name:
            continue
        if "4级" in fname or "四级" in fname or "cet4" in fname.lower():
            continue

        # Determine year and month - prioritize filename, then parent dir
        year, month = None, None

        # Try filename first
        ym_match = re.search(r"(20\d{2})[年.](\d{1,2})", fname)
        if not ym_match:
            # Handle 2-digit year like "21年12月"
            ym_match = re.search(r"(\d{2})年(\d{1,2})月?", fname)
            if ym_match and 15 <= int(ym_match.group(1)) <= 26:
                year = 2000 + int(ym_match.group(1))
                month = int(ym_match.group(2))
        if ym_match and not year:
            year = int(ym_match.group(1))
            month = int(ym_match.group(2))

        # If not in filename, try parent directory name
        if not year:
            ym_match = re.search(r"(20\d{2})[年.](\d{1,2})", parent_name)
            if ym_match:
                year = int(ym_match.group(1))
                month = int(ym_match.group(2))

        # If still not found, try grandparent or the path with CET6 marker
        if not year:
            cet6_match = re.search(r"CET6.*?(20\d{2})[年.](\d{1,2})", rel)
            if cet6_match:
                year = int(cet6_match.group(1))
                month = int(cet6_match.group(2))

        if not year:
            continue

        # Determine set number
        set_num = 0
        combined = fname

        if re.search(r"第?二[、,].*?三.*?套|二[、]三套", combined):
            set_num = 23
        elif "全" in combined and "套" in combined:
            set_num = 0
        else:
            for pat, num in [(r"第[一1]套|音频[一1]|（第1套）|第1套", 1),
                             (r"第[二2]套|音频[二2]|（第2套）|第2套", 2),
                             (r"第[三3]套|音频[三3]|（第3套）|第3套", 3)]:
                if re.search(pat, combined):
                    set_num = num
                    break

        if set_num == 0 and not ("全" in combined):
            if "一套" in fname or "一" == fname.rstrip(".mp3MP")[-1:]:
                set_num = 1
            elif "二套" in fname or re.search(r"二(?!、)", fname):
                set_num = 2
            elif "三套" in fname or "三" == fname.rstrip(".mp3MP")[-1:]:
                set_num = 3

        results.append((mp3, f"{year}.{month:02d}", set_num))

    return results


def copy_mp3s():
    """Copy matched CET-6 MP3 files to target directories."""
    log("\n" + "=" * 60)
    log("TASK 2: Matching and copying MP3 files")
    log("=" * 60)

    mp3s = find_cet6_mp3s()
    log(f"Found {len(mp3s)} CET-6 MP3 files")

    copied = 0
    skipped = 0
    no_target = 0

    for mp3_path, exam_date, set_num in sorted(mp3s, key=lambda x: (x[1], x[2])):
        target_dir = BASE_DIR / f"CET6_{exam_date}"
        if not target_dir.exists():
            log(f"  [NO TARGET] {exam_date} set{set_num}: {mp3_path.name}")
            no_target += 1
            continue

        if set_num == 0:
            dest_name = f"CET6_{exam_date}_listening.mp3"
        elif set_num == 23:
            dest_name = f"CET6_{exam_date}_set2_3_listening.mp3"
        else:
            dest_name = f"CET6_{exam_date}_set{set_num}_listening.mp3"

        dest_path = target_dir / dest_name
        if dest_path.exists():
            skipped += 1
            continue

        shutil.copy2(mp3_path, dest_path)
        log(f"  [COPY] {exam_date} set{set_num}: {mp3_path.name} -> {dest_name}")
        copied += 1

    log(f"\nMP3 Summary: Copied={copied}, Skipped(exists)={skipped}, No target={no_target}")


# ============================================================

def main():
    log("CET-6 Listening Resources Organizer")
    log(f"Base: {BASE_DIR}")
    copy_mp3s()
    extract_all_part2()
    log("\nDone!")


if __name__ == "__main__":
    main()
