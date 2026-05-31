#!/usr/bin/env python3
"""
Extract listening answers (and explanations) from CET-6 解析/答案 PDFs.
Output: cet6_YYYY.MM[_setN]_q_answer.txt
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = r"C:\Users\aaron\.tessdata"


def fullwidth_to_halfwidth(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif ch == '　':
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result)


def is_readable_text(text: str) -> bool:
    """Check if extracted text is readable (not garbled font encoding)."""
    if len(text) < 200:
        return False
    sample = text[:2000]
    cjk_count = sum(1 for c in sample if '一' <= c <= '鿿')
    ascii_count = sum(1 for c in sample if 'A' <= c <= 'z')
    return (cjk_count + ascii_count) > len(sample) * 0.15


def get_text_pdftotext(pdf_path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, timeout=30, text=True,
            encoding="utf-8", errors="replace"
        )
        if result.returncode == 0 and is_readable_text(result.stdout):
            return result.stdout
    except Exception:
        pass
    return ""


def get_text_ocr(pdf_path: Path, max_pages: int = 15) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        png_root = os.path.join(tmpdir, "page")
        try:
            subprocess.run(
                ["pdftopng", "-r", "250", str(pdf_path), png_root],
                capture_output=True, timeout=180
            )
        except Exception:
            return ""

        pngs = sorted(Path(tmpdir).glob("page-*.png"))[:max_pages]
        if not pngs:
            return ""

        full_text = ""
        for png in pngs:
            try:
                result = subprocess.run(
                    [TESSERACT, str(png), "stdout",
                     "--tessdata-dir", TESSDATA_DIR,
                     "-l", "chi_sim+eng", "--psm", "6"],
                    capture_output=True, timeout=90,
                    text=True, encoding="utf-8", errors="replace"
                )
                if result.returncode == 0:
                    full_text += result.stdout + "\n"
            except Exception:
                continue
            # Early exit if we found enough answers
            answers = extract_compact_answers(full_text)
            if len(answers) >= 25:
                break
        return full_text


def extract_compact_answers(text: str) -> dict[int, str]:
    """Extract answers from compact key like '1.B 2.A 3.C ...' or '１．Ｂ ２．Ａ'."""
    text_hw = fullwidth_to_halfwidth(text)
    answers = {}
    for m in re.finditer(r'(\d{1,2})\s*[\.．]\s*([A-D])\b', text_hw):
        qnum = int(m.group(1))
        if 1 <= qnum <= 25:
            answers[qnum] = m.group(2)
    return answers


def extract_detailed_answers(text: str) -> dict[int, dict]:
    """Extract per-question answers and explanations from 答案详解 sections."""
    text_hw = fullwidth_to_halfwidth(text)
    results = {}

    answer_indicators = [
        r'答\s*案\s*[：:.]?\s*(?:为\s*)?([A-D])\s*[)）]?',
        r'([A-D])\s*[)）]?\s*项\s*(?:与|为|是).*?(?:相符|正确)',
        r'故\s*([A-D])\s*项',
        r'(?:选|正\s*确\s*答\s*案\s*[为是]?)\s*([A-D])\s*[)）]?',
        r'由\s*此\s*可\s*知\s*,?\s*([A-D])',
        r'因\s*此\s*,?\s*答?\s*案?\s*[为是]?\s*([A-D])\s*[)）]?',
        r'选\s*项\s*([A-D])\s*[)）]?\s*(?:正确|为正确|是.*?正确)',
        r'故\s*选\s*项\s*([A-D])\s*正确',
        r'故\s*答\s*案\s*为\s*([A-D])\s*[)）]?',
    ]

    # First pass: line-by-line extraction
    lines = text_hw.split('\n')
    current_q = None
    current_answer = None
    current_explanation = []
    in_explanation = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        m = re.match(r'\s*(\d{1,2})\s*[.:)]\s*\S', line)
        if m:
            qnum = int(m.group(1))
            if 1 <= qnum <= 25:
                if current_q and current_answer:
                    results[current_q] = {
                        'answer': current_answer,
                        'explanation': '\n'.join(current_explanation).strip()
                    }
                current_q = qnum
                current_answer = None
                current_explanation = []
                in_explanation = False
                for pat in answer_indicators:
                    ans_match = re.search(pat, line)
                    if ans_match:
                        current_answer = ans_match.group(1)
                        break
                continue

        if current_q and not current_answer:
            for pat in answer_indicators:
                ans_match = re.search(pat, stripped)
                if ans_match:
                    current_answer = ans_match.group(1)
                    in_explanation = True
                    break
            if current_answer:
                continue

        ans_match = re.match(r'\s*答案\s*[：:.]?\s*([A-D])', stripped)
        if ans_match and current_q:
            current_answer = ans_match.group(1)
            in_explanation = False
            continue

        exp_match = re.match(r'\s*(?:详解|解析|解)\s*[：:.]?\s*(.*)', stripped)
        if exp_match and current_q:
            exp_text = exp_match.group(1).strip()
            if exp_text:
                current_explanation.append(exp_text)
            in_explanation = True
            continue

        if in_explanation and current_q and stripped:
            if not re.match(r'\d{1,2}\s*[.:)]', stripped):
                if not re.match(r'答案\s*[：:]', stripped):
                    current_explanation.append(stripped)

    if current_q and current_answer:
        results[current_q] = {
            'answer': current_answer,
            'explanation': '\n'.join(current_explanation).strip()
        }

    # Second pass: block-based search for missed questions
    # Join text into blocks between question numbers
    q_positions = []
    for m in re.finditer(r'(?:^|\n)\s*(\d{1,2})\s*[.:)]\s*\S', text_hw):
        qnum = int(m.group(1))
        if 1 <= qnum <= 25:
            q_positions.append((qnum, m.start()))

    for idx, (qnum, start) in enumerate(q_positions):
        if qnum in results:
            continue
        end = q_positions[idx + 1][1] if idx + 1 < len(q_positions) else start + 2000
        block = text_hw[start:end].replace('\n', ' ')
        for pat in answer_indicators:
            ans_match = re.search(pat, block)
            if ans_match:
                results[qnum] = {
                    'answer': ans_match.group(1),
                    'explanation': ''
                }
                break

    return results


def find_listening_section(text: str) -> str:
    """Extract only the listening-related portion of the text."""
    text_hw = fullwidth_to_halfwidth(text)

    # Find Part II / Listening section start
    start_patterns = [
        r'Part\s*(II|Ⅱ|Il)\s*.*?Listening',
        r'听力\s*(理解|部分|原文|答案)',
        r'Section\s*A\s*\n',
        r'Conversation\s*(One|1)',
    ]
    start_idx = 0
    for pat in start_patterns:
        m = re.search(pat, text_hw, re.IGNORECASE)
        if m:
            start_idx = m.start()
            break

    # Find Part III / Reading section start (end boundary)
    end_patterns = [
        r'Part\s*(III|Ⅲ|Il1|IIl)\s*.*?Reading',
        r'Part\s*(III|Ⅲ)\s*',
        r'阅读\s*(理解|部分)',
        r'Section\s*A\s*.*?(?:passage|blanks|reading)',
    ]
    end_idx = len(text_hw)
    for pat in end_patterns:
        m = re.search(pat, text_hw[start_idx + 100:], re.IGNORECASE)
        if m:
            end_idx = start_idx + 100 + m.start()
            break

    return text[start_idx:end_idx]


def extract_listening_answers(text: str) -> tuple[dict[int, str], dict[int, dict]]:
    """
    Extract listening answers (Q1-25) from full PDF text.
    Returns (compact_answers, detailed_answers).
    """
    # First try compact answer key (most reliable)
    compact = extract_compact_answers(text)
    listening_compact = {k: v for k, v in compact.items() if 1 <= k <= 25}

    # Try to get detailed answers from listening section
    listening_text = find_listening_section(text)
    detailed = extract_detailed_answers(listening_text)

    # If compact didn't find enough, try from full text with Q1-25 filter
    if len(listening_compact) < 20:
        all_compact = extract_compact_answers(text)
        for k, v in all_compact.items():
            if 1 <= k <= 25 and k not in listening_compact:
                listening_compact[k] = v

    # Fallback: sequential extraction from listening section
    # Find all "答案为X" patterns in order and assign to Q1-25
    total = max(len(listening_compact), len(detailed))
    if total < 15:
        seq = extract_sequential_answers(listening_text)
        if len(seq) > total:
            # Use sequential results to fill gaps
            for k, v in seq.items():
                if k not in listening_compact:
                    listening_compact[k] = v

    return listening_compact, detailed


def extract_sequential_answers(text: str) -> dict[int, str]:
    """
    Find all answer indicators sequentially in text and assign to Q1-25.
    Handles OCR text where question numbers are unreliable but answers appear in order.
    """
    text_hw = fullwidth_to_halfwidth(text)

    answer_pats = [
        r'答\s*案\s*[：:.]?\s*(?:为\s*)?([A-D])\s*[)）]?',
        r'因\s*此\s*,?\s*答?\s*案?\s*[为是]?\s*([A-D])\s*[)）]?',
        r'故\s*答\s*案\s*为\s*([A-D])\s*[)）]?',
        r'([A-D])\s*[)）]?\s*项\s*与.*?相\s*符',
    ]

    # Combine into one pattern
    combined = '|'.join(f'(?:{p})' for p in answer_pats)
    answers = {}
    q_num = 1

    for m in re.finditer(combined, text_hw):
        # Get the matched letter from whichever group matched
        letter = None
        for g in m.groups():
            if g and len(g) == 1 and g in 'ABCD':
                letter = g
                break
        if letter and q_num <= 25:
            answers[q_num] = letter
            q_num += 1

    return answers


def format_output(compact: dict[int, str], detailed: dict[int, dict]) -> str:
    """Format the extracted answers into readable output."""
    lines = []
    lines.append("CET-6 Listening Answers (Q1-25)")
    lines.append("=" * 40)
    lines.append("")

    # Compact answer key
    lines.append("Answer Key:")
    for i in range(1, 26):
        ans = compact.get(i) or detailed.get(i, {}).get('answer', '?')
        lines.append(f"  {i:2d}. {ans}")
    lines.append("")

    # Detailed explanations if available
    if detailed:
        lines.append("Explanations:")
        lines.append("-" * 40)
        for i in range(1, 26):
            if i in detailed:
                d = detailed[i]
                ans = d.get('answer', compact.get(i, '?'))
                exp = d.get('explanation', '')
                lines.append(f"{i}. [{ans}]")
                if exp:
                    for exp_line in exp.split('\n'):
                        lines.append(f"   {exp_line}")
                lines.append("")

    return '\n'.join(lines).strip()


def detect_set_number(filename: str) -> list[int]:
    """Detect set number(s) from PDF filename. Returns list of set numbers."""
    chinese_nums = {'一': 1, '二': 2, '三': 3, '1': 1, '2': 2, '3': 3}

    # Combined sets: "第2、3套"
    m = re.search(r'第(\d)[、,](\d)套', filename)
    if m:
        return [int(m.group(1)), int(m.group(2))]

    # "全N套" (all sets combined)
    m = re.search(r'全(\d)套', filename)
    if m:
        return list(range(1, int(m.group(1)) + 1))

    # "第N套" with Arabic numeral
    m = re.search(r'第\s*(\d)\s*套', filename)
    if m:
        return [int(m.group(1))]

    # "第X套" with Chinese numeral
    m = re.search(r'第([一二三])套', filename)
    if m:
        return [chinese_nums[m.group(1)]]

    # "（卷N）" pattern
    m = re.search(r'[（(]卷([一二三1-3])[)）]', filename)
    if m:
        ch = m.group(1)
        return [chinese_nums.get(ch, int(ch) if ch.isdigit() else 1)]

    # "（第N套）"
    m = re.search(r'[（(]第\s*(\d)\s*套[)）]', filename)
    if m:
        return [int(m.group(1))]

    # "setN" or "_N_" in filename
    m = re.search(r'set(\d)', filename)
    if m:
        return [int(m.group(1))]

    # Single set (no number found)
    return [1]


def get_exam_date(dir_name: str) -> str:
    """Extract YYYY.MM from directory name like CET6_2024.06."""
    m = re.match(r'CET6_(\d{4}\.\d{2})', dir_name)
    return m.group(1) if m else ""


def is_answer_pdf(filename: str) -> bool:
    """Check if a PDF is an answer/explanation file."""
    return bool(re.search(r'解析|答案|详解', filename))


def count_sets_in_dir(exam_dir: Path) -> int:
    """Count how many distinct sets exist in a directory based on q_stem or audio files."""
    stems = list(exam_dir.glob("cet6_*_q_stem.txt"))
    set_nums = set()
    for s in stems:
        m = re.search(r'set(\d)', s.name)
        if m:
            set_nums.add(int(m.group(1)))
    if set_nums:
        return len(set_nums)
    # Fallback: check audio files
    audios = list(exam_dir.glob("CET6_*_listening.*"))
    for a in audios:
        m = re.search(r'set(\d)', a.name)
        if m:
            set_nums.add(int(m.group(1)))
    return max(len(set_nums), 1)


def main():
    print("Extracting listening answers from 解析/答案 PDFs")
    print("=" * 60)

    results = []
    errors = []

    for exam_dir in sorted(BASE_DIR.iterdir()):
        if not exam_dir.is_dir():
            continue
        if not re.match(r"CET6_\d{4}\.\d{2}$", exam_dir.name):
            continue

        date = get_exam_date(exam_dir.name)
        if not date:
            continue

        # Find answer PDFs
        answer_pdfs = [
            f for f in sorted(exam_dir.glob("*.pdf"))
            if is_answer_pdf(f.name)
        ]

        if not answer_pdfs:
            print(f"  [{exam_dir.name}] No answer PDFs found")
            continue

        num_sets = count_sets_in_dir(exam_dir)

        for pdf in answer_pdfs:
            set_numbers = detect_set_number(pdf.name)

            # Check if output already exists and is good
            all_exist = True
            for set_num in set_numbers:
                if num_sets > 1:
                    out_name = f"cet6_{date}_set{set_num}_q_answer.txt"
                else:
                    out_name = f"cet6_{date}_q_answer.txt"
                out_path = exam_dir / out_name
                if not out_path.exists():
                    all_exist = False
                    break
            if all_exist:
                print(f"  [{exam_dir.name}] Skip (exists): {pdf.name}")
                continue

            print(f"  [{exam_dir.name}] Processing: {pdf.name} (sets: {set_numbers})")

            # Get text
            text = get_text_pdftotext(pdf)
            method = "pdftotext"
            if not text:
                print(f"    -> Scanned PDF, using OCR...")
                text = get_text_ocr(pdf)
                method = "OCR"
            else:
                # Verify pdftotext actually has useful content
                test_compact, test_detailed = extract_listening_answers(text)
                test_total = len(test_compact) if test_compact else len(test_detailed)
                if test_total < 5:
                    print(f"    -> pdftotext found {test_total} answers, trying OCR...")
                    ocr_text = get_text_ocr(pdf)
                    if ocr_text:
                        ocr_compact, _ = extract_listening_answers(ocr_text)
                        if len(ocr_compact) > test_total:
                            text = ocr_text
                            method = "OCR"

            if not text or len(text) < 100:
                errors.append(f"{exam_dir.name}/{pdf.name}: no text extracted")
                print(f"    -> ERROR: Could not extract text")
                continue

            # Extract answers
            compact, detailed = extract_listening_answers(text)
            total_found = len(compact) if compact else len(detailed)

            if total_found < 10:
                errors.append(
                    f"{exam_dir.name}/{pdf.name}: only {total_found} answers found"
                )
                print(f"    -> WARNING: Only {total_found}/25 answers found ({method})")

            # Generate output for each set
            for set_num in set_numbers:
                if num_sets > 1:
                    out_name = f"cet6_{date}_set{set_num}_q_answer.txt"
                else:
                    out_name = f"cet6_{date}_q_answer.txt"

                out_path = exam_dir / out_name
                output = format_output(compact, detailed)
                out_path.write_text(output, encoding="utf-8")
                results.append(f"{exam_dir.name}/{out_name}")
                print(f"    -> Saved: {out_name} ({total_found}/25 answers, {method})")

    print("\n" + "=" * 60)
    print(f"Total files created: {len(results)}")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    main()
