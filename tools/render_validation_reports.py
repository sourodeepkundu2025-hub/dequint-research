"""Render every page of the eleven reports and audit page bounds/placeholders."""

import json
from pathlib import Path

from PIL import Image, ImageDraw
import pymupdf


ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / "output/validation_reports"
manifest = json.loads((directory / "report_manifest.json").read_text())
output = directory / "rendered"
output.mkdir(exist_ok=True)
thumbs, checks = [], []
for report in manifest["reports"]:
    with pymupdf.open(ROOT / report["path"]) as pdf:
        for index, page in enumerate(pdf):
            path = output / f"report_{report['number']:02d}_page_{index+1:02d}.png"
            page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25),alpha=False).save(path)
            outside = [word[4] for word in page.get_text("words") if word[0]<0 or word[1]<0
                       or word[2]>page.rect.width+1 or word[3]>page.rect.height+1]
            checks.append({"report":report["number"],"page":index+1,"outside_page_words":outside})
            thumb = Image.open(path).convert("RGB")
            thumb.thumbnail((350,495))
            tile = Image.new("RGB",(370,525),"#e2e7e8")
            tile.paste(thumb,((370-thumb.width)//2,8))
            ImageDraw.Draw(tile).text((12,505),f"Report {report['number']}, page {index+1}",fill="black")
            thumbs.append(tile)
sheet = Image.new("RGB",(4*370,((len(thumbs)+3)//4)*525),"white")
for index,thumb in enumerate(thumbs):
    sheet.paste(thumb,((index%4)*370,(index//4)*525))
sheet.save(output/"contact_sheet.png")
(output/"render_receipt.json").write_text(json.dumps({"report_pages":len(checks),"checks":checks,
    "visual_review":"Requires actual image inspection; no bounds failure is not visual approval"},indent=2),encoding="utf-8")
print(json.dumps({"report_pages":len(checks),"outside_page_words":sum(len(c['outside_page_words']) for c in checks)}))
