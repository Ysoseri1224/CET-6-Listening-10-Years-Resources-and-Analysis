#!/usr/bin/env python3
"""
Clean all cet6_*_q_stem.txt files for readability.
Fixes: OCR artifacts, fullwidth chars, excess whitespace, page markers, etc.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")


def fullwidth_to_halfwidth(text: str) -> str:
    """Convert fullwidth ASCII characters to halfwidth."""
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif ch == '　':  # fullwidth space
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result)


def clean_text(text: str) -> str:
    """Clean OCR artifacts and normalize formatting."""

    # Convert fullwidth to halfwidth
    text = fullwidth_to_halfwidth(text)

    # Fix common OCR errors
    text = re.sub(r'\bJn\b', 'In', text)
    text = re.sub(r'\bln\b', 'In', text)
    text = re.sub(r'/n this section', 'In this section', text)
    text = re.sub(r'Directions\s*[;:]\s*', 'Directions: ', text)
    # Fix "o f" -> "of", "i f" -> "if" (OCR space insertion)
    text = re.sub(r'\bo f\b', 'of', text)
    text = re.sub(r'\bi f\b', 'if', text)
    text = re.sub(r'\bi t\b', 'it', text)

    # Remove page number artifacts (e.g., "6:1", "6-2", "6- 3", "{, 112u")
    text = re.sub(r'^\s*\d+[:-]\s*\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\{\s*,\s*\w+\s*$', '', text, flags=re.MULTILINE)

    # Remove page header/footer lines with exam info
    text = re.sub(r'^\s*\*?\s*\d{4}\s*[年&]\s*\d{1,2}\s*[月)]\s*\d*\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*20\d{2}.*?[六4]级.*?第?\d套.*$', '', text, flags=re.MULTILINE)

    # Remove OCR garbage lines: mostly non-ASCII with few English letters, short
    # e.g., "2022 12 ARiNRAGA ILE 1 HK 10K"
    text = re.sub(r'^\s*\d{4}\s+\d{1,2}\s+[A-Z][A-Za-z]+.*?[HK]{2,}.*$', '', text, flags=re.MULTILINE)
    # Generic: lines with random uppercase sequences that don't look like questions/options
    text = re.sub(r'^\s*\d{4}\s+\d{1,2}\s+\w+\s+\w+\s+\d+\s*$', '', text, flags=re.MULTILINE)

    # Remove lines that are OCR page markers (year + month + garbled text)
    text = re.sub(r'^\s*\*?.*?20\d{2}\s*.*?[月]\s*\d*\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\*?\s*20\d{2}\s+\S?\s+\d{1,2}\s+\S?\s*\d*\s*$', '', text, flags=re.MULTILINE)

    # Remove lines that are just OCR noise (mostly symbols/punctuation, <5 alphanumeric chars)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append('')
            continue

        # Count meaningful characters
        alpha_count = len(re.findall(r'[a-zA-Z0-9]', stripped))
        total_count = len(stripped)

        # Skip lines that are mostly garbage (symbols, fullwidth noise)
        if total_count > 5 and alpha_count < 3 and not re.match(r'^[A-D]\)', stripped):
            continue

        # Skip barcode-like patterns
        if re.match(r'^[<>＜＞\s\-=_.,:;|{}()\[\]]+$', stripped):
            continue

        # Skip lines with OCR box artifacts
        if re.match(r'^[\s§}IJ£ffi-]+$', stripped):
            continue

        # Skip OCR page markers (year + random garbled text)
        if re.match(r'^\d{4}\s+\d{1,2}\s+[A-Z].*\d+\s*$', stripped) and len(stripped) < 50:
            continue

        # Skip page header/footer like "1 . 2025年 12月六级真题(第一套)."
        if re.search(r'\d{4}\s*年.*?[六四]级.*?[真题套]', stripped) and len(stripped) < 60:
            continue

        # Skip isolated punctuation/symbols (single char noise)
        if len(stripped) <= 2 and not re.match(r'^[A-D]\)$', stripped):
            continue

        # Skip lines that are just garbled OCR (high ratio of unusual chars)
        if total_count > 10:
            unusual = len(re.findall(r'[^\x20-\x7E\n]', stripped))
            if unusual / total_count > 0.5 and alpha_count < total_count * 0.3:
                continue

        cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)

    # Normalize "Part II" header - keep it simple
    text = re.sub(
        r'Part\s*(?:Il|II|II)\s+Listening\s+Comprehension\s*\(\s*30\s*minutes?\s*\)',
        'Part II Listening Comprehension (30 minutes)',
        text, flags=re.IGNORECASE
    )

    # Fix "Questions | to 4" -> "Questions 1 to 4"
    text = re.sub(r'Questions\s*\|\s*to', 'Questions 1 to', text)

    # Fix "Answer Sheet I" -> "Answer Sheet 1"
    text = re.sub(r'Answer Sheet I\b', 'Answer Sheet 1', text)

    # Collapse multiple spaces into single space (but preserve leading indent)
    new_lines = []
    for line in text.split('\n'):
        # Preserve structure but clean internal spacing
        line = re.sub(r'  +', ' ', line)
        # Remove trailing OCR noise (isolated dots, pipes, dashes, semicolons)
        line = re.sub(r'\s*[|;]\s*$', '', line)
        line = re.sub(r'\s+[\.\-]\s*$', '', line)
        # Remove trailing OCR artifacts like "oe", "yn", "sa", "co" at end of lines
        line = re.sub(r'\s+[a-z]{1,2}\s*$', '', line)
        line = line.rstrip()
        new_lines.append(line)
    text = '\n'.join(new_lines)

    # Remove excessive blank lines (max 1 blank line between content)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove blank lines between answer options (A/B/C/D lines)
    # Pattern: option line, blank line, option line
    text = re.sub(
        r'(\n\s*[A-D]\).*)\n\n(\s*[A-D]\))',
        r'\1\n\2',
        text
    )
    # Repeat to catch consecutive cases
    for _ in range(4):
        text = re.sub(
            r'(\n\s*[A-D]\).*)\n\n(\s*[A-D]\))',
            r'\1\n\2',
            text
        )

    # Remove blank line between question number line and next option
    # e.g., "2. A) ...\n\nB) ..."
    text = re.sub(
        r'(\n\s*\d+[\.\)]\s*A\).*)\n\n(\s*B\))',
        r'\1\n\2',
        text
    )
    for _ in range(4):
        text = re.sub(
            r'(\n\s*[A-D]\).*)\n\n(\s*[A-D]\))',
            r'\1\n\2',
            text
        )

    # Remove blank lines within a question block (between numbered Q and its options)
    text = re.sub(
        r'(\n\s*\d+\.\s*A\).*)\n\n(\s*B\))',
        r'\1\n\2',
        text
    )

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def main():
    print("Cleaning q_stem files for readability")
    print("=" * 60)

    cleaned = 0
    for exam_dir in sorted(BASE_DIR.iterdir()):
        if not exam_dir.is_dir() or not re.match(r"CET6_\d{4}\.\d{2}$", exam_dir.name):
            continue

        for f in sorted(exam_dir.glob("cet6_*_q_stem.txt")):
            original = f.read_text(encoding="utf-8")
            cleaned_text = clean_text(original)

            if cleaned_text != original:
                f.write_text(cleaned_text, encoding="utf-8")
                old_len = len(original)
                new_len = len(cleaned_text)
                print(f"  [CLEAN] {exam_dir.name}/{f.name} ({old_len} -> {new_len} chars)")
                cleaned += 1

    print(f"\nCleaned {cleaned} files")


if __name__ == "__main__":
    main()
