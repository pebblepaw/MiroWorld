#!/usr/bin/env python3
from pathlib import Path
import textwrap
import pdfplumber

IN = Path("Sample_Inputs/Marketing/Airbnb_Pitch_Example.pdf")
OUT = Path("Sample_Inputs/Marketing/Airbnb_Pitch_Example.md")

if not IN.exists():
    print("Input PDF not found:", IN)
    raise SystemExit(1)

with pdfplumber.open(IN) as pdf, OUT.open("w", encoding="utf-8") as out:
    out.write(f"# {IN.name}\n\n")
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if not text:
            continue
        # Split into paragraph blocks by double-newline if present
        blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
        out.write(f"## Page {i+1}\n\n")
        for blk in blocks:
            # join wrapped lines within a block and reflow
            joined = ' '.join([ln.strip() for ln in blk.splitlines() if ln.strip()])
            para = textwrap.fill(joined, width=100)
            out.write(para + "\n\n")

print("Written cleaned Markdown to:", OUT)
