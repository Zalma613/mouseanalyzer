#!/usr/bin/env python3
"""Export ellenőrzése: CSV-összegek konzisztenciája, futások sorszáma, képek száma és olvashatósága.

Használat: python3 scripts/verify_exports.py [kimeneti_mappa]
"""
import csv
import glob
import os
import sys
from collections import defaultdict

import cv2

out_dir = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Documents/MouseAnalyzer_Eredmenyek")
with open(os.path.join(out_dir, "Minden_Egyed_Meresi_Adatai.csv"), encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

runs = defaultdict(list)
tot = defaultdict(int)
problems = 0
for r in rows:
    eid = r["Egyed_ID"]
    runs[eid].append(int(r["Futas_Sorszam"]))
    d, p = int(r["Melynyulasok_Szama"]), int(r["Mancs_Labhiba_Db"])
    fp, hp = int(r["Mellso_Labhiba_Db"]), int(r["Hatso_Labhiba_Db"])
    n, t = int(r["Orr_Lenezes_Db"]), int(r["Hatso_Farok_Db"])
    if p != fp + hp or d != p + n + t:
        print(f"HIBA összeg: {eid} futás {r['Futas_Sorszam']}")
        problems += 1
    for k, v in (("dip", d), ("paw", p), ("fore", fp), ("hind", hp), ("nose", n), ("tail", t)):
        tot[k] += v

for eid, rn in runs.items():
    if rn != list(range(1, len(rn) + 1)):
        print(f"FIGYELEM nem folytonos futásszám: {eid} {rn}")
    if len(rn) < 3:
        print(f"Info: {eid} csak {len(rn)} futás")

imgs = glob.glob(os.path.join(out_dir, "Egyed_*_eredmenyek", "*_lenyulas_*.jpg"))
bad = [p for p in imgs if (im := cv2.imread(p)) is None or im.shape[0] < 100]
print(f"Futások: {len(rows)} | Egyedek: {len(runs)}")
print(f"Lenyúlások: {tot['dip']} (mancs {tot['paw']} [mellső {tot['fore']}, hátsó {tot['hind']}], "
      f"orr {tot['nose']}, farok {tot['tail']})")
print(f"Lenyúlás-képek: {len(imgs)} | sérült: {len(bad)}")
if len(imgs) != tot["dip"]:
    print("HIBA: a képek száma nem egyezik a CSV-vel")
    problems += 1
sys.exit(1 if problems or bad else 0)
