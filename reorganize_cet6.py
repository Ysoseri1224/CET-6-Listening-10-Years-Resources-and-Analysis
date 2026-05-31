#!/usr/bin/env python3
"""
CET6-Resources reorganization script:
1. Flatten subdirectories in CET6_20xx.xx folders
2. Extract Part II from exam PDFs with normalized naming
3. Rename existing q_stem files to normalized names
4. Normalize MP3/M4A audio file names
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")


def get_exam_dirs() -> list[Path]:
    """Get all CET6_20xx.xx directories (excluding abandon)."""
    results = []
    for d in sorted(BASE_DIR.iterdir()):
        if d.is_dir() and re.match(r"CET6_\d{4}\.\d{2}$", d.name):
            results.append(d)
    return results


# ============================================================
# STEP 1: Flatten subdirectories
# ============================================================

def flatten_subdirs():
    print("=" * 60)
    print("STEP 1: Flatten subdirectories")
    print("=" * 60)

    moved = 0
    conflicts = 0

    for exam_dir in get_exam_dirs():
        subdirs = [d for d in exam_dir.iterdir() if d.is_dir()]
        if not subdirs:
            continue

        for subdir in subdirs:
            for f in subdir.rglob("*"):
                if not f.is_file():
                    continue
                dest = exam_dir / f.name
                if dest.exists():
                    stem = f.stem
                    suffix = f.suffix
                    counter = 1
                    while dest.exists():
                        dest = exam_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                    conflicts += 1
                shutil.move(str(f), str(dest))
                moved += 1

        # Remove empty subdirs
        for subdir in subdirs:
            if subdir.exists():
                shutil.rmtree(subdir)

    print(f"  Moved {moved} files, {conflicts} conflicts resolved")


# ============================================================
# STEP 2: Extract Part II from PDFs
# ============================================================

def find_exam_pdfs_in_dir(exam_dir: Path) -> list[Path]:
    """Find exam paper PDFs (真题/试题, not 答案/解析) in a flat directory."""
    results = []
    for pdf in exam_dir.glob("*.pdf"):
        name = pdf.name
        is_exam = "真题" in name or "试题" in name
        is_answer = "解析" in name or "答案" in name or "详解" in name
        if is_exam and not is_answer and pdf.stat().st_size > 50000:
            results.append(pdf)
    return sorted(results)


def extract_part2(pdf_path: Path) -> str | None:
    """Extract Part II Listening Comprehension from a PDF using pdftotext."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, timeout=30, text=True,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            return None
        text = result.stdout
    except Exception:
        return None

    if not text or len(text) < 200:
        return None

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

    part3_start = len(text)
    for pattern in [r"Part\s*(?:III|Ⅲ)\s*Reading", r"Part\s*(?:III|Ⅲ)\b", r"Part\s*III\b"]:
        m = re.search(pattern, text[part2_start + 100:], re.IGNORECASE | re.MULTILINE)
        if m:
            part3_start = part2_start + 100 + m.start()
            break

    part2_text = text[part2_start:part3_start].strip()
    return part2_text if len(part2_text) > 100 else None


def get_set_number_from_pdf(pdf_path: Path) -> int:
    """Extract set number from PDF filename."""
    name = pdf_path.name
    m = re.search(r"第?[（(]?(\d)[）)]?套", name)
    if m:
        return int(m.group(1))
    m = re.search(r"[（(]([一二三])[）)]", name)
    if m:
        return {"一": 1, "二": 2, "三": 3}.get(m.group(1), 0)
    return 0


def extract_all_part2():
    print("\n" + "=" * 60)
    print("STEP 2: Extract Part II from exam PDFs")
    print("=" * 60)

    success = 0
    failed = 0
    skipped = 0

    for exam_dir in get_exam_dirs():
        date_str = exam_dir.name.replace("CET6_", "")
        pdfs = find_exam_pdfs_in_dir(exam_dir)
        if not pdfs:
            continue

        multi_set = len(pdfs) > 1

        for pdf_path in pdfs:
            set_num = get_set_number_from_pdf(pdf_path) if multi_set else 0

            if multi_set and set_num == 0:
                # Try to infer from position
                set_num = pdfs.index(pdf_path) + 1

            if multi_set:
                out_name = f"cet6_{date_str}_set{set_num}_q_stem.txt"
            else:
                out_name = f"cet6_{date_str}_q_stem.txt"

            out_path = exam_dir / out_name
            if out_path.exists():
                skipped += 1
                continue

            part2 = extract_part2(pdf_path)
            if part2:
                out_path.write_text(part2, encoding="utf-8")
                print(f"  [OK] {date_str}: {pdf_path.name} -> {out_name} ({len(part2)} chars)")
                success += 1
            else:
                print(f"  [FAIL] {date_str}: {pdf_path.name}")
                failed += 1

    print(f"\n  Extract summary: Success={success}, Failed={failed}, Skipped={skipped}")


