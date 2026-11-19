#!/usr/bin/env python3
import json
from pathlib import Path
from PIL import Image, ImageDraw

d = Path("delivery")
cands = json.loads(Path("submission/de_an/candidates.json").read_text(encoding="utf-8"))["candidates"]
classes80 = dict(ln.strip().split(" ", 1) for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip())
classes80 = {int(k): v.strip() for k, v in classes80.items()}
pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
pan_cats = {c["id"]: c["name"] for c in pan["categories"]}
pan_anns = {Path(a["file_name"]).stem: a["segments_info"] for a in pan["annotations"]}

out_dir = Path("runs/de_an_preview")
out_dir.mkdir(parents=True, exist_ok=True)

stems = sorted({c["image"] for c in cands})
for stem in stems:
    img_p = d / "images" / f"{stem}.jpg"
    if not img_p.is_file():
        continue
    im = Image.open(img_p).convert("RGB")
    W, H = im.size
    draw = ImageDraw.Draw(im)
    for s in pan_anns.get(stem, []):
        bx, by, bw, bh = s["bbox"]
        cname = pan_cats.get(s["category_id"], "?")
        draw.rectangle([bx, by, bx + bw, by + bh], outline="lime", width=2)
        draw.text((bx + 2, max(0, by - 12)), f"PAN:{cname}", fill="lime")
    lbl_p = d / "labels" / f"{stem}.txt"
    if lbl_p.is_file():
        for ln in lbl_p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            c, x, y, w, h = map(float, ln.split()[:5])
            x1, y1, x2, y2 = (x - w/2)*W, (y - h/2)*H, (x + w/2)*W, (y + h/2)*H
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            draw.text((x1 + 2, y1 + 2), f"DET:{classes80.get(int(c), '?')}", fill="red")
    im.save(out_dir / f"{stem}.jpg")

print(f"Da ve {len(stems)} anh ung vien tai: {out_dir}")
