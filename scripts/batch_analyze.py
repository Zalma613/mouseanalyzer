#!/usr/bin/env python3
"""
Fej nélküli (GUI nélküli) kötegelt elemzés a MouseTracker motorral.

Használat:
    python3 scripts/batch_analyze.py --videos "/út/a/videokhoz" \
        [--out ~/Documents/MouseAnalyzer_Eredmenyek] [--mirror "/út/a/masolathoz"] \
        [--workers 6] [--only 13_1.MOV diab_2.MOV] [--keep-existing]

Lépések:
  1. Videók beolvasása természetes sorrendben (1, 2, ..., 20, diab_1, ..., diab_23).
  2. Videónkénti automatikus kalibráció (auto_calib=True), 3 futásos L->R protokoll.
  3. Párhuzamos feldolgozás (execute_parallel_processing).
  4. Automatikus képminőség-szűrés (elmosódott / kézzel takart / háttér / statikus fokcsúcs).
  5. Export (_export_worker), majd a fő CSV újraépítése az egyedi CSV-kből, természetes sorrendben.
  6. Opcionális tükrözés egy második mappába.

FIGYELEM: --only nélkül, --keep-existing nélkül a kimeneti mappában lévő Egyed_* mappák
és a Minden_Egyed_Meresi_Adatai.csv TÖRLŐDNEK a futás elején.
"""
import argparse
import csv
import glob
import json
import os
import shutil
import sys
import time

import cv2
import numpy as np

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_DIR)
import tkinter as tk  # noqa: E402

import MouseTracker as mt  # noqa: E402

VIDEO_EXTS = (".mov", ".mp4", ".avi", ".mkv", ".m4v")


def subject_key(name):
    """Természetes rendezés: előbb a sima számok (1, 2, 13_1, ...), utána diab_N."""
    b = os.path.splitext(os.path.basename(name))[0]
    if b.startswith("Egyed_") and b.endswith("_eredmenyek"):
        b = b[len("Egyed_"):-len("_eredmenyek")]
    is_diab = b.startswith("diab_")
    rest = (b[5:] if is_diab else b).split("_")
    try:
        num = int(rest[0])
    except ValueError:
        num = 999
    return (1 if is_diab else 0, num, "_".join(rest[1:]))


def quality_filter(pending_results):
    """Rossz/hamis lenyúlásképek automatikus kizárása az export előtt."""
    kept = excluded = reclassified = 0
    report = []
    for res in sorted(pending_results, key=lambda r: subject_key(r["video_name"])):
        vname = res["video_name"]
        v_rx, v_ry, v_rw, v_rh = res["roi_data"][:4]
        first = mt.decode_frame_compressed(res["first_frame_buf"])
        first_gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY) if first is not None else None

        for r in res["runs"]:
            rnum = r["run_num"]
            for di, d in enumerate(r["dips"], 1):
                gx, gy = int(d["x"]), int(d["y"])
                depth = float(d.get("dip_depth", 0.0))
                skin = float(d.get("paw_skin_score", 0.0))
                aspect = float(d.get("dip_aspect", 1.0))
                tag = f"{vname} Run#{rnum} Dip#{di} ({d['sec']:.2f}s)"

                def drop(reason, d=d, tag=tag):
                    d["valid"] = False
                    d["save_crop"] = False
                    report.append(f"[KIZÁRVA - {reason}] {tag}")

                snap = mt.decode_frame_compressed(d.get("frame_buf"))
                if snap is None:
                    drop("üres kép")
                    excluded += 1
                    continue
                sh, sw = snap.shape[:2]
                g = cv2.cvtColor(snap, cv2.COLOR_BGR2GRAY)

                # 1. Elmosódás
                roi = g[max(0, v_ry):min(sh, v_ry + v_rh), max(0, v_rx):min(sw, v_rx + v_rw)]
                lap = float(cv2.Laplacian(roi, cv2.CV_64F).var()) if roi.size else 0.0
                if lap < 12.0:
                    drop(f"elmosódott (lap={lap:.1f})")
                    excluded += 1
                    continue

                # 2. A lenyúlás csúcsa világos háttér (nem rózsaszín bőr)
                ty1, ty2 = max(0, gy - 6), min(sh, gy + 4)
                tx1, tx2 = max(0, gx - 5), min(sw, gx + 6)
                tip = g[ty1:ty2, tx1:tx2]
                if tip.size == 0:
                    drop("üres csúcs")
                    excluded += 1
                    continue
                p20 = float(np.percentile(tip, 20))
                if p20 > 145.0 and skin < 11.5:
                    drop(f"világos háttér (p20={p20:.1f}, skin={skin:.1f})")
                    excluded += 1
                    continue

                # 3. Változatlan, statikus létrafok-csúcs (az első képkockához képest)
                if first_gray is not None and (ty2 - ty1) >= 4 and (tx2 - tx1) >= 4:
                    cur = tip.astype(np.float32)
                    best = 999.0
                    for dy in range(-8, 4):
                        b1, b2 = ty1 + dy, ty2 + dy
                        if 0 <= b1 and b2 <= sh:
                            best = min(best, float(np.mean(np.abs(cur - first_gray[b1:b2, tx1:tx2].astype(np.float32)))))
                    if best < 16.5 and skin < 12.0:
                        drop(f"statikus fokcsúcs (mad={best:.1f})")
                        excluded += 1
                        continue

                # 4. Kísérletező keze/karja a ROI felső sávjában
                if first_gray is not None:
                    ys1, ys2 = max(0, v_ry), max(1, v_ry + 25)
                    xs1, xs2 = max(0, gx - 120), min(sw, gx + 120)
                    top = g[ys1:ys2, xs1:xs2]
                    if top.size:
                        td = float(np.mean(np.abs(top.astype(np.float32) - first_gray[ys1:ys2, xs1:xs2].astype(np.float32))))
                        if td > 42.0:
                            drop(f"kéz/kar a felső sávban (top_diff={td:.1f})")
                            excluded += 1
                            continue

                # 5. Mély, rózsaszín/függőleges hátsó-végtag csúszás: FAROK -> HÁTSÓ LÁB
                if d.get("dlc_code") == "HIND_TAIL" and depth >= 18.0 and (skin >= 10.5 or aspect <= 0.85):
                    d["dlc_code"], d["dlc_subcode"], d["dlc_part"] = "PAW", "HINDPAW", "HÁTSÓ LÁB (Lábhiba)"
                    reclassified += 1
                    report.append(f"[ÁTSOROLVA FAROK -> HÁTSÓ LÁB] {tag}")
                kept += 1

    print(f"\n🔍 Minőségszűrés: megtartva {kept} | kizárva {excluded} | átsorolva {reclassified}", flush=True)
    for line in report:
        print("  " + line, flush=True)