# ============================================================
# STEP 3: Rename existing q_stem files
# ============================================================

def rename_q_stems():
    print("\n" + "=" * 60)
    print("STEP 3: Rename existing q_stem files")
    print("=" * 60)

    renamed = 0
    for exam_dir in get_exam_dirs():
        date_str = exam_dir.name.replace("CET6_", "")

        for f in list(exam_dir.glob("q_stem*")):
            if not f.is_file():
                continue
            old_name = f.name

            # Already normalized
            if old_name.startswith("cet6_"):
                continue

            # Determine set number
            m = re.search(r"set(\d)", old_name)
            if m:
                set_num = int(m.group(1))
                new_name = f"cet6_{date_str}_set{set_num}_q_stem.txt"
            else:
                new_name = f"cet6_{date_str}_q_stem.txt"

            new_path = exam_dir / new_name
            if new_path.exists() and new_path != f:
                print(f"  [SKIP] {exam_dir.name}/{old_name} -> {new_name} (target exists)")
                continue

            f.rename(new_path)
            print(f"  [RENAME] {exam_dir.name}/{old_name} -> {new_name}")
            renamed += 1

    print(f"\n  Renamed {renamed} q_stem files")


# ============================================================
# STEP 4: Normalize audio file names (MP3 + M4A)
# ============================================================

def normalize_audio():
    print("\n" + "=" * 60)
    print("STEP 4: Normalize audio file names")
    print("=" * 60)

    renamed = 0
    skipped = 0
    deleted = 0

    for exam_dir in get_exam_dirs():
        date_str = exam_dir.name.replace("CET6_", "")

        audio_files = list(exam_dir.glob("*.mp3")) + list(exam_dir.glob("*.m4a"))
        if not audio_files:
            continue

        for af in audio_files:
            name = af.name
            ext = af.suffix  # .mp3 or .m4a

            # Already normalized
            if re.match(r"CET6_\d{4}\.\d{2}(_set\d)?_listening\.(mp3|m4a)$", name):
                continue

            # Skip non-六级 files
            if "四级" in name or "四级" in name.lower():
                print(f"  [SKIP-4] {exam_dir.name}/{name}")
                skipped += 1
                continue

            # Determine set number from filename
            set_num = 0
            for pat, num in [(r"第?[（(]?1[）)]?套|第一套|第一", 1),
                             (r"第?[（(]?2[）)]?套|第二套|第二", 2),
                             (r"第?[（(]?3[）)]?套|第三套|第三", 3)]:
                if re.search(pat, name):
                    set_num = num
                    break

            # Try numeric patterns like "2016-12-1.mp3"
            if set_num == 0:
                m = re.search(r"-(\d)\.mp3$", name)
                if m:
                    set_num = int(m.group(1))

            # Determine if this exam has multiple sets
            same_ext_files = [f for f in audio_files if f.suffix == ext and f != af]
            has_multiple = len(same_ext_files) > 0

            if has_multiple and set_num == 0:
                print(f"  [SKIP] {exam_dir.name}/{name} (can't determine set number)")
                skipped += 1
                continue

            if set_num > 0:
                new_name = f"CET6_{date_str}_set{set_num}_listening{ext}"
            else:
                new_name = f"CET6_{date_str}_listening{ext}"

            new_path = exam_dir / new_name
            if new_path.exists() and new_path != af:
                # Duplicate - delete the non-normalized one
                af.unlink()
                print(f"  [DEL] {exam_dir.name}/{name} (duplicate of {new_name})")
                deleted += 1
                continue

            af.rename(new_path)
            print(f"  [RENAME] {exam_dir.name}/{name} -> {new_name}")
            renamed += 1

    print(f"\n  Audio summary: Renamed={renamed}, Skipped={skipped}, Deleted={deleted}")


# ============================================================

def main():
    print(f"CET6-Resources Reorganization")
    print(f"Base: {BASE_DIR}\n")

    flatten_subdirs()
    rename_q_stems()
    extract_all_part2()
    normalize_audio()

    print("\n" + "=" * 60)
    print("All done!")


if __name__ == "__main__":
    main()
