#!/usr/bin/env python3
from pathlib import Path
import shutil

from PyPDF2 import PdfReader, PdfWriter

in_path = Path("Sample_Inputs/Marketing/Airbnb_Pitch_Example.pdf")
if not in_path.exists():
    print("Input file not found:", in_path)
    raise SystemExit(1)

tmp_out = in_path.with_name(in_path.stem + "_rotated.tmp.pdf")
reader = PdfReader(str(in_path))
writer = PdfWriter()

for page in reader.pages:
    # try counter-clockwise rotate first, fall back to clockwise 270
    try:
        page.rotate_counter_clockwise(90)
    except Exception:
        try:
            page.rotate_clockwise(270)
        except Exception:
            pass
    writer.add_page(page)

with open(tmp_out, "wb") as f:
    writer.write(f)

# replace original
shutil.move(str(tmp_out), str(in_path))
print("Rotated and overwrote:", in_path)
