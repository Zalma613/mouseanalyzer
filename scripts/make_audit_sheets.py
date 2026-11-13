#!/usr/bin/env python3
"""Áttekintő lapok (8x8 csempe) az összes lenyúlás-képről, a piros kör köré vágva, szemrevételezéshez.

Használat: python3 scripts/make_audit_sheets.py [kimeneti_mappa] [lapok_mappaja]
"""
import glob
import os
import re
import sys

import cv2
import numpy as np

out_dir = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Documents/MouseAnalyzer_Eredmenyek")
sheet_dir = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else os.path.join(out_dir, "_audit_lapok"))
os.makedirs(sheet_dir, exist_ok=True)


def key(p):
    m = re.match(r"egyed_(.+)_futas_(\d+)_lenyulas_(\d+)\.jpg", os.path.basename(p))
    if not m:
        return (9, 0, "", 0, 0)
    eid = m.group(1)
    d = eid.startswith("diab_")
    rest = (eid[5:] if d else eid).split("_")
    try:
        n = int(rest[0])
    except ValueError:
        n = 999
    return (1 if d else 0, n, "_".join(rest[1:]), int(m.group(2)), int(m.group(3)))


imgs = sorted(glob.glob(os.path.join(out_dir, "Egyed_*_eredmenyek", "*_lenyulas_*.jpg")), key=key)
tiles = []
for i, p in enumerate(imgs, 1):
    im = cv2.imread(p)
    h, w = im.shape[:2]
    band = im[300:780]
    ys, xs = np.where((band[:, :, 2] > 220) & (band[:, :, 1] < 30) & (band[:, :, 0] < 30))  # piros kör
    cx, cy = (int(np.median(xs)), 300 + int(np.median(ys))) if len(xs) else (w // 2, h // 2)
    x1, y1 = max(0, min(w - 260, cx - 130)), max(0, min(h - 180, cy - 100))
    tile = np.vstack([cv2.resize(im[10:52, 15:665], (260, 22)), im[y1:y1 + 180, x1:x1 + 260].copy()])
    name = os.path.basename(p).replace("egyed_", "").replace("_futas_", " R").replace("_lenyulas_", " D")[:-4]
    cv2.rectangle(tile, (0, 178), (260, 202), (20, 20, 20), -1)
    cv2.putText(tile, f"#{i}: {name}", (6, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
    tiles.append(tile)

for s in range(0, len(tiles), 64):
    chunk = tiles[s:s + 64]
    while len(chunk) % 8:
        chunk.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(chunk[r:r + 8]) for r in range(0, len(chunk), 8)])
    path = os.path.join(sheet_dir, f"audit_lap_{s // 64 + 1}.jpg")
    cv2.imwrite(path, sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    print("Mentve:", path)
