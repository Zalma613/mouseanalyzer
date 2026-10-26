import os
import sys
import csv
import json
import queue
import shutil
import ctypes
import tempfile
import subprocess
import threading
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import cv2
import numpy as np


APP_NAME = "MouseAnalyzer PRO"
APP_VERSION = "2.0"
APP_ID = "zalma.mouseanalyzer.pro.2.0"


# ==============================================================================
# RESOURCE PATH & NATIVE OS BRANDING (macOS Dock/Menu & Windows Taskbar)
# ==============================================================================
def get_resource_path(relative_path):
    """Finds bundled resources (icon.ico, icon.icns) both in dev and PyInstaller builds."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.getcwd(), relative_path)


def configure_native_os_identity():
    """
    Replaces default 'Python' process branding with 'MouseAnalyzer PRO'
    on Windows Taskbar and macOS Menu Bar / Dock.
    """
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle()
            if bundle:
                info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if info is not None:
                    info["CFBundleName"] = APP_NAME
                    info["CFBundleDisplayName"] = APP_NAME
        except Exception:
            pass


def apply_window_icon(root):
    """Applies icon.ico (Windows) or icon.icns (macOS) to the Tkinter root & Dock."""
    ico_path = get_resource_path("icon.ico")
    icns_path = get_resource_path("icon.icns")

    if sys.platform == "win32" and os.path.exists(ico_path):
        try:
            root.iconbitmap(default=ico_path)
        except Exception:
            pass
    elif sys.platform == "darwin":
        if os.path.exists(icns_path):
            try:
                from AppKit import NSApplication, NSImage
                ns_app = NSApplication.sharedApplication()
                ns_img = NSImage.alloc().initWithContentsOfFile_(icns_path)
                if ns_img:
                    ns_app.setApplicationIconImage_(ns_img)
            except Exception:
                pass
        # Fallback for Tkinter window icon via OpenCV decoding of icon.ico
        if os.path.exists(ico_path):
            try:
                img = cv2.imread(ico_path, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    ok, buf = cv2.imencode(".png", img)
                    if ok:
                         root._app_icon_ref = tk.PhotoImage(data=buf.tobytes())
                        root.iconphoto(True, root._app_icon_ref)
            except Exception:
                pass
    else:
        if os.path.exists(ico_path):
            try:
                img = cv2.imread(ico_path, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    ok, buf = cv2.imencode(".png", img)
                    if ok:
                        root._app_icon_ref = tk.PhotoImage(data=buf.tobytes())
                        root.iconphoto(True, root._app_icon_ref)
            except Exception:
                pass


configure_native_os_identity()


# ==============================================================================
# SAFE WORKING DIRECTORY SETUP (macOS .app & Windows .exe compatible)
# ==============================================================================
def setup_safe_working_directory(folder_name="MouseAnalyzer_Eredmenyek"):
    docs_dir = os.path.expanduser("~/Documents")
    if not os.path.exists(docs_dir):
        docs_dir = os.path.expanduser("~")
    safe_dir = os.path.join(docs_dir, folder_name)
    os.makedirs(safe_dir, exist_ok=True)
    try:
        os.chdir(safe_dir)
    except Exception:
        pass
    return safe_dir


SAFE_BASE_DIR = setup_safe_working_directory()

cv2.setUseOptimized(True)
try:
    cv2.ocl.setUseOpenCL(True)
except Exception:
    pass


# ==============================================================================
# BILINGUAL TRANSLATION DICTIONARY (HU / EN)
# ==============================================================================
TRANSLATIONS = {
    "hu": {
        "subtitle": "  PRO  //  Horizontális Létra & AI Kulcspont Elemző",
        "out_dir_prefix": "Zalma Edition  •  Kimeneti mappa:",
        "btn_change_dir": "📁 Kimeneti Mappa",
        "btn_open_dir": "📂 Eredmények",
        "kpi_videos": "BETÖLTÖTT VIDEÓK",
        "kpi_calib": "KALIBRÁCIÓS PROFIL",
        "kpi_engine": "DETEKTÁLÓ MOTOR",
        "kpi_dlc": "AI KULCSPONT MODUL",
        "kpi_vid_val": "{n} db videó",
        "kpi_cal_none": "Nincs kalibrálva",
        "kpi_cal_active": "Aktív ({w}x{h} px)",
        "sec1_title": "1. Kiválasztott Videók és Egyed Azonosítók (Dupla kattintás = ID szerkesztés)",
        "btn_add_vid": "＋ Videók Hozzáadása...",
        "btn_edit_id": "✎ Kijelölt ID Szerkesztése",
        "btn_remove_vid": "✕ Kijelölt Eltávolítása",
        "btn_clear_vid": "Lista Ürítése",
        "col_fname": "Videó Fájlnév",
        "col_id": "Egyed Azonosító (ID)",
        "col_status": "Feldolgozási Állapot",
        "col_path": "Elérési Útvonal",
        "status_waiting": "Várakozik",
        "sec2_title": "2. Elemzési Paraméterek, Kálmán-Szűrő, DeepLabCut AI & Hardveres Gyorsítás",
        "chk_zones": "Pálya szektorokra bontása (Start / Közép / Cél)",
        "chk_kin": "Kinematika (cm/s) + Sebesség-Heatmapek",
        "chk_rev": "Interaktív lenyúlás-felülvizsgáló ablak",
        "chk_gpu": "🚀 GPU (UMat + HW Dekóder) & Aszinkron Olvasó",
        "chk_kalman": "🎯 Kálmán-szűrős trajektória-simítás + Adaptív AI Maszk",
        "chk_dlc_sa": "🧠 AI Kulcspont-analízis (SuperAnimal: Orr vs. Mancs vs. Farok)",
        "chk_dlc_exp": "📸 Active Learning DLC Tanítóképek kigyűjtése",
        "lbl_threads": "Szálak:",
        "lbl_stride": "Lépésköz:",
        "lbl_cooldown": "Refrakter (mp):",
        "lbl_mindist": "Min. táv (px):",
        "lbl_gatecm": "Kapuk (cm):",
        "lbl_dec": "CSV Tizedes:",
        "btn_load_prof": "📂 Profil Betöltése",
        "btn_save_prof": "💾 Profil Mentése",
        "btn_start": "▶  Új Kalibrálás és Elemzés Indítása",
        "btn_quick": "⚡ Gyors Indítás (Mentett Kalibrációval)",
        "btn_stop": "■  Leállítás",
        "prog_idle": "Készültség: {done} / {total} videó (Várakozás indításra)",
        "prog_run": "Készültség: {done} / {total} videó ({pct:.0f}%)",
        "sec3_title": "3. Részletes Futási és Állapot (State Machine) Napló",
        "msg_no_vid_title": "Hiányzó videók",
        "msg_no_vid_body": "Kérlek, előbb adj hozzá legalább egy videót a listához!",
        "msg_no_geom_title": "Nincs mentett geometria",
        "msg_no_geom_body": "Előbb tölts be egy JSON profilt vagy végezz egy kalibrációt!",
        "msg_select_row": "Előbb jelölj ki egy sort a táblázatban!",
        "edit_id_title": "Egyed Azonosító (ID) Módosítása",
        "edit_id_prompt": "Add meg az Egyed új azonosítóját:",
        "btn_save_enter": "Mentés (Enter)",
    },
    "en": {
        "subtitle": "  PRO  //  Horizontal Ladder & AI Pose Estimation Suite",
        "out_dir_prefix": "Zalma Edition  •  Output directory:",
        "btn_change_dir": "📁 Output Folder",
        "btn_open_dir": "📂 Open Results",
        "kpi_videos": "LOADED VIDEOS",
        "kpi_calib": "CALIBRATION PROFILE",
        "kpi_engine": "TRACKING ENGINE",
        "kpi_dlc": "AI KEYPOINT MODULE",
        "kpi_vid_val": "{n} videos",
        "kpi_cal_none": "Not calibrated",
        "kpi_cal_active": "Active ({w}x{h} px)",
        "sec1_title": "1. Selected Videos & Subject IDs (Double-click row = Edit ID)",
        "btn_add_vid": "＋ Add Videos...",
        "btn_edit_id": "✎ Edit Selected ID",
        "btn_remove_vid": "✕ Remove Selected",
        "btn_clear_vid": "Clear List",
        "col_fname": "Video Filename",
        "col_id": "Subject ID",
        "col_status": "Processing Status",
        "col_path": "File Path",
        "status_waiting": "Queued",
        "sec2_title": "2. Analysis Parameters, Kalman Filter, DeepLabCut AI & Hardware Acceleration",
        "chk_zones": "Split track into sectors (Start / Mid / Goal)",
        "chk_kin": "Kinematics (cm/s) + Velocity Heatmaps",
        "chk_rev": "Interactive dip review & inspector window",
        "chk_gpu": "🚀 GPU (UMat + HW Decoder) & Async Prefetch",
        "chk_kalman": "🎯 Kalman Filter trajectory smoothing + Adaptive AI Mask",
        "chk_dlc_sa": "🧠 AI Keypoint Classification (SuperAnimal: Nose vs. Paw vs. Tail)",
        "chk_dlc_exp": "📸 Export Active Learning DLC Training Crops",
        "lbl_threads": "Threads:",
        "lbl_stride": "Frame Stride:",
        "lbl_cooldown": "Refractory (s):",
        "lbl_mindist": "Min. dist (px):",
        "lbl_gatecm": "Gates (cm):",
        "lbl_dec": "CSV Decimal:",
        "btn_load_prof": "📂 Load Profile",
        "btn_save_prof": "💾 Save Profile",
        "btn_start": "▶  Start New Calibration & Analysis",
        "btn_quick": "⚡ Quick Start (Use Saved Calibration)",
        "btn_stop": "■  Stop",
        "prog_idle": "Progress: {done} / {total} videos (Ready)",
        "prog_run": "Progress: {done} / {total} videos ({pct:.0f}%)",
        "sec3_title": "3. Real-Time Execution & State Machine Log",
        "msg_no_vid_title": "Missing Videos",
        "msg_no_vid_body": "Please add at least one video to the queue first!",
        "msg_no_geom_title": "No Saved Geometry",
        "msg_no_geom_body": "Please load a JSON profile or run calibration first!",
        "msg_select_row": "Please select a video row in the table first!",
        "edit_id_title": "Edit Subject ID",
        "edit_id_prompt": "Enter new Subject ID:",
        "btn_save_enter": "Save (Enter)",
    }
}


# ==============================================================================
# HELPER UTILITIES & KALMAN FILTER TRACKER
# ==============================================================================
def save_image_unicode(path, img):
    try:
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = ".jpg"
        is_success, im_buf_arr = cv2.imencode(ext, img)
        if is_success:
            im_buf_arr.tofile(path)
            return True
    except Exception:
        pass
    return False


def encode_frame_compressed(img, quality=94):
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buf if ok else None


def decode_frame_compressed(buf):
    if buf is None:
        return None
    if isinstance(buf, np.ndarray) and buf.ndim == 3:
        return buf
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def close_opencv_windows():
    cv2.destroyAllWindows()
    for _ in range(10):
        cv2.waitKey(1)


def is_window_open(win_name):
    try:
        return cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) >= 1
    except Exception:
        return False


def open_video_accelerated(video_path, use_hw=True):
    norm_path = os.path.normpath(video_path)
    if use_hw and hasattr(cv2, "CAP_PROP_HW_ACCELERATION") and hasattr(cv2, "VIDEO_ACCELERATION_ANY"):
        try:
            cap = cv2.VideoCapture(
                norm_path,
                cv2.CAP_ANY,
                [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY]
            )
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    return cap
                cap.release()
        except Exception:
            pass
    return cv2.VideoCapture(norm_path)


class MouseKalmanTracker:
    """
    2D Constant-Velocity Kalman Filter for smoothing rodent center-of-mass
    trajectories and predicting position across brief rung occlusions.
    """
    def __init__(self):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                              [0, 1, 0, 0]], np.float32)
        self.kf.transitionMatrix = np.array([[1, 0, 1, 0],
                                             [0, 1, 0, 1],
                                             [0, 0, 1, 0],
                                             [0, 0, 0, 1]], np.float32)
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.4
        self.initialized = False

    def reset(self, x, y):
        self.kf.statePost = np.array([[np.float32(x)],
                                      [np.float32(y)],
                                      [0.0],
                                      [0.0]], dtype=np.float32)
        self.kf.errorCovPost = np.eye(4, dtype=np.float32)
        self.initialized = True

    def update(self, x, y):
        if not self.initialized:
            self.reset(x, y)
            return int(x), int(y)
        self.kf.predict()
        meas = np.array([[np.float32(x)], [np.float32(y)]], dtype=np.float32)
        est = self.kf.correct(meas)
        return int(est[0, 0]), int(est[1, 0])


class AsyncVideoReader:
    def __init__(self, cap, v_rx, v_ry, v_rw, v_rh, stride=1, queue_size=48):
        self.cap = cap
        self.v_rx = v_rx
        self.v_ry = v_ry
        self.v_rw = v_rw
        self.v_rh = v_rh
        self.stride = max(1, stride)
        self.q = queue.Queue(maxsize=queue_size)
        self.stopped = False
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _safe_put(self, item):
        while not self.stopped:
            try:
                self.q.put(item, timeout=0.08)
                return True
            except queue.Full:
                continue
        return False

    def _worker(self):
        frame_idx = 0
        while not self.stopped:
            if self.stride > 1 and (frame_idx % self.stride != 0):
                if not self.cap.grab():
                    break
                frame_idx += 1
                continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                break

            crop = frame[self.v_ry:self.v_ry + self.v_rh, self.v_rx:self.v_rx + self.v_rw].copy()
            if not self._safe_put((frame_idx, frame, crop)):
                break
            frame_idx += 1

        try:
            self.q.put(None, timeout=0.1)
        except queue.Full:
            pass

    def read(self):
        while not self.stopped:
            try:
                return self.q.get(timeout=0.1)
            except queue.Empty:
                if not self.thread.is_alive():
                    return None
                continue
        return None

    def stop(self):
        self.stopped = True
        try:
            while not self.q.empty():
                self.q.get_nowait()
        except Exception:
            pass
        if self.thread.is_alive():
            self.thread.join(timeout=0.5)


# ==============================================================================
# DEEPLABCUT / YOLO / MORPHOLOGICAL POSE CLASSIFIER
# ==============================================================================
class DLCAddonManager:
    def __init__(self, log_callback):
        self.log = log_callback
        self.dlc_available = False
        self.yolo_available = False
        self._check_ai_environment()

    def _check_ai_environment(self):
        try:
            self.dlc_available = importlib.util.find_spec("deeplabcut") is not None
        except Exception:
            self.dlc_available = False
        try:
            self.yolo_available = importlib.util.find_spec("ultralytics") is not None
        except Exception:
            self.yolo_available = False

    def export_training_dataset(self, pending_results, base_folder=None):
        if base_folder is None:
            base_folder = os.path.join(SAFE_BASE_DIR, "DLC_Tanitokepek_Export")
        os.makedirs(base_folder, exist_ok=True)
        crops_dir = os.path.join(base_folder, "1_Dinamikus_Eger_Kivagasok_Crop")
        full_dir = os.path.join(base_folder, "2_Teljes_Kamera_Kepkockak")
        os.makedirs(crops_dir, exist_ok=True)
        os.makedirs(full_dir, exist_ok=True)

        exported_count = 0
        manifest = []

        for res in pending_results:
            animal_id = res["safe_id"]
            video_name = os.path.splitext(res["video_name"])[0]

            for r in res["runs"]:
                run_num = r["run_num"]

                for d_idx, d in enumerate(r["dips"], start=1):
                    frame = decode_frame_compressed(d["frame_buf"])
                    if frame is None:
                        continue
                    fh, fw = frame.shape[:2]
                    dx, dy = int(d["x"]), int(d["y"])

                    cx1 = max(0, dx - 180)
                    cy1 = max(0, dy - 160)
                    cx2 = min(fw, dx + 180)
                    cy2 = min(fh, dy + 100)
                    crop_img = frame[cy1:cy2, cx1:cx2]

                    base_fname = f"egyed_{animal_id}_{video_name}_run{run_num}_dip{d_idx}_{d['sec']:.2f}s.jpg"
                    crop_path = os.path.join(crops_dir, base_fname)
                    full_path = os.path.join(full_dir, base_fname)

                    save_image_unicode(crop_path, crop_img)
                    save_image_unicode(full_path, frame)

                    manifest.append({
                        "file": base_fname,
                        "type": "dip_event",
                        "animal_id": animal_id,
                        "run": run_num,
                        "sec": round(d["sec"], 3),
                        "global_dip_xy": [dx, dy],
                        "crop_bbox_xyxy": [cx1, cy1, cx2, cy2],
                        "local_dip_xy_in_crop": [dx - cx1, dy - cy1],
                        "dlc_part": d.get("dlc_part", "UNCLASSIFIED"),
                        "dlc_code": d.get("dlc_code", "UNKNOWN")
                    })
                    exported_count += 1

        manifest_path = os.path.join(base_folder, "dlc_training_metadata.json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

        self.log(
            f"[DLC/YOLO Active Learning] {exported_count} db tanítókép (Crop + Teljes + JSON) "
            f"kimentve: {os.path.abspath(base_folder)}"
        )
        return exported_count

    def _parse_superanimal_keypoints_if_any(self, temp_dir, crop_records, tw, th):
        try:
            import glob
            import pandas as pd
            h5_files = glob.glob(os.path.join(temp_dir, "*.h5"))
            if not h5_files:
                return False

            df = pd.read_hdf(h5_files[0])
            scorer = df.columns.get_level_values(0)[0]
            bodyparts = df[scorer].columns.get_level_values(0).unique()

            for idx, (d, c_img, cx1, cy1) in enumerate(crop_records):
                if idx >= len(df):
                    break
                orig_h, orig_w = c_img.shape[:2]
                scale_x = orig_w / float(tw)
                scale_y = orig_h / float(th)

                local_dip_x = d["x"] - cx1
                local_dip_y = d["y"] - cy1

                best_part = None
                best_dist = 999999.0

                for bp in bodyparts:
                    try:
                        bx = float(df[scorer][bp]["x"].iloc[idx]) * scale_x
                        by = float(df[scorer][bp]["y"].iloc[idx]) * scale_y
                        prob = float(df[scorer][bp].get("likelihood", pd.Series([1.0] * len(df))).iloc[idx])
                        if prob < 0.25 or np.isnan(bx) or np.isnan(by):
                            continue
                        dist = float(np.hypot(bx - local_dip_x, by - local_dip_y))
                        if dist < best_dist:
                            best_dist = dist
                            best_part = bp.lower()
                    except Exception:
                        continue

                if best_part:
                    d["dlc_classified_by_nn"] = True
                    if any(k in best_part for k in ("nose", "snout", "head", "chin", "ear", "eye")):
                        d["dlc_part"] = f"ORR / FEJ ({best_part})"
                        d["dlc_code"] = "NOSE"
                    elif any(k in best_part for k in ("paw", "knee", "ankle", "wrist", "elbow", "hoof", "foot", "limb")):
                        d["dlc_part"] = f"MANCS / LÁB ({best_part})"
                        d["dlc_code"] = "PAW"
                    elif any(k in best_part for k in ("tail", "hip", "back", "pelvis")):
                        d["dlc_part"] = f"HÁTSÓ / FAROK ({best_part})"
                        d["dlc_code"] = "HIND_TAIL"
                    else:
                        d["dlc_part"] = f"TESTRÉSZ ({best_part})"
                        d["dlc_code"] = "PAW"
            return True
        except Exception:
            return False

    def classify_dips_with_superanimal(self, pending_results):
        self.log("🧠 [AI Kulcspont-analízis] Lenyúlások anatómiai osztályozása (Orr vs. Mancs vs. Farok)...")

        parsed_from_dlc = False

        if self.dlc_available:
            temp_dir = tempfile.mkdtemp(prefix="dlc_superanimal_crops_")
            try:
                import deeplabcut
                crop_records = []
                for res in pending_results:
                    for r in res["runs"]:
                        for d in r["dips"]:
                            frame = decode_frame_compressed(d["frame_buf"])
                            if frame is None:
                                continue
                            fh, fw = frame.shape[:2]
                            dx, dy = int(d["x"]), int(d["y"])
                            cx1, cy1 = max(0, dx - 180), max(0, dy - 160)
                            cx2, cy2 = min(fw, dx + 180), min(fh, dy + 100)
                            crop_records.append((d, frame[cy1:cy2, cx1:cx2], cx1, cy1))

                if crop_records:
                    temp_video = os.path.join(temp_dir, "dips_batch.mp4")
                    th, tw = 260, 360
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(temp_video, fourcc, 10.0, (tw, th))
                    for _, c_img, _, _ in crop_records:
                        writer.write(cv2.resize(c_img, (tw, th)))
                    writer.release()

                    deeplabcut.video_inference_superanimal(
                        [temp_video],
                        superanimal_name="superanimal_quadruped",
                        videotype=".mp4",
                        scale_list=[200, 300]
                    )
                    parsed_from_dlc = self._parse_superanimal_keypoints_if_any(temp_dir, crop_records, tw, th)
                    self.log("   ✔ SuperAnimal-Quadruped neurális háló sikeresen lefutott a kivágásokon!")
            except Exception as e:
                self.log(f"   ℹ SuperAnimal közvetlen futtatás átugorva ({e}), irányvektoros morfológiai elemző használata...")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        # Enhanced Morphological + Velocity-Vector Fallback Classifier
        for res in pending_results:
            for r in res["runs"]:
                traj = r["trajectory"]
                for d in r["dips"]:
                    if parsed_from_dlc and d.get("dlc_classified_by_nn"):
                        continue

                    dx, dy, d_sec = d["x"], d["y"], d["sec"]
                    closest_pt = min(traj, key=lambda pt: abs(pt[2] - d_sec)) if traj else (dx, dy, d_sec)
                    cx_body, cy_body, _ = closest_pt

                    rel_x = dx - cx_body
                    aspect_ratio = d.get("dip_aspect", 1.0)

                    # Nose dips are farther ahead of the body centroid and wider/rounder than thin paw slips
                    if rel_x > 20 or (rel_x > 12 and aspect_ratio > 1.25):
                        d["dlc_part"] = "ORR (Exploráció)"
                        d["dlc_code"] = "NOSE"
                    elif rel_x >= -24:
                        d["dlc_part"] = "MANCS (Lábhiba)"
                        d["dlc_code"] = "PAW"
                    else:
                        d["dlc_part"] = "HÁTSÓ LÁB / FAROK"
                        d["dlc_code"] = "HIND_TAIL"


# ==============================================================================
# MAIN APPLICATION
# ==============================================================================
class PerVideoIDTrackerApp:
    PALETTE = {
        "bg_main": "#0D1117",
        "bg_card": "#161B22",
        "bg_panel": "#1F2630",
        "border": "#30363D",
        "text_main": "#F0F6FC",
        "text_muted": "#8B949E",
        "emerald": "#10B981",
        "emerald_hover": "#059669",
        "emerald_soft": "#064E3B",
        "wood_amber": "#D97706",
        "blue": "#2563EB",
        "blue_hover": "#1D4ED8",
        "danger": "#EF4444",
        "danger_hover": "#DC2626",
        "teal": "#0D9488",
        "teal_hover": "#0F766E"
    }

    def __init__(self, root):
        self.root = root
        self.lang = "hu"
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1260x890")
        self.root.minsize(1080, 750)
        self.root.configure(bg=self.PALETTE["bg_main"])

        apply_window_icon(self.root)

        self.output_base_dir = SAFE_BASE_DIR

        self.video_data = []
        self.is_running = False
        self.completed_videos = 0
        self.pending_results = []

        self.calib_dark_thresh = 120
        self.calib_diff_thresh = 40
        self.calib_ladder_thresh = 150
        self.calib_fault_Ratio = 80

        self.saved_geometry = None

        self.kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.kernel_horiz = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 3))
        self.kernel_fill = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

        self.gpu_available = cv2.ocl.haveOpenCL()
        self.dlc_addon = DLCAddonManager(self.log)

        self._setup_styles()
        self._build_ui()
        self._try_autoload_last_profile()
        self._refresh_kpi_cards()

    def tr(self, key, **kwargs):
        text = TRANSLATIONS.get(self.lang, TRANSLATIONS["hu"]).get(key, key)
        return text.format(**kwargs) if kwargs else text

    def toggle_language(self):
        self.lang = "en" if self.lang == "hu" else "hu"
        self.btn_lang.config(text="🌐 HU / EN  [EN]" if self.lang == "en" else "🌐 HU / EN  [HU]")
        self._update_ui_texts()
        self._refresh_kpi_cards()

    def _setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        font_family = "SF Pro Display" if sys.platform == "darwin" else "Segoe UI"
        self.ui_font = font_family
        self.mono_font = "Menlo" if sys.platform == "darwin" else "Consolas"

        P = self.PALETTE

        style.configure("TFrame", background=P["bg_main"])
        style.configure("Card.TFrame", background=P["bg_card"])
        style.configure("TLabel", background=P["bg_card"], foreground=P["text_main"], font=(font_family, 10))

        style.configure(
            "Dark.TCheckbutton",
            background=P["bg_card"],
            foreground=P["text_main"],
            font=(font_family, 9),
            focuscolor=P["bg_card"]
        )
        style.map(
            "Dark.TCheckbutton",
            background=[("active", P["bg_card"])],
            foreground=[("active", P["emerald"])]
        )

        style.configure(
            "Treeview",
            background=P["bg_main"],
            foreground=P["text_main"],
            rowheight=28,
            fieldbackground=P["bg_main"],
            borderwidth=0,
            font=(font_family, 10)
        )
        style.configure(
            "Treeview.Heading",
            background=P["bg_panel"],
            foreground=P["text_main"],
            relief="flat",
            padding=(8, 6),
            font=(font_family, 9, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", P["emerald_soft"])],
            foreground=[("selected", "#6EE7B7")]
        )
        style.map("Treeview.Heading", background=[("active", P["border"])])

        style.configure(
            "Emerald.Horizontal.TProgressbar",
            troughcolor=P["bg_main"],
            background=P["emerald"],
            bordercolor=P["border"],
            lightcolor=P["emerald"],
            darkcolor=P["emerald"],
            thickness=14
        )

        btn_specs = {
            "Emerald.TButton": (P["emerald"], P["emerald_hover"], "#052E16", (font_family, 10, "bold")),
            "Teal.TButton":    (P["teal"], P["teal_hover"], "#FFFFFF", (font_family, 10, "bold")),
            "Primary.TButton": (P["blue"], P["blue_hover"], "#FFFFFF", (font_family, 9, "bold")),
            "Wood.TButton":    (P["wood_amber"], "#B45309", "#FFFFFF", (font_family, 9, "bold")),
            "Danger.TButton":  (P["danger"], P["danger_hover"], "#FFFFFF", (font_family, 10, "bold")),
            "Ghost.TButton":   (P["bg_panel"], P["border"], P["text_main"], (font_family, 9, "bold")),
            "SoftRed.TButton": ("#3B181E", "#581C24", "#FCA5A5", (font_family, 9, "bold")),
        }
        for s_name, (bg_col, active_col, fg_col, fnt) in btn_specs.items():
            style.configure(
                s_name,
                background=bg_col,
                foreground=fg_col,
                font=fnt,
                padding=(11, 6),
                borderwidth=0,
                relief="flat"
            )
            style.map(
                s_name,
                background=[("active", active_col), ("disabled", "#21262D")],
                foreground=[("disabled", "#484F58")]
            )

    def _create_section_card(self, parent, title_text, accent_color=None):
        P = self.PALETTE
        if accent_color is None:
            accent_color = P["emerald"]

        outer = tk.Frame(parent, bg=P["border"], padx=1, pady=1)
        inner = tk.Frame(outer, bg=P["bg_card"], padx=14, pady=10)
        inner.pack(fill="both", expand=True)

        title_row = tk.Frame(inner, bg=P["bg_card"])
        title_row.pack(fill="x", pady=(0, 8))

        accent_bar = tk.Frame(title_row, bg=accent_color, width=4, height=16)
        accent_bar.pack(side="left", padx=(0, 8))

        lbl = tk.Label(
            title_row,
            text=title_text,
            bg=P["bg_card"],
            fg=P["text_main"],
            font=(self.ui_font, 10, "bold")
        )
        lbl.pack(side="left")

        return outer, inner, lbl

    def _build_ui(self):
        P = self.PALETTE

        # ── TOP HEADER BAR ──────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=P["bg_card"], padx=22, pady=12, highlightthickness=1, highlightbackground=P["border"])
        header.pack(fill="x")

        header_left = tk.Frame(header, bg=P["bg_card"])
        header_left.pack(side="left", fill="y")

        title_line = tk.Frame(header_left, bg=P["bg_card"])
        title_line.pack(anchor="w")

        tk.Label(
            title_line, text="🦊  MOUSEANALYZER", bg=P["bg_card"], fg=P["emerald"],
            font=(self.ui_font, 15, "bold")
        ).pack(side="left")
        self.lbl_subtitle = tk.Label(
            title_line, text=self.tr("subtitle"),
            bg=P["bg_card"], fg=P["text_main"], font=(self.ui_font, 12)
        )
        self.lbl_subtitle.pack(side="left")

        self.lbl_output_dir = tk.Label(
            header_left,
            text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}",
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)
        )
        self.lbl_output_dir.pack(anchor="w", pady=(3, 0))

        header_right = tk.Frame(header, bg=P["bg_card"])
        header_right.pack(side="right")

        self.btn_lang = ttk.Button(
            header_right, text="🌐 HU / EN  [HU]", command=self.toggle_language, style="Primary.TButton"
        )
        self.btn_lang.pack(side="left", padx=(0, 8))

        self.btn_change_dir = ttk.Button(
            header_right, text=self.tr("btn_change_dir"), command=self.choose_output_folder, style="Ghost.TButton"
        )
        self.btn_change_dir.pack(side="left", padx=(0, 8))

        self.btn_open_dir = ttk.Button(
            header_right, text=self.tr("btn_open_dir"), command=self.open_results_folder, style="Wood.TButton"
        )
        self.btn_open_dir.pack(side="left")

        # ── KPI METRIC STRIP ────────────────────────────────────────────────
        kpi_strip = tk.Frame(self.root, bg=P["bg_main"], padx=20, pady=8)
        kpi_strip.pack(fill="x")

        self.kpi_vars = {
            "videos": tk.StringVar(value="0"),
            "calib": tk.StringVar(value="-"),
            "engine": tk.StringVar(value="Kalman + OpenCL GPU" if self.gpu_available else "Kalman + Multi-CPU"),
            "dlc": tk.StringVar(value="SuperAnimal NN" if self.dlc_addon.dlc_available else "Vector + Morph AI")
        }

        self.kpi_title_labels = {}
        kpi_defs = [
            ("videos", "kpi_videos", self.kpi_vars["videos"], P["emerald"]),
            ("calib", "kpi_calib", self.kpi_vars["calib"], P["wood_amber"]),
            ("engine", "kpi_engine", self.kpi_vars["engine"], "#38BDF8"),
            ("dlc", "kpi_dlc", self.kpi_vars["dlc"], "#A78BFA"),
        ]

        for idx, (k_key, k_tr_key, k_var, k_col) in enumerate(kpi_defs):
            card = tk.Frame(kpi_strip, bg=P["bg_card"], padx=14, pady=8, highlightthickness=1, highlightbackground=P["border"])
            card.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 6, 0))
            lbl_t = tk.Label(card, text=self.tr(k_tr_key), bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 8, "bold"))
            lbl_t.pack(anchor="w")
            self.kpi_title_labels[k_key] = lbl_t
            tk.Label(card, textvariable=k_var, bg=P["bg_card"], fg=k_col, font=(self.ui_font, 11, "bold")).pack(anchor="w", pady=(2, 0))

        # ── MAIN WORKSPACE CONTAINER ────────────────────────────────────────
        main_frame = tk.Frame(self.root, bg=P["bg_main"], padx=20, pady=2)
        main_frame.pack(fill="both", expand=True)

        # 1. VIDEO QUEUE CARD
        list_outer, list_card, self.lbl_sec1 = self._create_section_card(
            main_frame, self.tr("sec1_title"), P["emerald"]
        )
        list_outer.pack(fill="both", expand=True, pady=(0, 8))

        toolbar = tk.Frame(list_card, bg=P["bg_card"])
        toolbar.pack(fill="x", pady=(0, 8))

        self.btn_add_vid = ttk.Button(toolbar, text=self.tr("btn_add_vid"), command=self.browse_videos, style="Emerald.TButton")
        self.btn_add_vid.pack(side="left", padx=(0, 6))

        self.btn_edit_id = ttk.Button(toolbar, text=self.tr("btn_edit_id"), command=lambda: self.edit_animal_id(None), style="Ghost.TButton")
        self.btn_edit_id.pack(side="left", padx=(0, 6))

        self.btn_remove_vid = ttk.Button(toolbar, text=self.tr("btn_remove_vid"), command=self.remove_selected_video, style="SoftRed.TButton")
        self.btn_remove_vid.pack(side="left", padx=(0, 6))

        self.btn_clear_vid = ttk.Button(toolbar, text=self.tr("btn_clear_vid"), command=self.clear_videos, style="Ghost.TButton")
        self.btn_clear_vid.pack(side="right")

        tree_container = tk.Frame(list_card, bg=P["border"], padx=1, pady=1)
        tree_container.pack(fill="both", expand=True)

        columns = ("filename", "animal_id", "status", "path")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=5, selectmode="browse")
        self.tree.heading("filename", text=self.tr("col_fname"))
        self.tree.heading("animal_id", text=self.tr("col_id"))
        self.tree.heading("status", text=self.tr("col_status"))
        self.tree.heading("path", text=self.tr("col_path"))

        self.tree.column("filename", width=260, anchor="w")
        self.tree.column("animal_id", width=180, anchor="center")
        self.tree.column("status", width=180, anchor="center")
        self.tree.column("path", width=260, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.edit_animal_id)

        # 2. ANALYSIS & HARDWARE CONFIGURATION CARD
        ctrl_outer, control_card, self.lbl_sec2 = self._create_section_card(
            main_frame, self.tr("sec2_title"), P["wood_amber"]
        )
        ctrl_outer.pack(fill="x", pady=(0, 8))

        opt_frame1 = tk.Frame(control_card, bg=P["bg_card"])
        opt_frame1.pack(fill="x", pady=(0, 6))

        self.var_enable_zones = tk.BooleanVar(value=True)
        self.chk_zones = ttk.Checkbutton(
            opt_frame1, text=self.tr("chk_zones"), variable=self.var_enable_zones, style="Dark.TCheckbutton"
        )
        self.chk_zones.pack(side="left", padx=(0, 14))

        self.var_enable_kinematics = tk.BooleanVar(value=True)
        self.chk_kin = ttk.Checkbutton(
            opt_frame1, text=self.tr("chk_kin"), variable=self.var_enable_kinematics, style="Dark.TCheckbutton"
        )
        self.chk_kin.pack(side="left", padx=(0, 14))

        self.var_enable_review = tk.BooleanVar(value=True)
        self.chk_rev = ttk.Checkbutton(
            opt_frame1, text=self.tr("chk_rev"), variable=self.var_enable_review, style="Dark.TCheckbutton"
        )
        self.chk_rev.pack(side="left", padx=(0, 14))

        self.var_use_gpu = tk.BooleanVar(value=(sys.platform != "win32"))
        self.chk_gpu = ttk.Checkbutton(
            opt_frame1, text=self.tr("chk_gpu"), variable=self.var_use_gpu, style="Dark.TCheckbutton"
        )
        self.chk_gpu.pack(side="left")

        # AI / Kalman / DLC Banner strip
        opt_frame_dlc = tk.Frame(control_card, bg=P["bg_panel"], padx=10, pady=6, highlightthickness=1, highlightbackground=P["border"])
        opt_frame_dlc.pack(fill="x", pady=(0, 8))

        self.var_use_kalman = tk.BooleanVar(value=True)
        self.chk_kalman = tk.Checkbutton(
            opt_frame_dlc, text=self.tr("chk_kalman"),
            variable=self.var_use_kalman, bg=P["bg_panel"], fg="#38BDF8",
            selectcolor=P["bg_main"], activebackground=P["bg_panel"], activeforeground="#38BDF8",
            font=(self.ui_font, 9, "bold")
        )
        self.chk_kalman.pack(side="left", padx=(0, 14))

        self.var_dlc_superanimal = tk.BooleanVar(value=True)
        self.chk_dlc_sa = tk.Checkbutton(
            opt_frame_dlc, text=self.tr("chk_dlc_sa"),
            variable=self.var_dlc_superanimal, bg=P["bg_panel"], fg="#6EE7B7",
            selectcolor=P["bg_main"], activebackground=P["bg_panel"], activeforeground="#6EE7B7",
            font=(self.ui_font, 9, "bold")
        )
        self.chk_dlc_sa.pack(side="left", padx=(0, 14))

        self.var_dlc_export_train = tk.BooleanVar(value=True)
        self.chk_dlc_exp = tk.Checkbutton(
            opt_frame_dlc, text=self.tr("chk_dlc_exp"),
            variable=self.var_dlc_export_train, bg=P["bg_panel"], fg="#FBBF24",
            selectcolor=P["bg_main"], activebackground=P["bg_panel"], activeforeground="#FBBF24",
            font=(self.ui_font, 9, "bold")
        )
        self.chk_dlc_exp.pack(side="left")

        # Numeric Spinboxes + Decimal Separator + JSON Profile Buttons
        param_row = tk.Frame(control_card, bg=P["bg_main"], padx=10, pady=7, highlightthickness=1, highlightbackground=P["border"])
        param_row.pack(fill="x", pady=(0, 8))

        def make_spin(parent, tr_key, from_, to_, val, width=4, inc=1.0, fg_col=P["text_main"]):
            lbl = tk.Label(parent, text=self.tr(tr_key), bg=P["bg_main"], fg=fg_col, font=(self.ui_font, 9, "bold"))
            lbl.pack(side="left")
            sp = tk.Spinbox(
                parent, from_=from_, to=to_, increment=inc, width=width,
                font=(self.ui_font, 10, "bold"), bg=P["bg_panel"], fg=P["text_main"],
                insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat"
            )
            sp.pack(side="left", padx=(4, 10))
            sp.delete(0, tk.END)
            sp.insert(0, str(val))
            return lbl, sp

        self.lbl_threads, self.spin_threads = make_spin(param_row, "lbl_threads", 1, 16, "4", width=3, inc=1)
        self.lbl_stride, self.spin_stride = make_spin(param_row, "lbl_stride", 1, 5, "1", width=3, inc=1, fg_col="#FBBF24")
        self.lbl_cooldown, self.spin_cooldown = make_spin(param_row, "lbl_cooldown", 0.05, 5.0, "0.50", width=5, inc=0.05, fg_col="#38BDF8")
        self.lbl_mindist, self.spin_min_dist = make_spin(param_row, "lbl_mindist", 0, 200, "25", width=4, inc=5)
        self.lbl_gatecm, self.spin_gate_cm = make_spin(param_row, "lbl_gatecm", 1.0, 500.0, "60.0", width=5, inc=1.0, fg_col=P["emerald"])

        self.lbl_dec = tk.Label(param_row, text=self.tr("lbl_dec"), bg=P["bg_main"], fg="#A78BFA", font=(self.ui_font, 9, "bold"))
        self.lbl_dec.pack(side="left")
        self.var_decimal = tk.StringVar(value=".")
        self.combo_dec = ttk.Combobox(param_row, textvariable=self.var_decimal, values=[". (OriginPro)", ", (HU Excel)"], width=11, state="readonly")
        self.combo_dec.current(0)
        self.combo_dec.pack(side="left", padx=(4, 8))

        self.btn_load_prof = ttk.Button(param_row, text=self.tr("btn_load_prof"), command=self.load_calibration_json, style="Ghost.TButton")
        self.btn_load_prof.pack(side="right", padx=(4, 0))

        self.btn_save_prof = ttk.Button(param_row, text=self.tr("btn_save_prof"), command=self.save_calibration_json, style="Ghost.TButton")
        self.btn_save_prof.pack(side="right", padx=(4, 4))

        # Action Launch Row
        ctrl_top = tk.Frame(control_card, bg=P["bg_card"])
        ctrl_top.pack(fill="x", pady=(2, 0))

        self.btn_start = ttk.Button(ctrl_top, text=self.tr("btn_start"), command=self.start_workflow, style="Emerald.TButton")
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_quick_start = ttk.Button(
            ctrl_top, text=self.tr("btn_quick"), command=self.start_quick_workflow, style="Teal.TButton", state="disabled"
        )
        self.btn_quick_start.pack(side="left", expand=True, fill="x", padx=6)

        self.btn_stop = ttk.Button(ctrl_top, text=self.tr("btn_stop"), command=self.stop_analysis, style="Danger.TButton", state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 0))

        # Progress bar
        prog_frame = tk.Frame(control_card, bg=P["bg_card"])
        prog_frame.pack(fill="x", pady=(8, 0))

        self.progress_lbl = tk.Label(
            prog_frame, text=self.tr("prog_idle", done=0, total=0),
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)
        )
        self.progress_lbl.pack(anchor="w", pady=(0, 3))

        self.progress_bar = ttk.Progressbar(prog_frame, style="Emerald.Horizontal.TProgressbar", mode="determinate")
        self.progress_bar.pack(fill="x")

        # 3. CONSOLE LOG CARD
        log_outer, log_card, self.lbl_sec3 = self._create_section_card(
            main_frame, self.tr("sec3_title"), "#38BDF8"
        )
        log_outer.pack(fill="both", expand=True, pady=(0, 8))

        self.log_area = scrolledtext.ScrolledText(
            log_card, wrap=tk.WORD, font=(self.mono_font, 9),
            height=6, state="disabled", bg=P["bg_main"], fg="#E2E8F0",
            insertbackground=P["emerald"], relief="flat", borderwidth=0
        )
        self.log_area.pack(fill="both", expand=True)

        self.log(
            f"{APP_NAME} v{APP_VERSION} Ready! Output: {self.output_base_dir}\n"
            f"GPU OpenCL: {'YES' if self.gpu_available else 'NO'} | "
            f"Kalman Filter + MOG2 Fusion: ACTIVE | "
            f"DeepLabCut: {'ACTIVE' if self.dlc_addon.dlc_available else 'Vector+Morphological AI'}."
        )

    def _update_ui_texts(self):
        self.lbl_subtitle.config(text=self.tr("subtitle"))
        self.lbl_output_dir.config(text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}")
        self.btn_change_dir.config(text=self.tr("btn_change_dir"))
        self.btn_open_dir.config(text=self.tr("btn_open_dir"))

        for k_key, tr_key in [("videos", "kpi_videos"), ("calib", "kpi_calib"), ("engine", "kpi_engine"), ("dlc", "kpi_dlc")]:
            self.kpi_title_labels[k_key].config(text=self.tr(tr_key))

        self.lbl_sec1.config(text=self.tr("sec1_title"))
        self.btn_add_vid.config(text=self.tr("btn_add_vid"))
        self.btn_edit_id.config(text=self.tr("btn_edit_id"))
        self.btn_remove_vid.config(text=self.tr("btn_remove_vid"))
        self.btn_clear_vid.config(text=self.tr("btn_clear_vid"))

        self.tree.heading("filename", text=self.tr("col_fname"))
        self.tree.heading("animal_id", text=self.tr("col_id"))
        self.tree.heading("status", text=self.tr("col_status"))
        self.tree.heading("path", text=self.tr("col_path"))

        self.lbl_sec2.config(text=self.tr("sec2_title"))
        self.chk_zones.config(text=self.tr("chk_zones"))
        self.chk_kin.config(text=self.tr("chk_kin"))
        self.chk_rev.config(text=self.tr("chk_rev"))
        self.chk_gpu.config(text=self.tr("chk_gpu"))
        self.chk_kalman.config(text=self.tr("chk_kalman"))
        self.chk_dlc_sa.config(text=self.tr("chk_dlc_sa"))
        self.chk_dlc_exp.config(text=self.tr("chk_dlc_exp"))

        self.lbl_threads.config(text=self.tr("lbl_threads"))
        self.lbl_stride.config(text=self.tr("lbl_stride"))
        self.lbl_cooldown.config(text=self.tr("lbl_cooldown"))
        self.lbl_mindist.config(text=self.tr("lbl_mindist"))
        self.lbl_gatecm.config(text=self.tr("lbl_gatecm"))
        self.lbl_dec.config(text=self.tr("lbl_dec"))

        self.btn_load_prof.config(text=self.tr("btn_load_prof"))
        self.btn_save_prof.config(text=self.tr("btn_save_prof"))
        self.btn_start.config(text=self.tr("btn_start"))
        self.btn_quick_start.config(text=self.tr("btn_quick"))
        self.btn_stop.config(text=self.tr("btn_stop"))
        self.lbl_sec3.config(text=self.tr("sec3_title"))

        if not self.is_running:
            self.progress_lbl.config(text=self.tr("prog_idle", done=self.completed_videos, total=len(self.video_data)))

    def _refresh_kpi_cards(self):
        self.kpi_vars["videos"].set(self.tr("kpi_vid_val", n=len(self.video_data)))
        if self.saved_geometry:
            g = self.saved_geometry
            self.kpi_vars["calib"].set(self.tr("kpi_cal_active", w=g["rw"], h=g["rh"]))
        else:
            self.kpi_vars["calib"].set(self.tr("kpi_cal_none"))

    def choose_output_folder(self):
        if self.is_running:
            return
        chosen = filedialog.askdirectory(initialdir=self.output_base_dir)
        if chosen:
            self.output_base_dir = os.path.abspath(chosen)
            os.makedirs(self.output_base_dir, exist_ok=True)
            self.lbl_output_dir.config(text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}")
            self.log(f"📁 Output dir: {self.output_base_dir}")
            self._try_autoload_last_profile()

    def _build_profile_dict(self):
        try:
            cooldown_val = float(self.spin_cooldown.get())
        except ValueError:
            cooldown_val = 0.50
        try:
            min_dist_val = int(self.spin_min_dist.get())
        except ValueError:
            min_dist_val = 25
        try:
            gate_cm_val = float(self.spin_gate_cm.get())
        except ValueError:
            gate_cm_val = 60.0
        try:
            stride_val = max(1, int(self.spin_stride.get()))
        except ValueError:
            stride_val = 1

        return {
            "language": self.lang,
            "calib_dark_thresh": self.calib_dark_thresh,
            "calib_diff_thresh": self.calib_diff_thresh,
            "calib_ladder_thresh": self.calib_ladder_thresh,
            "calib_fault_Ratio": self.calib_fault_Ratio,
            "dip_cooldown_sec": cooldown_val,
            "dip_min_dist_px": min_dist_val,
            "gate_dist_cm": gate_cm_val,
            "frame_stride": stride_val,
            "enable_zones": self.var_enable_zones.get(),
            "enable_kinematics": self.var_enable_kinematics.get(),
            "enable_review": self.var_enable_review.get(),
            "use_gpu": self.var_use_gpu.get(),
            "use_kalman": self.var_use_kalman.get(),
            "dlc_superanimal": self.var_dlc_superanimal.get(),
            "dlc_export_train": self.var_dlc_export_train.get(),
            "geometry": self.saved_geometry
        }

    def _apply_profile_dict(self, data):
        if "language" in data and data["language"] in ("hu", "en") and data["language"] != self.lang:
            self.toggle_language()

        self.calib_dark_thresh = int(data.get("calib_dark_thresh", 120))
        self.calib_diff_thresh = int(data.get("calib_diff_thresh", 40))
        self.calib_ladder_thresh = int(data.get("calib_ladder_thresh", 150))
        self.calib_fault_Ratio = int(data.get("calib_fault_Ratio", 80))

        if "dip_cooldown_sec" in data:
            self.spin_cooldown.delete(0, tk.END)
            self.spin_cooldown.insert(0, f"{float(data['dip_cooldown_sec']):.2f}")
        if "dip_min_dist_px" in data:
            self.spin_min_dist.delete(0, tk.END)
            self.spin_min_dist.insert(0, str(int(data["dip_min_dist_px"])))
        if "gate_dist_cm" in data:
            self.spin_gate_cm.delete(0, tk.END)
            self.spin_gate_cm.insert(0, f"{float(data['gate_dist_cm']):.1f}")
        if "frame_stride" in data:
            self.spin_stride.delete(0, tk.END)
            self.spin_stride.insert(0, str(max(1, int(data["frame_stride"]))))

        for key, var in [
            ("enable_zones", self.var_enable_zones),
            ("enable_kinematics", self.var_enable_kinematics),
            ("enable_review", self.var_enable_review),
            ("use_gpu", self.var_use_gpu),
            ("use_kalman", self.var_use_kalman),
            ("dlc_superanimal", self.var_dlc_superanimal),
            ("dlc_export_train", self.var_dlc_export_train),
        ]:
            if key in data:
                var.set(bool(data[key]))

        geom = data.get("geometry")
        if isinstance(geom, dict) and all(k in geom for k in ("rx", "ry", "rw", "rh", "left_gate_x", "right_gate_x")):
            self.saved_geometry = geom
            self.btn_quick_start.config(state="normal")
        self._refresh_kpi_cards()

    def _try_autoload_last_profile(self):
        default_path = os.path.join(self.output_base_dir, "utolso_kalibracio.json")
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._apply_profile_dict(data)
                if self.saved_geometry:
                    g = self.saved_geometry
                    self.log(
                        f"[Auto-Profile] 'utolso_kalibracio.json' loaded! "
                        f"ROI=({g['rx']},{g['ry']},{g['rw']}x{g['rh']}), "
                        f"Gates X=({g['left_gate_x']} -> {g['right_gate_x']})."
                    )
            except Exception:
                pass

    def save_calibration_json(self):
        fpath = filedialog.asksaveasfilename(
            initialdir=self.output_base_dir,
            defaultextension=".json",
            initialfile="mouse_calibration_profile.json",
            filetypes=[("JSON Profile", "*.json"), ("All files", "*.*")]
        )
        if not fpath:
            return
        try:
            data = self._build_profile_dict()
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.log(f"💾 Profile saved: {fpath}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_calibration_json(self):
        if self.is_running:
            return
        fpath = filedialog.askopenfilename(
            initialdir=self.output_base_dir,
            filetypes=[("JSON Profile", "*.json"), ("All files", "*.*")]
        )
        if not fpath:
            return
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_profile_dict(data)
            self.log(f"📂 Profile loaded: {os.path.basename(fpath)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def log(self, message):
        def _append():
            if hasattr(self, "log_area"):
                self.log_area.config(state="normal")
                self.log_area.insert(tk.END, message + "\n")
                self.log_area.see(tk.END)
                self.log_area.config(state="disabled")
        self.root.after(0, _append)

    def update_row_status(self, uid, status_text):
        def _update():
            if self.tree.exists(uid):
                vals = list(self.tree.item(uid, "values"))
                vals[2] = status_text
                self.tree.item(uid, values=vals)
        self.root.after(0, _update)

    def increment_progress(self, total):
        def _inc():
            self.completed_videos += 1
            pct = (self.completed_videos / max(1, total)) * 100
            self.progress_bar["value"] = pct
            self.progress_lbl.config(text=self.tr("prog_run", done=self.completed_videos, total=total, pct=pct))
        self.root.after(0, _inc)

    def browse_videos(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv *.MP4 *.MOV *.AVI *.MKV"), ("All files", "*.*")]
        )
        if not files:
            return

        added = 0
        existing_paths = {item["path"] for item in self.video_data}

        for fpath in files:
            if fpath in existing_paths:
                continue
            fname = os.path.basename(fpath)
            digits = "".join(filter(str.isdigit, os.path.splitext(fname)[0]))
            suggested_id = digits[-3:] if digits else "1"

            uid = f"vid_{len(self.video_data)}_{abs(hash(fpath)) % 100000}"
            item_dict = {"uid": uid, "path": fpath, "name": fname, "id": suggested_id}
            self.video_data.append(item_dict)
            self.tree.insert("", "end", iid=uid, values=(fname, suggested_id, self.tr("status_waiting"), fpath))
            added += 1

        self._refresh_kpi_cards()
        self.log(f"+ {added} videos added. (Total: {len(self.video_data)})")
        self.progress_lbl.config(text=self.tr("prog_idle", done=0, total=len(self.video_data)))

    def remove_selected_video(self):
        if self.is_running:
            return
        sel = self.tree.selection()
        if not sel:
            return
        uid = sel[0]
        self.tree.delete(uid)
        self.video_data = [v for v in self.video_data if v["uid"] != uid]
        self._refresh_kpi_cards()
        self.progress_lbl.config(text=self.tr("prog_idle", done=0, total=len(self.video_data)))

    def clear_videos(self):
        if self.is_running:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.video_data.clear()
        self._refresh_kpi_cards()
        self.progress_bar["value"] = 0
        self.progress_lbl.config(text=self.tr("prog_idle", done=0, total=0))

    def edit_animal_id(self, event):
        if self.is_running:
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", self.tr("msg_select_row"))
            return

        P = self.PALETTE
        uid = sel[0]
        current_values = self.tree.item(uid, "values")

        top = tk.Toplevel(self.root)
        top.title(self.tr("edit_id_title"))
        top.geometry("380x175")
        top.configure(bg=P["bg_card"])
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()

        tk.Label(top, text=current_values[0], bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)).pack(pady=(14, 2))
        tk.Label(top, text=self.tr("edit_id_prompt"), bg=P["bg_card"], fg=P["text_main"], font=(self.ui_font, 10, "bold")).pack(pady=2)

        entry = tk.Entry(
            top, font=(self.ui_font, 12, "bold"), justify="center",
            bg=P["bg_main"], fg=P["emerald"], insertbackground=P["emerald"], relief="flat"
        )
        entry.pack(pady=8, padx=35, fill="x", ipady=4)
        entry.insert(0, current_values[1])
        entry.select_range(0, tk.END)
        entry.focus()

        def save_id(event_key=None):
            new_id = entry.get().strip()
            if new_id:
                self.tree.item(uid, values=(current_values[0], new_id, current_values[2], current_values[3]))
                for item in self.video_data:
                    if item["uid"] == uid:
                        item["id"] = new_id
                        break
                self.log(f"ID updated: {current_values[0]} -> #{new_id}")
            top.destroy()

        entry.bind("<Return>", save_id)
        ttk.Button(top, text=self.tr("btn_save_enter"), command=save_id, style="Emerald.TButton").pack(pady=6)

    def open_results_folder(self):
        folder = os.path.abspath(self.output_base_dir)
        os.makedirs(folder, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception:
            messagebox.showinfo("Folder", folder)

    def start_workflow(self):
        if not self.video_data:
            messagebox.showerror(self.tr("msg_no_vid_title"), self.tr("msg_no_vid_body"))
            return

        self.is_running = True
        self.completed_videos = 0
        self.pending_results.clear()
        self.progress_bar["value"] = 0
        self.btn_start.config(state="disabled")
        self.btn_quick_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        self.root.after(100, self.setup_and_run_parallel)

    def start_quick_workflow(self):
        if not self.video_data:
            messagebox.showerror(self.tr("msg_no_vid_title"), self.tr("msg_no_vid_body"))
            return
        if not self.saved_geometry:
            messagebox.showwarning(self.tr("msg_no_geom_title"), self.tr("msg_no_geom_body"))
            return

        self.is_running = True
        self.completed_videos = 0
        self.pending_results.clear()
        self.progress_bar["value"] = 0
        self.btn_start.config(state="disabled")
        self.btn_quick_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        g = self.saved_geometry
        self._launch_processing_thread(
            g["rx"], g["ry"], g["rw"], g["rh"],
            g["left_gate_x"], g["right_gate_x"]
        )

    def _compute_clean_background(self, cap, rx, ry, rw, rh, num_samples=16):
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        bg_frames = []

        if total_frames > num_samples:
            indices = np.linspace(0, total_frames - 2, num_samples, dtype=int)
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                r, f = cap.read()
                if r and f is not None:
                    bg_frames.append(cv2.cvtColor(f[ry:ry+rh, rx:rx+rw], cv2.COLOR_BGR2GRAY))
        else:
            for _ in range(12):
                r, f = cap.read()
                if r and f is not None:
                    bg_frames.append(cv2.cvtColor(f[ry:ry+rh, rx:rx+rw], cv2.COLOR_BGR2GRAY))

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not bg_frames:
            return None
        return np.median(bg_frames, axis=0).astype(np.uint8)

    def _create_ladder_mask(self, base_gray, ladder_thresh):
        _, ladder_mask = cv2.threshold(base_gray, ladder_thresh, 255, cv2.THRESH_BINARY_INV)
        ladder_mask = cv2.dilate(ladder_mask, self.kernel_small, iterations=1)
        return ladder_mask

    def _detect_mouse_on_crop(
        self, crop, base_gray, inv_ladder_mask, rw, rh, dark_t, diff_t,
        use_umat=False, u_base_gray=None, u_inv_ladder=None, mog2_subtractor=None
    ):
        if use_umat and u_base_gray is not None and u_inv_ladder is not None:
            u_crop = cv2.UMat(crop)
            u_gray = cv2.cvtColor(u_crop, cv2.COLOR_BGR2GRAY)
            u_diff = cv2.subtract(u_base_gray, u_gray)
            _, u_diff_mask = cv2.threshold(u_diff, diff_t, 255, cv2.THRESH_BINARY)
            _, u_dark_mask = cv2.threshold(u_gray, dark_t, 255, cv2.THRESH_BINARY_INV)

            u_raw = cv2.bitwise_and(u_diff_mask, u_dark_mask)
            u_raw = cv2.bitwise_and(u_raw, u_inv_ladder)

            u_clean = cv2.morphologyEx(u_raw, cv2.MORPH_OPEN, self.kernel_small)
            u_clean = cv2.morphologyEx(u_clean, cv2.MORPH_CLOSE, self.kernel_horiz)
            u_clean = cv2.dilate(u_clean, self.kernel_small, iterations=1)
            u_clean = cv2.bitwise_and(u_clean, u_inv_ladder)
            clean_mask = u_clean.get()
        else:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            diff = cv2.subtract(base_gray, gray)
            _, diff_mask = cv2.threshold(diff, diff_t, 255, cv2.THRESH_BINARY)
            _, dark_mask = cv2.threshold(gray, dark_t, 255, cv2.THRESH_BINARY_INV)

            raw_mask = cv2.bitwise_and(diff_mask, dark_mask)

            # Hybrid MOG2 Adaptive Foreground Reinforcement (helps when lighting shifts or paw is bright)
            if mog2_subtractor is not None:
                fg_mog = mog2_subtractor.apply(gray, learningRate=0.001)
                _, fg_mog = cv2.threshold(fg_mog, 200, 255, cv2.THRESH_BINARY)
                fg_mog = cv2.bitwise_and(fg_mog, dark_mask)
                raw_mask = cv2.bitwise_or(raw_mask, fg_mog)

            raw_mask = cv2.bitwise_and(raw_mask, inv_ladder_mask)

            clean_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, self.kernel_small)
            clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_CLOSE, self.kernel_horiz)
            clean_mask = cv2.dilate(clean_mask, self.kernel_small, iterations=1)
            clean_mask = cv2.bitwise_and(clean_mask, inv_ladder_mask)

        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_contour = None
        max_area = 0
        max_allowed_area = rw * rh * 0.65

        for c in contours:
            area = cv2.contourArea(c)
            if 350 < area < max_allowed_area:
                x_c, y_c, w_c, h_c = cv2.boundingRect(c)
                if h_c > w_c * 2.5 and y_c < 10:
                    continue
                if area > max_area:
                    max_area = area
                    best_contour = c

        if best_contour is None:
            return False, None, None

        final_mouse_mask = np.zeros_like(clean_mask)
        x_c, y_c, w_c, h_c = cv2.boundingRect(best_contour)
        cv2.drawContours(final_mouse_mask, [best_contour], -1, 255, -1)

        min_x, min_y = x_c, y_c
        max_x, max_y = x_c + w_c, y_c + h_c

        for c in contours:
            if c is not best_contour:
                c_area = cv2.contourArea(c)
                if 25 < c_area < 1800:
                    cx, cy, cw, ch = cv2.boundingRect(c)
                    if (x_c - 30 <= cx <= x_c + w_c + 30) and (y_c - 10 <= cy <= y_c + h_c + 55):
                        cv2.drawContours(final_mouse_mask, [c], -1, 255, -1)
                        min_x = min(min_x, cx)
                        min_y = min(min_y, cy)
                        max_x = max(max_x, cx + cw)
                        max_y = max(max_y, cy + ch)

        merged_bbox = (min_x, min_y, max_x - min_x, max_y - min_y)
        return True, final_mouse_mask, merged_bbox

    def _quick_check_start_gate(self, crop, base_gray, inv_ladder_mask, x1_loc, x2_loc, dark_t, diff_t):
        sub_crop = crop[:, x1_loc:x2_loc]
        sub_base = base_gray[:, x1_loc:x2_loc]
        sub_inv_lad = inv_ladder_mask[:, x1_loc:x2_loc]

        gray = cv2.cvtColor(sub_crop, cv2.COLOR_BGR2GRAY)
        diff = cv2.subtract(sub_base, gray)
        _, diff_mask = cv2.threshold(diff, diff_t, 255, cv2.THRESH_BINARY)
        _, dark_mask = cv2.threshold(gray, dark_t, 255, cv2.THRESH_BINARY_INV)
        diff_mask = cv2.bitwise_and(diff_mask, dark_mask)
        diff_mask = cv2.bitwise_and(diff_mask, sub_inv_lad)
        return cv2.countNonZero(diff_mask) > 300

    def _check_real_dip_below_line(self, final_mouse_mask, fault_y_local):
        if fault_y_local >= final_mouse_mask.shape[0]:
            return False, 0, 0, 1.0

        below_zone = final_mouse_mask[fault_y_local:, :]
        if cv2.countNonZero(below_zone) < 28:
            return False, 0, 0, 1.0

        sub_contours, _ = cv2.findContours(below_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_dip = None
        max_depth = -1

        for sc in sub_contours:
            if cv2.contourArea(sc) >= 28:
                pts = sc.reshape(-1, 2)
                max_idx = np.argmax(pts[:, 1])
                depth_y = int(pts[max_idx, 1])
                if depth_y > max_depth:
                    max_depth = depth_y
                    dip_x_local = int(pts[max_idx, 0])
                    dip_y_local = fault_y_local + depth_y
                    _, _, sw, sh = cv2.boundingRect(sc)
                    aspect = float(sw) / max(1.0, float(sh))
                    best_dip = (True, dip_x_local, dip_y_local, aspect)

        if best_dip is not None:
            return best_dip
        return False, 0, 0, 1.0

    def _generate_heatmap_image(
        self, base_frame, trajectory_pts, valid_dips, title_text,
        blend_alpha=0.48, draw_dip_circles_red=False
    ):
        h, w = base_frame.shape[:2]
        acc = np.zeros((h, w), dtype=np.float32)

        if (
            trajectory_pts
            and isinstance(trajectory_pts[0], (tuple, list))
            and len(trajectory_pts[0]) == 3
            and isinstance(trajectory_pts[0][0], (int, float, np.number))
        ):
            runs_trajectories = [trajectory_pts]
        else:
            runs_trajectories = trajectory_pts if trajectory_pts else []

        for traj in runs_trajectories:
            for pt in traj:
                px, py = int(pt[0]), int(pt[1])
                if 0 <= px < w and 0 <= py < h:
                    cv2.circle(acc, (px, py), 18, 1.0, -1)

        for d in valid_dips:
            dx, dy = int(d["x"]), int(d["y"])
            if 0 <= dx < w and 0 <= py < h:
                cv2.circle(acc, (dx, dy), 26, 3.5, -1)

        if np.max(acc) > 0:
            if self.gpu_available and self.var_use_gpu.get():
                try:
                    u_acc = cv2.UMat(acc)
                    u_blur = cv2.GaussianBlur(u_acc, (51, 51), 0)
                    acc = u_blur.get()
                except Exception:
                    acc = cv2.GaussianBlur(acc, (51, 51), 0)
            else:
                acc = cv2.GaussianBlur(acc, (51, 51), 0)

            norm = cv2.normalize(acc, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            color_hm = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
            mask = norm > 12
            result = base_frame.copy()
            blended = cv2.addWeighted(base_frame, 1.0 - blend_alpha, color_hm, blend_alpha, 0)
            result[mask] = blended[mask]
        else:
            result = base_frame.copy()

        all_segments = []
        all_positive_speeds = []

        for traj in runs_trajectories:
            if len(traj) < 2:
                continue
            raw_speeds = []
            pts_pairs = []
            for i in range(1, len(traj)):
                x0, y0, t0 = traj[i - 1]
                x1, y1, t1 = traj[i]
                dt = t1 - t0
                dist = float(np.hypot(x1 - x0, y1 - y0))
                spd = dist / dt if dt > 0.0001 else 0.0
                raw_speeds.append(spd)
                pts_pairs.append(((int(x0), int(y0)), (int(x1), int(y1))))

            smoothed = []
            for i in range(len(raw_speeds)):
                w_slice = raw_speeds[max(0, i - 1):min(len(raw_speeds), i + 2)]
                s_val = float(sum(w_slice) / len(w_slice))
                smoothed.append(s_val)
                if s_val > 2.0:
                    all_positive_speeds.append(s_val)

            for pair, s_val in zip(pts_pairs, smoothed):
                all_segments.append((pair[0], pair[1], s_val))

        if all_positive_speeds:
            v_ref = max(float(np.percentile(all_positive_speeds, 90)), 15.0)
        else:
            v_ref = 100.0

        for p0, p1, _ in all_segments:
            cv2.line(result, p0, p1, (20, 20, 20), 6, cv2.LINE_AA)

        for p0, p1, spd in all_segments:
            ratio = min(1.0, max(0.0, spd / v_ref))
            if ratio < 0.5:
                r_norm = ratio * 2.0
                b_c, g_c, r_c = 0, int(255 * r_norm), 255
            else:
                r_norm = (ratio - 0.5) * 2.0
                b_c, g_c, r_c = 0, 255, int(255 * (1.0 - r_norm))

            cv2.line(result, p0, p1, (b_c, g_c, r_c), 3, cv2.LINE_AA)

        for idx, d in enumerate(valid_dips, start=1):
            dx, dy, d_sec = int(d["x"]), int(d["y"]), d["sec"]
            short_code = d.get("dlc_code", "")
            tag_suffix = f"[{short_code}]" if short_code else ""
            if draw_dip_circles_red:
                cv2.circle(result, (dx, dy), 13, (255, 255, 255), 3)
                cv2.circle(result, (dx, dy), 12, (0, 0, 255), 2)
                cv2.putText(
                    result, f"#{idx}{tag_suffix} ({d_sec:.2f}s)", (dx - 30, dy + 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 2
                )
            else:
                cv2.circle(result, (dx, dy), 10, (255, 255, 255), 2)
                cv2.putText(
                    result, f"#{idx}{tag_suffix}", (dx - 15, dy - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2
                )

        if title_text:
            cv2.putText(
                result, title_text, (25, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.56,
                (20, 20, 220) if draw_dip_circles_red else (255, 255, 255), 2
            )

        leg_x = max(25, w - 330)
        cv2.rectangle(result, (leg_x - 10, 12), (w - 15, 52), (30, 30, 30), -1)
        cv2.putText(result, "Path:", (leg_x, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(result, "SLOW (Red)", (leg_x + 60, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 50, 255), 2)
        cv2.putText(result, "->", (leg_x + 165, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1)
        cv2.putText(result, "FAST (Green)", (leg_x + 195, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 255, 50), 2)

        return result

    def setup_and_run_parallel(self):
        first_video = self.video_data[0]["path"]
        cap = open_video_accelerated(first_video, use_hw=self.var_use_gpu.get())
        if not cap.isOpened():
            messagebox.showerror("Error", "Could not open the first video!")
            self.reset_ui()
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ret, first_frame = cap.read()
        if not ret:
            cap.release()
            messagebox.showerror("Error", "Could not read first video frame!")
            self.reset_ui()
            return

        frame_h, frame_w = first_frame.shape[:2]

        guide_img = first_frame.copy()
        cv2.putText(
            guide_img, "1. Select ROI (from mouse back down to dip zone) -> Press ENTER",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
        )
        roi = cv2.selectROI("1. Select ROI (ENTER = Confirm)", guide_img, showCrosshair=True)
        close_opencv_windows()

        rx, ry, rw, rh = [int(v) for v in roi]
        if rw == 0 or rh == 0:
            rx, ry, rw, rh = 0, 0, frame_w, frame_h

        gate_clicks = []
        temp_img = first_frame.copy()
        cv2.rectangle(temp_img, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 2)
        cv2.putText(
            temp_img, "2. Click LEFT (Start) then RIGHT (Goal) gate lines!",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )

        win_gate = "2. Select Start & Goal Gates (2 Clicks)"

        def gate_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                gate_clicks.append(x)
                cv2.line(temp_img, (x, ry), (x, ry + rh), (0, 0, 255), 2)
                cv2.imshow(win_gate, temp_img)

        cv2.namedWindow(win_gate, cv2.WINDOW_NORMAL)
        cv2.imshow(win_gate, temp_img)
        cv2.setMouseCallback(win_gate, gate_callback)

        while len(gate_clicks) < 2:
            if not is_window_open(win_gate):
                break
            key = cv2.waitKey(50) & 0xFF
            if key == 27 or key == ord('q'):
                break
        close_opencv_windows()

        if len(gate_clicks) < 2:
            cap.release()
            self.reset_ui()
            return

        left_gate_x = min(gate_clicks[0], gate_clicks[1])
        right_gate_x = max(gate_clicks[0], gate_clicks[1])

        base_gray = self._compute_clean_background(cap, rx, ry, rw, rh, num_samples=16)
        if base_gray is None:
            cap.release()
            self.reset_ui()
            return

        win_calib = "3. Live Calibration (BLUE = Rungs, GREEN = Mouse) - ENTER = Start"
        cv2.namedWindow(win_calib, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_calib, min(1150, frame_w), min(780, frame_h + 120))

        def nothing(val):
            pass

        start_preview_frame = 690 if total_frames > 700 else min(30, max(0, total_frames - 1))

        cv2.createTrackbar("Frame", win_calib, start_preview_frame, max(1, total_frames - 1), nothing)
        cv2.createTrackbar("Brightness", win_calib, self.calib_dark_thresh, 220, nothing)
        cv2.createTrackbar("Motion Diff", win_calib, self.calib_diff_thresh, 100, nothing)
        cv2.createTrackbar("Rung Mask", win_calib, self.calib_ladder_thresh, 220, nothing)
        cv2.createTrackbar("Fault Line %", win_calib, self.calib_fault_Ratio, 98, nothing)

        last_track_frame = -1
        current_calib_frame = first_frame.copy()
        cv2.imshow(win_calib, current_calib_frame)

        while True:
            if not is_window_open(win_calib):
                close_opencv_windows()
                cap.release()
                self.reset_ui()
                return

            f_idx = max(0, cv2.getTrackbarPos("Frame", win_calib))
            dark_t = max(40, cv2.getTrackbarPos("Brightness", win_calib))
            diff_t = max(5, cv2.getTrackbarPos("Motion Diff", win_calib))
            ladder_t = max(30, cv2.getTrackbarPos("Rung Mask", win_calib))
            fault_pct = max(20, cv2.getTrackbarPos("Fault Line %", win_calib))

            if f_idx != last_track_frame:
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                r, f_read = cap.read()
                if r and f_read is not None:
                    current_calib_frame = f_read
                last_track_frame = f_idx

            disp = current_calib_frame.copy()
            crop = disp[ry:ry+rh, rx:rx+rw]

            ladder_mask = self._create_ladder_mask(base_gray, ladder_t)
            inv_ladder_mask = cv2.bitwise_not(ladder_mask)
            detected, mask, bbox = self._detect_mouse_on_crop(crop, base_gray, inv_ladder_mask, rw, rh, dark_t, diff_t)

            overlay = np.zeros_like(crop)
            overlay[ladder_mask == 255] = (255, 100, 0)
            if mask is not None:
                overlay[mask == 255] = (0, 255, 0)
            disp[ry:ry+rh, rx:rx+rw] = cv2.addWeighted(crop, 0.72, overlay, 0.28, 0)

            fault_y_local = int(rh * (fault_pct / 100.0))
            fault_y_global = ry + fault_y_local
            cv2.line(disp, (rx, fault_y_global), (rx + rw, fault_y_global), (0, 0, 255), 2)

            if detected and bbox is not None and mask is not None:
                bx, by, bw, bh = bbox
                cv2.rectangle(disp, (rx + bx, ry + by), (rx + bx + bw, ry + by + bh), (0, 255, 0), 2)

                is_dip, dip_x_loc, dip_y_loc, _ = self._check_real_dip_below_line(mask, fault_y_local)
                if is_dip:
                    cv2.circle(disp, (rx + dip_x_loc, ry + dip_y_loc), 12, (0, 0, 255), 3)

            cv2.rectangle(disp, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 2)
            cv2.line(disp, (left_gate_x, ry), (left_gate_x, ry + rh), (255, 0, 0), 2)
            cv2.line(disp, (right_gate_x, ry), (right_gate_x, ry + rh), (255, 0, 0), 2)

            cv2.imshow(win_calib, disp)
            key = cv2.waitKey(40) & 0xFF
            if key in (13, 32):
                self.calib_dark_thresh = dark_t
                self.calib_diff_thresh = diff_t
                self.calib_ladder_thresh = ladder_t
                self.calib_fault_Ratio = fault_pct
                break
            elif key == 27:
                close_opencv_windows()
                cap.release()
                self.reset_ui()
                return

        close_opencv_windows()
        cap.release()

        self.saved_geometry = {
            "rx": rx, "ry": ry, "rw": rw, "rh": rh,
            "left_gate_x": left_gate_x, "right_gate_x": right_gate_x
        }
        self._refresh_kpi_cards()

        try:
            default_profile_path = os.path.join(self.output_base_dir, "utolso_kalibracio.json")
            with open(default_profile_path, "w", encoding="utf-8") as f:
                json.dump(self._build_profile_dict(), f, indent=4, ensure_ascii=False)
        except Exception:
            pass

        self._launch_processing_thread(rx, ry, rw, rh, left_gate_x, right_gate_x)

    def _launch_processing_thread(self, rx, ry, rw, rh, left_gate_x, right_gate_x):
        try:
            dip_cooldown_sec = float(self.spin_cooldown.get())
        except ValueError:
            dip_cooldown_sec = 0.50

        try:
            dip_min_dist_px = int(self.spin_min_dist.get())
        except ValueError:
            dip_min_dist_px = 25

        try:
            gate_dist_cm = max(0.1, float(self.spin_gate_cm.get()))
        except ValueError:
            gate_dist_cm = 60.0

        try:
            frame_stride = max(1, int(self.spin_stride.get()))
        except ValueError:
            frame_stride = 1

        gate_px_span = max(1, right_gate_x - left_gate_x)
        px_per_cm = gate_px_span / gate_dist_cm

        roi_data = (
            rx, ry, rw, rh,
            left_gate_x, right_gate_x,
            self.calib_dark_thresh, self.calib_diff_thresh,
            self.calib_ladder_thresh, self.calib_fault_Ratio,
            self.var_enable_zones.get(),
            self.var_enable_kinematics.get(),
            dip_cooldown_sec,
            dip_min_dist_px,
            gate_dist_cm,
            px_per_cm,
            frame_stride,
            self.var_use_gpu.get(),
            self.var_use_kalman.get()
        )

        try:
            max_workers = int(self.spin_threads.get())
        except ValueError:
            max_workers = 4

        threading.Thread(
            target=self.execute_parallel_processing,
            args=(list(self.video_data), roi_data, max_workers),
            daemon=True
        ).start()

    def execute_parallel_processing(self, video_data, roi_data, max_workers):
        lock = threading.Lock()
        total_videos = len(video_data)

        (rx, ry, rw, rh, left_gate_x, right_gate_x, dark_t, diff_t,
         ladder_t, fault_pct, z_active, kin_active,
         dip_cooldown_sec, dip_min_dist_px, gate_dist_cm, px_per_cm, frame_stride, use_gpu, use_kalman) = roi_data

        cv2.ocl.setUseOpenCL(bool(use_gpu and self.gpu_available))

        self.log(
            f"\n---> TURBO Engine started ({max_workers} threads, Stride={frame_stride}, "
            f"Kalman+MOG2={'ON' if use_kalman else 'OFF'}) | Scale: {px_per_cm:.2f} px/cm"
        )

        def process_single_video(item):
            if not self.is_running:
                return

            uid = item["uid"]
            video_path = item["path"]
            video_name = item["name"]
            animal_id = item["id"]

            self.update_row_status(uid, "Init Background...")

            safe_id = "".join(c for c in animal_id if c.isalnum() or c in ('-', '_')) or "1"
            output_dir = os.path.join(self.output_base_dir, f"Egyed_{safe_id}_eredmenyek")

            fault_y_local = int(rh * (fault_pct / 100.0))
            zone_width = (right_gate_x - left_gate_x) / 3.0
            z1_boundary = left_gate_x + zone_width
            z2_boundary = left_gate_x + 2.0 * zone_width

            cap = open_video_accelerated(video_path, use_hw=use_gpu)
            if not cap.isOpened():
                self.update_row_status(uid, "Error (Open)")
                self.increment_progress(total_videos)
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps <= 0:
                fps = 30.0

            ret, first_frame = cap.read()
            if not ret:
                cap.release()
                self.update_row_status(uid, "Error (Empty)")
                self.increment_progress(total_videos)
                return

            fh, fw = first_frame.shape[:2]
            v_rx = min(max(0, rx), fw - 10)
            v_ry = min(max(0, ry), fh - 10)
            v_rw = min(rw, fw - v_rx)
            v_rh = min(rh, fh - v_ry)

            faded_bg_template = cv2.addWeighted(first_frame, 0.22, np.full_like(first_frame, 255), 0.78, 0)
            base_gray = self._compute_clean_background(cap, v_rx, v_ry, v_rw, v_rh, num_samples=16)
            if base_gray is None:
                cap.release()
                self.update_row_status(uid, "Error (BG)")
                self.increment_progress(total_videos)
                return

            ladder_mask = self._create_ladder_mask(base_gray, ladder_t)
            inv_ladder_mask = cv2.bitwise_not(ladder_mask)

            mog2_sub = cv2.createBackgroundSubtractorMOG2(history=400, varThreshold=28, detectShadows=True) if use_kalman else None
            if mog2_sub is not None:
                mog2_sub.apply(base_gray, learningRate=1.0)

            kalman = MouseKalmanTracker() if use_kalman else None

            use_umat_for_roi = bool(use_gpu and self.gpu_available and (v_rw * v_rh >= 90000) and not use_kalman)
            u_base_gray = cv2.UMat(base_gray) if use_umat_for_roi else None
            u_inv_ladder = cv2.UMat(inv_ladder_mask) if use_umat_for_roi else None

            stride_pad = 35 * (frame_stride - 1)
            start_x1_loc = max(0, (left_gate_x - 120) - v_rx)
            start_x2_loc = min(v_rw, (left_gate_x + 210 + stride_pad) - v_rx)

            master_roi_canvas = np.full((v_rh, v_rw, 3), 255, dtype=np.uint8)
            current_run_roi = np.full((v_rh, v_rw, 3), 255, dtype=np.uint8)

            state = None

            def set_state(new_state, sec_val=0.0, detail=""):
                nonlocal state
                if state != new_state:
                    state = new_state
                    extra = f" — {detail}" if detail else ""
                    self.log(f"   [{video_name} | #{animal_id}] STATE -> {new_state} ({sec_val:.2f}s){extra}")
                    self.update_row_status(uid, f"{new_state} ({sec_val:.1f}s)")

            set_state("WAIT_FOR_LEFT_START", 0.0, "Waiting for left-gate entry...")

            run_count = 0
            start_time = 0.0
            last_seen_time = 0.0
            cooldown_sec_accum = 0.0

            dip_events = []
            in_dip_event = False
            last_dip_sec = -999.0
            last_dip_x = -999

            freeze_events = []
            current_still_sec = 0.0
            in_freeze_event = False
            current_freeze_start_sec = 0.0
            current_freeze_x = 0
            current_freeze_y_top = 0
            prev_mouse_x = None

            trajectory = []
            zone_Moving_times = [0.0, 0.0, 0.0]
            video_runs_list = []

            reader = AsyncVideoReader(cap, v_rx, v_ry, v_rw, v_rh, stride=frame_stride, queue_size=48)

            try:
                while self.is_running:
                    item_pack = reader.read()
                    if item_pack is None:
                        break

                    frame_idx, frame, crop = item_pack
                    current_sec = frame_idx / fps

                    if state == "WAIT_FOR_LEFT_START" and (start_x2_loc - start_x1_loc > 40):
                        if not self._quick_check_start_gate(
                            crop, base_gray, inv_ladder_mask, start_x1_loc, start_x2_loc, dark_t, diff_t
                        ):
                            continue

                    mouse_detected, final_mouse_mask, bbox = self._detect_mouse_on_crop(
                        crop, base_gray, inv_ladder_mask, v_rw, v_rh, dark_t, diff_t,
                        use_umat=use_umat_for_roi, u_base_gray=u_base_gray, u_inv_ladder=u_inv_ladder,
                        mog2_subtractor=mog2_sub
                    )

                    mouse_x_global = None
                    mouse_y_center_global = None
                    mouse_y_top_global = v_ry
                    if mouse_detected and bbox is not None:
                        x_c, y_c, w_c, h_c = bbox
                        raw_gx = v_rx + x_c + (w_c // 2)
                        raw_gy = v_ry + y_c + (h_c // 2)
                        if kalman is not None and state == "RUNNING":
                            mouse_x_global, mouse_y_center_global = kalman.update(raw_gx, raw_gy)
                        else:
                            mouse_x_global, mouse_y_center_global = raw_gx, raw_gy
                        mouse_y_top_global = v_ry + y_c

                    if state == "WAIT_FOR_LEFT_START":
                        if mouse_detected and (left_gate_x - 110 <= mouse_x_global <= left_gate_x + 200 + stride_pad):
                            run_count += 1
                            if kalman is not None:
                                kalman.reset(mouse_x_global, mouse_y_center_global)
                            set_state("RUNNING", current_sec, f"Run #{run_count} started...")
                            start_time = current_sec
                            last_seen_time = current_sec
                            current_run_roi.fill(255)

                            dip_events = []
                            in_dip_event = False
                            last_dip_sec = -999.0
                            last_dip_x = -999

                            freeze_events = []
                            current_still_sec = 0.0
                            in_freeze_event = False
                            current_freeze_start_sec = current_sec
                            current_freeze_x = mouse_x_global
                            current_freeze_y_top = mouse_y_top_global
                            prev_mouse_x = mouse_x_global

                            trajectory = [(mouse_x_global, mouse_y_center_global, current_sec)]
                            zone_Moving_times = [0.0, 0.0, 0.0]

                    elif state == "RUNNING":
                        if mouse_detected:
                            dt = max(0.0, current_sec - last_seen_time)
                            last_seen_time = current_sec

                            trajectory.append((mouse_x_global, mouse_y_center_global, current_sec))
                            if dt < 0.5:
                                if mouse_x_global < z1_boundary:
                                    zone_Moving_times[0] += dt
                                elif mouse_x_global < z2_boundary:
                                    zone_Moving_times[1] += dt
                                else:
                                    zone_Moving_times[2] += dt

                            paint_mask = cv2.morphologyEx(final_mouse_mask, cv2.MORPH_CLOSE, self.kernel_fill)
                            m_bool = paint_mask == 255
                            current_run_roi[m_bool] = np.minimum(current_run_roi[m_bool], crop[m_bool])

                            is_dip, dip_x_loc, dip_y_loc, dip_aspect = self._check_real_dip_below_line(final_mouse_mask, fault_y_local)
                            if is_dip:
                                dip_x_glob = v_rx + dip_x_loc
                                dip_y_glob = v_ry + dip_y_loc
                                time_since_last_dip = current_sec - last_dip_sec
                                dist_from_last_dip = abs(dip_x_glob - last_dip_x)

                                if (not in_dip_event) and (time_since_last_dip >= dip_cooldown_sec) and (
                                    dist_from_last_dip >= dip_min_dist_px or time_since_last_dip >= dip_cooldown_sec * 1.8
                                ):
                                    in_dip_event = True
                                    last_dip_sec = current_sec
                                    last_dip_x = dip_x_glob

                                    dip_events.append({
                                        "x": dip_x_glob,
                                        "y": dip_y_glob,
                                        "sec": current_sec,
                                        "dip_aspect": dip_aspect,
                                        "frame_buf": encode_frame_compressed(frame),
                                        "valid": True,
                                        "save_crop": False,
                                        "dlc_part": "MANCS / ORR",
                                        "dlc_code": "PAW"
                                    })
                            else:
                                in_dip_event = False

                            if prev_mouse_x is not None:
                                if abs(mouse_x_global - prev_mouse_x) < (2.5 * frame_stride):
                                    if current_still_sec == 0.0:
                                        current_freeze_start_sec = current_sec
                                        current_freeze_x = mouse_x_global
                                        current_freeze_y_top = mouse_y_top_global
                                    current_still_sec += dt

                                    if current_still_sec >= 0.30 and not in_freeze_event:
                                        in_freeze_event = True
                                else:
                                    if in_freeze_event:
                                        f_dur = current_sec - current_freeze_start_sec
                                        freeze_events.append((
                                            current_freeze_start_sec, current_sec, f_dur,
                                            current_freeze_x, current_freeze_y_top
                                        ))
                                    current_still_sec = 0.0
                                    in_freeze_event = False
                            prev_mouse_x = mouse_x_global

                            if mouse_x_global >= right_gate_x:
                                if in_freeze_event:
                                    f_dur = current_sec - current_freeze_start_sec
                                    freeze_events.append((
                                        current_freeze_start_sec, current_sec, f_dur,
                                        current_freeze_x, current_freeze_y_top
                                    ))
                                    in_freeze_event = False
                                    current_still_sec = 0.0

                                end_time = current_sec
                                transit_time = end_time - start_time

                                if transit_time > 0.4:
                                    np.minimum(master_roi_canvas, current_run_roi, out=master_roi_canvas)

                                    path_len_px = 0.0
                                    max_speed_px_s = 0.0
                                    for i in range(1, len(trajectory)):
                                        x0, y0, t0 = trajectory[i - 1]
                                        x1, y1, t1 = trajectory[i]
                                        step_d = float(np.hypot(x1 - x0, y1 - y0))
                                        step_t = t1 - t0
                                        path_len_px += step_d
                                        if step_t > 0.001:
                                            spd = step_d / step_t
                                            if spd > max_speed_px_s:
                                                max_speed_px_s = spd

                                    avg_speed_px_s = path_len_px / transit_time if transit_time > 0 else 0.0
                                    path_len_cm = path_len_px / px_per_cm
                                    avg_speed_cm_s = avg_speed_px_s / px_per_cm
                                    max_speed_cm_s = max_speed_px_s / px_per_cm

                                    full_clean_canvas = np.full_like(first_frame, 255)
                                    full_clean_canvas[v_ry:v_ry+v_rh, v_rx:v_rx+v_rw] = current_run_roi

                                    video_runs_list.append({
                                        "run_num": run_count,
                                        "start_time": start_time,
                                        "end_time": end_time,
                                        "transit_time": transit_time,
                                        "clean_canvas_buf": encode_frame_compressed(full_clean_canvas),
                                        "dips": list(dip_events),
                                        "freezes": list(freeze_events),
                                        "trajectory": list(trajectory),
                                        "zone_times": list(zone_Moving_times),
                                        "path_len_px": path_len_px,
                                        "avg_speed_px_s": avg_speed_px_s,
                                        "max_speed_px_s": max_speed_px_s,
                                        "path_len_cm": path_len_cm,
                                        "avg_speed_cm_s": avg_speed_cm_s,
                                        "max_speed_cm_s": max_speed_cm_s
                                    })

                                    self.log(
                                        f"   ✔ [#{animal_id}] Run #{run_count} DONE: "
                                        f"Time={transit_time:.2f}s | Dips={len(dip_events)} | "
                                        f"Speed={avg_speed_cm_s:.1f} cm/s"
                                    )

                                set_state("COOLDOWN", current_sec, f"Run #{run_count} reached goal gate...")
                                cooldown_sec_accum = 0.0

                            elif (current_sec - start_time) > 1.5 and mouse_x_global < left_gate_x - 80:
                                run_count -= 1
                                set_state("COOLDOWN", current_sec, "Mouse turned back behind start gate...")
                                cooldown_sec_accum = 0.0
                        else:
                            if (current_sec - last_seen_time) > 2.0:
                                set_state("WAIT_FOR_LEFT_START", current_sec, "Lost track >2s, resetting...")

                    elif state == "COOLDOWN":
                        step_sec = frame_stride / fps
                        if not mouse_detected:
                            cooldown_sec_accum += step_sec
                            if cooldown_sec_accum >= 1.0:
                                set_state("WAIT_FOR_LEFT_START", current_sec, "Track clear, ready for next run...")
                        else:
                            cooldown_sec_accum = 0.0
                            if mouse_x_global is not None and mouse_x_global <= left_gate_x + 50:
                                set_state("WAIT_FOR_LEFT_START", current_sec, "Mouse back at left gate...")
            finally:
                reader.stop()
                cap.release()

            master_white_canvas = np.full_like(first_frame, 255)
            master_white_canvas[v_ry:v_ry+v_rh, v_rx:v_rx+v_rw] = master_roi_canvas

            with lock:
                self.pending_results.append({
                    "uid": uid,
                    "video_name": video_name,
                    "animal_id": animal_id,
                    "safe_id": safe_id,
                    "output_dir": output_dir,
                    "first_frame_buf": encode_frame_compressed(first_frame),
                    "faded_bg_buf": encode_frame_compressed(faded_bg_template),
                    "master_white_buf": encode_frame_compressed(master_white_canvas),
                    "roi_data": roi_data,
                    "runs": video_runs_list
                })

            self.update_row_status(uid, f"Done ({len(video_runs_list)} runs)")
            self.increment_progress(total_videos)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(process_single_video, video_data))

        if self.is_running and self.pending_results:
            if self.var_dlc_superanimal.get():
                self.dlc_addon.classify_dips_with_superanimal(self.pending_results)
            if self.var_dlc_export_train.get():
                self.dlc_addon.export_training_dataset(self.pending_results, os.path.join(self.output_base_dir, "DLC_Tanitokepek_Export"))

        total_dips_found = sum(len(r["dips"]) for res in self.pending_results for r in res["runs"])
        if self.is_running and self.var_enable_review.get() and total_dips_found > 0:
            self.root.after(0, self.open_review_window)
        else:
            self.root.after(0, self.finalize_and_export_all)

    def open_review_window(self):
        P = self.PALETTE
        rev_win = tk.Toplevel(self.root)
        rev_win.title(f"{APP_NAME} — Interactive Dip & AI Keypoint Inspector")
        rev_win.geometry("1180x780")
        rev_win.configure(bg=P["bg_main"])
        rev_win.transient(self.root)
        rev_win.grab_set()
        rev_win.lift()
        rev_win.focus_force()

        top_banner = tk.Frame(rev_win, bg=P["bg_card"], padx=18, pady=10, highlightthickness=1, highlightbackground=P["border"])
        top_banner.pack(fill="x")
        tk.Label(
            top_banner,
            text="HOTKEYS:  [↑/↓ or A/D] Navigate  |  [SPACE / X] Toggle Valid  |  [T] Cycle Part (Paw/Nose/Tail)  |  [Z] 2x Zoom Loupe  |  [S] Save Snapshot  |  [ENTER] Finish",
            bg=P["bg_card"], fg=P["emerald"], font=(self.ui_font, 9, "bold")
        ).pack(anchor="w")

        body = tk.Frame(rev_win, bg=P["bg_main"], padx=16, pady=12)
        body.pack(fill="both", expand=True)

        left_outer, left_panel, _ = self._create_section_card(body, "Detected Dips & AI Classification", P["emerald"])
        left_outer.pack(side="left", fill="y", padx=(0, 12))

        cols = ("ego", "run", "sec", "part", "valid", "save")
        dip_tree = ttk.Treeview(left_panel, columns=cols, show="headings", height=20, selectmode="browse")
        dip_tree.heading("ego", text="ID")
        dip_tree.heading("run", text="Run")
        dip_tree.heading("sec", text="Time (s)")
        dip_tree.heading("part", text="AI Bodypart [T]")
        dip_tree.heading("valid", text="Valid?")
        dip_tree.heading("save", text="Save JPG?")

        dip_tree.column("ego", width=60, anchor="center")
        dip_tree.column("run", width=55, anchor="center")
        dip_tree.column("sec", width=70, anchor="center")
        dip_tree.column("part", width=140, anchor="center")
        dip_tree.column("valid", width=80, anchor="center")
        dip_tree.column("save", width=80, anchor="center")
        dip_tree.pack(side="left", fill="y")

        sb = ttk.Scrollbar(left_panel, orient="vertical", command=dip_tree.yview)
        sb.pack(side="right", fill="y")
        dip_tree.configure(yscrollcommand=sb.set)

        right_outer, right_panel, _ = self._create_section_card(body, "Camera Frame Inspector (with 2x Loupe)", P["wood_amber"])
        right_outer.pack(side="left", fill="both", expand=True)

        img_label = tk.Label(right_panel, bg=P["bg_main"], text="Select a dip event on the left", fg=P["text_muted"])
        img_label.pack(fill="both", expand=True, pady=(0, 10))

        ctrl_box = tk.Frame(right_panel, bg=P["bg_card"])
        ctrl_box.pack(fill="x")

        var_valid = tk.BooleanVar(value=True)
        var_save = tk.BooleanVar(value=False)
        var_zoom = tk.BooleanVar(value=True)

        dip_lookup = {}
        ordered_iids = []
        item_counter = 0
        for res in self.pending_results:
            for r in res["runs"]:
                for d in r["dips"]:
                    iid = f"dip_{item_counter}"
                    item_counter += 1
                    ordered_iids.append(iid)
                    dip_lookup[iid] = (res, r, d)
                    dip_tree.insert(
                        "", "end", iid=iid,
                        values=(
                            f"#{res['animal_id']}",
                            f"#{r['run_num']}",
                            f"{d['sec']:.2f}s",
                            d.get("dlc_part", "MANCS (Lábhiba)"),
                            "YES" if d["valid"] else "REMOVED",
                            "Save" if d["save_crop"] else "No"
                        )
                    )

        current_iid = [None]
        photo_ref = [None]

        def render_preview(iid):
            if not iid or iid not in dip_lookup:
                return
            res, r, d = dip_lookup[iid]
            rx, ry, rw, rh, _, _, _, _, _, fault_pct, *_ = res["roi_data"]
            fault_y_glob = ry + int(rh * (fault_pct / 100.0))

            raw_frame = decode_frame_compressed(d["frame_buf"])
            if raw_frame is None:
                return
            disp = raw_frame.copy()
            cv2.line(disp, (rx, fault_y_glob), (rx + rw, fault_y_glob), (0, 0, 255), 2)

            part_str = d.get("dlc_part", "MANCS (Lábhiba)")
            dx, dy = int(d["x"]), int(d["y"])

            if d["valid"]:
                cv2.circle(disp, (dx, dy), 18, (0, 0, 255), 3)
                status_str = f"VALID ({d['sec']:.2f}s) -> [{part_str}]"
                if d["save_crop"]:
                    status_str += " [SNAPSHOT]"
                cv2.putText(disp, status_str, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            else:
                cv2.circle(disp, (dx, dy), 18, (128, 128, 128), 2)
                cv2.putText(
                    disp, f"IGNORED ({d['sec']:.2f}s) [{part_str}]",
                    (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (160, 160, 160), 2
                )

            if var_zoom.get():
                fh, fw = raw_frame.shape[:2]
                pad = 65
                zx1, zy1 = max(0, dx - pad), max(0, dy - pad)
                zx2, zy2 = min(fw, dx + pad), min(fh, dy + pad)
                crop_z = raw_frame[zy1:zy2, zx1:zx2].copy()
                if crop_z.size > 0:
                    local_fy = fault_y_glob - zy1
                    if 0 <= local_fy < crop_z.shape[0]:
                        cv2.line(crop_z, (0, local_fy), (crop_z.shape[1], local_fy), (0, 0, 255), 1)
                    cv2.circle(crop_z, (dx - zx1, dy - zy1), 6, (0, 255, 255), 2)
                    loupe = cv2.resize(crop_z, (210, 210), interpolation=cv2.INTER_CUBIC)
                    cv2.rectangle(loupe, (0, 0), (209, 209), (16, 185, 129), 3)
                    cv2.putText(loupe, "2x LOUPE [Z]", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (16, 185, 129), 2)
                    disp[fh - 225:fh - 15, fw - 225:fw - 15] = loupe

            h_orig, w_orig = disp.shape[:2]
            target_w = 590
            target_h = int(h_orig * (target_w / max(1, w_orig)))
            resized = cv2.resize(disp, (target_w, target_h))
            ok, buf = cv2.imencode(".ppm", resized)
            if ok:
                photo = tk.PhotoImage(data=buf.tobytes())
                photo_ref[0] = photo
                img_label.config(image=photo, text="")

        def update_tree_row(iid):
            res, r, d = dip_lookup[iid]
            dip_tree.item(
                iid,
                values=(
                    f"#{res['animal_id']}",
                    f"#{r['run_num']}",
                    f"{d['sec']:.2f}s",
                    d.get("dlc_part", "MANCS (Lábhiba)"),
                    "YES" if d["valid"] else "REMOVED",
                    "Save" if d["save_crop"] else "No"
                )
            )

        def on_select(event=None):
            sel = dip_tree.selection()
            if not sel:
                return
            iid = sel[0]
            current_iid[0] = iid
            _, _, d = dip_lookup[iid]
            var_valid.set(d["valid"])
            var_save.set(d["save_crop"])
            render_preview(iid)

        def on_toggle_checkboxes():
            iid = current_iid[0]
            if not iid:
                return
            _, _, d = dip_lookup[iid]
            d["valid"] = var_valid.get()
            if not d["valid"]:
                var_save.set(False)
                d["save_crop"] = False
            else:
                d["save_crop"] = var_save.get()
            update_tree_row(iid)
            render_preview(iid)

        def step_selection(delta):
            if not ordered_iids:
                return
            curr = current_iid[0]
            if curr in ordered_iids:
                idx = ordered_iids.index(curr)
                new_idx = max(0, min(len(ordered_iids) - 1, idx + delta))
            else:
                new_idx = 0
            target = ordered_iids[new_idx]
            dip_tree.selection_set(target)
            dip_tree.focus(target)
            dip_tree.see(target)
            on_select()

        def hotkey_toggle_valid(event=None):
            iid = current_iid[0]
            if not iid:
                return
            _, _, d = dip_lookup[iid]
            d["valid"] = not d["valid"]
            if not d["valid"]:
                d["save_crop"] = False
            var_valid.set(d["valid"])
            var_save.set(d["save_crop"])
            update_tree_row(iid)
            render_preview(iid)
            return "break"

        def hotkey_cycle_part(event=None):
            iid = current_iid[0]
            if not iid:
                return
            _, _, d = dip_lookup[iid]
            code = d.get("dlc_code", "PAW")
            if code == "PAW":
                d["dlc_code"] = "NOSE"
                d["dlc_part"] = "ORR (Exploráció)"
            elif code == "NOSE":
                d["dlc_code"] = "HIND_TAIL"
                d["dlc_part"] = "HÁTSÓ LÁB / FAROK"
            else:
                d["dlc_code"] = "PAW"
                d["dlc_part"] = "MANCS (Lábhiba)"
            update_tree_row(iid)
            render_preview(iid)
            return "break"

        def hotkey_toggle_save(event=None):
            iid = current_iid[0]
            if not iid:
                return
            _, _, d = dip_lookup[iid]
            d["save_crop"] = not d["save_crop"]
            if d["save_crop"]:
                d["valid"] = True
            var_valid.set(d["valid"])
            var_save.set(d["save_crop"])
            update_tree_row(iid)
            render_preview(iid)
            return "break"

        def hotkey_toggle_zoom(event=None):
            var_zoom.set(not var_zoom.get())
            render_preview(current_iid[0])
            return "break"

        quick_btn_row = tk.Frame(ctrl_box, bg=P["bg_panel"], pady=6, padx=6)
        quick_btn_row.pack(fill="x", pady=(6, 0))

        ttk.Button(quick_btn_row, text="◀ Prev [↑/A]", command=lambda: step_selection(-1), style="Ghost.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="Next [↓/D] ▶", command=lambda: step_selection(1), style="Ghost.TButton").pack(side="left", padx=(0, 10))
        ttk.Button(quick_btn_row, text="⭕ Valid [Space]", command=hotkey_toggle_valid, style="SoftRed.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="🐾 Part [T]", command=hotkey_cycle_part, style="Teal.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="🔍 2x Loupe [Z]", command=hotkey_toggle_zoom, style="Ghost.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="💾 Save JPG [S]", command=hotkey_toggle_save, style="Primary.TButton").pack(side="left")

        dip_tree.bind("<<TreeviewSelect>>", on_select)
        if ordered_iids:
            dip_tree.selection_set(ordered_iids[0])
            dip_tree.focus(ordered_iids[0])
            on_select()

        bottom_bar = tk.Frame(rev_win, bg=P["bg_main"], padx=16, pady=10)
        bottom_bar.pack(fill="x")

        def confirm_and_close(event=None):
            try:
                rev_win.grab_release()
            except Exception:
                pass
            rev_win.destroy()
            self.finalize_and_export_all()

        for k in ("<Up>", "<Left>"):
            rev_win.bind(k, lambda e: (step_selection(-1), "break")[1])
        for k in ("<Down>", "<Right>"):
            rev_win.bind(k, lambda e: (step_selection(1), "break")[1])
        for k in ("<a>", "<A>"):
            rev_win.bind(k, lambda e: step_selection(-1))
        for k in ("<d>", "<D>"):
            rev_win.bind(k, lambda e: step_selection(1))
        for k in ("<space>", "<Delete>", "<BackSpace>", "<x>", "<X>"):
            rev_win.bind(k, hotkey_toggle_valid)
        for k in ("<t>", "<T>"):
            rev_win.bind(k, hotkey_cycle_part)
        for k in ("<s>", "<S>", "<m>", "<M>"):
            rev_win.bind(k, hotkey_toggle_save)
        for k in ("<z>", "<Z>"):
            rev_win.bind(k, hotkey_toggle_zoom)
        rev_win.bind("<Return>", confirm_and_close)

        ttk.Button(
            bottom_bar, text="✔  Confirm Review & Export All Results [ENTER]",
            command=confirm_and_close, style="Emerald.TButton"
        ).pack(side="right")

        rev_win.protocol("WM_DELETE_WINDOW", confirm_and_close)

    def finalize_and_export_all(self):
        if not self.pending_results:
            self.reset_ui()
            return

        self.log("\n💾 Exporting CSV tables and velocity heatmaps in background...")
        threading.Thread(target=self._export_worker, daemon=True).start()

    def _fmt_num(self, val, fmt_str="{:.2f}"):
        s = fmt_str.format(val)
        if self.var_decimal.get().startswith(","):
            return s.replace(".", ",")
        return s

    def _export_worker(self):
        try:
            os.makedirs(self.output_base_dir, exist_ok=True)
            master_csv = os.path.join(self.output_base_dir, "Minden_Egyed_Meresi_Adatai.csv")

            csv_headers = [
                'Egyed_ID', 'Video_Fajl', 'Futas_Sorszam',
                'Belepesi_Ido_mp', 'Kilepesi_Ido_mp',
                'Teljes_Athaladasi_Ido_mp', 'Netto_Mozgasi_Ido_mp',
                'Melynyulasok_Szama', 'Mancs_Labhiba_Db', 'Orr_Lenezes_Db', 'Hatso_Farok_Db',
                'Melynyulasok_Idopontjai_mp',
                'Megallasok_Szama', 'Megallasok_OsszIdeje_mp', 'Megallasok_Intervallumai_Tol_Ig',
                'Skala_px_per_cm',
                'Megtett_Ut_cm', 'Atlagsebesseg_cm_mp', 'Max_Sebesseg_cm_mp',
                'Megtett_Ut_px', 'Atlagsebesseg_px_mp', 'Max_Sebesseg_px_mp',
                'Start_Zona_Ido_mp', 'Start_Lenyulas_Db', 'Start_Megallas_Db',
                'Kozep_Zona_Ido_mp', 'Kozep_Lenyulas_Db', 'Kozep_Megallas_Db',
                'Cel_Zona_Ido_mp', 'Cel_Lenyulas_Db', 'Cel_Megallas_Db'
            ]

            if not os.path.exists(master_csv):
                with open(master_csv, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(csv_headers)

            for res in self.pending_results:
                uid = res["uid"]
                video_name = res["video_name"]
                animal_id = res["animal_id"]
                safe_id = res["safe_id"]
                output_dir = res["output_dir"]
                first_frame = decode_frame_compressed(res["first_frame_buf"])
                faded_bg_template = decode_frame_compressed(res["faded_bg_buf"])
                master_white_canvas = decode_frame_compressed(res["master_white_buf"])
                roi_data = res["roi_data"]
                runs = res["runs"]

                (rx, ry, rw, rh, left_gate_x, right_gate_x, _, _,
                 _, fault_pct, z_active, kin_active, _, _, gate_dist_cm, px_per_cm, _, _, _) = roi_data

                fault_y_local = int(rh * (fault_pct / 100.0))
                zone_width = (right_gate_x - left_gate_x) / 3.0
                z1_boundary = left_gate_x + zone_width
                z2_boundary = left_gate_x + 2.0 * zone_width

                os.makedirs(output_dir, exist_ok=True)
                csv_filename = os.path.join(output_dir, f"egyed_{safe_id}_meresi_adatok.csv")

                all_video_trajectories = []
                all_video_valid_dips = []

                for r in runs:
                    run_count = r["run_num"]
                    start_time = r["start_time"]
                    end_time = r["end_time"]
                    transit_time = r["transit_time"]
                    clean_canvas = decode_frame_compressed(r["clean_canvas_buf"])
                    freeze_events = r["freezes"]
                    trajectory = r["trajectory"]
                    zone_times = r["zone_times"]

                    valid_dips = [d for d in r["dips"] if d["valid"]]
                    dip_count = len(valid_dips)
                    paw_faults = sum(1 for d in valid_dips if d.get("dlc_code") == "PAW")
                    nose_peeks = sum(1 for d in valid_dips if d.get("dlc_code") == "NOSE")
                    hind_tails = sum(1 for d in valid_dips if d.get("dlc_code") == "HIND_TAIL")

                    all_video_trajectories.append(trajectory)
                    all_video_valid_dips.extend(valid_dips)

                    freeze_count = len(freeze_events)
                    freeze_sec_total = sum(ev[2] for ev in freeze_events)
                    net_moving_time = max(0.0, transit_time - freeze_sec_total)

                    for idx_pt, d in enumerate(valid_dips, start=1):
                        if d["save_crop"]:
                            snap = decode_frame_compressed(d["frame_buf"])
                            if snap is not None:
                                cv2.line(snap, (rx, ry + fault_y_local), (rx + rw, ry + fault_y_local), (0, 0, 255), 1)
                                cv2.circle(snap, (d["x"], d["y"]), 16, (0, 0, 255), 3)
                                part_lbl = d.get("dlc_part", "")
                                cv2.putText(
                                    snap,
                                    f"ID #{animal_id} | Run #{run_count} | Dip #{idx_pt} ({d['sec']:.2f}s) [{part_lbl}]",
                                    (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
                                )
                                snap_path = os.path.join(
                                    output_dir, f"egyed_{safe_id}_futas_{run_count}_lenyulas_{idx_pt}.jpg"
                                )
                                save_image_unicode(snap_path, snap)

                    zone_dips = [0, 0, 0]
                    zone_freezes = [0, 0, 0]
                    for d in valid_dips:
                        if d["x"] < z1_boundary:
                            zone_dips[0] += 1
                        elif d["x"] < z2_boundary:
                            zone_dips[1] += 1
                        else:
                            zone_dips[2] += 1

                    for _, _, _, fx, _ in freeze_events:
                        if fx < z1_boundary:
                            zone_freezes[0] += 1
                        elif fx < z2_boundary:
                            zone_freezes[1] += 1
                        else:
                            zone_freezes[2] += 1

                    freeze_intervals_str = (
                        " | ".join(f"{fs:.2f}s-{fe:.2f}s ({fd:.2f}s)" for fs, fe, fd, _, _ in freeze_events)
                        if freeze_events else "None"
                    )
                    dip_times_str = (
                        ", ".join(f"{d['sec']:.2f}s[{d.get('dlc_code', 'PAW')}]" for d in valid_dips)
                        if valid_dips else "None"
                    )

                    run_with_faded_ladder = np.minimum(faded_bg_template, clean_canvas)

                    if z_active:
                        cv2.line(run_with_faded_ladder, (int(z1_boundary), ry), (int(z1_boundary), ry + rh), (150, 150, 150), 1, cv2.LINE_AA)
                        cv2.line(run_with_faded_ladder, (int(z2_boundary), ry), (int(z2_boundary), ry + rh), (150, 150, 150), 1, cv2.LINE_AA)

                    faded_base_for_hm = run_with_faded_ladder.copy()

                    for idx_pt, d in enumerate(valid_dips, start=1):
                        dx, dy, d_sec = d["x"], d["y"], d["sec"]
                        short_code = d.get("dlc_code", "PAW")
                        cv2.circle(run_with_faded_ladder, (dx, dy), 12, (0, 0, 255), 2)
                        cv2.putText(
                            run_with_faded_ladder, f"#{idx_pt}[{short_code}] ({d_sec:.2f}s)", (dx - 30, dy + 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2
                        )

                    info_line1 = (
                        f"ID #{animal_id} | Run #{run_count} | "
                        f"Total: {transit_time:.2f}s | Net: {net_moving_time:.2f}s | "
                        f"Vel: {r['avg_speed_cm_s']:.1f} cm/s"
                    )
                    info_line2 = (
                        f"Dips: {dip_count} (Paw:{paw_faults}, Nose:{nose_peeks}) | "
                        f"Freezes: {freeze_count} ({freeze_sec_total:.2f}s)"
                    )

                    for canvas_img in (clean_canvas, run_with_faded_ladder):
                        cv2.putText(canvas_img, info_line1, (25, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 220), 2)
                        cv2.putText(canvas_img, info_line2, (25, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (180, 60, 0), 2)

                    img_clean_path = os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_tiszta_{transit_time:.2f}s.jpg")
                    img_faded_path = os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_halvany_{transit_time:.2f}s.jpg")
                    save_image_unicode(img_clean_path, clean_canvas)
                    save_image_unicode(img_faded_path, run_with_faded_ladder)

                    if kin_active:
                        hm_title = f"ID #{animal_id} | Run #{run_count} | Dist: {r['path_len_cm']:.1f}cm | Avg: {r['avg_speed_cm_s']:.1f}cm/s"
                        hm_img = self._generate_heatmap_image(
                            first_frame, [trajectory], valid_dips, hm_title,
                            blend_alpha=0.48, draw_dip_circles_red=False
                        )
                        save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_heatmap.jpg"), hm_img)

                        faded_hm_img = self._generate_heatmap_image(
                            faded_base_for_hm, [trajectory], valid_dips, info_line1,
                            blend_alpha=0.42, draw_dip_circles_red=True
                        )
                        cv2.putText(faded_hm_img, info_line2, (25, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (180, 60, 0), 2)
                        save_image_unicode(
                            os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_halvany_heatmap_{transit_time:.2f}s.jpg"),
                            faded_hm_img
                        )

                    fn = self._fmt_num
                    row_data = [
                        str(animal_id), video_name, run_count,
                        fn(start_time), fn(end_time),
                        fn(transit_time), fn(net_moving_time),
                        dip_count, paw_faults, nose_peeks, hind_tails,
                        dip_times_str,
                        freeze_count, fn(freeze_sec_total), freeze_intervals_str,
                        fn(px_per_cm),
                        fn(r['path_len_cm']),
                        fn(r['avg_speed_cm_s']),
                        fn(r['max_speed_cm_s']),
                        fn(r['path_len_px'], "{:.1f}"),
                        fn(r['avg_speed_px_s'], "{:.1f}"),
                        fn(r['max_speed_px_s'], "{:.1f}"),
                        fn(zone_times[0]), zone_dips[0], zone_freezes[0],
                        fn(zone_times[1]), zone_dips[1], zone_freezes[1],
                        fn(zone_times[2]), zone_dips[2], zone_freezes[2]
                    ]

                    csv_exists = os.path.exists(csv_filename)
                    with open(csv_filename, mode='a', newline='', encoding='utf-8-sig') as f:
                        writer = csv.writer(f, delimiter=';')
                        if not csv_exists:
                            writer.writerow(csv_headers)
                        writer.writerow(row_data)

                    with open(master_csv, mode='a', newline='', encoding='utf-8-sig') as f2:
                        writer2 = csv.writer(f2, delimiter=';')
                        writer2.writerow(row_data)

                saved_runs_for_video = len(runs)
                if saved_runs_for_video > 0:
                    master_faded_clean = np.minimum(faded_bg_template, master_white_canvas)
                    master_faded = master_faded_clean.copy()
                    summary_title = f"ID #{animal_id} Summary ({saved_runs_for_video} runs) - {video_name}"
                    cv2.putText(master_faded, summary_title, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 0, 0), 2)
                    save_image_unicode(
                        os.path.join(output_dir, f"egyed_{safe_id}_OSSZESITETT_{saved_runs_for_video}_futas.jpg"),
                        master_faded
                    )

                    if kin_active:
                        master_hm_title = f"ID #{animal_id} COMBINED Heatmap & Velocity ({saved_runs_for_video} runs)"
                        master_hm = self._generate_heatmap_image(
                            first_frame, all_video_trajectories, all_video_valid_dips, master_hm_title,
                            blend_alpha=0.48, draw_dip_circles_red=False
                        )
                        save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_OSSZESITETT_heatmap.jpg"), master_hm)

                        master_faded_hm = self._generate_heatmap_image(
                            master_faded_clean, all_video_trajectories, all_video_valid_dips, master_hm_title,
                            blend_alpha=0.42, draw_dip_circles_red=True
                        )
                        save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_OSSZESITETT_halvany_heatmap.jpg"), master_faded_hm)

                self.update_row_status(uid, f"Saved ({saved_runs_for_video} runs)")
                self.log(f"✔ Saved: {video_name} -> ID #{animal_id} ({saved_runs_for_video} runs)")

            self.pending_results.clear()
            self.log("\n==========================================")
            self.log("ALL EXPORTS COMPLETED SUCCESSFULLY!")
            self.log(f"Master CSV: {os.path.abspath(master_csv)}")
            self.log("==========================================")
        except Exception as e:
            self.log(f"❌ Export error: {e}")
        finally:
            self.root.after(0, self.reset_ui)

    def stop_analysis(self):
        self.is_running = False
        self.log("Stopping... closing worker threads cleanly...")

    def reset_ui(self):
        self.is_running = False
        self.btn_start.config(state="normal")
        if self.saved_geometry is not None:
            self.btn_quick_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._refresh_kpi_cards()


if __name__ == "__main__":
    root = tk.Tk()
    app = PerVideoIDTrackerApp(root)

    root.lift()
    root.attributes("-topmost", True)
    root.after(250, lambda: root.attributes("-topmost", False))
    root.focus_force()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        close_opencv_windows()