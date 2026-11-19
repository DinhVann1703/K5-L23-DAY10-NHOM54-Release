#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from pngutil import read_rgb, segment_id  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iou_xyxy(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("delivery")
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", default=None)
    args = ap.parse_args()

    d = Path(args.delivery)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}

    classes80 = {}
    for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            idx, name = ln.strip().split(" ", 1)
            classes80[int(idx)] = name.strip()

    pan = json.loads((d / "panoptic.json").read_text(encoding="utf-8"))
    pan_cats = {c["id"]: c for c in pan["categories"]}
    pan_anns = {Path(a["file_name"]).stem: a["segments_info"] for a in pan["annotations"]}

    errors: list[dict[str, str]] = []
    candidates: list[dict] = []
    scenes: dict[str, set[str]] = {}

    for stem, it in sorted(man.items()):
        m = meta.get(stem, {})
        if m:
            scenes.setdefault(m["scene_id"], set()).add(m["split"])
            job = jobs.get(m["job_id"], {})
            if job and m.get("guideline_version") != job.get("guideline"):
                errors.append({"type": "guideline_mismatch", "target": stem})

        img_path = d / it["image"]
        if not img_path.is_file():
            errors.append({"type": "missing_image", "target": stem})
            continue
        if sha256_file(img_path) != it["image_sha256"]:
            errors.append({"type": "wrong_hash", "target": stem})

        lbl_path = d / it["label"]
        boxes = []
        has_invalid_cls = False
        has_oob = False
        if lbl_path.is_file():
            for ln in lbl_path.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                parts = ln.split()
                c = int(float(parts[0]))
                x, y, w, h = map(float, parts[1:5])
                if not (0 <= c < 80):
                    has_invalid_cls = True
                if x - w / 2 < -0.01 or y - h / 2 < -0.01 or x + w / 2 > 1.01 or y + h / 2 > 1.01 or w <= 0 or h <= 0:
                    has_oob = True
                boxes.append((c, x, y, w, h))

        if has_invalid_cls:
            errors.append({"type": "invalid_class", "target": stem})
        if has_oob:
            errors.append({"type": "bbox_out_of_bounds", "target": stem})

        dup = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                c1, x1, y1, w1, h1 = boxes[i]
                c2, x2, y2, w2, h2 = boxes[j]
                if c1 == c2 and abs(x1 - x2) < 0.012 and abs(y1 - y2) < 0.012 and abs(w1 - w2) < 0.015 and abs(h1 - h2) < 0.015:
                    dup = True
                    break
            if dup:
                break
        if dup:
            errors.append({"type": "duplicate_box", "target": stem})

        segs = pan_anns.get(stem, [])
        if any(s["category_id"] not in pan_cats for s in segs):
            errors.append({"type": "invalid_category_id", "target": stem})

        mask_path = d / it["mask"]
        if not mask_path.is_file():
            continue
        W, H, pixels = read_rgb(mask_path)

        pix_counts: dict[int, int] = {}
        for idx in range(0, len(pixels), 3):
            sid = segment_id(pixels, idx)
            if sid != 0:
                pix_counts[sid] = pix_counts.get(sid, 0) + 1

        overlap_found = False
        for s in segs:
            cat = pan_cats.get(s["category_id"], {})
            if cat.get("isthing") == 1 and s.get("iscrowd", 0) == 0 and s["area"] > 100:
                actual = pix_counts.get(s["id"], 0)
                if actual < 0.65 * s["area"]:
                    overlap_found = True
                    break
        if overlap_found:
            errors.append({"type": "thing_overlap", "target": stem})

        if has_invalid_cls or has_oob:
            continue

        px_boxes = []
        for idx_b, (c, x, y, w, h) in enumerate(boxes):
            x1 = max(0.0, (x - w / 2) * W)
            y1 = max(0.0, (y - h / 2) * H)
            x2 = min(float(W), (x + w / 2) * W)
            y2 = min(float(H), (y + h / 2) * H)
            px_boxes.append({"idx": idx_b, "class": classes80.get(c, str(c)), "xyxy": (x1, y1, x2, y2)})

        thing_segs = []
        for s in segs:
            cat = pan_cats.get(s["category_id"], {})
            if cat.get("isthing") == 1 and s.get("iscrowd", 0) == 0 and s["area"] >= 150:
                bx, by, bw, bh = s["bbox"]
                thing_segs.append({
                    "id": s["id"],
                    "class": cat["name"],
                    "xyxy": (float(bx), float(by), float(bx + bw), float(by + bh)),
                    "area": s["area"],
                })

        matched_seg = set()
        for b in px_boxes:
            bx1, by1, bx2, by2 = int(b["xyxy"][0]), int(b["xyxy"][1]), int(b["xyxy"][2]), int(b["xyxy"][3])
            in_counts: dict[int, int] = {}
            for py in range(max(0, by1), min(H, by2)):
                row_off = py * W * 3
                for px in range(max(0, bx1), min(W, bx2)):
                    sid = segment_id(pixels, row_off + px * 3)
                    if sid != 0:
                        in_counts[sid] = in_counts.get(sid, 0) + 1

            best_s = None
            best_score = 0.0
            for s in thing_segs:
                inter_px = in_counts.get(s["id"], 0)
                if inter_px == 0:
                    continue
                iou = iou_xyxy(b["xyxy"], s["xyxy"])
                cov = inter_px / max(1, s["area"])
                sc = max(iou, cov * 0.8)
                if sc > best_score:
                    best_score = sc
                    best_s = (s, iou, cov)

            if best_s and best_score >= 0.35:
                s, iou, cov = best_s
                matched_seg.add(s["id"])
                if b["class"] != s["class"]:
                    candidates.append({
                        "image": stem,
                        "suspect": "class_swap_or_category_swap",
                        "det_class": b["class"],
                        "pan_class": s["class"],
                        "iou": round(iou, 3),
                    })
                elif iou < 0.55 and cov >= 0.45:
                    candidates.append({
                        "image": stem,
                        "suspect": "bbox_drift",
                        "class": b["class"],
                        "iou": round(iou, 3),
                        "cov": round(cov, 3),
                    })

        for b in px_boxes:
            covered = []
            for s in thing_segs:
                if s["class"] == b["class"] and iou_xyxy(b["xyxy"], s["xyxy"]) > 0.15:
                    sx1, sy1, sx2, sy2 = s["xyxy"]
                    bx1, by1, bx2, by2 = b["xyxy"]
                    if sx1 >= bx1 - 5 and sy1 >= by1 - 5 and sx2 <= bx2 + 5 and sy2 <= by2 + 5:
                        covered.append(s)
            if len(covered) >= 2:
                candidates.append({
                    "image": stem,
                    "suspect": "instance_merge",
                    "class": b["class"],
                    "num_segments": len(covered),
                })

        for s in thing_segs:
            if s["id"] not in matched_seg and s["area"] >= 400:
                if not any(iou_xyxy(b["xyxy"], s["xyxy"]) > 0.25 for b in px_boxes):
                    candidates.append({
                        "image": stem,
                        "suspect": "missing_box",
                        "class": s["class"],
                        "area": s["area"],
                    })

    for sc, splits in sorted(scenes.items()):
        if len(splits) > 1:
            errors.append({"type": "scene_leak", "target": sc})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.candidates:
        cand_path = Path(args.candidates)
        cand_path.parent.mkdir(parents=True, exist_ok=True)
        cand_path.write_text(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Found {len(errors)} rule errors, {len(candidates)} semantic candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
