
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pngutil import read_rgb, segment_id  # noqa: E402


# ============================================================
# FILE UTILITIES
# ============================================================

def safe_path(root: Path, relative: str) -> Path:
    """Chỉ cho phép đọc file nằm bên trong delivery."""
    root = root.resolve()
    path = (root / str(relative)).resolve()

    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError(f"Path nằm ngoài delivery: {relative}")

    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def iou_xyxy(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:

    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)

    inter = iw * ih

    if inter <= 0:
        return 0.0

    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


# ============================================================
# DETECTION LABEL READER
# ============================================================

def read_yolo_labels(path: Path):
    boxes = []
    invalid_class = False
    bbox_out = False

    if not path.is_file():
        return boxes, invalid_class, bbox_out

    for line in path.read_text(encoding="utf-8").splitlines():

        if not line.strip():
            continue

        parts = line.split()

        if len(parts) < 5:
            bbox_out = True
            continue

        try:
            class_id = int(parts[0])
        except ValueError:
            invalid_class = True
            continue

        if not 0 <= class_id < 80:
            invalid_class = True

        try:
            x, y, w, h = map(float, parts[1:5])
        except ValueError:
            bbox_out = True
            continue

        if not all(math.isfinite(v) for v in (x, y, w, h)):
            bbox_out = True
            continue

        x1 = x - w / 2
        y1 = y - h / 2
        x2 = x + w / 2
        y2 = y + h / 2

        if (
            x1 < -1e-6
            or y1 < -1e-6
            or x2 > 1.0 + 1e-6
            or y2 > 1.0 + 1e-6
            or w <= 0
            or h <= 0
        ):
            bbox_out = True

        boxes.append((class_id, x, y, w, h))

    return boxes, invalid_class, bbox_out


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    ap = argparse.ArgumentParser(
        description="Dataset Release Handover - Rule Validator"
    )

    ap.add_argument("delivery")
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidates", default=None)

    args = ap.parse_args()

    d = Path(args.delivery).resolve()

    if not d.is_dir():
        raise SystemExit(f"Không tìm thấy delivery: {d}")

    # --------------------------------------------------------
    # LOAD DELIVERY METADATA
    # --------------------------------------------------------

    manifest_doc = json.loads(
        (d / "manifest.json").read_text(encoding="utf-8")
    )

    man = manifest_doc["items"]

    metadata_doc = json.loads(
        (d / "metadata.json").read_text(encoding="utf-8")
    )

    meta = {
        m["image"]: m
        for m in metadata_doc["items"]
    }

    with (d / "jobs.csv").open(
        encoding="utf-8",
        newline=""
    ) as f:
        jobs = {
            r["job_id"]: r
            for r in csv.DictReader(f)
        }

    # --------------------------------------------------------
    # LOAD DETECTION CLASSES
    # --------------------------------------------------------

    classes80 = {}

    for line in (d / "classes.txt").read_text(
        encoding="utf-8"
    ).splitlines():

        parts = line.strip().split(maxsplit=1)

        if len(parts) != 2:
            continue

        try:
            classes80[int(parts[0])] = parts[1].strip()
        except ValueError:
            continue

    # --------------------------------------------------------
    # LOAD PANOPTIC INFORMATION
    # --------------------------------------------------------

    pan = json.loads(
        (d / "panoptic.json").read_text(encoding="utf-8")
    )

    pan_cats = {
        c["id"]: c
        for c in pan["categories"]
    }

    pan_anns = {
        Path(a["file_name"]).stem: a["segments_info"]
        for a in pan["annotations"]
    }

    pan_dims = {
        Path(im["file_name"]).stem: (
            int(im["width"]),
            int(im["height"])
        )
        for im in pan.get("images", [])
    }

    # --------------------------------------------------------
    # RESULT CONTAINERS
    # --------------------------------------------------------

    errors: list[dict] = []
    candidates: list[dict] = []

    scenes: dict[str, set[str]] = {}

    # ========================================================
    # PROCESS EACH IMAGE
    # ========================================================

    for stem, item in sorted(man.items()):

        # ----------------------------------------------------
        # 1. METADATA RULES
        # ----------------------------------------------------

        m = meta.get(stem, {})

        if m:

            scene_id = m.get("scene_id")
            split = m.get("split")

            if scene_id is not None:
                scenes.setdefault(
                    str(scene_id), set()
                ).add(str(split))

            job = jobs.get(m.get("job_id"), {})

            if (
                job
                and m.get("guideline_version") != job.get("guideline")
            ):
                errors.append({
                    "type": "guideline_mismatch",
                    "target": stem
                })

        # ----------------------------------------------------
        # 2. FILE PATHS
        # ----------------------------------------------------

        paths = {}

        for key in ("image", "label", "mask"):

            try:
                paths[key] = safe_path(d, item[key])
            except (ValueError, KeyError):
                paths[key] = None

        img_path = paths["image"]
        lbl_path = paths["label"]
        mask_path = paths["mask"]

        # ----------------------------------------------------
        # 3. MISSING IMAGE
        # ----------------------------------------------------

        image_exists = (
            img_path is not None
            and img_path.is_file()
        )

        if not image_exists:
            errors.append({
                "type": "missing_image",
                "target": stem
            })

        # ----------------------------------------------------
        # 4. WRONG SHA256
        # ----------------------------------------------------

        hash_mismatch = False

        hash_fields = {
            "image": "image_sha256",
            "label": "label_sha256",
            "mask": "mask_sha256",
        }

        for key, hash_key in hash_fields.items():

            path = paths[key]
            expected = item.get(hash_key)

            if path is None or not path.is_file():
                continue

            if expected is not None:
                actual = sha256_file(path)

                if actual.lower() != str(expected).lower():
                    hash_mismatch = True

        if hash_mismatch:
            errors.append({
                "type": "wrong_hash",
                "target": stem
            })

        # ----------------------------------------------------
        # 5. DETECTION LABEL RULES
        # ----------------------------------------------------

        if lbl_path is not None and lbl_path.is_file():

            boxes, has_invalid_cls, has_oob = read_yolo_labels(
                lbl_path
            )

        else:
            boxes = []
            has_invalid_cls = False
            has_oob = False

        if has_invalid_cls:
            errors.append({
                "type": "invalid_class",
                "target": stem
            })

        if has_oob:
            errors.append({
                "type": "bbox_out_of_bounds",
                "target": stem
            })

        # ----------------------------------------------------
        # 6. DUPLICATE BOX
        # ----------------------------------------------------

        dup = False

        W0, H0 = pan_dims.get(stem, (0, 0))

        if W0 > 0 and H0 > 0:

            for i in range(len(boxes)):

                for j in range(i + 1, len(boxes)):

                    c1, x1, y1, w1, h1 = boxes[i]
                    c2, x2, y2, w2, h2 = boxes[j]

                    if c1 != c2:
                        continue

                    if min(w1, h1, w2, h2) <= 0:
                        continue

                    same_size = (
                        abs(w1 - w2) * W0 <= 0.5
                        and abs(h1 - h2) * H0 <= 0.5
                    )

                    near_center = (
                        abs(x1 - x2) * W0 <= 2.0
                        and abs(y1 - y2) * H0 <= 2.0
                    )

                    if same_size and near_center:
                        dup = True
                        break

                if dup:
                    break

        if dup:
            errors.append({
                "type": "duplicate_box",
                "target": stem
            })

        # ----------------------------------------------------
        # 7. PANOPTIC CATEGORY ID
        # ----------------------------------------------------

        segs = pan_anns.get(stem, [])

        invalid_category = any(
            s.get("category_id") not in pan_cats
            for s in segs
        )

        if invalid_category:
            errors.append({
                "type": "invalid_category_id",
                "target": stem
            })

        # ----------------------------------------------------
        # READ PANOPTIC MASK
        # ----------------------------------------------------

        if mask_path is None or not mask_path.is_file():
            continue

        try:
            W, H, pixels = read_rgb(mask_path)
        except (OSError, ValueError):
            continue

        # ----------------------------------------------------
        # 8. THING OVERLAP
        # ----------------------------------------------------

        pix_counts: dict[int, int] = {}

        for idx in range(0, len(pixels), 3):

            sid = segment_id(pixels, idx)

            if sid == 0:
                continue

            pix_counts[sid] = (
                pix_counts.get(sid, 0) + 1
            )

        overlap_found = False

        for s in segs:

            cat = pan_cats.get(
                s.get("category_id"), {}
            )

            if cat.get("isthing") != 1:
                continue

            if s.get("iscrowd", 0) != 0:
                continue

            try:
                declared_area = float(s.get("area", 0))
            except (ValueError, TypeError):
                continue

            if declared_area <= 0:
                continue

            actual_area = pix_counts.get(
                s.get("id"), 0
            )

            # area khai báo lớn hơn số pixel thật
            if actual_area < declared_area:
                overlap_found = True
                break

        if overlap_found:
            errors.append({
                "type": "thing_overlap",
                "target": stem
            })

        # ====================================================
        # SEMANTIC CANDIDATES
        # Chỉ chạy khi người dùng truyền --candidates
        # ====================================================

        if not args.candidates:
            continue

        if not image_exists or lbl_path is None or not lbl_path.is_file():
            continue

        # ----------------------------------------------------
        # CONVERT YOLO BOXES TO PIXEL COORDINATES
        # ----------------------------------------------------

        px_boxes = []

        for idx_b, (c, x, y, w, h) in enumerate(boxes):

            if not 0 <= c < 80:
                continue

            if c not in classes80:
                continue

            if w <= 0 or h <= 0:
                continue

            if (
                x - w / 2 < 0
                or y - h / 2 < 0
                or x + w / 2 > 1
                or y + h / 2 > 1
            ):
                continue

            x1 = (x - w / 2) * W
            y1 = (y - h / 2) * H
            x2 = (x + w / 2) * W
            y2 = (y + h / 2) * H

            px_boxes.append({
                "idx": idx_b,
                "class": classes80[c],
                "xyxy": (x1, y1, x2, y2)
            })

        # ----------------------------------------------------
        # COLLECT PANOPTIC THING SEGMENTS
        # ----------------------------------------------------

        thing_segs = []

        for s in segs:

            cat = pan_cats.get(
                s.get("category_id"), {}
            )

            if cat.get("isthing") != 1:
                continue

            if s.get("iscrowd", 0) != 0:
                continue

            if s.get("area", 0) < 150:
                continue

            bbox = s.get("bbox")

            if not isinstance(bbox, list) or len(bbox) != 4:
                continue

            bx, by, bw, bh = map(float, bbox)

            if bw <= 0 or bh <= 0:
                continue

            thing_segs.append({
                "id": s["id"],
                "class": cat["name"],
                "xyxy": (
                    bx,
                    by,
                    bx + bw,
                    by + bh
                ),
                "area": float(s["area"])
            })

        if not px_boxes or not thing_segs:
            continue

        # ----------------------------------------------------
        # MATCH DETECTION BOXES WITH PANOPTIC SEGMENTS
        # ----------------------------------------------------

        matched_seg = set()

        # Một segment xuất hiện trong nhiều box cùng lớp
        # là dấu hiệu có thể đã bị instance_merge.
        segment_box_hits: dict[int, set[int]] = {}

        for b in px_boxes:

            bx1, by1, bx2, by2 = b["xyxy"]

            ix1 = max(0, int(math.floor(bx1)))
            iy1 = max(0, int(math.floor(by1)))
            ix2 = min(W, int(math.ceil(bx2)))
            iy2 = min(H, int(math.ceil(by2)))

            in_counts: dict[int, int] = {}

            for py in range(iy1, iy2):

                row_off = py * W * 3

                for px in range(ix1, ix2):

                    sid = segment_id(
                        pixels,
                        row_off + px * 3
                    )

                    if sid != 0:
                        in_counts[sid] = (
                            in_counts.get(sid, 0) + 1
                        )

            best_s = None
            best_score = 0.0

            for s in thing_segs:

                inter_px = in_counts.get(s["id"], 0)

                if inter_px == 0:
                    continue

                iou = iou_xyxy(
                    b["xyxy"],
                    s["xyxy"]
                )

                cov = inter_px / max(1.0, s["area"])

                score = max(iou, cov * 0.8)

                # Lưu dấu hiệu instance merge
                if (
                    s["class"] == b["class"]
                    and cov >= 0.15
                ):
                    segment_box_hits.setdefault(
                        s["id"], set()
                    ).add(b["idx"])

                if score > best_score:
                    best_score = score
                    best_s = (s, iou, cov)

            if best_s and best_score >= 0.35:

                s, iou, cov = best_s

                matched_seg.add(s["id"])

                # --------------------------------------------
                # CLASS SWAP / CATEGORY SWAP
                # --------------------------------------------

                if b["class"] != s["class"]:

                    candidates.append({
                        "image": stem,
                        "suspect": "class_swap_or_category_swap",
                        "det_class": b["class"],
                        "pan_class": s["class"],
                        "iou": round(iou, 3)
                    })

                # --------------------------------------------
                # BBOX DRIFT
                # --------------------------------------------

                elif iou < 0.55 and cov >= 0.45:

                    candidates.append({
                        "image": stem,
                        "suspect": "bbox_drift",
                        "class": b["class"],
                        "iou": round(iou, 3),
                        "cov": round(cov, 3)
                    })

        # ----------------------------------------------------
        # INSTANCE MERGE
        # Một segment có pixel nằm trong ít nhất 2 box
        # detection cùng lớp.
        # ----------------------------------------------------

        for s in thing_segs:

            hits = segment_box_hits.get(
                s["id"], set()
            )

            if len(hits) >= 2:

                candidates.append({
                    "image": stem,
                    "suspect": "instance_merge",
                    "class": s["class"],
                    "num_boxes": len(hits)
                })

        # ----------------------------------------------------
        # MISSING BOX
        # Segment lớn nhưng không có detection box tương ứng.
        # ----------------------------------------------------

        for s in thing_segs:

            if s["id"] in matched_seg:
                continue

            if s["area"] < 400:
                continue

            overlaps = any(
                iou_xyxy(b["xyxy"], s["xyxy"]) > 0.25
                for b in px_boxes
            )

            if not overlaps:

                candidates.append({
                    "image": stem,
                    "suspect": "missing_box",
                    "class": s["class"],
                    "area": s["area"]
                })

    # ========================================================
    # 9. SCENE LEAK
    # ========================================================

    for scene_id, splits in sorted(scenes.items()):

        if len(splits) > 1:

            errors.append({
                "type": "scene_leak",
                "target": scene_id
            })

    # ========================================================
    # WRITE OUTPUT
    # ========================================================

    errors.sort(
        key=lambda row: (
            row["type"],
            row["target"]
        )
    )

    out_path = Path(args.out)

    out_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    out_path.write_text(
        json.dumps(
            {"errors": errors},
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    if args.candidates:

        cand_path = Path(args.candidates)

        cand_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        cand_path.write_text(
            json.dumps(
                {"candidates": candidates},
                ensure_ascii=False,
                indent=2
            ) + "\n",
            encoding="utf-8"
        )

    print(
        f"Found {len(errors)} rule errors, "
        f"{len(candidates)} semantic candidates."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
