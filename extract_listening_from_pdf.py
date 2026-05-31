#!/usr/bin/env python3
"""
Extract CET-6 listening transcripts from answer/解析 PDF files.
Handles the common issue of missing spaces in PDF text extraction.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pdfplumber

OUTPUT_DIR = Path(__file__).parent / "listening_transcripts"
OUTPUT_DIR.mkdir(exist_ok=True)

BASE_DIR = Path(__file__).parent / "CET6-Resources"


def fix_spacing(text: str) -> str:
    """Fix missing spaces in extracted PDF text."""
    # Add space before uppercase letters that follow lowercase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Add space before common words that are stuck together
    text = re.sub(r"([a-z])(I['’])", r'\1 \2', text)
    # Fix punctuation spacing
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([,;:])([A-Za-z])', r'\1 \2', text)
    # Fix common contractions that got split
    text = text.replace('I’m', "I'm")
    text = text.replace('I’ve', "I've")
    text = text.replace('don’t', "don't")
    text = text.replace('doesn’t', "doesn't")
    text = text.replace('didn’t', "didn't")
    text = text.replace('won’t', "won't")
    text = text.replace('wouldn’t', "wouldn't")
    text = text.replace('couldn’t', "couldn't")
    text = text.replace('shouldn’t', "shouldn't")
    text = text.replace('isn’t', "isn't")
    text = text.replace('aren’t', "aren't")
    text = text.replace('wasn’t', "wasn't")
    text = text.replace('weren’t', "weren't")
    text = text.replace('hasn’t', "hasn't")
    text = text.replace('haven’t', "haven't")
    text = text.replace('hadn’t', "hadn't")
    text = text.replace('it’s', "it's")
    text = text.replace('that’s', "that's")
    text = text.replace('what’s', "what's")
    text = text.replace('there’s', "there's")
    text = text.replace('let’s', "let's")
    text = text.replace('he’s', "he's")
    text = text.replace('she’s', "she's")
    text = text.replace('we’re', "we're")
    text = text.replace('they’re', "they're")
    text = text.replace('you’re', "you're")
    text = text.replace('we’ve', "we've")
    text = text.replace('they’ve', "they've")
    text = text.replace('you’ve', "you've")
    text = text.replace('’', "'")
    # Fix the special apostrophe character from PDFs
    text = text.replace('', "'")
    text = text.replace('�', "'")
    # Remove line numbers that appear in extracted text
    text = re.sub(r'^\d+\n', '', text, flags=re.MULTILINE)
    # Clean up multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text


def extract_transcript_section(full_text: str) -> str:
    """Extract the listening transcript (听力原文) section from full PDF text."""
    # Find the start of transcript section
    start_markers = ['听力原文', '·听力原文·']
    start_idx = -1
    for marker in start_markers:
        idx = full_text.find(marker)
        if idx >= 0:
            start_idx = idx
            break

    if start_idx < 0:
        return ""

    # Find the end - usually marked by Part III or 阅读 section
    end_markers = ['Part III', 'PartIII', 'Part Ⅲ', '阅读理解', 'Reading Comprehension',
                   '·词汇注释·', '词汇注释', '难词注释']
    end_idx = len(full_text)
    for marker in end_markers:
        idx = full_text.find(marker, start_idx + 100)
        if idx >= 0 and idx < end_idx:
            end_idx = idx

    raw_transcript = full_text[start_idx:end_idx]
    return raw_transcript


def clean_transcript(raw: str) -> str:
    """Clean extracted transcript text."""
    # Remove the header
    raw = re.sub(r'^.*?听力原文.*?\n', '', raw, count=1)

    # Fix spacing
    raw = fix_spacing(raw)

    # Remove Chinese annotations and explanations
    lines = raw.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append('')
            continue

        # Keep lines that are section markers
        if re.match(r'^(Section [ABC]|Conversation|Passage|Recording|Directions)', line, re.IGNORECASE):
            cleaned_lines.append('\n' + line)
            continue

        # Keep lines starting with M: or W: (speaker markers)
        if re.match(r'^[MW]\s*[:：]', line):
            cleaned_lines.append(line)
            continue

        # Keep lines starting with Q (questions)
        if re.match(r'^Q\d+', line):
            cleaned_lines.append(line)
            continue

        # Calculate English ratio
        eng_chars = len(re.findall(r'[a-zA-Z]', line))
        total_chars = len(line)
        if total_chars > 0 and eng_chars / total_chars > 0.6:
            cleaned_lines.append(line)
        elif total_chars > 0 and eng_chars / total_chars > 0.3 and len(line) > 50:
            # Mixed line - try to extract English part
            eng_parts = re.findall(r'[A-Za-z][A-Za-z\s,.\'"!?;:\-()]+[.!?]', line)
            if eng_parts:
                for part in eng_parts:
                    if len(part) > 30:
                        cleaned_lines.append(part.strip())

    # Join and clean up
    result = '\n'.join(cleaned_lines)
    # Remove excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def find_answer_pdfs() -> list[tuple[str, Path]]:
    """Find all answer/解析 PDFs that might contain listening transcripts."""
    results = []
    if not BASE_DIR.exists():
        print(f"Base directory not found: {BASE_DIR}", file=sys.stderr)
        return results

    for exam_dir in sorted(BASE_DIR.iterdir()):
        if not exam_dir.is_dir() or not exam_dir.name.startswith('CET6_'):
            continue

        exam_date = exam_dir.name.replace('CET6_', '')

        # Look for 解析 PDFs
        for root, dirs, files in os.walk(exam_dir):
            for f in files:
                if not f.lower().endswith('.pdf'):
                    continue
                if '解析' in f or '答案' in f or '详解' in f:
                    filepath = Path(root) / f
                    # Check if it's a real PDF (not LFS pointer)
                    if filepath.stat().st_size > 10000:
                        results.append((exam_date, filepath))

    return results


def main():
    print(f"Scanning for answer PDFs in: {BASE_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    pdfs = find_answer_pdfs()
    print(f"Found {len(pdfs)} answer PDFs")

    success = 0
    failed = 0
    no_transcript = 0

    for exam_date, pdf_path in pdfs:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Check if PDF has extractable text
                total_chars = sum(len(p.extract_text() or '') for p in pdf.pages)
                if total_chars < 500:
                    continue

                # Extract full text
                full_text = ''
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + '\n'

                # Extract transcript section
                raw_transcript = extract_transcript_section(full_text)
                if not raw_transcript:
                    no_transcript += 1
                    continue

                # Clean the transcript
                cleaned = clean_transcript(raw_transcript)

                if len(cleaned) < 200:
                    print(f"  [{exam_date}] Too short after cleaning ({len(cleaned)} chars): {pdf_path.name}")
                    failed += 1
                    continue

                # Determine set number from filename
                set_num = 1
                m = re.search(r'[第]?(\d)[套]', pdf_path.name)
                if m:
                    set_num = int(m.group(1))

                # Save
                filename = f"CET6_{exam_date}_set{set_num}_listening.txt"
                output_path = OUTPUT_DIR / filename
                output_path.write_text(cleaned, encoding='utf-8')
                print(f"  [{exam_date}] OK: {len(cleaned)} chars -> {filename}")
                success += 1

        except Exception as e:
            print(f"  [{exam_date}] ERROR: {e}", file=sys.stderr)
            failed += 1

    print("\n" + "=" * 60)
    print(f"Done! Success: {success}, No transcript section: {no_transcript}, Failed: {failed}")
    print(f"Files saved to: {OUTPUT_DIR}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
