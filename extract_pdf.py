# -*- coding: utf-8 -*-
"""Extract text from the Project Requirements PDF into a UTF-8 text file."""
import sys
from pypdf import PdfReader

src = r"c:/Users/ashok/Downloads/Project_Requirements.pdf"
out = r"c:/Users/ashok/OneDrive/Documents/VSCODE/AI-Prof/project_requirements.txt"

reader = PdfReader(src)
with open(out, "w", encoding="utf-8") as fh:
    fh.write(f"TOTAL_PAGES: {len(reader.pages)}\n")
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        fh.write(f"\n===== PAGE {i + 1} =====\n")
        fh.write(text)
print("done:", out)