def rebuild_master_csv(out_dir):
    dirs = sorted(glob.glob(os.path.join(out_dir, "Egyed_*_eredmenyek")), key=subject_key)
    header, rows = None, []
    for sd in dirs:
        files = glob.glob(os.path.join(sd, "egyed_*_meresi_adatok.csv"))
        if not files:
            continue
        with open(files[0], encoding="utf-8-sig") as f:
            lst = list(csv.reader(f, delimiter=";"))
        if lst:
            header = header or lst[0]
            rows += [x for x in lst[1:] if x]
    if header:
        with open(os.path.join(out_dir, "Minden_Egyed_Meresi_Adatai.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(header)
            w.writerows(rows)
    print(f"📊 Fő CSV újraépítve: {len(rows)} futás, {len(dirs)} egyed", flush=True)


def write_calibration_report(pending_results, out_dir):
    """Videónkénti kalibráció (ROI, kapuk, px/cm, küszöbök) CSV-be és ellenőrző képekre."""
    cdir = os.path.join(out_dir, "_kalibracio")
    os.makedirs(cdir, exist_ok=True)
    rows = []
    for res in sorted(pending_results, key=lambda r: subject_key(r["video_name"])):
        rd = res["roi_data"]
        v_rx, v_ry, v_rw, v_rh, lg, rg, dark_t, diff_t, ladder_t, fault_pct = rd[:10]
        px_per_cm = rd[15]
        rows.append([res["video_name"], v_rx, v_ry, v_rw, v_rh, lg, rg, rg - lg, f"{px_per_cm:.3f}",
                     dark_t, diff_t, ladder_t, fault_pct, len(res.get("runs", []))])
        img = mt.decode_frame_compressed(res.get("first_frame_buf"))
        if img is not None:
            vis = img.copy()
            cv2.rectangle(vis, (v_rx, v_ry), (v_rx + v_rw, v_ry + v_rh), (255, 160, 0), 2)
            for x, lab in ((lg, "START"), (rg, "GOAL")):
                cv2.line(vis, (x, 0), (x, vis.shape[0]), (0, 220, 0), 2)
                cv2.putText(vis, lab, (max(5, x - 60), 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 160, 0), 3)
            fy = v_ry + int(v_rh * fault_pct / 100.0)
            cv2.line(vis, (v_rx, fy), (v_rx + v_rw, fy), (0, 0, 255), 1)
            cv2.putText(vis, f"{res['video_name']}  gates {lg}->{rg}  {px_per_cm:.2f} px/cm", (20, vis.shape[0] - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
            cv2.imwrite(os.path.join(cdir, os.path.splitext(res["video_name"])[0] + "_kalibracio.jpg"),
                        cv2.resize(vis, (vis.shape[1] // 2, vis.shape[0] // 2)))
    with open(os.path.join(cdir, "kalibracio.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Video", "ROI_x", "ROI_y", "ROI_w", "ROI_h", "Bal_kapu_x", "Jobb_kapu_x", "Kapu_tav_px",
                    "px_per_cm", "Fenyesseg", "Diff", "Letra", "Hibavonal_pct", "Futasok"])
        w.writerows(rows)
    print(f"📐 Kalibrációs jelentés: {cdir} ({len(rows)} videó)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True)
    ap.add_argument("--out", default=mt.get_safe_base_dir("MouseAnalyzer_Eredmenyek"))
    ap.add_argument("--mirror", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--runs", default="3")
    ap.add_argument("--gate-cm", type=float, default=60.0)
    ap.add_argument("--only", nargs="*", default=None, help="Csak ezeket a fájlneveket futtatja újra")
    ap.add_argument("--keep-existing", action="store_true")
    args = ap.parse_args()

    out_dir = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(
        (p for p in glob.glob(os.path.join(args.videos, "*")) if p.lower().endswith(VIDEO_EXTS)),
        key=subject_key,
    )
    if args.only:
        wanted = set(args.only)
        files = [p for p in files if os.path.basename(p) in wanted]
    if not files:
        sys.exit("Nincs feldolgozandó videó.")

    # Régi kimenet törlése (teljes futásnál mindent, --only esetén csak az érintett egyedeket)
    if args.only:
        for p in files:
            shutil.rmtree(os.path.join(out_dir, f"Egyed_{os.path.splitext(os.path.basename(p))[0]}_eredmenyek"),
                          ignore_errors=True)
    elif not args.keep_existing:
        for e in os.listdir(out_dir):
            p = os.path.join(out_dir, e)
            if e.startswith("Egyed_") and os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif e == "Minden_Egyed_Meresi_Adatai.csv":
                os.remove(p)

    root = tk.Tk()
    root.withdraw()
    app = mt.PerVideoIDTrackerApp(root)
    app.output_base_dir = out_dir
    app.var_enable_review.set(False)
    app.var_auto_calib.set(True)
    app.var_yolo_fusion.set(True)
    app.var_use_kalman.set(True)
    app.var_enable_zones.set(True)
    app.var_enable_kinematics.set(True)
    app.var_lock_lr_direction.set(True)
    app.var_bidirectional.set(False)
    app.var_protocol_runs.set(args.runs)

    def log(msg):
        print(msg, flush=True)

    app.log = app.auto_engine.log = app.hybrid_locator.log = app.dlc_addon.log = log

    app._append_video_list(files)
    for v in app.video_data:
        print(f"  Sorban: {v['name']:18s} -> ID: {v['id']}", flush=True)

    cap0 = cv2.VideoCapture(app.video_data[0]["path"])
    cal0 = app.auto_engine.auto_calibrate_from_video(cap0, num_bg_samples=24)
    cap0.release()
    rx, ry, rw, rh = cal0["rx"], cal0["ry"], cal0["rw"], cal0["rh"]
    lg, rg = cal0["left_gate_x"], cal0["right_gate_x"]
    app.calib_dark_thresh = cal0["calib_dark_thresh"]
    app.calib_diff_thresh = cal0["calib_diff_thresh"]
    app.calib_ladder_thresh = cal0["calib_ladder_thresh"]
    app.calib_fault_Ratio = cal0["calib_fault_Ratio"]
    app._cached_first_video_bg = (app.video_data[0]["path"], (rx, ry, rw, rh), cal0.get("roi_bg"))

    roi_cfg = mt.ROIConfig(
        rx=rx, ry=ry, rw=rw, rh=rh, left_gate_x=lg, right_gate_x=rg,
        dark_t=app.calib_dark_thresh, diff_t=app.calib_diff_thresh,
        ladder_t=app.calib_ladder_thresh, fault_pct=app.calib_fault_Ratio,
        z_active=True, kin_active=True, dip_cooldown_sec=0.50, dip_min_dist_px=30,
        gate_dist_cm=args.gate_cm, px_per_cm=(rg - lg) / args.gate_cm,
        frame_stride=args.stride, use_gpu=app.gpu_available, use_kalman=True,
        bidirectional=False, protocol_runs=args.runs, lock_lr=True,
    )
    app._run_flags = {
        "use_gpu": app.gpu_available, "auto_calib": True, "use_yolo_fusion": True,
        "dlc_superanimal": False, "dlc_export_train": False, "enable_review": False,
        "lock_lr_active": True, "use_comma": False,
    }

    t0 = time.time()
    app.is_running = True
    app.execute_parallel_processing(list(app.video_data), roi_cfg, max_workers=args.workers)
    app.pending_results.sort(key=lambda r: subject_key(r["video_name"]))
    write_calibration_report(app.pending_results, out_dir)
    quality_filter(app.pending_results)
    app._export_worker()
    app.hybrid_locator.stop()
    with open(os.path.join(out_dir, "utolso_kalibracio.json"), "w", encoding="utf-8") as f:
        json.dump(app._build_profile_dict(), f, indent=4, ensure_ascii=False)
    root.destroy()

    rebuild_master_csv(out_dir)

    if args.mirror:
        shutil.rmtree(args.mirror, ignore_errors=True)
        shutil.copytree(out_dir, args.mirror, ignore=shutil.ignore_patterns("Ultralytics"))
        print(f"Tükrözve ide: {args.mirror}", flush=True)
    print(f"✅ Kész {time.time() - t0:.0f} s alatt. Kimenet: {out_dir}", flush=True)


if __name__ == "__main__":
    main()
