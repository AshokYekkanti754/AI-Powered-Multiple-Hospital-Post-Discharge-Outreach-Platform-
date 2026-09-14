# -*- coding: utf-8 -*-
"""Print specific pages from the raw extraction (one word per line -> joined)."""
import re
import sys

data = open(r"c:/Users/ashok/OneDrive/Documents/VSCODE/AI-Prof/project_requirements.txt", encoding="utf-8").read()
blocks = re.split(r"===== PAGE (\d+) =====", data)
pages = {}
for i in range(1, len(blocks), 2):
    pages[int(blocks[i])] = blocks[i + 1].strip()

lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
hi = int(sys.argv[2]) if len(sys.argv) > 2 else lo
outname = f"pages_{lo}_{hi}.txt"
with open(outname, "w", encoding="utf-8") as fh:
    for num in range(lo, hi + 1):
        if num in pages:
            words = " ".join(pages[num].split())
            fh.write(f"\n===== PAGE {num} =====\n{words}\n")
print("wrote", outname)