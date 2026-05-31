#!/usr/bin/env python3
"""Validate all q_stem files contain correct listening content."""
import re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

base = Path(r"D:\荣荣\CET6_training_camp\CET6-Resources")
issues = []

for exam_dir in sorted(base.iterdir()):
    if not exam_dir.is_dir() or not re.match(r"CET6_\d{4}\.\d{2}$", exam_dir.name):
        continue
    for f in sorted(exam_dir.glob("cet6_*_q_stem.txt")):
        text = f.read_text(encoding="utf-8")
        name = f"{exam_dir.name}/{f.name}"

        has_a = bool(re.search(r"Section\s*A", text, re.IGNORECASE))
        has_b = bool(re.search(r"Section\s*B", text, re.IGNORECASE))
        has_c = bool(re.search(r"Section\s*C", text, re.IGNORECASE))
        has_hear = bool(re.search(r"you will hear", text, re.IGNORECASE))
        has_read = bool(re.search(r"read\s+a\s+passage\s+with\s+ten|there\s+is\s+a\s+passage\s+with\s+ten", text, re.IGNORECASE))
        has_placeholder = bool(re.search(r"不再提供听力|同第一套|同第二套|一致", text))

        q_nums = set()
        for m in re.finditer(r"(?m)(?:^|\n)\s*(\d{1,2})[\.\)]\s*[A-D]\)", text):
            q_nums.add(int(m.group(1)))

        problems = []
        if not has_hear:
            problems.append('no "you will hear"')
        if has_read:
            problems.append("contains reading content!")
        if has_placeholder:
            problems.append("placeholder text")
        if not has_a:
            problems.append("missing Section A")
        if not has_b:
            problems.append("missing Section B")
        if not has_c:
            problems.append("missing Section C")

        q_range = f"Q{min(q_nums)}-{max(q_nums)}" if q_nums else "no Qs found"

        status = "OK" if not problems else "ISSUE"
        line = f"  [{status}] {name} ({len(text)} chars, {q_range})"
        if problems:
            line += f" -- {'; '.join(problems)}"
            issues.append(name)
        print(line)

print(f"\nTotal issues: {len(issues)}")
for i in issues:
    print(f"  {i}")
