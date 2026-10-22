import os
import sys
import csv
import json
import queue
import shutil
import tempfile
import subprocess
import threading
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import cv2
import numpy as np

# Munkakönyvtár beállítása a script (vagy a lefordított .app / .exe) mappájára
if getattr(sys, 'frozen', False):
    # Ha le van fordítva PyInstallerrel (.exe vagy .app)
    os.chdir(os.path.dirname(sys.executable))
else:
    # Ha sima python szkriptként futtatod
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# OpenCV többszálúság és GPU (OpenCL / Apple Metal) engedélyezése
cv2.setUseOptimized(True)
try:
    cv2.ocl.setUseOpenCL(True)
except Exception:
    pass


def save_image_unicode(path, img):
    """Ékezetes útvonalakat is támogató képmentés."""
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


def close_opencv_windows():
    """macOS és Linux alatt is garantáltan bezárja az OpenCV ablakokat."""
    cv2.destroyAllWindows()
    for _ in range(10):
        cv2.waitKey(1)


def open_video_accelerated(video_path, use_hw=True):
    """Hardveres (GPU VideoToolbox / D3D11 / VAAPI) videódekódolás megkísérlése."""
    if use_hw and hasattr(cv2, "CAP_PROP_HW_ACCELERATION") and hasattr(cv2, "VIDEO_ACCELERATION_ANY"):
        try:
            cap = cv2.VideoCapture(
                video_path,
                cv2.CAP_ANY,
                [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY]
            )
            if cap.isOpened():
                return cap
        except Exception:
            pass
    return cv2.VideoCapture(video_path)


class AsyncVideoReader:
    """
    Háttérszálon futó aszinkron videóolvasó (Prefetch Buffer).
    """
    def __init__(self, cap, v_rx, v_ry, v_rw, v_rh, stride=1, queue_size=48):
        self.cap = cap
        self.v_rx = v_rx
        self.v_ry = v_ry
        self.v_rw = v_rw
        self.v_rh = v_rh
        self.stride = max(1, stride)
        self.q = queue.Queue(maxsize=queue_size)
        self.stopped = False
        self.thread = threading.Thread(target=self._Positive_worker, daemon=True)
        self.thread.start()

    def _Positive_worker(self):
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
            self.q.put((frame_idx, frame, crop))
            frame_idx += 1

        self.q.put(None)

    def read(self):
        return self.q.get()

    def stop(self):
        self.stopped = True
        try:
            while not self.q.empty():
                self.q.get_nowait()
        except Exception:
            pass


# ==============================================================================
# DEEPLABCUT (SUPERANIMAL-QUADRUPED) & TANÍTÓKÉP-KIGYŰJTŐ ADDON MODUL
# ==============================================================================
class DLCAddonManager:
    """
    Opcionális DeepLabCut SuperAnimal-Quadruped integráció és Active Learning
    tanítókép-kigyűjtő, amely a meglévő OpenCV trajektóriára és lenyúlásokra épül.
    """
    def __init__(self, log_callback):
        self.log = log_callback
        self.dlc_available = False
        self._check_dlc_environment()

    def _check_dlc_environment(self):
        """
        NEM tölti be a nehéz PyTorch/TensorFlow csomagokat az indításkor (így nem akad
        össze a Tkinter/OpenCV ablakkezelővel), csak ellenőrzi a csomag meglétét.
        """
        try:
            self.dlc_available = importlib.util.find_spec("deeplabcut") is not None
        except Exception:
            self.dlc_available = False

    def export_training_dataset(self, pending_results, base_folder="DLC_Tanitokepek_Export"):
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
                    frame = d["frame"]
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
            f"🎯 [DLC Export] {exported_count} db kritikus tanítókép (Crop + Teljes + JSON) "
            f"kimentve ide: {os.path.abspath(base_folder)}"
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
                            frame = d["frame"]
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
                self.log(f"   ℹ SuperAnimal közvetlen futtatás átugorva ({e}), morfológiai kulcspont-elemző használata...")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        for res in pending_results:
            for r in res["runs"]:
                traj = r["trajectory"]
                for d in r["dips"]:
                    if parsed_from_dlc and "dlc_code" in d:
                        continue

                    dx, dy, d_sec = d["x"], d["y"], d["sec"]
                    closest_pt = min(traj, key=lambda pt: abs(pt[2] - d_sec)) if traj else (dx, dy, d_sec)
                    cx_body, cy_body, _ = closest_pt

                    rel_x = dx - cx_body
                    if rel_x > 18:
                        d["dlc_part"] = "ORR (Exploráció)"
                        d["dlc_code"] = "NOSE"
                    elif rel_x >= -22:
                        d["dlc_part"] = "MANCS (Lábhiba)"
                        d["dlc_code"] = "PAW"
                    else:
                        d["dlc_part"] = "HÁTSÓ LÁB / FAROK"
                        d["dlc_code"] = "HIND_TAIL"


class PerVideoIDTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Egér elemző PROMAX + DeepLabCut Addon")
        self.root.geometry("1180x860")
        self.root.minsize(1000, 720)
        self.root.configure(bg="#F3F4F6")

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

    def _setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        font_family = "Helvetica" if sys.platform == "darwin" else "Segoe UI"
        self.ui_font = font_family

        style.configure("TFrame", background="#F3F4F6")
        style.configure("TLabel", background="#F3F4F6", foreground="#1F2937", font=(font_family, 10))
        style.configure("Header.TLabel", background="#1E293B", foreground="#FFFFFF", font=(font_family, 15, "bold"))
        style.configure("SubHeader.TLabel", background="#1E293B", foreground="#94A3B8", font=(font_family, 9))

        style.configure("Treeview",
                        background="#FFFFFF",
                        foreground="#1F2937",
                        rowheight=26,
                        fieldbackground="#FFFFFF",
                        font=(font_family, 10))
        style.configure("Treeview.Heading",
                        background="#E2E8F0",
                        foreground="#0F172A",
                        font=(font_family, 10, "bold"))
        style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#1E3A8A")])
        style.configure("Green.Horizontal.TProgressbar", troughcolor="#E2E8F0", background="#10B981", thickness=16)

        btn_specs = {
            "Primary.TButton": ("#2563EB", "#1D4ED8", "#FFFFFF", (font_family, 9, "bold")),
            "Success.TButton": ("#10B981", "#059669", "#FFFFFF", (font_family, 10, "bold")),
            "Teal.TButton":    ("#0D9488", "#0F766E", "#FFFFFF", (font_family, 10, "bold")),
            "Danger.TButton":  ("#EF4444", "#DC2626", "#FFFFFF", (font_family, 10, "bold")),
            "Info.TButton":    ("#3B82F6", "#2563EB", "#FFFFFF", (font_family, 9, "bold")),
            "Neutral.TButton": ("#E2E8F0", "#CBD5E1", "#1E293B", (font_family, 9, "bold")),
            "SoftRed.TButton": ("#FEE2E2", "#FECACA", "#991B1B", (font_family, 9, "bold")),
            "SoftGrn.TButton": ("#DCFCE7", "#BBF7D0", "#166534", (font_family, 9, "bold")),
            "SoftBlu.TButton": ("#E0E7FF", "#C7D2FE", "#1E40AF", (font_family, 9, "bold")),
        }
        for s_name, (bg_col, active_col, fg_col, fnt) in btn_specs.items():
            style.configure(s_name, background=bg_col, foreground=fg_col, font=fnt, padding=(10, 5), borderwidth=0)
            style.map(
                s_name,
                background=[("active", active_col), ("disabled", "#CBD5E1")],
                foreground=[("disabled", "#64748B")]
            )

    def _build_ui(self):
        header_frame = tk.Frame(self.root, bg="#1E293B", padx=20, pady=10)
        header_frame.pack(fill="x")

        ttk.Label(header_frame, text="Egér elemző PROMAX + DeepLabCut Addon", style="Header.TLabel").pack(anchor="w")
        gpu_status_txt = "GPU (OpenCL/Metal) Aktív" if self.gpu_available else "CPU SIMD Optimalizált"
        dlc_status_txt = "DLC SuperAnimal Telepítve" if self.dlc_addon.dlc_available else "Morfológiai AI Kulcspont-becslő Aktív"
        ttk.Label(
            header_frame,
            text=f"Made by Zalma",
            style="SubHeader.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        steps_frame = tk.Frame(self.root, bg="#DBEAFE", padx=15, pady=6)
        steps_frame.pack(fill="x", padx=20, pady=(8, 4))
        steps_text = (
            "Használat:   "
            "1. Videók hozzáadása   ➜   "
            "2. Beállítások   ➜   "
            "3. Kalibrálás vagy Gyors Indítás"
        )
        tk.Label(steps_frame, text=steps_text, bg="#DBEAFE", fg="#1E3A8A", font=(self.ui_font, 9, "bold")).pack(anchor="w")

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=4)

        list_card = tk.LabelFrame(
            main_frame, text=" 1. Kiválasztott videók és Egyed azonosítók ",
            font=(self.ui_font, 10, "bold"), bg="#FFFFFF", fg="#0F172A", padx=12, pady=8
        )
        list_card.pack(fill="both", expand=True, pady=(0, 6))

        toolbar = tk.Frame(list_card, bg="#FFFFFF")
        toolbar.pack(fill="x", pady=(0, 6))

        ttk.Button(
            toolbar, text="+ Videók Hozzáadása...", command=self.browse_videos, style="Primary.TButton"
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            toolbar, text="✎ Kijelölt Egyed ID Szerkesztése", command=lambda: self.edit_animal_id(None), style="Neutral.TButton"
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            toolbar, text="✕ Kijelölt Eltávolítása", command=self.remove_selected_video, style="SoftRed.TButton"
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            toolbar, text="Lista Ürítése", command=self.clear_videos, style="Neutral.TButton"
        ).pack(side="right")

        tree_container = tk.Frame(list_card, bg="#FFFFFF")
        tree_container.pack(fill="both", expand=True)

        columns = ("filename", "animal_id", "status", "path")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=4, selectmode="browse")
        self.tree.heading("filename", text="Videó Fájlnév")
        self.tree.heading("animal_id", text="Egyed Azonosító (Dupla kattintás = Szerkesztés)")
        self.tree.heading("status", text="Állapot")
        self.tree.heading("path", text="Elérési út")

        self.tree.column("filename", width=250, anchor="w")
        self.tree.column("animal_id", width=220, anchor="center")
        self.tree.column("status", width=150, anchor="center")
        self.tree.column("path", width=180, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.edit_animal_id)

        control_card = tk.LabelFrame(
            main_frame, text=" 2. Elemzés Beállításai, DeepLabCut Addon, Hardveres (GPU) Gyorsítás és JSON Profilok ",
            font=(self.ui_font, 10, "bold"), bg="#FFFFFF", fg="#0F172A", padx=12, pady=8
        )
        control_card.pack(fill="x", pady=(0, 6))

        opt_frame1 = tk.Frame(control_card, bg="#FFFFFF")
        opt_frame1.pack(fill="x", pady=(0, 4))

        self.var_enable_zones = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame1, text="Pálya szektorokra bontása (Start/Közép/Cél)",
            variable=self.var_enable_zones
        ).pack(side="left", padx=(0, 14))

        self.var_enable_kinematics = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame1, text="Kinematika (cm/s) + Heatmapek",
            variable=self.var_enable_kinematics
        ).pack(side="left", padx=(0, 14))

        self.var_enable_review = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame1, text="Lenyúlások felülvizsgálata",
            variable=self.var_enable_review
        ).pack(side="left", padx=(0, 14))

        self.var_use_gpu = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame1, text="🚀 GPU (UMat + HW Dekóder) és Aszinkron Olvasó",
            variable=self.var_use_gpu
        ).pack(side="left")

        opt_frame_dlc = tk.Frame(control_card, bg="#EEF2FF", padx=8, pady=4)
        opt_frame_dlc.pack(fill="x", pady=(0, 6))

        self.var_dlc_superanimal = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opt_frame_dlc,
            text="🧠 AI Kulcspont-analízis (SuperAnimal-Quadruped)",
            variable=self.var_dlc_superanimal, bg="#EEF2FF", fg="#1E3A8A",
            activebackground="#EEF2FF", font=(self.ui_font, 9, "bold")
        ).pack(side="left", padx=(0, 15))

        self.var_dlc_export_train = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opt_frame_dlc,
            text="🎯 DLC Tanítóképek automatikus kigyűjtése (saját modell tanítása)",
            variable=self.var_dlc_export_train, bg="#EEF2FF", fg="#065F46",
            activebackground="#EEF2FF", font=(self.ui_font, 9, "bold")
        ).pack(side="left")

        param_row = tk.Frame(control_card, bg="#F8FAFC", padx=8, pady=5)
        param_row.pack(fill="x", pady=(0, 6))

        tk.Label(param_row, text="Szálak:", bg="#F8FAFC", fg="#1F2937", font=(self.ui_font, 9)).pack(side="left")
        self.spin_threads = tk.Spinbox(param_row, from_=1, to=12, width=3, font=(self.ui_font, 10))
        self.spin_threads.pack(side="left", padx=(3, 10))
        self.spin_threads.delete(0, tk.END)
        self.spin_threads.insert(0, "4")

        tk.Label(param_row, text="Képkocka-lépésköz:", bg="#F8FAFC", fg="#B45309", font=(self.ui_font, 9, "bold")).pack(side="left")
        self.spin_stride = tk.Spinbox(param_row, from_=1, to=5, width=3, font=(self.ui_font, 10))
        self.spin_stride.pack(side="left", padx=(3, 10))
        self.spin_stride.delete(0, tk.END)
        self.spin_stride.insert(0, "1")

        tk.Label(param_row, text="Refrakter (mp):", bg="#F8FAFC", font=(self.ui_font, 9, "bold"), fg="#1E3A8A").pack(side="left")
        self.spin_cooldown = tk.Spinbox(param_row, from_=0.05, to=5.0, increment=0.05, width=5, font=(self.ui_font, 10))
        self.spin_cooldown.pack(side="left", padx=(3, 10))
        self.spin_cooldown.delete(0, tk.END)
        self.spin_cooldown.insert(0, "0.50")

        tk.Label(param_row, text="Min. táv (px):", bg="#F8FAFC", fg="#1F2937", font=(self.ui_font, 9)).pack(side="left")
        self.spin_min_dist = tk.Spinbox(param_row, from_=0, to=200, increment=5, width=4, font=(self.ui_font, 10))
        self.spin_min_dist.pack(side="left", padx=(3, 10))
        self.spin_min_dist.delete(0, tk.END)
        self.spin_min_dist.insert(0, "25")

        tk.Label(param_row, text="Kapuk (cm):", bg="#F8FAFC", font=(self.ui_font, 9, "bold"), fg="#047857").pack(side="left")
        self.spin_gate_cm = tk.Spinbox(param_row, from_=1.0, to=500.0, increment=1.0, width=5, font=(self.ui_font, 10))
        self.spin_gate_cm.pack(side="left", padx=(3, 10))
        self.spin_gate_cm.delete(0, tk.END)
        self.spin_gate_cm.insert(0, "60.0")

        ttk.Button(
            param_row, text="📂 Profil Betöltése", command=self.load_calibration_json, style="SoftBlu.TButton"
        ).pack(side="right", padx=(4, 0))

        ttk.Button(
            param_row, text="💾 Profil Mentése", command=self.save_calibration_json, style="SoftGrn.TButton"
        ).pack(side="right", padx=(4, 4))

        ctrl_top = tk.Frame(control_card, bg="#FFFFFF")
        ctrl_top.pack(fill="x", pady=(2, 0))

        self.btn_start = ttk.Button(
            ctrl_top, text="▶  Új Kalibrálás és Elemzés Indítása", command=self.start_workflow, style="Success.TButton"
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_quick_start = ttk.Button(
            ctrl_top, text="⚡ Gyors Indítás (Mentett Kalibrációval)", command=self.start_quick_workflow,
            style="Teal.TButton", state="disabled"
        )
        self.btn_quick_start.pack(side="left", expand=True, fill="x", padx=5)

        self.btn_stop = ttk.Button(
            ctrl_top, text="■  Leállítás", command=self.stop_analysis, style="Danger.TButton", state="disabled"
        )
        self.btn_stop.pack(side="left", padx=5)

        ttk.Button(
            ctrl_top, text="📂 Eredmények Mappa", command=self.open_results_folder, style="Info.TButton"
        ).pack(side="right", padx=(5, 0))

        prog_frame = tk.Frame(control_card, bg="#FFFFFF")
        prog_frame.pack(fill="x", pady=(8, 0))

        self.progress_lbl = tk.Label(
            prog_frame, text="Készültség: 0 / 0 videó (Várakozás indításra)",
            bg="#FFFFFF", fg="#475569", font=(self.ui_font, 9)
        )
        self.progress_lbl.pack(anchor="w", pady=(0, 2))

        self.progress_bar = ttk.Progressbar(prog_frame, style="Green.Horizontal.TProgressbar", mode="determinate")
        self.progress_bar.pack(fill="x")

        log_card = tk.LabelFrame(
            main_frame, text=" 3. Részletes Futási és Állapot (State) Napló ",
            font=(self.ui_font, 10, "bold"), bg="#FFFFFF", fg="#0F172A", padx=12, pady=6
        )
        log_card.pack(fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(
            log_card, wrap=tk.WORD, font=("Menlo" if sys.platform == "darwin" else "Consolas", 9),
            height=5, state="disabled", bg="#F8FAFC", fg="#1E293B"
        )
        self.log_area.pack(fill="both", expand=True)

        self.log(
            f"Rendszer kész! GPU OpenCL támogatás: {'IGEN' if self.gpu_available else 'NEM'} | "
            f"DeepLabCut csomag: {'AKTÍV' if self.dlc_addon.dlc_available else 'Tartalék Morfológiai Kulcspont-analízis'}. "
            "Gyorsabb elemzésért állítsd a 'Képkocka-lépésköz' értéket 2-re!"
        )

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
            "dlc_superanimal": self.var_dlc_superanimal.get(),
            "dlc_export_train": self.var_dlc_export_train.get(),
            "geometry": self.saved_geometry
        }

    def _apply_profile_dict(self, data):
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

        if "enable_zones" in data:
            self.var_enable_zones.set(bool(data["enable_zones"]))
        if "enable_kinematics" in data:
            self.var_enable_kinematics.set(bool(data["enable_kinematics"]))
        if "enable_review" in data:
            self.var_enable_review.set(bool(data["enable_review"]))
        if "use_gpu" in data:
            self.var_use_gpu.set(bool(data["use_gpu"]))
        if "dlc_superanimal" in data:
            self.var_dlc_superanimal.set(bool(data["dlc_superanimal"]))
        if "dlc_export_train" in data:
            self.var_dlc_export_train.set(bool(data["dlc_export_train"]))

        geom = data.get("geometry")
        if isinstance(geom, dict) and all(k in geom for k in ("rx", "ry", "rw", "rh", "left_gate_x", "right_gate_x")):
            self.saved_geometry = geom
            self.btn_quick_start.config(state="normal")

    def _try_autoload_last_profile(self):
        default_path = "utolso_kalibracio.json"
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._apply_profile_dict(data)
                if self.saved_geometry:
                    g = self.saved_geometry
                    self.log(
                        f"[Automatikus Profil] 'utolso_kalibracio.json' betöltve! "
                        f"ROI=({g['rx']},{g['ry']},{g['rw']}x{g['rh']}), "
                        f"Kapuk X=({g['left_gate_x']} -> {g['right_gate_x']}). "
                        f"Használhatod a '⚡ Gyors Indítás' gombot is!"
                    )
            except Exception:
                pass

    def save_calibration_json(self):
        fpath = filedialog.asksaveasfilename(
            title="Kalibrációs Profil Mentése",
            defaultextension=".json",
            initialfile="eger_kalibracio_profil.json",
            filetypes=[("JSON Profil Fájl", "*.json"), ("Minden fájl", "*.*")]
        )
        if not fpath:
            return
        try:
            data = self._build_profile_dict()
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.log(f"💾 Kalibrációs profil sikeresen elmentve: {fpath}")
        except Exception as e:
            messagebox.showerror("Mentési hiba", f"Nem sikerült elmenteni a JSON fájlt:\n{e}")

    def load_calibration_json(self):
        if self.is_running:
            return
        fpath = filedialog.askopenfilename(
            title="Kalibrációs Profil Betöltése",
            filetypes=[("JSON Profil Fájl", "*.json"), ("Minden fájl", "*.*")]
        )
        if not fpath:
            return
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_profile_dict(data)
            if self.saved_geometry:
                g = self.saved_geometry
                self.log(
                    f"📂 Profil betöltve: {os.path.basename(fpath)} | "
                    f"ROI=({g['rx']},{g['ry']},{g['rw']}x{g['rh']}), Kapuk=({g['left_gate_x']}..{g['right_gate_x']} px)"
                )
            else:
                self.log(f"📂 Profil betöltve (geometria nélkül): {os.path.basename(fpath)}")
        except Exception as e:
            messagebox.showerror("Betöltési hiba", f"Hibás vagy sérült JSON profil:\n{e}")

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
            self.progress_lbl.config(text=f"Készültség: {self.completed_videos} / {total} videó ({pct:.0f}%)")
        self.root.after(0, _inc)

    def browse_videos(self):
        files = filedialog.askopenfilenames(
            title="Videók kiválasztása",
            filetypes=[("Videó fájlok", "*.mp4 *.mov *.avi *.mkv"), ("Minden fájl", "*.*")]
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
            self.tree.insert("", "end", iid=uid, values=(fname, suggested_id, "Várakozik", fpath))
            added += 1

        self.log(f"Hozzáadva {added} db új videó. (Összesen: {len(self.video_data)} db)")
        self.progress_lbl.config(text=f"Készültség: 0 / {len(self.video_data)} videó")

    def remove_selected_video(self):
        if self.is_running:
            return
        sel = self.tree.selection()
        if not sel:
            return
        uid = sel[0]
        self.tree.delete(uid)
        self.video_data = [v for v in self.video_data if v["uid"] != uid]
        self.progress_lbl.config(text=f"Készültség: 0 / {len(self.video_data)} videó")

    def clear_videos(self):
        if self.is_running:
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.video_data.clear()
        self.progress_bar["value"] = 0
        self.progress_lbl.config(text="Készültség: 0 / 0 videó")
        self.log("Videólista ürítve.")

    def edit_animal_id(self, event):
        if self.is_running:
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Tipp", "Előbb jelölj ki egy sort a táblázatban!")
            return

        uid = sel[0]
        current_values = self.tree.item(uid, "values")

        top = tk.Toplevel(self.root)
        top.title("Egyed Azonosító (ID) Módosítása")
        top.geometry("360x160")
        top.configure(bg="#FFFFFF")
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()

        tk.Label(top, text=f"Fájl: {current_values[0]}", bg="#FFFFFF", fg="#475569", font=(self.ui_font, 9)).pack(pady=(12, 2))
        tk.Label(top, text="Add meg az Egyed új azonosítóját:", bg="#FFFFFF", fg="#0F172A", font=(self.ui_font, 10, "bold")).pack(pady=2)

        entry = ttk.Entry(top, font=(self.ui_font, 11), justify="center")
        entry.pack(pady=6, padx=30, fill="x")
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
                self.log(f"Azonosító módosítva: {current_values[0]} -> Egyed #{new_id}")
            top.destroy()

        entry.bind("<Return>", save_id)
        ttk.Button(top, text="Mentés (Enter)", command=save_id, style="Success.TButton").pack(pady=6)

    def open_results_folder(self):
        folder = os.path.abspath(".")
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception:
            messagebox.showinfo("Mappa helye", f"Az eredmények ide kerülnek:\n{folder}")

    def start_workflow(self):
        if not self.video_data:
            messagebox.showerror("Hiányzó videók", "Kérlek, előbb adj hozzá legalább egy videót a listához!")
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
            messagebox.showerror("Hiányzó videók", "Kérlek, előbb adj hozzá legalább egy videót a listához!")
            return
        if not self.saved_geometry:
            messagebox.showwarning("Nincs mentett geometria", "Előbb tölts be egy JSON profilt vagy végezz egy kalibrációt!")
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
        use_umat=False, u_base_gray=None, u_inv_ladder=None
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

            raw_mask = cv2.bitwise_and(diff_mask, dark_mask, dst=diff_mask)
            cv2.bitwise_and(raw_mask, inv_ladder_mask, dst=raw_mask)

            clean_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, self.kernel_small)
            cv2.morphologyEx(clean_mask, cv2.MORPH_CLOSE, self.kernel_horiz, dst=clean_mask)
            cv2.dilate(clean_mask, self.kernel_small, dst=clean_mask, iterations=1)
            cv2.bitwise_and(clean_mask, inv_ladder_mask, dst=clean_mask)

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
                        if cx < min_x:
                            min_x = cx
                        if cy < min_y:
                            min_y = cy
                        if cx + cw > max_x:
                            max_x = cx + cw
                        if cy + ch > max_y:
                            max_y = cy + ch

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
        cv2.bitwise_and(diff_mask, dark_mask, dst=diff_mask)
        cv2.bitwise_and(diff_mask, sub_inv_lad, dst=diff_mask)
        return cv2.countNonZero(diff_mask) > 320

    def _check_real_dip_below_line(self, final_mouse_mask, fault_y_local):
        if fault_y_local >= final_mouse_mask.shape[0]:
            return False, 0, 0

        below_zone = final_mouse_mask[fault_y_local:, :]
        if cv2.countNonZero(below_zone) < 28:
            return False, 0, 0

        sub_contours, _ = cv2.findContours(below_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for sc in sub_contours:
            if cv2.contourArea(sc) >= 28:
                pts = sc.reshape(-1, 2)
                max_idx = np.argmax(pts[:, 1])
                dip_x_local = int(pts[max_idx, 0])
                dip_y_local = fault_y_local + int(pts[max_idx, 1])
                return True, dip_x_local, dip_y_local

        return False, 0, 0

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
            if 0 <= dx < w and 0 <= dy < h:
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
                b_c = 0
                g_c = int(255 * r_norm)
                r_c = 255
            else:
                r_norm = (ratio - 0.5) * 2.0
                b_c = 0
                g_c = 255
                r_c = int(255 * (1.0 - r_norm))

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
        cv2.putText(result, "Utvonal:", (leg_x, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(result, "LASSU (Piros)", (leg_x + 75, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 50, 255), 2)
        cv2.putText(result, "->", (leg_x + 190, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1)
        cv2.putText(result, "GYORS (Zold)", (leg_x + 215, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 255, 50), 2)

        return result

    def setup_and_run_parallel(self):
        first_video = self.video_data[0]["path"]
        cap = open_video_accelerated(first_video, use_hw=self.var_use_gpu.get())
        if not cap.isOpened():
            messagebox.showerror("Hiba", "Nem sikerült megnyitni az első videót!")
            self.reset_ui()
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ret, first_frame = cap.read()
        if not ret:
            cap.release()
            messagebox.showerror("Hiba", "Nem sikerült beolvasni az első képkockát!")
            self.reset_ui()
            return

        frame_h, frame_w = first_frame.shape[:2]

        self.log("1. LÉPÉS: Jelöld ki a vizsgálandó területet (egér hátától a lenyúlás határig), majd nyomj ENTER-t.")
        guide_img = first_frame.copy()
        cv2.putText(
            guide_img, "1. Jelold ki a letrat es a feher peremet alatta -> Nyomj ENTER-t",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
        )
        roi = cv2.selectROI("1. Terulet Kijelolese (ENTER = Tovabb)", guide_img, showCrosshair=True)
        close_opencv_windows()

        rx, ry, rw, rh = [int(v) for v in roi]
        if rw == 0 or rh == 0:
            rx, ry, rw, rh = 0, 0, frame_w, frame_h

        gate_clicks = []
        temp_img = first_frame.copy()
        cv2.rectangle(temp_img, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 2)
        cv2.putText(
            temp_img, "2. Kattints a BAL (Start) majd a JOBB (Cel) piros filctoll vonalra!",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
        )

        win_gate = "2. Start es Cel Kapuk Kijelolese (2 kattintas)"

        def gate_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                gate_clicks.append(x)
                cv2.line(temp_img, (x, ry), (x, ry + rh), (0, 0, 255), 2)
                cv2.imshow(win_gate, temp_img)

        self.log("2. LÉPÉS: Kattints a BAL (Start), majd a JOBB (Cél) kapura!")
        cv2.imshow(win_gate, temp_img)
        cv2.setMouseCallback(win_gate, gate_callback)

        while len(gate_clicks) < 2:
            key = cv2.waitKey(50) & 0xFF
            if key == 27 or key == ord('q'):
                break
        close_opencv_windows()

        if len(gate_clicks) < 2:
            cap.release()
            self.log("Kapuk kijelölése megszakítva.")
            self.reset_ui()
            return

        left_gate_x = min(gate_clicks[0], gate_clicks[1])
        right_gate_x = max(gate_clicks[0], gate_clicks[1])

        self.log("3. LÉPÉS: KÉK = Kimaszkolt létrafokok, ZÖLD = Egér. Nyomj ENTER-t az indításhoz!")
        base_gray = self._compute_clean_background(cap, rx, ry, rw, rh, num_samples=16)

        win_calib = "3. Elo Kalibracio (KEK = Kizart Letra, ZOLD = Eger) - ENTER = Inditas"
        cv2.namedWindow(win_calib, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_calib, min(1150, frame_w), min(780, frame_h + 120))

        def nothing(val):
            pass

        start_preview_frame = 690 if total_frames > 700 else min(30, max(0, total_frames - 1))

        cv2.createTrackbar("Kepkocka", win_calib, start_preview_frame, max(1, total_frames - 1), nothing)
        cv2.createTrackbar("Vilagossag (Orr)", win_calib, self.calib_dark_thresh, 220, nothing)
        cv2.createTrackbar("Elmozdulas", win_calib, self.calib_diff_thresh, 100, nothing)
        cv2.createTrackbar("Letra Maszk", win_calib, self.calib_ladder_thresh, 220, nothing)
        cv2.createTrackbar("Piros vonal (%)", win_calib, self.calib_fault_Ratio, 98, nothing)

        last_track_frame = -1
        current_calib_frame = first_frame.copy()

        while True:
            f_idx = cv2.getTrackbarPos("Kepkocka", win_calib)
            dark_t = max(40, cv2.getTrackbarPos("Vilagossag (Orr)", win_calib))
            diff_t = max(5, cv2.getTrackbarPos("Elmozdulas", win_calib))
            ladder_t = max(30, cv2.getTrackbarPos("Letra Maszk", win_calib))
            fault_pct = max(20, cv2.getTrackbarPos("Piros vonal (%)", win_calib))

            if f_idx != last_track_frame:
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                r, f_read = cap.read()
                if r:
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

            if self.var_enable_zones.get():
                z_w = (right_gate_x - left_gate_x) / 3.0
                z1_x = int(left_gate_x + z_w)
                z2_x = int(left_gate_x + 2 * z_w)
                cv2.line(disp, (z1_x, ry), (z1_x, ry + rh), (200, 200, 0), 1)
                cv2.line(disp, (z2_x, ry), (z2_x, ry + rh), (200, 200, 0), 1)
                cv2.putText(disp, "START", (left_gate_x + 10, ry + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 2)
                cv2.putText(disp, "KOZEP", (z1_x + 10, ry + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 2)
                cv2.putText(disp, "CEL", (z2_x + 10, ry + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 2)

            if detected and bbox is not None and mask is not None:
                bx, by, bw, bh = bbox
                cv2.rectangle(disp, (rx + bx, ry + by), (rx + bx + bw, ry + by + bh), (0, 255, 0), 2)

                is_dip, dip_x_loc, dip_y_loc = self._check_real_dip_below_line(mask, fault_y_local)
                if is_dip:
                    cv2.circle(disp, (rx + dip_x_loc, ry + dip_y_loc), 12, (0, 0, 255), 3)
                    cv2.putText(
                        disp, "VALODI ORR/LAB LENYULAS!", (rx + bx, max(30, ry + by - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
                    )

            cv2.rectangle(disp, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 2)
            cv2.line(disp, (left_gate_x, ry), (left_gate_x, ry + rh), (255, 0, 0), 2)
            cv2.line(disp, (right_gate_x, ry), (right_gate_x, ry + rh), (255, 0, 0), 2)
            cv2.putText(
                disp, "KEK = Kimaszkolt letrafokok | ZOLD = Eger | Nyomj ENTER-t az inditashoz!",
                (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2
            )

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
                self.log("Kalibráció megszakítva.")
                self.reset_ui()
                return

        close_opencv_windows()
        cap.release()

        self.saved_geometry = {
            "rx": rx, "ry": ry, "rw": rw, "rh": rh,
            "left_gate_x": left_gate_x, "right_gate_x": right_gate_x
        }
        try:
            with open("utolso_kalibracio.json", "w", encoding="utf-8") as f:
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
            self.var_use_gpu.get()
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
         dip_cooldown_sec, dip_min_dist_px, gate_dist_cm, px_per_cm, frame_stride, use_gpu) = roi_data

        cv2.ocl.setUseOpenCL(bool(use_gpu and self.gpu_available))

        self.log(
            f"\n---> TURBO Elemzés elindítva {max_workers} szálon "
            f"(Lépésköz={frame_stride}, GPU/Async={'BE' if use_gpu else 'KI'}) | "
            f"Skála: {px_per_cm:.2f} px/cm | Refrakter idő: {dip_cooldown_sec:.2f}s"
        )

        def process_single_video(item):
            if not self.is_running:
                return

            uid = item["uid"]
            video_path = item["path"]
            video_name = item["name"]
            animal_id = item["id"]

            self.update_row_status(uid, "Háttér és létra-maszk...")

            safe_id = "".join(c for c in animal_id if c.isalnum() or c in ('-', '_')) or "1"
            output_dir = f"Egyed_{safe_id}_eredmenyek"

            fault_y_local = int(rh * (fault_pct / 100.0))
            zone_width = (right_gate_x - left_gate_x) / 3.0
            z1_boundary = left_gate_x + zone_width
            z2_boundary = left_gate_x + 2.0 * zone_width

            cap = open_video_accelerated(video_path, use_hw=use_gpu)
            if not cap.isOpened():
                self.update_row_status(uid, "Hiba (Nem nyitható)")
                self.increment_progress(total_videos)
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps <= 0:
                fps = 30.0

            ret, first_frame = cap.read()
            if not ret:
                cap.release()
                self.update_row_status(uid, "Hiba (Üres videó)")
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
                self.update_row_status(uid, "Hiba (Háttér)")
                self.increment_progress(total_videos)
                return

            ladder_mask = self._create_ladder_mask(base_gray, ladder_t)
            inv_ladder_mask = cv2.bitwise_not(ladder_mask)

            use_umat_for_roi = bool(use_gpu and self.gpu_available and (v_rw * v_rh >= 90000))
            u_base_gray = cv2.UMat(base_gray) if use_umat_for_roi else None
            u_inv_ladder = cv2.UMat(inv_ladder_mask) if use_umat_for_roi else None

            start_x1_loc = max(0, (left_gate_x - 110) - v_rx)
            start_x2_loc = min(v_rw, (left_gate_x + 190) - v_rx)

            self.update_row_status(uid, "Elemzés folyamatban...")
            self.log(f"Feldolgozás alatt: {video_name} (Egyed #{animal_id})")

            master_roi_canvas = np.full((v_rh, v_rw, 3), 255, dtype=np.uint8)
            current_run_roi = np.full((v_rh, v_rw, 3), 255, dtype=np.uint8)

            state = None

            def set_state(new_state, sec_val=0.0, detail=""):
                nonlocal state
                if state != new_state:
                    state = new_state
                    extra = f" — {detail}" if detail else ""
                    self.log(f"   [{video_name} | Egyed #{animal_id}] STATE -> {new_state} ({sec_val:.2f}s){extra}")
                    self.update_row_status(uid, f"{new_state} ({sec_val:.1f}s)")

            set_state("WAIT_FOR_LEFT_START", 0.0, "Várakozás az egér belépésére a bal (Start) kapunál...")

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
                    use_umat=use_umat_for_roi, u_base_gray=u_base_gray, u_inv_ladder=u_inv_ladder
                )

                mouse_x_global = None
                mouse_y_center_global = None
                mouse_y_top_global = v_ry
                if mouse_detected and bbox is not None:
                    x_c, y_c, w_c, h_c = bbox
                    mouse_x_global = v_rx + x_c + (w_c // 2)
                    mouse_y_center_global = v_ry + y_c + (h_c // 2)
                    mouse_y_top_global = v_ry + y_c

                if state == "WAIT_FOR_LEFT_START":
                    if mouse_detected and (left_gate_x - 100 <= mouse_x_global <= left_gate_x + 180):
                        run_count += 1
                        set_state("RUNNING", current_sec, f"Belépés észlelve! Futás #{run_count} követése...")
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

                        is_dip, dip_x_loc, dip_y_loc = self._check_real_dip_below_line(final_mouse_mask, fault_y_local)
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
                                    "frame": frame.copy(),
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
                                    "clean_canvas": full_clean_canvas,
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
                                    f"   ✔ [Egyed #{animal_id}] Futás #{run_count} KÉSZ: "
                                    f"Idő={transit_time:.2f}s | Lenyúlás={len(dip_events)} db | "
                                    f"Sebesség={avg_speed_cm_s:.1f} cm/s ({avg_speed_px_s:.0f} px/s)"
                                )

                            set_state("COOLDOWN", current_sec, f"Futás #{run_count} elérte a célkaput, várakozás a pálya ürülésére...")
                            cooldown_sec_accum = 0.0

                        elif (current_sec - start_time) > 1.5 and mouse_x_global < left_gate_x - 80:
                            run_count -= 1
                            set_state("COOLDOWN", current_sec, "Az egér visszafordult a bal kapu mögé, futás elvetve...")
                            cooldown_sec_accum = 0.0
                    else:
                        if (current_sec - last_seen_time) > 2.0:
                            set_state("WAIT_FOR_LEFT_START", current_sec, "Az egér 2 mp-e eltűnt a képről, visszaállás alaphelyzetbe...")

                elif state == "COOLDOWN":
                    step_sec = frame_stride / fps
                    if not mouse_detected:
                        cooldown_sec_accum += step_sec
                        if cooldown_sec_accum >= 1.0:
                            set_state("WAIT_FOR_LEFT_START", current_sec, "Pálya tiszta, várakozás a következő bal oldali indulásra...")
                    else:
                        cooldown_sec_accum = 0.0
                        if mouse_x_global is not None and mouse_x_global <= left_gate_x + 50:
                            set_state("WAIT_FOR_LEFT_START", current_sec, "Egér ismét a bal kapunál, felkészülés új futásra...")

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
                    "first_frame": first_frame,
                    "faded_bg_template": faded_bg_template,
                    "master_white_canvas": master_white_canvas,
                    "roi_data": roi_data,
                    "runs": video_runs_list
                })

            self.update_row_status(uid, f"Feldolgozva ({len(video_runs_list)} futás)")
            self.increment_progress(total_videos)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(process_single_video, video_data)

        if self.is_running and self.pending_results:
            if self.var_dlc_superanimal.get():
                self.dlc_addon.classify_dips_with_superanimal(self.pending_results)
            if self.var_dlc_export_train.get():
                self.dlc_addon.export_training_dataset(self.pending_results)

        total_dips_found = sum(len(r["dips"]) for res in self.pending_results for r in res["runs"])
        if self.is_running and self.var_enable_review.get() and total_dips_found > 0:
            self.log(f"\n---> Detektálás kész ({total_dips_found} db lenyúlás). Felülvizsgáló ablak megnyitása...")
            self.root.after(0, self.open_review_window)
        else:
            self.root.after(0, self.finalize_and_export_all)

    def open_review_window(self):
        rev_win = tk.Toplevel(self.root)
        rev_win.title("Lenyúlások Felülvizsgálata + AI Testrész-Osztályozó (Gyorsgombos szerkesztő)")
        rev_win.geometry("1120x740")
        rev_win.configure(bg="#F3F4F6")
        rev_win.transient(self.root)
        rev_win.grab_set()
        rev_win.lift()
        rev_win.focus_force()

        top_banner = tk.Frame(rev_win, bg="#1E293B", padx=15, pady=10)
        top_banner.pack(fill="x")
        tk.Label(
            top_banner,
            text="GYORSGOMBOK:  [↑/↓ vagy A/D] Léptetés  |  [SPACE / X] Piros kör Ki/Be  |  [T] Testrész váltás (Mancs/Orr/Farok)  |  [S] Képmentés  |  [ENTER] Mentés",
            bg="#1E293B", fg="#38BDF8", font=(self.ui_font, 9, "bold")
        ).pack(anchor="w")

        body = tk.Frame(rev_win, bg="#F3F4F6", padx=15, pady=10)
        body.pack(fill="both", expand=True)

        left_panel = tk.LabelFrame(
            body, text=" Észlelt Lenyúlások és AI Testrész-Osztályozás ", font=(self.ui_font, 10, "bold"),
            bg="#FFFFFF", fg="#0F172A", padx=8, pady=8
        )
        left_panel.pack(side="left", fill="y", padx=(0, 10))

        cols = ("ego", "run", "sec", "part", "valid", "save")
        dip_tree = ttk.Treeview(left_panel, columns=cols, show="headings", height=18, selectmode="browse")
        dip_tree.heading("ego", text="Egyed")
        dip_tree.heading("run", text="Futás")
        dip_tree.heading("sec", text="Idő (mp)")
        dip_tree.heading("part", text="AI Testrész [T]")
        dip_tree.heading("valid", text="Piros kör?")
        dip_tree.heading("save", text="Külön kép?")

        dip_tree.column("ego", width=60, anchor="center")
        dip_tree.column("run", width=55, anchor="center")
        dip_tree.column("sec", width=70, anchor="center")
        dip_tree.column("part", width=135, anchor="center")
        dip_tree.column("valid", width=80, anchor="center")
        dip_tree.column("save", width=80, anchor="center")
        dip_tree.pack(side="left", fill="y")

        sb = ttk.Scrollbar(left_panel, orient="vertical", command=dip_tree.yview)
        sb.pack(side="right", fill="y")
        dip_tree.configure(yscrollcommand=sb.set)

        right_panel = tk.LabelFrame(
            body, text=" Kamera Képkocka Előnézet és Gyorsműveletek ", font=(self.ui_font, 10, "bold"),
            bg="#FFFFFF", fg="#0F172A", padx=12, pady=10
        )
        right_panel.pack(side="left", fill="both", expand=True)

        img_label = tk.Label(right_panel, bg="#0F172A", text="Válassz egy lenyúlást a bal oldali listából!", fg="white")
        img_label.pack(fill="both", expand=True, pady=(0, 10))

        ctrl_box = tk.Frame(right_panel, bg="#FFFFFF")
        ctrl_box.pack(fill="x")

        var_valid = tk.BooleanVar(value=True)
        var_save = tk.BooleanVar(value=False)

        dip_lookup = {}
        ordered_iids = []
        item_counter = 0
        for res in self.pending_results:
            for r in res["runs"]:
                for d_idx, d in enumerate(r["dips"], start=1):
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
                            "IGEN" if d["valid"] else "TÖRÖLVE",
                            "Mentés" if d["save_crop"] else "Nem"
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

            disp = d["frame"].copy()
            cv2.line(disp, (rx, fault_y_glob), (rx + rw, fault_y_glob), (0, 0, 255), 2)

            part_str = d.get("dlc_part", "MANCS (Lábhiba)")
            if d["valid"]:
                cv2.circle(disp, (d["x"], d["y"]), 18, (0, 0, 255), 3)
                status_str = f"ERVENYES ({d['sec']:.2f}s) -> [{part_str}]"
                if d["save_crop"]:
                    status_str += " [KEPMENTES]"
                cv2.putText(
                    disp, status_str,
                    (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
                )
            else:
                cv2.putText(
                    disp, f"PIROS KOR TOROLVE ({d['sec']:.2f}s) [{part_str}]",
                    (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (128, 128, 128), 2
                )

            h_orig, w_orig = disp.shape[:2]
            target_w = 560
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
                    "IGEN" if d["valid"] else "TÖRÖLVE",
                    "Mentés" if d["save_crop"] else "Nem"
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

        chk_v = tk.Checkbutton(
            ctrl_box, text="✔ Érvényes lenyúlás [SPACE / X]",
            variable=var_valid, command=on_toggle_checkboxes, bg="#FFFFFF", fg="#991B1B",
            font=(self.ui_font, 10, "bold"), anchor="w"
        )
        chk_v.pack(fill="x", pady=2)

        chk_s = tk.Checkbutton(
            ctrl_box, text="💾 Külön pillanatkép (.jpg) mentése erről a lenyúlásról [S / M]",
            variable=var_save, command=on_toggle_checkboxes, bg="#FFFFFF", fg="#1E3A8A",
            font=(self.ui_font, 10), anchor="w"
        )
        chk_s.pack(fill="x", pady=2)

        quick_btn_row = tk.Frame(ctrl_box, bg="#F8FAFC", pady=6)
        quick_btn_row.pack(fill="x", pady=(6, 0))

        ttk.Button(
            quick_btn_row, text="◀ Előző [↑/A]", command=lambda: step_selection(-1), style="Neutral.TButton"
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            quick_btn_row, text="Következő [↓/D] ▶", command=lambda: step_selection(1), style="Neutral.TButton"
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            quick_btn_row, text="⭕ Ki/Be [Space]", command=hotkey_toggle_valid, style="SoftRed.TButton"
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            quick_btn_row, text="🐾 Testrész Váltás [T]", command=hotkey_cycle_part, style="SoftGrn.TButton"
        ).pack(side="left", padx=(0, 6))

        ttk.Button(
            quick_btn_row, text="💾 Képmentés [S]", command=hotkey_toggle_save, style="SoftBlu.TButton"
        ).pack(side="left")

        dip_tree.bind("<<TreeviewSelect>>", on_select)
        if ordered_iids:
            dip_tree.selection_set(ordered_iids[0])
            dip_tree.focus(ordered_iids[0])
            on_select()

        bottom_bar = tk.Frame(rev_win, bg="#F3F4F6", padx=15, pady=10)
        bottom_bar.pack(fill="x")

        def confirm_and_close(event=None):
            rev_win.destroy()
            self.finalize_and_export_all()

        rev_win.bind("<Up>", lambda e: (step_selection(-1), "break")[1])
        rev_win.bind("<Down>", lambda e: (step_selection(1), "break")[1])
        rev_win.bind("<Left>", lambda e: (step_selection(-1), "break")[1])
        rev_win.bind("<Right>", lambda e: (step_selection(1), "break")[1])
        rev_win.bind("<a>", lambda e: step_selection(-1))
        rev_win.bind("<A>", lambda e: step_selection(-1))
        rev_win.bind("<d>", lambda e: step_selection(1))
        rev_win.bind("<D>", lambda e: step_selection(1))

        rev_win.bind("<space>", hotkey_toggle_valid)
        rev_win.bind("<Delete>", hotkey_toggle_valid)
        rev_win.bind("<BackSpace>", hotkey_toggle_valid)
        rev_win.bind("<x>", hotkey_toggle_valid)
        rev_win.bind("<X>", hotkey_toggle_valid)

        rev_win.bind("<t>", hotkey_cycle_part)
        rev_win.bind("<T>", hotkey_cycle_part)

        rev_win.bind("<s>", hotkey_toggle_save)
        rev_win.bind("<S>", hotkey_toggle_save)
        rev_win.bind("<m>", hotkey_toggle_save)
        rev_win.bind("<M>", hotkey_toggle_save)

        rev_win.bind("<Return>", confirm_and_close)

        ttk.Button(
            bottom_bar, text="✔  Felülvizsgálat Befejezése és Eredmények Mentése [ENTER]",
            command=confirm_and_close, style="Success.TButton"
        ).pack(side="right")

        rev_win.protocol("WM_DELETE_WINDOW", confirm_and_close)

    def finalize_and_export_all(self):
        if not self.pending_results:
            self.reset_ui()
            return

        master_csv = "Minden_Egyed_Meresi_Adatai.csv"
        sample_roi = self.pending_results[0]["roi_data"]
        enable_zones = sample_roi[10]
        enable_kinematics = sample_roi[11]

        csv_headers = [
            'Egyed_ID', 'Video_Fajl', 'Futas_Sorszam',
            'Belepesi_Ido_mp', 'Kilepesi_Ido_mp',
            'Teljes_Athaladasi_Ido_mp', 'Netto_Mozgasi_Ido_mp',
            'Melynyulasok_Szama', 'Mancs_Labhiba_Db', 'Orr_Lenezes_Db', 'Hatso_Farok_Db',
            'Melynyulasok_Idopontjai_mp',
            'Megallasok_Szama', 'Megallasok_OsszIdeje_mp', 'Megallasok_Intervallumai_Tol_Ig'
        ]

        if enable_kinematics:
            csv_headers.extend([
                'Skala_px_per_cm',
                'Megtett_Ut_cm', 'Atlagsebesseg_cm_mp', 'Max_Sebesseg_cm_mp',
                'Megtett_Ut_px', 'Atlagsebesseg_px_mp', 'Max_Sebesseg_px_mp'
            ])

        if enable_zones:
            csv_headers.extend([
                'Start_Zona_Ido_mp', 'Start_Lenyulas_Db', 'Start_Megallas_Db',
                'Kozep_Zona_Ido_mp', 'Kozep_Lenyulas_Db', 'Kozep_Megallas_Db',
                'Cel_Zona_Ido_mp', 'Cel_Lenyulas_Db', 'Cel_Megallas_Db'
            ])

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
            first_frame = res["first_frame"]
            faded_bg_template = res["faded_bg_template"]
            master_white_canvas = res["master_white_canvas"]
            roi_data = res["roi_data"]
            runs = res["runs"]

            (rx, ry, rw, rh, left_gate_x, right_gate_x, _, _,
             _, fault_pct, z_active, kin_active, _, _, gate_dist_cm, px_per_cm, _, _) = roi_data

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
                clean_canvas = r["clean_canvas"].copy()
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
                        snap = d["frame"].copy()
                        cv2.line(snap, (rx, ry + fault_y_local), (rx + rw, ry + fault_y_local), (0, 0, 255), 1)
                        cv2.circle(snap, (d["x"], d["y"]), 16, (0, 0, 255), 3)
                        part_lbl = d.get("dlc_part", "")
                        cv2.putText(
                            snap,
                            f"Egyed #{animal_id} | Futas #{run_count} | Lenyulas #{idx_pt} ({d['sec']:.2f}s) [{part_lbl}]",
                            (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
                        )
                        snap_path = os.path.join(
                            output_dir, f"egyed_{safe_id}_futas_{run_count}_lenyulas_{idx_pt}.jpg"
                        )
                        save_image_unicode(snap_path, snap)

                zone_dips = [0, 0, 0]
                zone_freezes = [0, 0, 0]
                if z_active:
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
                    if freeze_events else "Nincs"
                )
                dip_times_str = (
                    ", ".join(f"{d['sec']:.2f}s[{d.get('dlc_code', 'PAW')}]" for d in valid_dips)
                    if valid_dips else "Nincs"
                )

                run_with_faded_ladder = np.minimum(faded_bg_template, clean_canvas)

                if z_active:
                    cv2.line(run_with_faded_ladder, (int(z1_boundary), ry), (int(z1_boundary), ry + rh), (150, 150, 150), 1, cv2.LINE_AA)
                    cv2.line(run_with_faded_ladder, (int(z2_boundary), ry), (int(z2_boundary), ry + rh), (150, 150, 150), 1, cv2.LINE_AA)

                for idx_fr, (fs, fe, fd, fx, fy_top) in enumerate(freeze_events, start=1):
                    label_y = max(ry + 25, fy_top - 15 - ((idx_fr % 2) * 20))
                    cv2.line(run_with_faded_ladder, (fx, fy_top), (fx, label_y + 5), (0, 140, 255), 2)
                    cv2.putText(
                        run_with_faded_ladder,
                        f"Megallas #{idx_fr}: {fs:.2f}-{fe:.2f}s ({fd:.2f}s)",
                        (max(10, fx - 70), label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 120, 255), 2
                    )

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
                    f"Egyed #{animal_id} | Futas #{run_count} | "
                    f"Teljes: {transit_time:.2f}s | Netto: {net_moving_time:.2f}s | "
                    f"Seb: {r['avg_speed_cm_s']:.1f} cm/s"
                )
                info_line2 = (
                    f"Lenyulas: {dip_count} db (Mancs:{paw_faults}, Orr:{nose_peeks}) | "
                    f"Megallas: {freeze_count} db, ossz: {freeze_sec_total:.2f}s"
                )

                for canvas_img in (clean_canvas, run_with_faded_ladder):
                    cv2.putText(canvas_img, info_line1, (25, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 220), 2)
                    cv2.putText(canvas_img, info_line2, (25, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (180, 60, 0), 2)

                img_clean_path = os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_tiszta_{transit_time:.2f}s.jpg")
                img_faded_path = os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_halvany_{transit_time:.2f}s.jpg")
                save_image_unicode(img_clean_path, clean_canvas)
                save_image_unicode(img_faded_path, run_with_faded_ladder)

                if kin_active:
                    hm_title = (
                        f"Egyed #{animal_id} | Futas #{run_count} | "
                        f"Ut: {r['path_len_cm']:.1f}cm | Atlag: {r['avg_speed_cm_s']:.1f}cm/s"
                    )
                    hm_img = self._generate_heatmap_image(
                        first_frame, [trajectory], valid_dips, hm_title,
                        blend_alpha=0.48, draw_dip_circles_red=False
                    )
                    hm_path = os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_heatmap.jpg")
                    save_image_unicode(hm_path, hm_img)

                    faded_hm_img = self._generate_heatmap_image(
                        faded_base_for_hm, [trajectory], valid_dips, info_line1,
                        blend_alpha=0.42, draw_dip_circles_red=True
                    )
                    cv2.putText(faded_hm_img, info_line2, (25, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (180, 60, 0), 2)
                    faded_hm_path = os.path.join(
                        output_dir, f"egyed_{safe_id}_futas_{run_count}_halvany_heatmap_{transit_time:.2f}s.jpg"
                    )
                    save_image_unicode(faded_hm_path, faded_hm_img)

                row_data = [
                    str(animal_id), video_name, run_count,
                    f"{start_time:.2f}", f"{end_time:.2f}",
                    f"{transit_time:.2f}", f"{net_moving_time:.2f}",
                    dip_count, paw_faults, nose_peeks, hind_tails,
                    dip_times_str,
                    freeze_count, f"{freeze_sec_total:.2f}", freeze_intervals_str
                ]

                if kin_active:
                    row_data.extend([
                        f"{px_per_cm:.2f}",
                        f"{r['path_len_cm']:.2f}",
                        f"{r['avg_speed_cm_s']:.2f}",
                        f"{r['max_speed_cm_s']:.2f}",
                        f"{r['path_len_px']:.1f}",
                        f"{r['avg_speed_px_s']:.1f}",
                        f"{r['max_speed_px_s']:.1f}"
                    ])

                if z_active:
                    row_data.extend([
                        f"{zone_times[0]:.2f}", zone_dips[0], zone_freezes[0],
                        f"{zone_times[1]:.2f}", zone_dips[1], zone_freezes[1],
                        f"{zone_times[2]:.2f}", zone_dips[2], zone_freezes[2]
                    ])

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
                summary_title = f"Egyed #{animal_id} Osszesitett ({saved_runs_for_video} db futas) - {video_name}"
                cv2.putText(master_faded, summary_title, (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 0, 0), 2)
                master_img_path = os.path.join(output_dir, f"egyed_{safe_id}_OSSZESITETT_{saved_runs_for_video}_futas.jpg")
                save_image_unicode(master_img_path, master_faded)

                if kin_active:
                    master_hm_title = f"Egyed #{animal_id} OSSZESITETT Heatmap & Sebesseg ({saved_runs_for_video} futas)"
                    master_hm = self._generate_heatmap_image(
                        first_frame, all_video_trajectories, all_video_valid_dips, master_hm_title,
                        blend_alpha=0.48, draw_dip_circles_red=False
                    )
                    master_hm_path = os.path.join(output_dir, f"egyed_{safe_id}_OSSZESITETT_heatmap.jpg")
                    save_image_unicode(master_hm_path, master_hm)

                    master_faded_hm = self._generate_heatmap_image(
                        master_faded_clean, all_video_trajectories, all_video_valid_dips, master_hm_title,
                        blend_alpha=0.42, draw_dip_circles_red=True
                    )
                    master_faded_hm_path = os.path.join(output_dir, f"egyed_{safe_id}_OSSZESITETT_halvany_heatmap.jpg")
                    save_image_unicode(master_faded_hm_path, master_faded_hm)

            self.update_row_status(uid, f"Kész ({saved_runs_for_video} futás)")
            self.log(f"Mentve: {video_name} -> Egyed #{animal_id} ({saved_runs_for_video} érvényes futás)")

        self.log("\n==========================================")
        self.log("MINDEN FELDOLGOZÁS ÉS MENTÉS BEFEJEZŐDÖTT!")
        self.log(f"Közös táblázat frissítve: {os.path.abspath(master_csv)}")
        self.log("==========================================")
        self.reset_ui()

    def stop_analysis(self):
        self.is_running = False
        self.log("Leállítás kérve... A folyamatban lévő képkockák befejezése...")

    def reset_ui(self):
        self.is_running = False
        self.btn_start.config(state="normal")
        if self.saved_geometry is not None:
            self.btn_quick_start.config(state="normal")
        self.btn_stop.config(state="disabled")


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
        print("\nProgram szabályosan bezárva.")