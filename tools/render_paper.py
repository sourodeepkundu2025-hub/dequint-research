"""Render the compiled manuscript and retain a basic text/bounds inspection receipt."""

import json
from pathlib import Path
import re

import pymupdf as fitz
from PIL import Image, ImageDraw


root = Path(__file__).resolve().parents[1]
pdf = root / "manuscript" / "main.pdf"
output = root / "manuscript" / "rendered"
output.mkdir(exist_ok=True)
document = fitz.open(pdf)
records, thumbnails = [], []
for index, page in enumerate(document):
    pixels = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    target = output / f"page_{index+1:02d}.png"
    pixels.save(target)
    text = page.get_text()
    outside = [word[4] for word in page.get_text("words") if word[0] < -1 or word[1] < -1
               or word[2] > page.rect.width + 1 or word[3] > page.rect.height + 1]
    records.append({"page": index + 1, "characters": len(text), "outside_page_words": outside,
                    "unresolved_markers": re.findall(r"\b(?:TBD|TODO|NaN)\b|\?\?", text)})
    thumb = Image.open(target).convert("RGB")
    thumb.thumbnail((450, 600))
    sheet = Image.new("RGB", (470, 630), "#dce0e2")
    sheet.paste(thumb, ((470-thumb.width)//2, 20))
    ImageDraw.Draw(sheet).text((15, 608), f"Page {index+1}", fill="black")
    thumbnails.append(sheet)
contact = Image.new("RGB", (1410, 630*((len(thumbnails)+2)//3)), "white")
for index, thumb in enumerate(thumbnails):
    contact.paste(thumb, ((index % 3)*470, (index//3)*630))
contact.save(output / "contact_sheet.png")
receipt = {"pages": len(document), "page_checks": records,
           "visual_review": "Requires inspection of rendered pages; bounds checks alone are insufficient"}
(output / "render_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
