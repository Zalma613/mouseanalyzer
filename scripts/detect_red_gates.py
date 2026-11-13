#!/usr/bin/env python3
"""Piros kapujelölők (függőleges piros vonalak a létra két szélén) automatikus felismerése.

Használat: python3 scripts/detect_red_gates.py VIDEO_MAPPA [--debug-dir DIR] [--json OUT.json]

Videónként N képkocka mediánjából (kéz/egér kiszűrve) piros-dominancia térképet számol
(R - max(G, B)), majd a bal és jobb képszél-sávban megkeresi a legerősebb függőleges piros oszlopot.
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

VIDEO_EXTS = (".mov", ".mp4", ".avi", ".mkv", ".m4v")


def median_frame(path, n=15):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for idx in np.linspace(0, max(1, total - 2), n, dtype=int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, fr = cap.read()
        if ok and fr is not None:
            frames.append(fr)
    cap.release()
    if not frames:
        return None
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def detect_gates(frame, ladder_y=None, side_frac=0.2):
    """Visszaad: dict(left_x, right_x, left_score, right_score, y_range)."""
    h, w = frame.shape[:2]
    f = frame.astype(np.int16)
    b, g, r = f[:, :, 0], f[:, :, 1], f[:, :, 2]
    redness = np.clip(r - np.maximum(g, b), 0, 255).astype(np.float32)
    redness[redness < 12] = 0  # zaj
    # Csak a létra fölötti / körüli sáv (ahol a papírcsíkon a jelölő van)
    y1 = int(h * 0.15)
    y2 = int(min(h, (ladder_y + 40) if ladder_y else h * 0.75))
    band = redness[y1:y2]
    col = band.sum(axis=0)
    col = np.convolve(col, np.ones(5) / 5, mode="same")
    sw = int(w * side_frac)
    lx = int(np.argmax(col[:sw]))
    rx = int(w - sw + np.argmax(col[w - sw:]))
    res = {"left_x": lx, "right_x": rx,
           "left_score": float(col[lx]), "right_score": float(col[rx]),
           "y_range": [y1, y2]}
    for side, x in (("left", lx), ("right", rx)):
        colv = redness[y1:y2, max(0, x - 3):x + 4].max(axis=1)
        ys = np.where(colv > 0)[0]
        res[f"{side}_len"] = int(len(ys))
        res[f"{side}_y"] = [int(y1 + ys.min()), int(y1 + ys.max())] if len(ys) else None
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos")
    ap.add_argument("--debug-dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    files = sorted(p for p in glob.glob(os.path.join(a.videos, "*")) if p.lower().endswith(VIDEO_EXTS))
    out = {}
    if a.debug_dir:
        os.makedirs(a.debug_dir, exist_ok=True)
    for p in files:
        fr = median_frame(p)
        if fr is None:
            print(f"{os.path.basename(p)}: OLVASÁSI HIBA", flush=True)
            continue
        d = detect_gates(fr)
        name = os.path.basename(p)
        out[name] = d
        print(f"{name:18s} L={d['left_x']:4d} (s={d['left_score']:7.0f}, len={d['left_len']:3d}, y={d['left_y']})"
              f"  R={d['right_x']:4d} (s={d['right_score']:7.0f}, len={d['right_len']:3d}, y={d['right_y']})", flush=True)
        if a.debug_dir:
            vis = fr.copy()
            for x in (d["left_x"], d["right_x"]):
                cv2.line(vis, (x, 0), (x, vis.shape[0]), (0, 255, 0), 2)
            cv2.imwrite(os.path.join(a.debug_dir, os.path.splitext(name)[0] + ".jpg"),
                        cv2.resize(vis, (960, 540)))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
