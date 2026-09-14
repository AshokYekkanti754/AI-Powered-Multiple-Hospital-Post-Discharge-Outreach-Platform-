# -*- coding: utf-8 -*-
"""Reflow the one-word-per-line extraction into readable paragraphs per page."""
import re

src = r"c:/Users/ashok/OneDrive/Documents/VSCODE/AI-Prof/project_requirements.txt"
out = r"c:/Users/ashok/OneDrive/Documents/VSCODE/AI-Prof/project_requirements_reflowed.txt"

pages = {}
current = None
buf = []
with open(src, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        m = re.match(r"===== PAGE (\d+) =====", line)
        if m:
            if current is not None:
                pages[current] = " ".join(buf)
            current = int(m.group(1))
            buf = []
        elif current is not None:
            buf.append(line.strip())
    if current is not None:
        pages[current] = " ".join(buf)

with open(out, "w", encoding="utf-8") as fh:
    for num in sorted(pages):
        fh.write(f"\n===== PAGE {num} =====\n")
        fh.write(pages[num])
        fh.write("\n")
print("pages:", len(pages))