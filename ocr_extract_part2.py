#!/usr/bin/env python3
"""
OCR-based Part II extraction for scanned CET-6 exam PDFs.
Pipeline: pdftopng -> tesseract OCR -> extract Part II section
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def get_exam_dirs() -> list[Path]:
    results = []
    for d in sorted(BASE_DIR.iterdir()):
        if d.is_dir() and re.match(r"CET6_\d{4}\.\d{2}$", d.name):
            results.append(d)
    return results


def find_missing_q_stems() -> list[tuple[Path, Path, str]]:
    """Find exam PDFs that don't have a corresponding q_stem file yet."""
    results = []
    for exam_dir in get_exam_dirs():
        date_str = exam_dir.name.replace("CET6_", "")
        pdfs = []
        for pdf in exam_dir.glob("*.pdf"):
            name = pdf.name
            is_exam = "真题" in name or "试题" in name
            is_answer = "解析" in name or "答案" in name or "详解" in name
            if is_exam and not is_answer and pdf.stat().st_size > 50000:
                pdfs.append(pdf)
        pdfs.sort()

        if not pdfs:
            continue

        multi_set = len(pdfs) > 1

        for pdf_path in pdfs:
            if multi_set:
                set_num = get_set_number(pdf_path, pdfs)
                out_name = f"cet6_{date_str}_set{set_num}_q_stem.txt"
            else:
                out_name = f"cet6_{date_str}_q_stem.txt"

            out_path = exam_dir / out_name
            if not out_path.exists():
                results.append((pdf_path, out_path, date_str))

    return results


def get_set_number(pdf_path: Path, all_pdfs: list[Path]) -> int:
    name = pdf_path.name
    m = re.search(r"第?[（(]?(\d)[）)]?套", name)
    if m:
        return int(m.group(1))
    m = re.search(r"[（(]([一二三])[）)]", name)
    if m:
        return {"一": 1, "二": 2, "三": 3}.get(m.group(1), 0)
    return all_pdfs.index(pdf_path) + 1


def pdf_to_text_ocr(pdf_path: Path) -> str | None:
    """Convert PDF to PNG pages, then OCR each page."""
    with tempfile.TemporaryDirectory() as tmpdir:
        png_root = os.path.join(tmpdir, "page")

        # pdftopng <pdf> <png-root> produces page-000001.png, page-000002.png, etc.
        try:
            subprocess.run(
                ["pdftopng", "-r", "300", str(pdf_path), png_root],
                capture_output=True, timeout=120
            )
        except Exception as e:
            print(f"    pdftopng error: {e}")
            return None

        png_files = sorted(Path(tmpdir).glob("page-*.png"))
        if not png_files:
            print(f"    No PNG files generated")
            return None

        print(f"    {len(png_files)} pages converted to PNG")

        full_text = ""
        for png in png_files:
            try:
                result = subprocess.run(
                    [TESSERACT, str(png), "stdout", "-l", "eng",
                     "--psm", "6"],
                    capture_output=True, timeout=60,
                    text=True, encoding="utf-8", errors="replace"
                )
                if result.returncode == 0 and result.stdout:
                    full_text += result.stdout + "\n"
            except Exception:
                continue

        return full_text if len(full_text) > 200 else None


def extract_part2_from_text(text: str) -> str | None:
    """Extract Part II Listening Comprehension section from OCR text."""
    part2_start = -1
    for pattern in [r"Part\s*(?:II|Ⅱ|I1|Il)\s*[:\s]*Listening",
                    r"Part\s*(?:II|Ⅱ)\b",
                    r"Listening\s*Comprehension"]:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            part2_start = m.start()
            break

    if part2_start < 0:
        m = re.search(r"Section\s*A\b", text, re.IGNORECASE)
        if m:
            part2_start = m.start()

    if part2_start < 0:
        return None

    part3_start = len(text)
    for pattern in [r"Part\s*(?:III|Ⅲ|II1|IIl)\s*[:\s]*Reading",
                    r"Part\s*(?:III|Ⅲ)\s*Reading",
                    r"Part\s*(?:III|Ⅲ)\b",
                    r"Reading\s*Comprehension"]:
        m = re.search(pattern, text[part2_start + 50:], re.IGNORECASE | re.MULTILINE)
        if m:
            part3_start = part2_start + 50 + m.start()
            break

    part2_text = text[part2_start:part3_start].strip()
    return part2_text if len(part2_text) > 100 else None


def main():
    print("OCR-based Part II Extraction")
    print(f"Base: {BASE_DIR}")
    print("=" * 60)

    missing = find_missing_q_stems()
    print(f"Found {len(missing)} PDFs needing OCR extraction\n")

    success = 0
    failed = 0

    for pdf_path, out_path, date_str in missing:
        print(f"  [{date_str}] {pdf_path.name}")

        text = pdf_to_text_ocr(pdf_path)
        if not text:
            print(f"    [FAIL] OCR produced no text")
            failed += 1
            continue

        part2 = extract_part2_from_text(text)
        if part2:
            out_path.write_text(part2, encoding="utf-8")
            print(f"    [OK] -> {out_path.name} ({len(part2)} chars)")
            success += 1
        else:
            # Save full OCR text for debugging
            debug_path = out_path.with_suffix(".ocr_full.txt")
            debug_path.write_text(text, encoding="utf-8")
            print(f"    [FAIL] Part II not found in OCR text ({len(text)} chars total)")
            print(f"    Saved full OCR to {debug_path.name} for inspection")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Done! Success={success}, Failed={failed}")


if __name__ == "__main__":
    main()
