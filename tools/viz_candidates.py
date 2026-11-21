from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw

def load_classes(classes_path: Path) -> list[str]:
    return [line.strip() for line in classes_path.read_text(encoding="utf-8").splitlines() if line.strip()]

def find_image(images_dir: Path, img_id: str) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = images_dir / f"{img_id}{ext}"
        if p.exists():
            return p
    return None

def draw_yolo_boxes(img: Image.Image, label_path: Path, classes: list[str]) -> Image.Image:
    out = img.copy().convert("RGB")
    draw = ImageDraw.Draw(out)
    w, h = out.size
    if not label_path.exists():
        draw.text((10, 10), "NO LABEL TXT", fill=(255, 80, 80))
        return out
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        cid = int(float(parts[0]))
        cx, cy, bw, bh = map(float, parts[1:5])
        x1 = (cx - bw / 2.0) * w
        y1 = (cy - bh / 2.0) * h
        x2 = (cx + bw / 2.0) * w
        y2 = (cy + bh / 2.0) * h
        cname = classes[cid] if 0 <= cid < len(classes) else f"id:{cid}"
        draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 120), width=3)
        draw.rectangle([x1, max(0, y1 - 18), x1 + max(60, len(cname) * 7 + 8), y1], fill=(0, 255, 120))
        draw.text((x1 + 4, max(0, y1 - 16)), cname, fill=(0, 0, 0))
    return out

def draw_panoptic(img: Image.Image, masks_dir: Path, pan_ann: dict | None, cat_map: dict[int, str], img_id: str) -> Image.Image:
    base = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    summary_lines = []
    mask_path = None
    if pan_ann and pan_ann.get("file_name"):
        cand = masks_dir / pan_ann["file_name"]
        if cand.exists():
            mask_path = cand
    if mask_path is None:
        for ext in (".png", ".jpg"):
            p = masks_dir / f"{img_id}{ext}"
            if p.exists():
                mask_path = p
                break
    if mask_path and pan_ann:
        m_img = Image.open(mask_path).convert("RGB")
        if m_img.size != base.size:
            m_img = m_img.resize(base.size, Image.Resampling.NEAREST)
        px = m_img.load()
        ov_px = overlay.load()
        segs = pan_ann.get("segments_info", [])
        color_to_seg = {}
        for idx, seg in enumerate(segs):
            rgb = seg.get("id")
            if isinstance(rgb, int):
                r = rgb & 255
                g = (rgb >> 8) & 255
                b = (rgb >> 16) & 255
            else:
                r, g, b = 128, 128, 128
            color_to_seg[(r, g, b)] = (seg, idx)
            cid = seg.get("category_id")
            cname = cat_map.get(cid, f"cat:{cid}")
            area = seg.get("area", "?")
            summary_lines.append(f"{cname} (area={area})")
        w, h = base.size
        for y in range(h):
            for x in range(w):
                c = px[x, y]
                if c in color_to_seg:
                    _, idx = color_to_seg[c]
                    col = ((idx * 73 + 50) % 220 + 30, (idx * 137 + 90) % 220 + 30, (idx * 211 + 30) % 220 + 30, 110)
                    ov_px[x, y] = col
    composed = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(composed)
    y_txt = 8
    for line in summary_lines[:10]:
        draw.text((10, y_txt), line, fill=(255, 255, 0))
        y_txt += 14
    return composed

def main() -> int:
    run_dir = Path("runs/r54007")
    delivery = run_dir / "delivery"
    classes = load_classes(delivery / "classes.txt")
    pan = json.loads((delivery / "panoptic.json").read_text(encoding="utf-8"))
    cat_map = {c["id"]: c["name"] for c in pan.get("categories", [])}
    file_to_id = {}
    for im in pan.get("images", []):
        stem = Path(im.get("file_name", "")).stem
        if stem:
            file_to_id[stem] = im.get("id")
    ann_by_img_id = {a.get("image_id"): a for a in pan.get("annotations", [])}

    cands = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8")).get("candidates", [])
    target_ids = sorted({x["image"] for x in cands if x.get("suspect") in ("class_swap_or_category_swap", "bbox_drift")})

    out_dir = run_dir / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for img_id in target_ids:
        img_path = find_image(delivery / "images", img_id)
        if not img_path:
            continue
        raw = Image.open(img_path)
        left = draw_yolo_boxes(raw, delivery / "labels" / f"{img_id}.txt", classes)
        pan_id = file_to_id.get(img_id)
        right = draw_panoptic(raw, delivery / "masks", ann_by_img_id.get(pan_id), cat_map, img_id)
        pair = Image.new("RGB", (left.width + right.width, max(left.height, right.height)))
        pair.paste(left, (0, 0))
        pair.paste(right, (left.width, 0))
        pair.save(out_dir / f"{img_id}.png")
        saved += 1
    print(f"Saved {saved} preview images to {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
