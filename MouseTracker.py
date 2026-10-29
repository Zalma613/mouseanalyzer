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
APP_ID = "zalma.mouseanalyzer.pro.3.6"
APP_VERSION = "3.6"

# ==============================================================================
# RESOURCE PATH & NATIVE OS BRANDING
# ==============================================================================
def get_resource_path(relative_path):
    """Finds bundled resources (icon.ico, icon.icns, .pt models) in dev, cwd, and PyInstaller builds."""
    search_dirs = []
    if hasattr(sys, "_MEIPASS"):
        search_dirs.append(sys._MEIPASS)
    search_dirs.append(os.path.dirname(os.path.abspath(__file__)))
    search_dirs.append(os.getcwd())
    for base_path in search_dirs:
        candidate = os.path.join(base_path, relative_path)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def configure_native_os_identity():
    """Configures native OS app identity for taskbars and dock."""
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
    """Applies icon.ico or icon.icns to the Tkinter window and Dock."""
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
# SAFE WORKING DIRECTORY SETUP & HARDWARE ACCELERATION
# ==============================================================================
def setup_safe_working_directory(folder_name="MouseAnalyzer_Eredmenyek"):
    docs_dir = os.path.expanduser("~/Documents")
    if not os.path.exists(docs_dir):
        docs_dir = os.path.expanduser("~")
    safe_dir = os.path.join(docs_dir, folder_name)
    os.makedirs(safe_dir, exist_ok=True)
    if hasattr(sys, "_MEIPASS") or not os.access(os.getcwd(), os.W_OK):
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
        "subtitle": "Professzionális Létra Kinematikai és Viselkedéselemző Munkaállomás",
        "out_dir_prefix": "Kimeneti könyvtár:",
        "btn_change_dir": "Mappa választása",
        "btn_open_dir": "Eredmények megnyitása",
        "btn_settings": "⚙ Speciális beállítások",
        "kpi_videos": "BETÖLTÖTT FELVÉTELEK",
        "kpi_calib": "KALIBRÁCIÓS ÁLLAPOT",
        "kpi_engine": "DETEKTÁLÓ MOTOR",
        "kpi_dlc": "HARDVERES GYORSÍTÁS (GPU)",
        "kpi_vid_val": "{n} felvétel",
        "kpi_cal_none": "Automatikus (Adaptív)",
        "kpi_cal_active": "Rögzített ({w}×{h} px)",
        "sec1_title": "Munkaterület — Vizsgálati Felvételek és Kötegelt Sor",
        "btn_add_vid": "＋ Felvételek hozzáadása",
        "btn_edit_id": "✎ Egyed ID szerkesztése",
        "btn_remove_vid": "✕ Kijelölt eltávolítása",
        "btn_clear_vid": "Lista ürítése",
        "col_fname": "Fájlnév",
        "col_id": "Egyed ID",
        "col_status": "Feldolgozási állapot",
        "col_path": "Elérési útvonal",
        "status_waiting": "Sorban áll",
        "sec2_title": "Elemzési Paraméterek és Vezérlőpult",
        "sub_calib": "DETEKTÁLÁSI ÉS ELLENŐRZÉSI MODULOK",
        "sub_params": "KINEMATIKAI ÉS SZŰRÉSI PARAMÉTEREK",
        "sub_profile": "PROFIL KEZELÉS",
        "sub_exec": "ELEMZÉS INDÍTÁSA",
        "chk_rev": "Interaktív esemény-ellenőrző ablak megnyitása",
        "chk_auto_calib": "Automatikus adaptív létra- és alany-kalibráció",
        "chk_yolo_fusion": "YOLO + anatómiai 9-pontos csontváz illesztés",
        "chk_lock_lr": "Bal -> Jobb anatómiai tengely rögzítése (100% orr/farok pontosság)",
        "chk_bidirectional": "Kétirányú és teljes mozgáskövetés (100% lefedettség)",
        "chk_zones": "Pálya szektorokra bontása (Start / Közép / Cél)",
        "chk_kin": "Kinematikai számítások (cm/s) és sebesség-hőtérképek",
        "chk_gpu": "Hardveres gyorsítás (GPU dekódolás & UMat)",
        "chk_kalman": "Kálmán-szűrő és elasztikus létragörbület-követés",
        "chk_dlc_sa": "Anatómiai testrész-osztályozás (Láb vs. Orr vs. Farok)",
        "chk_dlc_exp": "Aktív tanítóképek (DLC / YOLO) kigyűjtése",
        "lbl_runs_target": "Futások száma (videó):",
        "lbl_threads": "Feldolgozó szálak:",
        "lbl_stride": "Képkocka-lépésköz:",
        "lbl_cooldown": "Refrakter idő (mp):",
        "lbl_mindist": "Min. távolság (px):",
        "lbl_gatecm": "Kaputávolság (cm):",
        "lbl_dec": "CSV tizedesjel:",
        "btn_load_prof": "Profil betöltése",
        "btn_save_prof": "Profil mentése",
        "btn_train_ai": "🧠 AI Tanítás & Előnézet",
        "tt_train_ai": "Interaktív előnézeti ablak megnyitása: egérminták ellenőrzése, kizárása és az AI modell betanítása.",
        "train_preview_title": "Rodent AI Tanítás & Adathalmaz Előnézet",
        "train_preview_banner": "Ellenőrizze az egér detektálási kereteket (BBox), anatómiai vázat és kizárhatja a nem megfelelő mintákat a betanítás előtt.",
        "lbl_sample_nav": "Minta navigáció:",
        "btn_prev_sample": "◀ Előző (←)",
        "btn_next_sample": "Következő (→) ▶",
        "btn_exclude_sample": "❌ Minta Kizárása (Szóköz)",
        "btn_include_sample": "✔ Minta Visszavétele",
        "btn_auto_clean": "🧹 Gyanúsak kizárása",
        "tt_auto_clean": "Automatikusan kizárja a határértéken lévő, homályos vagy kapuhoz közeli mintákat.",
        "btn_rescan_samples": "🔄 Újrakeresés",
        "lbl_ds_telemetry": "Adathalmaz Összegzés",
        "lbl_tot_samples": "Összes kinyert minta:",
        "lbl_act_samples": "Aktív tanító minta:",
        "lbl_excl_samples": "Kizárt minták száma:",
        "lbl_src_videos": "Forrásvideók száma:",
        "lbl_train_params": "Tréning Hiperparaméterek",
        "lbl_epochs": "Korszakok (Epochs):",
        "lbl_device": "Számítási eszköz:",
        "btn_start_training": "🚀 AI Betanítás Indítása",
        "btn_test_model": "🔍 Betanított Modell Tesztelése",
        "lbl_training_prog": "Tréning folyamat:",
        "chk_zoom_rodent": "Egérre zoomolt nézet",
        "chk_show_ai": "AI detektálás mutatása",
        "status_harvesting": "Minták gyűjtése a videókból...",
        "status_ready": "Minták betöltve! Ellenőrizze a detektálásokat, majd indítsa a betanítást.",
        "status_training": "YOLOv8 egér detektor betanítása folyamatban...",
        "status_train_success": "✅ Betanítás sikeres! Új modell mentve és aktiválva: rodent_detector.pt",
        "status_train_fail": "❌ A betanítás sikertelen volt. Ellenőrizze a naplót!",
        "btn_start": "▶   Kalibrálás és Elemzés Indítása",
        "btn_quick": "▶▶  Gyors Indítás (Előnézet nélkül)",
        "btn_stop": "■   Leállítás",
        "prog_idle": "Rendszerállapot: Kész  |  Feldolgozva: {done} / {total} felvétel",
        "prog_run": "Rendszerállapot: Feldolgozás folyamatban  |  {done} / {total} felvétel ({pct:.0f}%)",
        "sec3_title": "Folyamatállapot, Telemetria és Eseménynapló",
        "msg_no_vid_title": "Hiányzó felvételek",
        "msg_no_vid_body": "Az elemzés indítása előtt adjon hozzá legalább egy videófájlt a listához.",
        "msg_select_row": "Kérjük, előbb jelöljön ki egy sort a táblázatban.",
        "edit_id_title": "Egyed Azonosító (ID) Módosítása",
        "edit_id_prompt": "Új egyed-azonosító megadása:",
        "btn_save_enter": "Alkalmaz (Enter)",
        "settings_title": "Részletes Elemzési és Hardver Beállítások",
        "btn_close_settings": "Alkalmaz és bezárás",
        "tt_add_vid": "Videófájlok (.mp4, .avi, .mov, .mkv) hozzáadása a kötegelt feldolgozási sorhoz.",
        "tt_edit_id": "A kijelölt felvétel Egyed ID-jának módosítása (Enter gomb, dupla kattintás vagy gomb).",
        "tt_remove_vid": "A kijelölt felvétel eltávolítása a munkaterületről.",
        "tt_clear_vid": "A teljes felvétellista ürítése.",
        "tt_auto_calib": "Automatikusan detektálja a létrát, kapukat, létragörbületet és optimális paramétereket.",
        "tt_yolo": "YOLO objektumdetekció és 9-pontos anatómiai csontváz illesztés.",
        "tt_rev": "Az elemzés végén nagyítható ellenőrző ablakot nyit meg az események áttekintéséhez.",
        "tt_gatecm": "A Start és Cél kapu közötti fizikai távolság centiméterben a valós sebességszámításhoz.",
        "tt_settings": "Hardveres szálak, képkocka-lépésköz, GPU gyorsítás és CSV formátum beállítása.",
        "tt_start": "Interaktív vizuális előnézetben ellenőrizheti a kapukat és a létrát, majd elindítja a mérést.",
        "tt_quick": "Előnézeti ablak nélkül, azonnal elindítja az elemzést adaptív paraméterekkel.",
        "tt_stop": "Azonnal megszakítja az aktív elemző szálakat.",
        "tt_change_dir": "A kimeneti CSV fájlok és hőtérképek célkönyvtárának módosítása.",
        "tt_open_dir": "Az eredmények mappájának megnyitása a fájlkezelőben.",
        "tt_train_ai": "Egyedi 9-pontos YOLOv8-Pose modell (mouse_pose_ai.pt) automatikus tanítása a videókból.",
        "review_title": "Kinematikai Esemény-Ellenőrző Munkaállomás",
        "review_banner_help": "Navigáció: [↑]/[↓] vagy [A]/[D] | Érvényesség: [Szóköz] | Testrész: [T] | Képkivágás mentése: [S] | Zoom: [Z] / [R] | Exportálás: [Enter]",
        "events_table_title": "Detektált Események Listája",
        "inspector_canvas_title": "Létra és Alany Részletes Előnézet",
        "btn_prev": "◀ Előző (A)",
        "btn_next": "Következő (D) ▶",
        "btn_toggle_valid": "Érvényesség váltása [Szóköz]",
        "btn_cycle_part": "Testrész váltása [T]",
        "btn_toggle_crop": "Képkivágás mentése [S]",
        "btn_confirm_export": "✔ Jóváhagyás & Exportálás (Enter)",
        "col_rev_id": "Alany ID",
        "col_rev_run": "Futás",
        "col_rev_sec": "Időpont",
        "col_rev_part": "Testrész [T]",
        "col_rev_valid": "Állapot",
        "col_rev_save": "Kép [S]",
        "val_valid": "ÉRVÉNYES",
        "val_ignored": "KIZÁRVA",
        "val_yes": "Igen",
        "val_no": "Nem",
        "btn_close": "Bezárás",
        "btn_cancel": "Mégse (Esc)",
        "app_window_title": "{app_name} v{version} — Tudományos Kinematikai és Viselkedéselemző Munkaállomás",
        "preview_inspector_title": "Adathalmaz és Detektálási Előnézet",
        "preview_trainer_title": "AI Modell Betanító Központ",
        "badge_queue": "FELVÉTELEK",
        "badge_controls": "VEZÉRLÉS",
        "badge_log": "ÁLLAPOT & NAPLÓ",
        "badge_inspector": "ELŐNÉZET",
        "badge_trainer": "TRÉNING",
        "badge_events": "ESEMÉNYEK",
        "lbl_sample_counter": "Minta: {cur} / {tot}",
        "status_waiting_samples": "Várakozás mintákra...",
        "lbl_img_size": "Képméret / BBox:",
        "lbl_model_type": "Modell típus:",
        "val_model_type": "9-pontos Pose AI (Mancs fókusz)",
        "sample_status_excluded": "❌ KIZÁRVA (A modell nem használja)",
        "sample_status_valid": "✔ ÉRVÉNYES TANÍTÓ MINTA",
        "tt_lang": "Nyelv váltása (Magyar / English)",
        "tt_lock_lr": "Rögzíti a szigorú balról jobbra haladási irányt (kiküszöböli az orr és farok felcserélését).",
        "tt_bidirectional": "Engedélyezi a kétirányú mozgáskövetést a teljes pályán.",
        "tt_cooldown": "Két lábhiba közötti minimális időablak (másodperc).",
        "tt_mindist": "Két különálló lábhiba közötti minimális távolság (pixel).",
        "tt_threads": "Párhuzamos feldolgozó processzorszálak száma.",
        "tt_load_prof": "Mentett kalibrációs profil (.json) betöltése a lemezről.",
        "tt_save_prof": "Jelenlegi beállítások mentése JSON profilként.",
        "tt_rescan_samples": "Videók újbóli átvizsgálása és minták kigyűjtése a beállítások alapján.",
        "calib_win_title": "Kalibrációs Előnézet (Görgő=Zoom, Jobb gomb=Mozgatás, Bal gomb=Kapu, ENTER=Indítás)",
        "calib_tb_frame": "Képkocka",
        "calib_tb_dark": "Fényerő Küszöb",
        "calib_tb_diff": "Mozgás Küszöb",
        "calib_tb_ladder": "Létra Maszk",
        "calib_tb_fault": "Hibavonal %",
        "calib_overlay_hint": "ZÖLD KAPU=Start | PIROS KAPU=Cél | PIROS VONAL=Hibavonal | ENTER=Indítás | R=Alaphelyzet",
        "tt_rev_prev": "Ugrás az előző detektált lábhibára / eseményre [A]",
        "tt_rev_next": "Ugrás a következő detektált lábhibára / eseményre [D]",
        "tt_rev_valid": "Esemény érvényességének váltása: ÉRVÉNYES ↔ KIZÁRVA [Szóköz]",
        "tt_rev_part": "Detektált testrész átminősítése (Mellső láb, Hátsó láb, Orr, Farok) [T]",
        "tt_rev_crop": "Képkivágás pillanatkép mentése a megerősített eseményről [S]",
        "tt_rev_export": "Összes eredmény véglegesítése, kinematikai táblázatok és hőtérképek exportálása [Enter]",
        "tt_rev_zoom": "Nagyítás a hiba helyére (2.5×) [Z]",
        "tt_rev_reset": "Nagyítás és pozíció visszaállítása alaphelyzetbe (1.0×) [R]",
    },
    "en": {
        "subtitle": "Professional Horizontal Ladder Kinematic & Behavioral Workstation",
        "out_dir_prefix": "Output directory:",
        "btn_change_dir": "Select Folder",
        "btn_open_dir": "Open Results",
        "btn_settings": "⚙ Advanced Settings",
        "kpi_videos": "QUEUED RECORDINGS",
        "kpi_calib": "CALIBRATION STATE",
        "kpi_engine": "DETECTION ENGINE",
        "kpi_dlc": "HARDWARE ACCELERATION (GPU)",
        "kpi_vid_val": "{n} recordings",
        "kpi_cal_none": "Automatic (Adaptive)",
        "kpi_cal_active": "Locked ({w}×{h} px)",
        "sec1_title": "Workspace — Video Queue & Subject Metadata",
        "btn_add_vid": "＋ Add Recordings",
        "btn_edit_id": "✎ Edit Subject ID",
        "btn_remove_vid": "✕ Remove Selected",
        "btn_clear_vid": "Clear Queue",
        "col_fname": "Filename",
        "col_id": "Subject ID",
        "col_status": "Processing Status",
        "col_path": "File Path",
        "status_waiting": "Queued",
        "sec2_title": "Analysis Configuration & Control Dock",
        "sub_calib": "DETECTION & VALIDATION MODULES",
        "sub_params": "KINEMATIC & FILTERING PARAMETERS",
        "sub_profile": "PROFILE MANAGEMENT",
        "sub_exec": "EXECUTION CONTROL",
        "chk_rev": "Open interactive event verification window",
        "chk_auto_calib": "Automatic adaptive ladder & subject calibration",
        "chk_yolo_fusion": "YOLO + anatomical 9-point skeleton fitting",
        "chk_lock_lr": "Lock Left -> Right anatomical heading (prevents nose/tail flip)",
        "chk_bidirectional": "Bidirectional & continuous tracking (100% movement capture)",
        "chk_zones": "Partition track into sectors (Start / Mid / Goal)",
        "chk_kin": "Compute kinematics (cm/s) & velocity heatmaps",
        "chk_gpu": "Hardware acceleration (GPU decoding & UMat)",
        "chk_kalman": "Kalman filter & elastic ladder track compensation",
        "chk_dlc_sa": "Anatomical classification (Fore/Hind limb vs. Snout vs. Tail)",
        "chk_dlc_exp": "Export active-learning training crops (DLC / YOLO)",
        "lbl_runs_target": "Protocol Runs / Video:",
        "lbl_threads": "Worker threads:",
        "lbl_stride": "Frame stride:",
        "lbl_cooldown": "Refractory (s):",
        "lbl_mindist": "Min. distance (px):",
        "lbl_gatecm": "Gate span (cm):",
        "lbl_dec": "CSV decimal:",
        "btn_load_prof": "Load Profile",
        "btn_save_prof": "Save Profile",
        "btn_train_ai": "🧠 AI Training & Preview",
        "tt_train_ai": "Open interactive preview window: inspect harvested rodent frames, exclude bad samples, and train AI model.",
        "train_preview_title": "Rodent AI Training & Dataset Preview",
        "train_preview_banner": "Inspect rodent bounding boxes (BBox), skeleton keypoints, and exclude invalid frames before fine-tuning the model.",
        "lbl_sample_nav": "Sample Navigation:",
        "btn_prev_sample": "◀ Prev (←)",
        "btn_next_sample": "Next (→) ▶",
        "btn_exclude_sample": "❌ Exclude Sample (Space)",
        "btn_include_sample": "✔ Include Sample",
        "btn_auto_clean": "🧹 Exclude Suspicious",
        "tt_auto_clean": "Automatically exclude borderline, blurred, or gate-adjacent samples.",
        "btn_rescan_samples": "🔄 Rescan",
        "lbl_ds_telemetry": "Dataset Telemetry",
        "lbl_tot_samples": "Total frames collected:",
        "lbl_act_samples": "Active training samples:",
        "lbl_excl_samples": "Excluded samples:",
        "lbl_src_videos": "Source videos:",
        "lbl_train_params": "Training Hyperparameters",
        "lbl_epochs": "Epochs:",
        "lbl_device": "Compute device:",
        "btn_start_training": "🚀 Start AI Training",
        "btn_test_model": "🔍 Test Trained Model",
        "lbl_training_prog": "Training Progress:",
        "chk_zoom_rodent": "Focus on Rodent",
        "chk_show_ai": "Show AI Detection",
        "status_harvesting": "Harvesting frames from videos...",
        "status_ready": "Samples loaded! Inspect detections and click Start AI Training.",
        "status_training": "Fine-tuning YOLOv8 rodent detector...",
        "status_train_success": "✅ Training successful! New model saved & activated: rodent_detector.pt",
        "status_train_fail": "❌ Training failed. Check application logs!",
        "btn_start": "▶   Start Calibration & Analysis",
        "btn_quick": "▶▶  Quick Start (Skip Preview)",
        "btn_stop": "■   Stop",
        "prog_idle": "System Status: Ready  |  Processed: {done} / {total} recordings",
        "prog_run": "System Status: Processing  |  {done} / {total} recordings ({pct:.0f}%)",
        "sec3_title": "System Status, Telemetry & Event Log",
        "msg_no_vid_title": "No Recordings Queued",
        "msg_no_vid_body": "Please add at least one video file before starting analysis.",
        "msg_select_row": "Please select a recording row in the table first.",
        "edit_id_title": "Modify Subject Identifier (ID)",
        "edit_id_prompt": "Enter new Subject ID:",
        "btn_save_enter": "Apply (Enter)",
        "settings_title": "Advanced Analysis & Hardware Configuration",
        "btn_close_settings": "Apply & Close",
        "tt_add_vid": "Add video files (.mp4, .avi, .mov, .mkv) to batch queue.",
        "tt_edit_id": "Modify Subject ID for selected row (press Enter, double-click, or edit button).",
        "tt_remove_vid": "Remove selected recording from queue.",
        "tt_clear_vid": "Clear all recordings from queue.",
        "tt_auto_calib": "Automatically detects ladder ROI, gates, sag, and optimal thresholds.",
        "tt_yolo": "Combines YOLO detection with 9-point articulated rodent skeleton fitting.",
        "tt_rev": "Opens zoomable inspector window to review and validate detected slips.",
        "tt_gatecm": "Physical distance between Start and Goal gates in cm for velocity scaling.",
        "tt_settings": "Configure worker threads, frame stride, GPU acceleration, and CSV formats.",
        "tt_start": "Opens interactive visual preview to inspect gates and ladder before running.",
        "tt_quick": "Starts batch analysis immediately using adaptive parameters without preview.",
        "tt_stop": "Immediately terminates all active analysis worker threads.",
        "tt_change_dir": "Select output directory for CSV tables and heatmaps.",
        "tt_open_dir": "Open active results directory in file manager.",
        "tt_train_ai": "Train a custom 9-keypoint YOLOv8-Pose model (mouse_pose_ai.pt) from videos.",
        "review_title": "Kinematic Event Inspector & Verification Workstation",
        "review_banner_help": "Navigation: [↑]/[↓] or [A]/[D] | Toggle Valid: [Space] | Cycle Body Part: [T] | Save Crop: [S] | Zoom: [Z] / [R] | Export: [Enter]",
        "events_table_title": "Detected Events List",
        "inspector_canvas_title": "Detailed Ladder & Rodent Inspector",
        "btn_prev": "◀ Prev (A)",
        "btn_next": "Next (D) ▶",
        "btn_toggle_valid": "Toggle Valid [Space]",
        "btn_cycle_part": "Cycle Body Part [T]",
        "btn_toggle_crop": "Save Snapshot [S]",
        "btn_confirm_export": "✔ Confirm & Export Metrics (Enter)",
        "col_rev_id": "Subject ID",
        "col_rev_run": "Run",
        "col_rev_sec": "Time",
        "col_rev_part": "Body Part [T]",
        "col_rev_valid": "Status",
        "col_rev_save": "Snap [S]",
        "val_valid": "VALID",
        "val_ignored": "IGNORED",
        "val_yes": "Yes",
        "val_no": "No",
        "btn_close": "Close",
        "btn_cancel": "Cancel (Esc)",
        "app_window_title": "{app_name} v{version} — Scientific Kinematic & Behavioral Workstation",
        "preview_inspector_title": "Dataset & Detection Inspector",
        "preview_trainer_title": "AI Model Training Center",
        "badge_queue": "DATA QUEUE",
        "badge_controls": "CONTROLS",
        "badge_log": "STATUS & LOG",
        "badge_inspector": "INSPECTOR",
        "badge_trainer": "TRAINER",
        "badge_events": "EVENTS",
        "lbl_sample_counter": "Sample: {cur} / {tot}",
        "status_waiting_samples": "Waiting for samples...",
        "lbl_img_size": "Image Size / BBox:",
        "lbl_model_type": "Model Type:",
        "val_model_type": "9-Keypoint Pose AI (Paw-Focused)",
        "sample_status_excluded": "❌ EXCLUDED (Omitted from AI training)",
        "sample_status_valid": "✔ VALID TRAINING SAMPLE",
        "tt_lang": "Switch language (Hungarian / English)",
        "tt_lock_lr": "Locks strict left-to-right heading per experimental protocol (prevents nose/tail inversions).",
        "tt_bidirectional": "Enables bidirectional tracking across entire track.",
        "tt_cooldown": "Minimum refractory time between consecutive foot slips (seconds).",
        "tt_mindist": "Minimum spatial distance between distinct foot slips (pixels).",
        "tt_threads": "Number of parallel worker CPU threads.",
        "tt_load_prof": "Load saved calibration profile (.json) from disk.",
        "tt_save_prof": "Save active calibration parameters to JSON profile.",
        "tt_rescan_samples": "Rescan queued recordings and harvest fresh rodent samples.",
        "calib_win_title": "Calibration Preview (Wheel=Zoom, RightDrag=Pan, LeftClick=Move Gate, ENTER=Start)",
        "calib_tb_frame": "Frame",
        "calib_tb_dark": "Brightness",
        "calib_tb_diff": "Motion Diff",
        "calib_tb_ladder": "Rung Mask",
        "calib_tb_fault": "Fault Line %",
        "calib_overlay_hint": "GREEN GATE=Start | RED GATE=Goal | RED LINE=Fault Line | ENTER=Start Analysis | R=Reset View",
        "tt_rev_prev": "Jump to previous detected foot fault or event [A]",
        "tt_rev_next": "Jump to next detected foot fault or event [D]",
        "tt_rev_valid": "Toggle event validity: VALID ↔ IGNORED [Space]",
        "tt_rev_part": "Cycle classified body part (Forepaw, Hindpaw, Snout, Tail) [T]",
        "tt_rev_crop": "Save cropped image snapshot of this event [S]",
        "tt_rev_export": "Confirm all events and export kinematic tables & heatmaps [Enter]",
        "tt_rev_zoom": "Zoom into slip location (2.5×) [Z]",
        "tt_rev_reset": "Reset zoom and position to fit overview (1.0×) [R]",
    }
}


# ==============================================================================
# FLICKER-FREE SINGLETON ON-HOVER TOOLTIP MANAGER
# ==============================================================================
class ToolTip:
    _active_tip = None

    def __init__(self, widget, text_func):
        self.widget = widget
        self.text_func = text_func
        self.tip_win = None
        self.after_id = None
        self.last_mouse = (0, 0)

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Motion>", self._on_motion, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")
        self.widget.bind("<Destroy>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        if event is not None:
            self.last_mouse = (event.x_root, event.y_root)
        self._cancel()
        self.after_id = self.widget.after(400, self._show)

    def _on_motion(self, event=None):
        if event is not None:
            self.last_mouse = (event.x_root, event.y_root)

    def _on_leave(self, event=None):
        if event is not None and self.tip_win is not None:
            try:
                under = self.widget.winfo_containing(event.x_root, event.y_root)
                if under == self.widget:
                    return
            except Exception:
                pass
        self._hide()

    def _cancel(self):
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self):
        self._cancel()
        if not self.widget.winfo_exists():
            return
        try:
            px, py = self.widget.winfo_pointerxy()
            under = self.widget.winfo_containing(px, py)
            if under != self.widget:
                return
        except Exception:
            px, py = self.last_mouse

        text = self.text_func() if callable(self.text_func) else str(self.text_func)
        if not text:
            return

        if ToolTip._active_tip is not None and ToolTip._active_tip is not self:
            ToolTip._active_tip._hide()
        ToolTip._active_tip = self

        if self.tip_win is not None:
            return

        self.tip_win = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass

        outer = tk.Frame(tw, bg="#334155", padx=1, pady=1)
        outer.pack()
        lbl = tk.Label(
            outer, text=text, justify="left", bg="#0F172A", fg="#F8FAFC",
            font=("Segoe UI" if sys.platform == "win32" else "SF Pro Text", 9),
            padx=10, pady=6, wraplength=320
        )
        lbl.pack()

        tw.update_idletasks()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()
        scr_w = tw.winfo_screenwidth()
        scr_h = tw.winfo_screenheight()

        x = min(max(8, px + 14), max(8, scr_w - tw_w - 12))
        y = py + 22
        if y + tw_h > scr_h - 16:
            y = max(8, py - tw_h - 10)

        tw.wm_geometry(f"+{int(x)}+{int(y)}")

    def _hide(self):
        self._cancel()
        if self.tip_win is not None:
            try:
                self.tip_win.destroy()
            except Exception:
                pass
            self.tip_win = None
        if ToolTip._active_tip is self:
            ToolTip._active_tip = None


# ==============================================================================
# OPENCV ZOOM & PAN VIEWPORT HELPER (EVENT-DRIVEN)
# ==============================================================================
class OpenCVZoomPanViewport:
    def __init__(self, img_w, img_h):
        self.img_w = max(1, int(img_w))
        self.img_h = max(1, int(img_h))
        self.zoom = 1.0
        self.cx = self.img_w / 2.0
        self.cy = self.img_h / 2.0
        self.panning = False
        self.pan_start_screen = (0, 0)
        self.pan_start_center = (self.cx, self.cy)
        self.dirty = True

    def reset(self):
        self.zoom = 1.0
        self.cx = self.img_w / 2.0
        self.cy = self.img_h / 2.0
        self.dirty = True

    def get_view_rect(self):
        vw = max(40.0, self.img_w / self.zoom)
        vh = max(30.0, self.img_h / self.zoom)
        x1 = float(np.clip(self.cx - vw / 2.0, 0.0, max(0.0, self.img_w - vw)))
        y1 = float(np.clip(self.cy - vh / 2.0, 0.0, max(0.0, self.img_h - vh)))
        self.cx = x1 + vw / 2.0
        self.cy = y1 + vh / 2.0
        ix1, iy1 = int(round(x1)), int(round(y1))
        ivw = max(1, min(self.img_w - ix1, int(round(vw))))
        ivh = max(1, min(self.img_h - iy1, int(round(vh))))
        return ix1, iy1, ivw, ivh

    def screen_to_image(self, sx, sy):
        vx, vy, vw, vh = self.get_view_rect()
        ix = int(round(vx + (sx / float(self.img_w)) * vw))
        iy = int(round(vy + (sy / float(self.img_h)) * vh))
        return int(np.clip(ix, 0, self.img_w - 1)), int(np.clip(iy, 0, self.img_h - 1))

    def handle_mouse(self, event, x, y, flags):
        if event == cv2.EVENT_MOUSEWHEEL:
            ix, iy = self.screen_to_image(x, y)
            if flags > 0:
                new_zoom = min(8.0, self.zoom * 1.25)
            else:
                new_zoom = max(1.0, self.zoom / 1.25)
            if abs(new_zoom - self.zoom) > 1e-4:
                ratio = self.zoom / new_zoom
                self.cx = ix + (self.cx - ix) * ratio
                self.cy = iy + (self.cy - iy) * ratio
                self.zoom = new_zoom
                self.dirty = True
            return True
        elif event in (cv2.EVENT_RBUTTONDOWN, cv2.EVENT_MBUTTONDOWN):
            self.panning = True
            self.pan_start_screen = (x, y)
            self.pan_start_center = (self.cx, self.cy)
            return True
        elif event == cv2.EVENT_MOUSEMOVE and self.panning:
            _, _, vw, vh = self.get_view_rect()
            dx = (x - self.pan_start_screen[0]) * (vw / float(self.img_w))
            dy = (y - self.pan_start_screen[1]) * (vh / float(self.img_h))
            self.cx = self.pan_start_center[0] - dx
            self.cy = self.pan_start_center[1] - dy
            self.dirty = True
            return True
        elif event in (cv2.EVENT_RBUTTONUP, cv2.EVENT_MBUTTONUP):
            self.panning = False
            return True
        return False

    def render(self, full_img):
        if self.zoom <= 1.01:
            out = full_img.copy()
        else:
            vx, vy, vw, vh = self.get_view_rect()
            crop = full_img[vy:vy + vh, vx:vx + vw]
            out = cv2.resize(crop, (self.img_w, self.img_h), interpolation=cv2.INTER_LINEAR)

        badge = f"Zoom: {self.zoom:.1f}x (Wheel=Zoom, RightDrag=Pan, R=Reset)"
        cv2.rectangle(out, (12, self.img_h - 38), (480, self.img_h - 10), (15, 23, 42), -1)
        cv2.putText(out, badge, (20, self.img_h - 19), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (16, 185, 129), 1, cv2.LINE_AA)
        return out


# ==============================================================================
# HELPER UTILITIES & KALMAN FILTER TRACKER
# ==============================================================================
def save_image_unicode(path, img):
    try:
        ext = os.path.splitext(path)[1] or ".jpg"
        is_success, im_buf_arr = cv2.imencode(ext, img)
        if is_success:
            im_buf_arr.tofile(path)
            return True
    except Exception:
        pass
    return False


def encode_frame_compressed(img, quality=94):
    if img is None:
        return None
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
    """2D Constant-Velocity Kalman Filter for smooth rodent center-of-mass trajectory tracking."""
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
    """
    High-throughput, low-memory background video prefetch reader.
    Keeps only cropped ROI frames in queue to maintain small RAM footprint (<35MB vs >300MB).
    """
    def __init__(self, cap, v_rx, v_ry, v_rw, v_rh, stride=1, queue_size=32):
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
            # If a dip occurs, frame is needed; pass frame or lightweight reference
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
# PARALLEL YOLO + OPENCV HYBRID SPATIAL LOCATOR ENGINE
# ==============================================================================
class ParallelYoloOpenCVEngine:
    """
    Thread-safe YOLO engine + 1D/2D OpenCV Torso-Core Density Locator.
    Correctly distinguishes genuine 9-keypoint rodent pose models from generic
    COCO human pose models (yolov8n-pose.pt), preventing human eyes/ears from
    being assigned to mouse paws/tail!
    """
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.yolo_model = None
        self.yolo_lock = threading.Lock()
        self.device = "cpu"
        self.yolo_executor = None
        self.stream_lock = threading.Lock()
        self.stream_states = {}
        self.latest_pose_by_stream = {}
        self.last_sync_pose = None
        self.is_pose_model = False
        self.is_rodent_pose = False
        self.model_name = "None"
        self._yolo_error_logged = False
        self.k_seed_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 9))
        self.k_open_3 = np.ones((3, 3), np.uint8)
        self.k_close_core = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 5))
        self.k_yolo_dilate = np.ones((11, 11), np.uint8)
        self.k_grad_3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        self._ignored_coco_classes = {
            "person", "bicycle", "car", "motorcycle", "bus", "truck", "traffic light",
            "bench", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
            "tv", "laptop", "remote", "keyboard", "cell phone", "microwave",
            "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "bottle", "cup"
        }
        self._init_yolo()

    def _init_yolo(self):
        try:
            if importlib.util.find_spec("ultralytics") is None:
                return
            from ultralytics import YOLO
            try:
                import torch
                if torch.cuda.is_available():
                    self.device = "cuda:0"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available() and sys.platform == "darwin":
                    self.device = "mps"
            except Exception:
                self.device = "cpu"

            for candidate in (
                "mouse_pose_ai.pt",
                "rodent_detector.pt",
                "mouse_yolo.pt",
                "ladder_yolo.pt",
                "yolov8n-pose.pt",
                "yolov8n-seg.pt",
                "yolov8n.pt",
            ):
                p = os.path.join(SAFE_BASE_DIR, candidate)
                if not os.path.exists(p):
                    p = get_resource_path(candidate)
                if os.path.exists(p):
                    self.yolo_model = YOLO(p)
                    self.model_name = candidate
                    names = getattr(self.yolo_model, "names", {}) or {}
                    # Check whether this model is trained specifically on rodent pose
                    is_pose = ("pose" in candidate.lower()) or getattr(self.yolo_model, "task", "") == "pose"
                    self.is_pose_model = is_pose
                    self.is_rodent_pose = is_pose and ("mouse" in candidate.lower() or "rodent" in str(names).lower())
                    if self.yolo_executor is None:
                        self.yolo_executor = ThreadPoolExecutor(
                            max_workers=max(2, min(4, os.cpu_count() or 4)), thread_name_prefix="mouse-yolo"
                        )
                    # Warm up GPU Metal/CUDA kernels immediately to eliminate startup latency
                    try:
                        dummy = np.zeros((128, 128, 3), dtype=np.uint8)
                        self.yolo_model.predict(dummy, device=self.device, verbose=False, imgsz=128)
                        if self.device == "mps":
                            import torch
                            torch.mps.synchronize()
                    except Exception:
                        pass
                    if self.is_rodent_pose:
                        mode_tag = "Custom 9-Keypoint Rodent Pose AI"
                    elif is_pose:
                        mode_tag = "YOLO Bounding Box + Anatomical OpenCV"
                    else:
                        mode_tag = "YOLO Object Detection + OpenCV"
                    self.log(f"⚡ [{mode_tag}] Loaded '{candidate}' on GPU ({self.device.upper()})")
                    return
        except Exception:
            self.yolo_model = None

    @staticmethod
    def _build_capsule_mask_from_pose(pose_kpts, bbox, rw, rh):
        mask = np.zeros((rh, rw), dtype=np.uint8)
        if not pose_kpts:
            if bbox is not None:
                x, y, w, h = bbox
                cv2.ellipse(
                    mask,
                    (int(x + w * 0.5), int(y + h * 0.5)),
                    (max(8, int(w * 0.45)), max(6, int(h * 0.42))),
                    0, 0, 360, 255, -1
                )
            return mask

        chain_keys = ["tail_tip", "tail_base", "hip_pt", "spine_mid", "shoulder_pt", "head_pt", "nose_pt"]
        radii = [3, 9, 14, 15, 13, 10, 6]
        pts = [pose_kpts.get(k) for k in chain_keys]
        for idx in range(len(pts) - 1):
            p1, p2 = pts[idx], pts[idx + 1]
            if p1 is not None and p2 is not None:
                thickness = max(4, (radii[idx] + radii[idx + 1]))
                cv2.line(mask, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), 255, thickness, cv2.LINE_AA)

        for p_parent, p_paw in [("hip_pt", "hind_paw_pt"), ("shoulder_pt", "fore_paw_pt")]:
            pa = pose_kpts.get(p_parent)
            pb = pose_kpts.get(p_paw)
            if pa is not None and pb is not None:
                cv2.line(mask, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), 255, 8, cv2.LINE_AA)
                cv2.circle(mask, (int(pb[0]), int(pb[1])), 5, 255, -1)
        return mask

    def _predict_yolo(self, crop_bgr, rw, rh):
        try:
            results = self.yolo_model.predict(
                crop_bgr, conf=0.20, verbose=False, device=self.device, imgsz=256
            )
            if self.device == "mps":
                try:
                    import torch
                    torch.mps.synchronize()
                except Exception:
                    pass
        except Exception:
            return None, None, None
        if not results:
            return None, None, None

        result = results[0]
        yolo_bbox = None
        yolo_seg_mask = None
        yolo_pose_kpts = None
        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes.xyxy.cpu().numpy()
            cls_ids = result.boxes.cls.cpu().numpy().astype(int) if result.boxes.cls is not None else None
            names = getattr(self.yolo_model, "names", {}) or {}
            is_generic_coco = len(names) > 15

            best_i = -1
            best_area = -1.0
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = [int(v) for v in box]
                bw, bh = x2 - x1, y2 - y1
                if bw < 16 or bh < 8 or bw >= rw * 0.85 or bh >= rh * 0.95:
                    continue
                if (y1 + bh * 0.5) > rh * 0.85:
                    continue
                if is_generic_coco and cls_ids is not None and i < len(cls_ids):
                    cname = str(names.get(int(cls_ids[i]), "")).lower()
                    if cname in self._ignored_coco_classes and cname != "mouse":
                        continue
                area = float(bw * bh)
                if area > best_area:
                    best_area = area
                    best_i = i

            if best_i >= 0:
                x1, y1, x2, y2 = [int(value) for value in boxes[best_i]]
                yolo_bbox = (x1, y1, x2 - x1, y2 - y1)
                # Only parse rodent pose keypoints if model is a trained rodent pose model
                if self.is_rodent_pose and result.keypoints is not None and result.keypoints.xy is not None and len(result.keypoints.xy) > best_i:
                    kpts_xy = result.keypoints.xy[best_i].cpu().numpy()
                    kpts_conf = (
                        result.keypoints.conf[best_i].cpu().numpy()
                        if getattr(result.keypoints, "conf", None) is not None
                        else np.ones(len(kpts_xy), dtype=np.float32)
                    )
                    if len(kpts_xy) >= 9:
                        kpt_names = [
                            "nose_pt", "head_pt", "shoulder_pt", "fore_paw_pt",
                            "spine_mid", "hip_pt", "hind_paw_pt", "tail_base", "tail_tip"
                        ]
                        parsed = {}
                        for k_idx, k_name in enumerate(kpt_names):
                            kx, ky = float(kpts_xy[k_idx][0]), float(kpts_xy[k_idx][1])
                            kc = float(kpts_conf[k_idx]) if k_idx < len(kpts_conf) else 1.0
                            if kx > 1.0 and ky > 1.0 and kc >= 0.20:
                                parsed[k_name] = (
                                    int(np.clip(round(kx), 0, rw - 1)),
                                    int(np.clip(round(ky), 0, rh - 1)),
                                )
                        if len(parsed) >= 5:
                            parsed["bbox"] = yolo_bbox
                            yolo_pose_kpts = parsed

                if result.masks is not None and len(result.masks.data) > best_i:
                    mask_data = result.masks.data[best_i].cpu().numpy()
                    yolo_seg_mask = (cv2.resize(mask_data, (rw, rh)) > 0.35).astype(np.uint8) * 255
                elif yolo_pose_kpts is not None:
                    yolo_seg_mask = self._build_capsule_mask_from_pose(yolo_pose_kpts, yolo_bbox, rw, rh)
        return yolo_bbox, yolo_seg_mask, yolo_pose_kpts

    def _get_yolo_result(self, crop_bgr, rw, rh, stream_id, frame_idx, max_age, force_direct=False):
        if self.yolo_model is None:
            return None, None, max_age + 1

        # Direct hardware GPU execution for Apple Silicon (MPS) and NVIDIA (CUDA):
        # Executes deep neural net directly on GPU in 4-6ms every 2 frames for continuous GPU utilization
        if self.device in ("mps", "cuda:0") or stream_id is None or frame_idx is None or force_direct:
            with self.stream_lock:
                state = self.stream_states.setdefault(stream_id or "default", {})
                last_f = state.get("frame_idx", -1)
                if frame_idx is None or (frame_idx - last_f) >= 2 or state.get("result") is None or force_direct:
                    try:
                        yolo_bbox, yolo_seg_mask, yolo_pose_kpts = self._predict_yolo(crop_bgr, rw, rh)
                        self.last_sync_pose = yolo_pose_kpts
                        state["result"] = (yolo_bbox, yolo_seg_mask, yolo_pose_kpts)
                        state["frame_idx"] = frame_idx or 0
                        if stream_id is not None:
                            self.latest_pose_by_stream[stream_id] = (yolo_pose_kpts, state["frame_idx"])
                        return yolo_bbox, yolo_seg_mask, 0
                    except Exception as exc:
                        if not self._yolo_error_logged:
                            self.log(f"⚠ YOLO GPU error: {exc}")
                            self._yolo_error_logged = True
                        return None, None, max_age + 1
                else:
                    res_tuple = state.get("result")
                    if res_tuple is not None:
                        return res_tuple[0], res_tuple[1], frame_idx - last_f
                    return None, None, max_age + 1

        with self.stream_lock:
            state = self.stream_states.setdefault(
                stream_id, {"future": None, "result": None, "frame_idx": -1, "pending_frame_idx": -1}
            )
            future = state.get("future")
            if future is not None and future.done():
                try:
                    state["result"] = future.result()
                    state["frame_idx"] = state.get("pending_frame_idx", frame_idx)
                    if state["result"] is not None and len(state["result"]) == 3:
                        self.latest_pose_by_stream[stream_id] = (state["result"][2], state["frame_idx"])
                    self._yolo_error_logged = False
                except Exception as exc:
                    if not self._yolo_error_logged:
                        self.log(f"⚠ YOLO error, continuing with OpenCV: {exc}")
                        self._yolo_error_logged = True
                state["future"] = None

            if state.get("future") is None:
                state["pending_frame_idx"] = frame_idx
                state["future"] = self.yolo_executor.submit(
                    self._predict_yolo, crop_bgr.copy(), rw, rh
                )

            result_age = frame_idx - state.get("frame_idx", -1)
            if result_age <= max_age:
                res_tuple = state.get("result")
                if res_tuple is not None:
                    yolo_bbox, yolo_seg_mask = res_tuple[0], res_tuple[1]
                    if len(res_tuple) >= 3 and res_tuple[2] is not None:
                        self.last_sync_pose = res_tuple[2]
                else:
                    yolo_bbox, yolo_seg_mask = None, None
                return yolo_bbox, yolo_seg_mask, result_age
            return None, None, result_age

    def get_latest_pose_for_bbox(self, bx, by, bw, bh, mw, mh):
        if not self.is_rodent_pose:
            return None
        pose = self.last_sync_pose
        if not pose or "bbox" not in pose:
            return None
        px, py, pw, ph = pose["bbox"]
        inter_x = max(0, min(bx + bw, px + pw) - max(bx, px))
        if inter_x <= 0:
            return None
        return pose

    def reset_stream(self, stream_id):
        with self.stream_lock:
            self.stream_states.pop(stream_id, None)
            self.latest_pose_by_stream.pop(stream_id, None)

    def locate_animal_roi_and_mask(
        self, crop_bgr, gray_smooth, base_smooth, inv_ladder_mask, fault_y_local,
        dark_t, diff_t, stream_id=None, frame_idx=None, ai_max_age=3, previous_bbox=None
    ):
        rh, rw = gray_smooth.shape[:2]

        torso_bottom = max(15, int(fault_y_local) - 8)
        torso_gray = gray_smooth[:torso_bottom, :]
        torso_base = base_smooth[:torso_bottom, :]
        torso_diff = cv2.subtract(torso_base, torso_gray)
        torso_absdiff = cv2.absdiff(torso_base, torso_gray)

        bg_grad = cv2.morphologyEx(torso_base, cv2.MORPH_GRADIENT, self.k_grad_3)
        static_imperfection = (torso_base <= min(215, dark_t + 8)) | (bg_grad >= 16)
        static_imperfection = cv2.dilate(
            static_imperfection.astype(np.uint8) * 255, self.k_open_3, iterations=1
        ) > 0

        seed_diff_t = max(10, int(diff_t * 0.75))
        low_diff_t = max(5, int(diff_t * 0.35))
        blemish_diff_t = max(seed_diff_t + 14, int(diff_t * 1.55))

        valid_seed_bool = (
            ((torso_diff >= seed_diff_t) & (torso_gray <= min(225, dark_t + 14)) & (~static_imperfection))
            | ((torso_diff >= blemish_diff_t) & (torso_gray <= dark_t))
            | ((torso_absdiff >= max(22, int(diff_t * 1.30))) & (torso_gray <= dark_t) & (~static_imperfection))
        )
        seed_mask = valid_seed_bool.astype(np.uint8) * 255

        if previous_bbox is not None:
            px, py, pw, ph = previous_bbox
            px1 = max(0, int(px - 18))
            px2 = min(rw, int(px + pw + 18))
            py1 = max(0, int(py - 10))
            py2 = min(torso_bottom, int(py + ph + 10))
            if px2 > px1 and py2 > py1:
                stationary_rescue = (
                    (torso_diff[py1:py2, px1:px2] >= low_diff_t)
                    & (torso_gray[py1:py2, px1:px2] <= dark_t)
                    & (~static_imperfection[py1:py2, px1:px2])
                ).astype(np.uint8) * 255
                seed_mask[py1:py2, px1:px2] = cv2.bitwise_or(
                    seed_mask[py1:py2, px1:px2], stationary_rescue
                )

        support_bool = (
            (torso_gray <= min(228, dark_t + 8))
            & (
                ((torso_diff >= low_diff_t) & (~static_imperfection))
                | (torso_diff >= blemish_diff_t)
            )
        )
        support_mask = support_bool.astype(np.uint8) * 255
        if inv_ladder_mask is not None:
            support_mask = cv2.bitwise_and(support_mask, inv_ladder_mask[:torso_bottom, :])

        seed_dilated = cv2.dilate(seed_mask, self.k_seed_dilate, iterations=2)
        core_mask = cv2.bitwise_and(support_mask, seed_dilated)
        core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_OPEN, self.k_open_3)
        core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_CLOSE, self.k_close_core)

        yolo_bbox, yolo_seg_mask, yolo_age = self._get_yolo_result(
            crop_bgr, rw, rh, stream_id, frame_idx, max(3, int(ai_max_age))
        )
        if yolo_age > max(3, int(ai_max_age)):
            yolo_bbox = None
            yolo_seg_mask = None

        contours, _ = cv2.findContours(core_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_c = None
        max_a = float("-inf")
        min_corridor_bottom = max(10, int(torso_bottom * 0.32))
        max_valid_torso_top = max(12, int(fault_y_local) - max(45, int(rh * 0.16)))
        min_torso_h = max(24, int(rh * 0.09))

        for c in contours:
            a = cv2.contourArea(c)
            if a <= 260:
                continue
            x_c, y_c, w_c, h_c = cv2.boundingRect(c)
            aspect_ratio = w_c / max(1.0, float(h_c))
            fill_ratio = a / max(1.0, float(w_c * h_c))
            if (
                w_c < 20
                or h_c < min_torso_h
                or y_c >= max_valid_torso_top
                or aspect_ratio < 0.40
                or aspect_ratio > 11.0
                or fill_ratio < 0.12
            ):
                continue
            if (y_c + h_c) < min_corridor_bottom:
                continue

            roi_diff = torso_diff[y_c:y_c + h_c, x_c:x_c + w_c]
            mean_diff = float(np.mean(roi_diff)) if roi_diff.size > 0 else 0.0
            p80_diff = float(np.percentile(roi_diff, 80)) if roi_diff.size > 0 else 0.0
            if (mean_diff < max(9.0, diff_t * 0.45) or p80_diff < max(20.0, diff_t * 0.90)) and previous_bbox is None:
                continue

            corridor_prox = 1.0 - min(1.0, abs((y_c + h_c) - torso_bottom) / max(18.0, float(torso_bottom)))
            score = np.log1p(a) + 2.0 * fill_ratio + min(2.2, mean_diff / 18.0) + 0.85 * corridor_prox
            if yolo_bbox is not None:
                yx, yy, yw, yh = yolo_bbox
                inter_x = max(0, min(x_c + w_c, yx + yw) - max(x_c, yx))
                if inter_x > 0:
                    score += 2.0 * (inter_x / max(1.0, float(max(w_c, yw))))
            if previous_bbox is not None:
                px, py, pw, ph = previous_bbox
                distance = np.hypot((x_c + w_c * 0.5) - (px + pw * 0.5), (y_c + h_c * 0.5) - (py + ph * 0.5))
                distance_scale = max(36.0, min(140.0, rw * 0.18))
                score += 3.2 * np.exp(-distance / distance_scale)
                score -= min(3.2, distance / distance_scale)
            if score > max_a:
                max_a = score
                best_c = c

        if best_c is None and yolo_bbox is None:
            return None, None

        if best_c is not None:
            cx, cy, cw, ch = cv2.boundingRect(best_c)
            c_mask = np.zeros_like(core_mask)
            cv2.drawContours(c_mask, [best_c], -1, 255, -1)
            col_heights = np.sum(c_mask[:, cx:cx + cw] > 0, axis=0)
            thick_cols = np.where(col_heights >= max(6, int(ch * 0.25)))[0]
            if len(thick_cols) >= 10:
                core_x1 = cx + int(thick_cols[0])
                core_x2 = cx + int(thick_cols[-1]) + 1
                if (core_x2 - core_x1) >= 16:
                    cx, cw = core_x1, core_x2 - core_x1

            if yolo_bbox is not None:
                yx, yy, yw, yh = yolo_bbox
                if abs((yx + yw * 0.5) - (cx + cw * 0.5)) < max(cw, yw) * 0.85:
                    cx = min(cx, yx)
                    cy = min(cy, yy)
                    cw = max(cx + cw, yx + yw) - cx
                    ch = max(cy + ch, yy + yh) - cy
        else:
            cx, cy, cw, ch = yolo_bbox

        spatial_gate = np.zeros((rh, rw), dtype=np.uint8)
        upper_x1 = max(0, cx - 280)
        upper_x2 = min(rw, cx + cw + 280)
        spatial_gate[:torso_bottom, upper_x1:upper_x2] = 255

        paw_x1 = max(0, cx - 14)
        paw_x2 = min(rw, cx + cw + 18)
        if paw_x2 > paw_x1:
            spatial_gate[torso_bottom:, paw_x1:paw_x2] = 255

        if yolo_bbox is not None and yolo_seg_mask is not None:
            yolo_dilated = cv2.dilate(yolo_seg_mask, self.k_yolo_dilate, iterations=1)
            spatial_gate = cv2.bitwise_or(spatial_gate, yolo_dilated)

        return (cx, cy, cw, ch), spatial_gate


# ==============================================================================
# ZERO-CALIBRATION & LIGHTWEIGHT ELASTIC LADDER TRACKING ENGINE
# ==============================================================================
class AutoAdaptiveLadderEngine:
    def __init__(self, log_callback=print):
        self.log = log_callback

    @staticmethod
    def _ensure_gray_2d(img):
        if img is None:
            return None
        if img.ndim == 3:
            if img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            elif img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            else:
                img = img[:, :, 0]
        return np.squeeze(img).astype(np.uint8)

    @staticmethod
    def compute_outlier_rejected_bg(stack):
        if stack.shape[0] <= 2:
            return np.max(stack, axis=0).astype(np.uint8)

        n_frames, sh, sw = stack.shape[:3]
        aligned = stack.copy()

        y1 = int(sh * 0.50) if sh <= 420 else int(sh * 0.45)
        y2 = int(sh * 0.88) if sh <= 420 else int(sh * 0.82)
        x1, x2 = int(sw * 0.08), int(sw * 0.92)
        if (y2 - y1) >= 24 and (x2 - x1) >= 64:
            ref_idx = 0
            ref_patch = np.float32(stack[ref_idx, y1:y2, x1:x2])
            hann = cv2.createHanningWindow((x2 - x1, y2 - y1), cv2.CV_32F)
            for i in range(1, n_frames):
                cur_patch = np.float32(stack[i, y1:y2, x1:x2])
                (dx, dy), resp = cv2.phaseCorrelate(ref_patch, cur_patch, hann)
                if resp > 0.12 and (0.45 <= np.hypot(dx, dy) < 24.0):
                    M = np.float32([[1.0, 0.0, -dx], [0.0, 1.0, -dy]])
                    aligned[i] = cv2.warpAffine(
                        stack[i], M, (sw, sh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
                    )

        p60 = np.percentile(aligned, 60, axis=0)
        clean_mask = (aligned >= (p60 - 12.0)) & (aligned <= (p60 + 16.0))
        bg_cnt = np.sum(clean_mask, axis=0)
        fallback_mask = aligned >= (p60 - 14.0)
        clean_mask = np.where(bg_cnt[None, :, :] > 0, clean_mask, fallback_mask)
        bg_sum = np.sum(aligned.astype(np.float32) * clean_mask, axis=0)
        bg_cnt = np.maximum(1, np.sum(clean_mask, axis=0))
        return np.clip(np.round(bg_sum / bg_cnt), 0, 255).astype(np.uint8)

    def auto_calibrate_from_video(self, cap, num_bg_samples=28):
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_count = min(num_bg_samples, max(6, total_frames - 1)) if total_frames > 6 else 10

        frames_gray = []
        sample_indices = []
        if total_frames > 6:
            indices = np.linspace(0, max(1, total_frames - 2), sample_count, dtype=int)
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ret, frm = cap.read()
                if ret and frm is not None:
                    frames_gray.append(self._ensure_gray_2d(frm))
                    sample_indices.append(int(idx))
        else:
            for idx in range(sample_count):
                ret, frm = cap.read()
                if ret and frm is not None:
                    frames_gray.append(self._ensure_gray_2d(frm))
                    sample_indices.append(idx)

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not frames_gray:
            raise RuntimeError("Could not read frames for automatic calibration.")

        stack_full = np.stack(frames_gray, axis=0)
        clean_bg_full = self.compute_outlier_rejected_bg(stack_full)
        clean_bg_full = self._ensure_gray_2d(clean_bg_full)
        fh, fw = clean_bg_full.shape[:2]

        k_rung = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        blackhat = cv2.morphologyEx(clean_bg_full, cv2.MORPH_BLACKHAT, k_rung)
        sobel_x = cv2.Sobel(clean_bg_full, cv2.CV_32F, 1, 0, ksize=3)
        sobel_x = cv2.convertScaleAbs(sobel_x)
        combined_energy = self._ensure_gray_2d(cv2.addWeighted(blackhat, 0.65, sobel_x, 0.35, 0))

        x_start, x_end = max(0, int(fw * 0.1)), min(fw, int(fw * 0.9))
        row_energy = np.mean(combined_energy[:, x_start:x_end], axis=1)
        row_energy[:int(fh * 0.12)] = 0
        row_energy[int(fh * 0.88):] = 0

        smooth_window = max(5, int(fh * 0.04) | 1)
        row_energy_smooth = np.convolve(row_energy, np.ones(smooth_window) / smooth_window, mode="same")
        ladder_y_center = int(np.argmax(row_energy_smooth))

        pad_above = max(80, int(fh * 0.17))
        pad_below = max(45, int(fh * 0.09))
        ry = max(0, ladder_y_center - pad_above)
        rh = min(fh - ry, pad_above + pad_below)

        strip_y1 = max(0, ladder_y_center - 15)
        strip_y2 = min(fh, ladder_y_center + 15)
        rung_strip = combined_energy[strip_y1:strip_y2, :]
        col_energy = np.mean(rung_strip, axis=0)
        col_thresh = np.percentile(col_energy, 30)
        active_cols = np.where(col_energy > col_thresh)[0]

        if len(active_cols) > 20:
            rx = max(0, int(np.percentile(active_cols, 2)) - 20)
            rx_end = min(fw, int(np.percentile(active_cols, 98)) + 20)
            rw = max(120, rx_end - rx)
        else:
            rx, rw = int(fw * 0.04), int(fw * 0.92)

        left_gate_x = int(rx + rw * 0.10)
        right_gate_x = int(rx + rw * 0.86)

        roi_bg = clean_bg_full[ry:ry + rh, rx:rx + rw]
        rung_y_local = max(14, min(rh - 14, ladder_y_center - ry))
        auto_params = self.compute_auto_thresholds(
            frames_gray, sample_indices, roi_bg, rx, ry, rw, rh, rung_y_local
        )
        rung_pts_local = self.extract_rung_keypoints(roi_bg, rung_y_local, auto_params["ladder_thresh"])

        self.log(
            f"🤖 [Auto-Calib] ROI=({rx},{ry},{rw}x{rh}) | Gates=({left_gate_x}->{right_gate_x}) | "
            f"BestFrame=#{auto_params['best_preview_frame']} | "
            f"Brightness={auto_params['dark_thresh']}, Diff={auto_params['diff_thresh']}, "
            f"RungMask={auto_params['ladder_thresh']}, FaultLine={auto_params['fault_ratio']}%"
        )

        return {
            "rx": rx, "ry": ry, "rw": rw, "rh": rh,
            "left_gate_x": left_gate_x, "right_gate_x": right_gate_x,
            "calib_dark_thresh": auto_params["dark_thresh"],
            "calib_diff_thresh": auto_params["diff_thresh"],
            "calib_ladder_thresh": auto_params["ladder_thresh"],
            "calib_fault_Ratio": auto_params["fault_ratio"],
            "best_preview_frame": auto_params["best_preview_frame"],
            "rung_pts_local": rung_pts_local,
            "base_rung_y_local": rung_y_local
        }

    def compute_auto_thresholds(self, frames_gray, sample_indices, roi_bg, rx, ry, rw, rh, rung_y_local):
        roi_bg = self._ensure_gray_2d(roi_bg)

        band_y1 = max(0, rung_y_local - 14)
        band_y2 = min(rh, rung_y_local + 22)
        rung_band = roi_bg[band_y1:band_y2, :]
        p25_rung = float(np.percentile(rung_band, 25))
        ladder_thresh = int(np.clip(p25_rung + 18, 95, 155))

        best_frame_idx = sample_indices[len(sample_indices) // 2] if sample_indices else 0
        best_mouse_score = -1.0
        best_mouse_gray_p82 = None

        body_y1 = max(0, rung_y_local - int(rh * 0.58))
        body_y2 = max(body_y1 + 15, rung_y_local - 6)
        mid_x1 = int(rw * 0.18)
        mid_x2 = int(rw * 0.80)

        for fg, f_idx in zip(frames_gray, sample_indices):
            fg_2d = self._ensure_gray_2d(fg)
            crop_f = fg_2d[ry:ry + rh, rx:rx + rw]
            if crop_f.shape != roi_bg.shape:
                continue

            sub_bg = roi_bg[body_y1:body_y2, mid_x1:mid_x2]
            sub_f = crop_f[body_y1:body_y2, mid_x1:mid_x2]
            diff_body = cv2.subtract(sub_bg, sub_f)
            strong_pixels = (diff_body > 22) & (sub_f < 115)
            count_strong = int(np.count_nonzero(strong_pixels))

            if 450 < count_strong < (sub_f.size * 0.55):
                score = float(count_strong) * float(np.mean(diff_body[strong_pixels]) + 15.0)
                if score > best_mouse_score:
                    best_mouse_score = score
                    best_frame_idx = int(f_idx)
                    mouse_intensities = sub_f[strong_pixels]
                    best_mouse_gray_p82 = float(np.percentile(mouse_intensities, 82))

        bg_median = float(np.median(roi_bg[body_y1:body_y2, :]))
        if best_mouse_gray_p82 is not None:
            dark_thresh = int(np.clip(best_mouse_gray_p82 + 32, 112, 146))
        else:
            dark_thresh = int(np.clip(bg_median - 45, 115, 145))

        diff_thresh = 24
        fault_y_local = min(rh - 6, rung_y_local + 15)
        fault_ratio = int(np.clip((fault_y_local / float(max(1, rh))) * 100.0, 62, 90))

        return {
            "dark_thresh": dark_thresh,
            "diff_thresh": diff_thresh,
            "ladder_thresh": ladder_thresh,
            "fault_ratio": fault_ratio,
            "best_preview_frame": best_frame_idx
        }

    def extract_rung_keypoints(self, roi_bg, rung_y_local, ladder_thresh):
        roi_bg = self._ensure_gray_2d(roi_bg)
        rh, rw = roi_bg.shape[:2]
        rung_y_local = int(np.clip(rung_y_local, 10, max(11, rh - 10)))

        y1 = max(0, rung_y_local - 16)
        y2 = min(rh, rung_y_local + 18)
        strip = roi_bg[y1:y2, :]

        _, m_dark = cv2.threshold(strip, ladder_thresh, 255, cv2.THRESH_BINARY_INV)
        edges = cv2.Canny(strip, 45, 130)
        combined = cv2.bitwise_or(m_dark, edges)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pts = []
        for c in contours:
            if 5 <= cv2.contourArea(c) <= 900:
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = float(M["m10"] / M["m00"])
                    cy = float(M["m01"] / M["m00"]) + y1
                    pts.append([cx, cy])

        if len(pts) < 6:
            xs = np.linspace(20, max(25, rw - 20), 18)
            pts = [[float(x), float(rung_y_local)] for x in xs]

        return np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2)


class ElasticLadderTracker:
    """
    Tracks camera shift and weight-induced ladder sag without drift,
    anchoring optical flow to the static clean background reference.
    """
    def __init__(self, base_gray, base_inv_ladder_mask, init_rung_pts, base_fault_y_local):
        if base_gray.ndim == 3:
            base_gray = cv2.cvtColor(base_gray, cv2.COLOR_BGR2GRAY)
        self.base_gray = np.squeeze(base_gray).astype(np.uint8).copy()
        self.base_inv_ladder = np.squeeze(base_inv_ladder_mask).astype(np.uint8).copy()
        self.rh, self.rw = self.base_gray.shape[:2]

        self.strip_y1 = max(0, int(self.rh * 0.48))
        self.strip_y2 = min(self.rh, max(self.strip_y1 + 24, int(self.rh * 0.90)))
        self.base_strip_float = np.float32(self.base_gray[self.strip_y1:self.strip_y2, :])
        self.hann_strip = cv2.createHanningWindow(
            (self.rw, self.strip_y2 - self.strip_y1), cv2.CV_32F
        )

        pts_arr = np.asarray(init_rung_pts, dtype=np.float32).reshape(-1, 1, 2)
        self.init_pts = pts_arr.copy()
        self.base_fault_y_local = float(base_fault_y_local)

        self.global_dx = 0.0
        self.global_dy = 0.0
        self.dy_curve_float = np.zeros(self.rw, dtype=np.float32)
        self.step_counter = 0

        self.grid_x, self.grid_y = np.meshgrid(
            np.arange(self.rw, dtype=np.float32),
            np.arange(self.rh, dtype=np.float32),
        )

        self.cached_warped_bg = self.base_gray
        self.cached_warped_inv_ladder = self.base_inv_ladder
        self.cached_fault_curve = np.full(self.rw, int(base_fault_y_local), dtype=np.int32)

        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )

    def update(self, crop_gray, mouse_bbox_local=None, force_update=False):
        self.step_counter += 1
        if not force_update and (self.step_counter % 2 != 1):
            return self.cached_warped_bg, self.cached_warped_inv_ladder, self.cached_fault_curve

        if crop_gray.ndim == 3:
            crop_gray = cv2.cvtColor(crop_gray, cv2.COLOR_BGR2GRAY)
        crop_gray = np.squeeze(crop_gray).astype(np.uint8)

        curr_strip = crop_gray[self.strip_y1:self.strip_y2, :].copy()
        mx1, my1, mx2, my2 = -1, -1, -1, -1
        if mouse_bbox_local is not None:
            bx, by, bw, bh = mouse_bbox_local
            mx1 = max(0, bx - 18)
            mx2 = min(self.rw, bx + bw + 18)
            my1 = max(0, by - 12)
            my2 = min(self.rh, by + bh + 12)
            if mx2 > mx1:
                curr_strip[:, mx1:mx2] = self.base_gray[self.strip_y1:self.strip_y2, mx1:mx2]

        (shift_x, shift_y), response = cv2.phaseCorrelate(
            self.base_strip_float, np.float32(curr_strip), self.hann_strip
        )
        if response > 0.12 and abs(shift_x) < 24.0 and abs(shift_y) < 24.0:
            alpha = 0.45 if (abs(shift_x - self.global_dx) > 1.5 or abs(shift_y - self.global_dy) > 1.5) else 0.22
            self.global_dx = (1.0 - alpha) * self.global_dx + alpha * float(shift_x)
            self.global_dy = (1.0 - alpha) * self.global_dy + alpha * float(shift_y)

        target_dy_curve = np.full(self.rw, self.global_dy, dtype=np.float32)

        if len(self.init_pts) >= 4:
            init_2d = self.init_pts.reshape(-1, 2)
            pred_pts = init_2d.copy()
            pred_pts[:, 0] += self.global_dx
            pred_pts[:, 1] += self.global_dy
            pred_pts_lk = pred_pts.reshape(-1, 1, 2).astype(np.float32)

            next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self.base_gray,
                crop_gray,
                self.init_pts,
                pred_pts_lk,
                flags=cv2.OPTFLOW_USE_INITIAL_FLOW,
                **self.lk_params
            )
            if next_pts is not None and status is not None:
                next_2d = next_pts.reshape(-1, 2)
                good_mask = status.reshape(-1) == 1

                valid_x = []
                valid_dy = []
                under_mouse_dy = []

                for i in range(len(next_2d)):
                    if not good_mask[i]:
                        continue
                    px, py = float(next_2d[i, 0]), float(next_2d[i, 1])
                    ix, iy = float(init_2d[i, 0]), float(init_2d[i, 1])
                    dx_i = px - ix
                    dy_i = py - iy

                    if abs(dx_i - self.global_dx) > 7.5 or abs(dy_i - self.global_dy) > 11.0:
                        continue

                    if mx1 <= ix <= mx2:
                        if (self.global_dy - 0.5) <= dy_i <= (self.global_dy + 8.5):
                            under_mouse_dy.append(dy_i)
                    else:
                        valid_x.append(ix)
                        valid_dy.append(dy_i)

                if len(valid_x) >= 4:
                    med_bg_dy = float(np.median(valid_dy))
                    self.global_dy = 0.65 * self.global_dy + 0.35 * med_bg_dy
                    target_dy_curve.fill(self.global_dy)

                if mouse_bbox_local is not None and len(under_mouse_dy) >= 1:
                    local_sag = max(0.0, float(np.median(under_mouse_dy)) - self.global_dy)
                    if 0.4 <= local_sag <= 7.5:
                        mcx = float(mouse_bbox_local[0] + mouse_bbox_local[2] * 0.5)
                        sigma = max(35.0, float(mouse_bbox_local[2]) * 0.65)
                        xs_f = np.arange(self.rw, dtype=np.float32)
                        sag_bell = local_sag * np.exp(-0.5 * ((xs_f - mcx) / sigma) ** 2)
                        target_dy_curve = target_dy_curve + sag_bell.astype(np.float32)

        self.dy_curve_float = 0.65 * self.dy_curve_float + 0.35 * target_dy_curve

        max_dev = float(np.max(np.abs(self.dy_curve_float - self.global_dy)))
        if abs(self.global_dx) < 0.30 and float(np.max(np.abs(self.dy_curve_float))) < 0.30:
            self.cached_warped_bg = self.base_gray
            self.cached_warped_inv_ladder = self.base_inv_ladder
        elif max_dev < 0.35:
            M = np.float32([[1.0, 0.0, self.global_dx], [0.0, 1.0, float(np.median(self.dy_curve_float))]])
            self.cached_warped_bg = cv2.warpAffine(
                self.base_gray, M, (self.rw, self.rh), borderMode=cv2.BORDER_REPLICATE
            )
            self.cached_warped_inv_ladder = cv2.warpAffine(
                self.base_inv_ladder, M, (self.rw, self.rh), borderMode=cv2.BORDER_CONSTANT, borderValue=255
            )
        else:
            map_x = (self.grid_x - np.float32(self.global_dx)).astype(np.float32)
            map_y = (self.grid_y - self.dy_curve_float[None, :]).astype(np.float32)
            self.cached_warped_bg = cv2.remap(
                self.base_gray, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
            )
            self.cached_warped_inv_ladder = cv2.remap(
                self.base_inv_ladder, map_x, map_y, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=255
            )

        self.cached_fault_curve = np.clip(
            np.round(self.base_fault_y_local + self.dy_curve_float), 10, self.rh - 2
        ).astype(np.int32)

        return self.cached_warped_bg, self.cached_warped_inv_ladder, self.cached_fault_curve


# ==============================================================================
# DEEPLABCUT / YOLO / BIOMECHANICAL POSE CLASSIFIER
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

                    cx1, cy1 = max(0, dx - 180), max(0, dy - 160)
                    cx2, cy2 = min(fw, dx + 180), min(fh, dy + 100)
                    crop_img = frame[cy1:cy2, cx1:cx2]

                    base_fname = f"egyed_{animal_id}_{video_name}_run{run_num}_dip{d_idx}_{d['sec']:.2f}s.jpg"
                    save_image_unicode(os.path.join(crops_dir, base_fname), crop_img)
                    save_image_unicode(os.path.join(full_dir, base_fname), frame)

                    manifest.append({
                        "file": base_fname,
                        "animal_id": animal_id,
                        "run": run_num,
                        "sec": round(d["sec"], 3),
                        "global_dip_xy": [dx, dy],
                        "crop_bbox_xyxy": [cx1, cy1, cx2, cy2],
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

        self.log(f"[Active Learning] {exported_count} training crops exported to: {os.path.abspath(base_folder)}")
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
                    elif any(k in best_part for k in ("paw", "knee", "ankle", "wrist", "elbow", "foot", "limb")):
                        d["dlc_part"] = f"MANCS / LÁB ({best_part})"
                        d["dlc_code"] = "PAW"
                    elif any(k in best_part for k in ("tail", "hip", "back", "pelvis")):
                        d["dlc_part"] = f"FAROK ({best_part})"
                        d["dlc_code"] = "HIND_TAIL"
                    else:
                        d["dlc_part"] = f"LÁB ({best_part})"
                        d["dlc_code"] = "PAW"
            return True
        except Exception:
            return False

    def classify_dips_with_superanimal(self, pending_results):
        self.log("🧠 [Anatomical Classifier] Classifying dip events (Forelimb/Hindlimb vs. Snout vs. Tail)...")
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
            except Exception:
                pass
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        for res in pending_results:
            for r in res["runs"]:
                traj = r["trajectory"]
                for d in r["dips"]:
                    if parsed_from_dlc and d.get("dlc_classified_by_nn"):
                        continue

                    dx, dy, d_sec = d["x"], d["y"], d["sec"]
                    move_dir = float(d.get("move_dir", 1.0))
                    if "move_dir" not in d and len(traj) >= 2:
                        near_pts = [pt for pt in traj if abs(pt[2] - d_sec) <= 0.60]
                        if len(near_pts) >= 2 and abs(near_pts[-1][0] - near_pts[0][0]) > 35:
                            move_dir = 1.0 if (near_pts[-1][0] - near_pts[0][0]) > 0 else -1.0
                        else:
                            move_dir = 1.0 if (traj[-1][0] - traj[0][0]) >= 0 else -1.0

                    if "torso_left_x" in d and "torso_width" in d:
                        b_left = float(d["torso_left_x"])
                        b_w = max(24.0, float(d["torso_width"]))
                        if move_dir >= 0:
                            rel_pos_norm = (dx - b_left) / b_w
                        else:
                            rel_pos_norm = ((b_left + b_w) - dx) / b_w
                    elif "body_left_x" in d and "body_width" in d:
                        b_left = float(d["body_left_x"])
                        b_w = max(28.0, float(d["body_width"]))
                        if move_dir >= 0:
                            rel_pos_norm = (dx - b_left) / b_w
                        else:
                            rel_pos_norm = ((b_left + b_w) - dx) / b_w
                    else:
                        closest_pt = min(traj, key=lambda pt: abs(pt[2] - d_sec)) if traj else (dx, dy, d_sec)
                        cx_body = closest_pt[0]
                        rel_pos_norm = 0.5 + (move_dir * (dx - cx_body) / 90.0)

                    aspect_ratio = float(d.get("dip_aspect", 1.0))
                    dip_depth = float(d.get("dip_depth", 10.0))
                    skin_score = float(d.get("paw_skin_score", 0.0))
                    head_pitch_down = bool(d.get("head_pitch_down", False))

                    part_label, part_code = self.classify_dip_features(
                        rel_pos_norm, aspect_ratio, dip_depth, skin_score, head_pitch_down
                    )
                    d["dlc_part"] = part_label
                    d["dlc_code"] = part_code

    @staticmethod
    def classify_dip_features(rel_pos_norm, aspect_ratio, dip_depth, skin_score=0.0, head_pitch_down=False):
        """
        Robust anatomical classification:
        - 0.00 .. 0.15: Tail / Rump (FAROK)
        - 0.15 .. 0.50: Hindlimb Foot Fault (HÁTSÓ LÁB)
        - 0.50 .. 0.85: Forelimb Foot Fault (MELLSŐ LÁB)
        - 0.85 .. 1.00: Snout / Nose Exploration (ORR)
        """
        # 1. Extreme anterior: Snout / Nose Exploration
        if rel_pos_norm >= 0.85:
            return "ORR (Exploráció)", "NOSE"

        # Transition zone: 0.80 - 0.85 (Forepaw vs. Snout)
        if rel_pos_norm >= 0.80:
            if head_pitch_down and dip_depth < 16.0 and skin_score < 10.0:
                return "ORR (Exploráció)", "NOSE"
            return "MELLSŐ LÁB (Lábhiba)", "PAW"

        # 2. Posterior Tail / Rump Zone
        if rel_pos_norm < 0.18 or (rel_pos_norm < 0.24 and aspect_ratio > 1.6 and dip_depth < 14.0):
            return "FAROK (Billenés)", "HIND_TAIL"

        # 3. Hindlimb vs. Forelimb Foot-Fault Zone
        if rel_pos_norm < 0.50:
            return "HÁTSÓ LÁB (Lábhiba)", "PAW"
        return "MELLSŐ LÁB (Lábhiba)", "PAW"

    def harvest_training_samples(self, app_ref, video_paths=None, max_samples_per_video=45, progress_cb=None, stop_event=None):
        """
        Extracts high-confidence rodent candidate frames with anatomy and bounding boxes from videos.
        Uses fast cap.grab() frame stepping for sub-second scanning speed.
        """
        if video_paths is None:
            video_paths = [v["path"] for v in getattr(app_ref, "video_data", []) if os.path.exists(v.get("path", ""))]
        if not video_paths:
            self.log("⚠ [Rodent AI Trainer] No loaded videos.")
            return []

        harvested = []
        sample_count = 0

        for v_idx, v_path in enumerate(video_paths):
            if stop_event and stop_event.is_set():
                break
            cap = cv2.VideoCapture(v_path)
            if not cap.isOpened():
                continue

            auto_res = app_ref.auto_engine.auto_calibrate_from_video(cap, num_bg_samples=24)
            rx, ry, rw, rh = auto_res["rx"], auto_res["ry"], auto_res["rw"], auto_res["rh"]
            lg_x, rg_x = auto_res.get("left_gate_x", 120), auto_res.get("right_gate_x", rw - 120)
            dark_t = auto_res["calib_dark_thresh"]
            diff_t = auto_res["calib_diff_thresh"]
            ladder_t = auto_res["calib_ladder_thresh"]
            fault_y_local = int(rh * (auto_res["calib_fault_Ratio"] / 100.0))

            base_gray = app_ref._compute_clean_background(cap, rx, ry, rw, rh, num_samples=24)
            if base_gray is None:
                cap.release()
                continue
            inv_ladder = cv2.bitwise_not(app_ref._create_ladder_mask(base_gray, ladder_t, fault_y_local=fault_y_local))

            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
            step = max(3, total_f // max(30, max_samples_per_video * 2))
            f_idx = 0
            collected = 0
            fc = np.full(rw, fault_y_local, dtype=np.int32)

            while cap.isOpened() and collected < max_samples_per_video:
                if stop_event and stop_event.is_set():
                    break
                if f_idx % step == 0:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    crop = frame[ry:ry + rh, rx:rx + rw]
                    det, mask, bbox, _ = app_ref._detect_mouse_on_crop(
                        crop, base_gray, inv_ladder, rw, rh, dark_t, diff_t,
                        fault_y_local=fault_y_local, return_skin=True, use_yolo=False
                    )
                    if det and bbox is not None and mask is not None:
                        bx, by, bw, bh = bbox
                        area = int(cv2.countNonZero(mask))
                        aspect = bw / float(max(1, bh))
                        cx = bx + bw * 0.5

                        # --- SMART RODENT SANITY FILTERS ---
                        # 1. Strictly exclude start & goal box wall touches
                        if bx < 35 or (bx + bw) > (rw - 35) or cx < (lg_x + 10) or cx > (rg_x - 10):
                            f_idx += 1
                            continue

                        # 2. Reject human hands & arms reaching from ceiling (top of frame)
                        if by <= 12 and bh > 140:
                            f_idx += 1
                            continue
                        if bh > 165 or by + bh >= rh - 2:
                            f_idx += 1
                            continue

                        # 3. Horizontal rodent elongation check
                        if aspect < 1.15 or aspect > 6.2:
                            f_idx += 1
                            continue

                        # 4. Realistic rodent dimensions & mass
                        if bw < 45 or bw > 750 or bh < 22 or area < 2800 or area > 42000:
                            f_idx += 1
                            continue

                        # Sharpness & Quality Check (Laplacian variance on rodent ROI)
                        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        mouse_roi = gray_crop[by:by + bh, bx:bx + bw]
                        lap_var = float(cv2.Laplacian(mouse_roi, cv2.CV_64F).var()) if mouse_roi.size > 0 else 0.0

                        # Pre-exclude marginal or blurred frames by default
                        is_marginal = (lap_var < 16.0) or (aspect < 1.35) or (area < 4500)
                        quality_score = int(np.clip(35.0 + lap_var * 0.4 + (aspect / 4.0) * 30.0, 10, 99))

                        anatomy = app_ref._extract_rodent_anatomy(mask, fc, bbox, move_dir=1.0, crop=crop)
                        sample = {
                            "uid": f"sample_{sample_count}",
                            "crop": crop.copy(),
                            "bbox": bbox,
                            "mask": mask.copy(),
                            "area": area,
                            "fault_y_local": fault_y_local,
                            "anatomy": anatomy,
                            "v_idx": v_idx,
                            "v_path": v_path,
                            "video_name": os.path.basename(v_path),
                            "f_idx": f_idx,
                            "sec": float(f_idx / fps),
                            "aspect": aspect,
                            "quality": quality_score,
                            "excluded": bool(is_marginal),
                            "ai_pred_bbox": None,
                        }
                        harvested.append(sample)
                        sample_count += 1
                        collected += 1
                        if progress_cb:
                            progress_cb(sample, sample_count)
                else:
                    if not cap.grab():
                        break
                f_idx += 1
            cap.release()

        return harvested

    def train_rodent_detector_from_samples(self, app_ref, samples, epochs=10, imgsz=256, progress_cb=None, stop_event=None):
        """
        Fine-tunes YOLOv8n detector strictly from active, validated rodent samples.
        Any sample with s['excluded'] == True is completely omitted from the training set.
        Generates both wide-context ladder images and high-resolution rodent-centered crops.
        """
        active = [s for s in samples if not s.get("excluded", False)]
        omitted_count = len(samples) - len(active)
        self.log(f"🧠 [Rodent AI Trainer] Dataset summary: {len(active)} active rodent samples. {omitted_count} excluded samples completely omitted from training.")

        if len(active) < 6:
            self.log(f"⚠ [Rodent AI Trainer] Need at least 6 active samples (have {len(active)} active, {omitted_count} excluded).")
            if progress_cb:
                progress_cb(0.0, f"Hiba: Legalább 6 aktív minta szükséges a betanításhoz! (Jelenleg {len(active)} aktív, {omitted_count} kizárva)")
            return None

        import torch
        train_device = "cpu"
        if torch.backends.mps.is_available():
            train_device = "mps"
        elif torch.cuda.is_available():
            train_device = "cuda:0"

        dataset_dir = tempfile.mkdtemp(prefix="rodent_yolo_ds_")
        try:
            img_tr = os.path.join(dataset_dir, "images", "train")
            img_va = os.path.join(dataset_dir, "images", "val")
            lbl_tr = os.path.join(dataset_dir, "labels", "train")
            lbl_va = os.path.join(dataset_dir, "labels", "val")
            for d_p in (img_tr, img_va, lbl_tr, lbl_va):
                os.makedirs(d_p, exist_ok=True)

            for idx, s in enumerate(active):
                crop = s["crop"]
                bx, by, bw, bh = s["bbox"]
                rh, rw = crop.shape[:2]

                is_val = (idx % 5 == 0)
                tgt_img = img_va if is_val else img_tr
                tgt_lbl = lbl_va if is_val else lbl_tr

                # 1. Full Ladder Crop (wide spatial context)
                cx_n = np.clip((bx + bw * 0.5) / float(rw), 0.01, 0.99)
                cy_n = np.clip((by + bh * 0.5) / float(rh), 0.01, 0.99)
                bw_n = np.clip(bw / float(rw), 0.02, 0.98)
                bh_n = np.clip(bh / float(rh), 0.02, 0.98)

                stem_full = f"rodent_f_{idx:04d}"
                cv2.imwrite(os.path.join(tgt_img, f"{stem_full}.jpg"), crop)
                with open(os.path.join(tgt_lbl, f"{stem_full}.txt"), "w", encoding="utf-8") as lf:
                    lf.write(f"0 {cx_n:.6f} {cy_n:.6f} {bw_n:.6f} {bh_n:.6f}\n")

                # 2. Rodent-Centric Context Crop (high-resolution fur, paws, snout features)
                pad_w = int(max(60, bw * 0.40))
                pad_h = int(max(30, bh * 0.40))
                c_x1 = max(0, bx - pad_w)
                c_y1 = max(0, by - pad_h)
                c_x2 = min(rw, bx + bw + pad_w)
                c_y2 = min(rh, by + bh + pad_h)

                ctx_crop = crop[c_y1:c_y2, c_x1:c_x2]
                ch, cw = ctx_crop.shape[:2]
                if ch >= 20 and cw >= 30:
                    rel_bx = bx - c_x1
                    rel_by = by - c_y1
                    rel_cx_n = np.clip((rel_bx + bw * 0.5) / float(cw), 0.01, 0.99)
                    rel_cy_n = np.clip((rel_by + bh * 0.5) / float(ch), 0.01, 0.99)
                    rel_bw_n = np.clip(bw / float(cw), 0.02, 0.98)
                    rel_bh_n = np.clip(bh / float(ch), 0.02, 0.98)

                    stem_ctx = f"rodent_c_{idx:04d}"
                    cv2.imwrite(os.path.join(tgt_img, f"{stem_ctx}.jpg"), ctx_crop)
                    with open(os.path.join(tgt_lbl, f"{stem_ctx}.txt"), "w", encoding="utf-8") as lf:
                        lf.write(f"0 {rel_cx_n:.6f} {rel_cy_n:.6f} {rel_bw_n:.6f} {rel_bh_n:.6f}\n")

            yaml_path = os.path.join(dataset_dir, "rodent.yaml")
            yaml_content = f"path: {dataset_dir}\ntrain: images/train\nval: images/val\nnames:\n  0: rodent\n"
            with open(yaml_path, "w", encoding="utf-8") as yf:
                yf.write(yaml_content)

            base_pt = get_resource_path("yolov8n.pt")
            if not os.path.exists(base_pt):
                base_pt = "yolov8n.pt"

            runs_dir = os.path.join(dataset_dir, "runs")
            train_script = os.path.join(dataset_dir, "run_train.py")
            script_code = (
                "from ultralytics import YOLO\n"
                f"model = YOLO({repr(base_pt)})\n"
                "model.train(\n"
                f"    data={repr(yaml_path)},\n"
                f"    epochs={int(epochs)},\n"
                f"    imgsz={int(imgsz)},\n"
                "    batch=16,\n"
                f"    device={repr(train_device)},\n"
                f"    project={repr(runs_dir)},\n"
                "    name='rodent_run',\n"
                "    exist_ok=True,\n"
                "    fliplr=0.0,\n"
                "    amp=False,\n"
                "    verbose=False,\n"
                "    plots=False,\n"
                "    workers=0,\n"
                ")\n"
            )
            with open(train_script, "w", encoding="utf-8") as sf:
                sf.write(script_code)

            if progress_cb:
                progress_cb(5.0, f"Tréning indítása: {len(active)} minta, {epochs} korszak ({train_device.upper()})...")

            proc = subprocess.Popen(
                [sys.executable, train_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            current_ep = 0
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                parts = line_str.split()
                for p in parts:
                    if "/" in p:
                        sub = p.split("/")
                        if len(sub) == 2 and sub[0].isdigit() and sub[1].isdigit():
                            ep_num = int(sub[0])
                            tot_ep = int(sub[1])
                            if tot_ep == int(epochs):
                                current_ep = ep_num
                                pct = min(95.0, 5.0 + 90.0 * (current_ep / float(tot_ep)))
                                if progress_cb:
                                    progress_cb(pct, f"Korszak {current_ep}/{tot_ep}: Betanítás folyamatban ({train_device.upper()})...")
                                break
                if progress_cb and ("loss" in line_str.lower() or "map" in line_str.lower()):
                    progress_cb(min(95.0, 5.0 + 90.0 * (current_ep / float(epochs))), line_str[:65])

            proc.wait()

            best_pt = os.path.join(runs_dir, "rodent_run", "weights", "best.pt")
            if not os.path.exists(best_pt):
                best_pt = os.path.join(runs_dir, "rodent_run", "weights", "last.pt")

            if os.path.exists(best_pt):
                target_pt = os.path.join(SAFE_BASE_DIR, "rodent_detector.pt")
                shutil.copy2(best_pt, target_pt)
                try:
                    local_pt = get_resource_path("rodent_detector.pt")
                    if os.path.abspath(local_pt) != os.path.abspath(target_pt):
                        shutil.copy2(best_pt, local_pt)
                except Exception:
                    pass
                self.log(f"✅ [Rodent AI Trainer] Custom model saved: {target_pt}")
                if hasattr(app_ref, "hybrid_locator"):
                    app_ref.hybrid_locator._init_yolo()
                    if hasattr(app_ref, "_refresh_kpi_summary"):
                        app_ref.root.after(0, app_ref._refresh_kpi_summary)
                if progress_cb:
                    progress_cb(100.0, f"✅ Betanítás sikeres! Modell mentve: rodent_detector.pt")
                return target_pt
            else:
                if progress_cb:
                    progress_cb(0.0, "❌ Hiba: A betanított súlyfájl nem jött létre.")
                return None
        except Exception as exc:
            self.log(f"❌ [Rodent AI Trainer] Training error: {exc}")
            if progress_cb:
                progress_cb(0.0, f"Hiba a tréning során: {exc}")
            return None
        finally:
            shutil.rmtree(dataset_dir, ignore_errors=True)

    def train_rodent_pose_from_samples(self, app_ref, samples, epochs=12, imgsz=256, progress_cb=None, stop_event=None):
        """
        Fine-tunes the 9-keypoint Rodent Pose AI (mouse_pose_ai.pt) strictly from active samples.
        Specifically optimizes paw detection (Forepaw and Hindpaw keypoints).
        Any sample with s['excluded'] == True is strictly excluded.
        Generates:
        1. Full ladder crop (wide-context spatial layout)
        2. High-resolution rodent and ventral limb crop (detailed paw textures & rung contacts)
        """
        active = [s for s in samples if not s.get("excluded", False)]
        omitted_count = len(samples) - len(active)
        self.log(f"🧠 [Paw AI Trainer] Dataset summary: {len(active)} active rodent samples. {omitted_count} excluded samples completely omitted from training.")

        if len(active) < 6:
            self.log(f"⚠ [Paw AI Trainer] Need at least 6 active samples (have {len(active)} active, {omitted_count} excluded).")
            if progress_cb:
                progress_cb(0.0, f"Hiba: Legalább 6 aktív minta szükséges a betanításhoz! (Jelenleg {len(active)} aktív, {omitted_count} kizárva)")
            return None

        import torch
        train_device = "cpu"
        if torch.backends.mps.is_available():
            train_device = "mps"
        elif torch.cuda.is_available():
            train_device = "cuda:0"

        dataset_dir = tempfile.mkdtemp(prefix="mouse_pose_ds_")
        try:
            img_tr = os.path.join(dataset_dir, "images", "train")
            img_va = os.path.join(dataset_dir, "images", "val")
            lbl_tr = os.path.join(dataset_dir, "labels", "train")
            lbl_va = os.path.join(dataset_dir, "labels", "val")
            for d_p in (img_tr, img_va, lbl_tr, lbl_va):
                os.makedirs(d_p, exist_ok=True)

            kpt_order = [
                "nose_pt", "head_pt", "shoulder_pt", "fore_paw_pt",
                "spine_mid", "hip_pt", "hind_paw_pt", "tail_base", "tail_tip"
            ]

            for idx, s in enumerate(active):
                crop = s["crop"]
                bx, by, bw, bh = s["bbox"]
                rh, rw = crop.shape[:2]
                anat = s.get("anatomy") or {}

                is_val = (idx % 5 == 0)
                tgt_img = img_va if is_val else img_tr
                tgt_lbl = lbl_va if is_val else lbl_tr

                # Determine keypoint coordinates in full-crop space
                kpts_coords = {}
                for k_name in kpt_order:
                    pt = anat.get(k_name)
                    if pt is not None:
                        kpts_coords[k_name] = (float(pt[0]), float(pt[1]))
                    else:
                        if k_name == "nose_pt":
                            kpts_coords[k_name] = (float(bx + bw), float(by + bh * 0.6))
                        elif k_name == "head_pt":
                            kpts_coords[k_name] = (float(bx + bw * 0.85), float(by + bh * 0.5))
                        elif k_name == "shoulder_pt":
                            kpts_coords[k_name] = (float(bx + bw * 0.65), float(by + bh * 0.5))
                        elif k_name == "fore_paw_pt":
                            kpts_coords[k_name] = (float(bx + bw * 0.60), float(by + bh * 0.9))
                        elif k_name == "spine_mid":
                            kpts_coords[k_name] = (float(bx + bw * 0.48), float(by + bh * 0.45))
                        elif k_name == "hip_pt":
                            kpts_coords[k_name] = (float(bx + bw * 0.25), float(by + bh * 0.5))
                        elif k_name == "hind_paw_pt":
                            kpts_coords[k_name] = (float(bx + bw * 0.22), float(by + bh * 0.9))
                        elif k_name == "tail_base":
                            kpts_coords[k_name] = (float(bx + bw * 0.05), float(by + bh * 0.5))
                        else:
                            kpts_coords[k_name] = (float(max(0, bx - 15)), float(by + bh * 0.5))

                # 1. Full Ladder Crop (wide spatial context)
                cx_n = np.clip((bx + bw * 0.5) / float(rw), 0.01, 0.99)
                cy_n = np.clip((by + bh * 0.5) / float(rh), 0.01, 0.99)
                bw_n = np.clip(bw / float(rw), 0.02, 0.98)
                bh_n = np.clip(bh / float(rh), 0.02, 0.98)

                lbl_parts_full = [f"0 {cx_n:.6f} {cy_n:.6f} {bw_n:.6f} {bh_n:.6f}"]
                for k_name in kpt_order:
                    kx, ky = kpts_coords[k_name]
                    kx_n = np.clip(kx / float(rw), 0.001, 0.999)
                    ky_n = np.clip(ky / float(rh), 0.001, 0.999)
                    lbl_parts_full.append(f"{kx_n:.6f} {ky_n:.6f} 2")
                lbl_line_full = " ".join(lbl_parts_full) + "\n"

                stem_full = f"pose_f_{idx:04d}"
                cv2.imwrite(os.path.join(tgt_img, f"{stem_full}.jpg"), crop)
                with open(os.path.join(tgt_lbl, f"{stem_full}.txt"), "w", encoding="utf-8") as lf:
                    lf.write(lbl_line_full)

                # 2. Rodent & Paw Zoom Crop (High Resolution context focused on paw contacts)
                pad_w = int(max(40, bw * 0.35))
                pad_h_top = int(max(20, bh * 0.25))
                pad_h_bot = int(max(30, bh * 0.45))
                c_x1 = max(0, bx - pad_w)
                c_y1 = max(0, by - pad_h_top)
                c_x2 = min(rw, bx + bw + pad_w)
                c_y2 = min(rh, by + bh + pad_h_bot)

                ctx_crop = crop[c_y1:c_y2, c_x1:c_x2]
                ch, cw = ctx_crop.shape[:2]
                if ch >= 30 and cw >= 40:
                    rel_bx = bx - c_x1
                    rel_by = by - c_y1
                    rel_cx_n = np.clip((rel_bx + bw * 0.5) / float(cw), 0.01, 0.99)
                    rel_cy_n = np.clip((rel_by + bh * 0.5) / float(ch), 0.01, 0.99)
                    rel_bw_n = np.clip(bw / float(cw), 0.02, 0.98)
                    rel_bh_n = np.clip(bh / float(ch), 0.02, 0.98)

                    lbl_parts_ctx = [f"0 {rel_cx_n:.6f} {rel_cy_n:.6f} {rel_bw_n:.6f} {rel_bh_n:.6f}"]
                    for k_name in kpt_order:
                        kx, ky = kpts_coords[k_name]
                        rel_kx = np.clip((kx - c_x1) / float(cw), 0.001, 0.999)
                        rel_ky = np.clip((ky - c_y1) / float(ch), 0.001, 0.999)
                        lbl_parts_ctx.append(f"{rel_kx:.6f} {rel_ky:.6f} 2")
                    lbl_line_ctx = " ".join(lbl_parts_ctx) + "\n"

                    stem_ctx = f"pose_c_{idx:04d}"
                    cv2.imwrite(os.path.join(tgt_img, f"{stem_ctx}.jpg"), ctx_crop)
                    with open(os.path.join(tgt_lbl, f"{stem_ctx}.txt"), "w", encoding="utf-8") as lf:
                        lf.write(lbl_line_ctx)

            yaml_path = os.path.join(dataset_dir, "mouse_pose.yaml")
            yaml_content = (
                f"path: {dataset_dir}\n"
                f"train: images/train\n"
                f"val: images/val\n"
                f"kpt_shape: [9, 3]\n"
                f"flip_idx: [0, 1, 2, 3, 4, 5, 6, 7, 8]\n"
                f"names:\n"
                f"  0: rodent\n"
            )
            with open(yaml_path, "w", encoding="utf-8") as yf:
                yf.write(yaml_content)

            base_pt = get_resource_path("mouse_pose_ai.pt")
            if not os.path.exists(base_pt):
                base_pt = get_resource_path("yolov8n-pose.pt")
            if not os.path.exists(base_pt):
                base_pt = "yolov8n-pose.pt"

            runs_dir = os.path.join(dataset_dir, "runs")
            train_script = os.path.join(dataset_dir, "run_train.py")
            script_code = (
                "from ultralytics import YOLO\n"
                f"model = YOLO({repr(base_pt)})\n"
                "model.train(\n"
                f"    data={repr(yaml_path)},\n"
                f"    epochs={int(epochs)},\n"
                f"    imgsz={int(imgsz)},\n"
                "    batch=16,\n"
                f"    device={repr(train_device)},\n"
                f"    project={repr(runs_dir)},\n"
                "    name='mouse_pose_run',\n"
                "    exist_ok=True,\n"
                "    fliplr=0.0,\n"
                "    amp=False,\n"
                "    verbose=False,\n"
                "    plots=False,\n"
                "    workers=0,\n"
                ")\n"
            )
            with open(train_script, "w", encoding="utf-8") as sf:
                sf.write(script_code)

            if progress_cb:
                progress_cb(5.0, f"Tréning indítása: {len(active)} aktív minta, {epochs} korszak ({train_device.upper()})...")

            proc = subprocess.Popen(
                [sys.executable, train_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            current_ep = 0
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                parts = line_str.split()
                for p in parts:
                    if "/" in p:
                        sub = p.split("/")
                        if len(sub) == 2 and sub[0].isdigit() and sub[1].isdigit():
                            ep_num = int(sub[0])
                            tot_ep = int(sub[1])
                            if tot_ep == int(epochs):
                                current_ep = ep_num
                                pct = min(95.0, 5.0 + 90.0 * (current_ep / float(tot_ep)))
                                if progress_cb:
                                    progress_cb(pct, f"Korszak {current_ep}/{tot_ep}: 9-pontos Paw Pose tréning ({train_device.upper()})...")
                                break
                if progress_cb and ("loss" in line_str.lower() or "map" in line_str.lower()):
                    progress_cb(min(95.0, 5.0 + 90.0 * (current_ep / float(epochs))), line_str[:65])

            proc.wait()

            best_pt = os.path.join(runs_dir, "mouse_pose_run", "weights", "best.pt")
            if not os.path.exists(best_pt):
                best_pt = os.path.join(runs_dir, "mouse_pose_run", "weights", "last.pt")

            if os.path.exists(best_pt):
                target_pt = os.path.join(SAFE_BASE_DIR, "mouse_pose_ai.pt")
                shutil.copy2(best_pt, target_pt)
                try:
                    local_pt = get_resource_path("mouse_pose_ai.pt")
                    if os.path.abspath(local_pt) != os.path.abspath(target_pt):
                        shutil.copy2(best_pt, local_pt)
                except Exception:
                    pass
                self.log(f"✅ [Paw AI Trainer] Custom 9-keypoint Paw Pose model saved: {target_pt}")
                if hasattr(app_ref, "hybrid_locator"):
                    app_ref.hybrid_locator._init_yolo()
                    if hasattr(app_ref, "_refresh_kpi_summary"):
                        app_ref.root.after(0, app_ref._refresh_kpi_summary)
                if progress_cb:
                    progress_cb(100.0, f"✅ Betanítás sikeres! Modell mentve: mouse_pose_ai.pt (Mancs & Tartás specializáció)")
                return target_pt
            else:
                if progress_cb:
                    progress_cb(0.0, "❌ Hiba: A betanított súlyfájl nem jött létre.")
                return None
        except Exception as exc:
            self.log(f"❌ [Paw AI Trainer] Training error: {exc}")
            if progress_cb:
                progress_cb(0.0, f"Hiba a tréning során: {exc}")
            return None
        finally:
            shutil.rmtree(dataset_dir, ignore_errors=True)

    def test_model_on_samples(self, model_path, samples):
        """
        Runs post-training verification strictly on active (non-excluded) preview samples.
        Any sample marked as excluded is explicitly skipped and has its ai_pred_bbox & ai_pred_pose wiped.
        Extracts both bounding boxes and 9 anatomical keypoints (Forepaw and Hindpaw).
        """
        for s in samples:
            if s.get("excluded", False):
                s["ai_pred_bbox"] = None
                s["ai_pred_pose"] = None

        if not os.path.exists(model_path):
            return 0, 0
        try:
            from ultralytics import YOLO
            model = YOLO(model_path)
            is_pose = ("pose" in model_path.lower()) or getattr(model, "task", "") == "pose"
            kpt_order = [
                "nose_pt", "head_pt", "shoulder_pt", "fore_paw_pt",
                "spine_mid", "hip_pt", "hind_paw_pt", "tail_base", "tail_tip"
            ]
            detected_count = 0
            active_count = 0
            for s in samples:
                # STRICT EXCLUSION ENFORCEMENT:
                if s.get("excluded", False):
                    s["ai_pred_bbox"] = None
                    s["ai_pred_pose"] = None
                    continue

                active_count += 1
                crop = s.get("crop")
                if crop is None:
                    s["ai_pred_bbox"] = None
                    s["ai_pred_pose"] = None
                    continue

                res = model.predict(crop, imgsz=256, conf=0.18, verbose=False)
                if res and len(res) > 0 and len(res[0].boxes) > 0:
                    box = res[0].boxes[0]
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
                    s["ai_pred_bbox"] = (x1, y1, max(1, x2 - x1), max(1, y2 - y1), conf)
                    detected_count += 1

                    # Extract Keypoints for Pose Model:
                    if is_pose and getattr(res[0], "keypoints", None) is not None and res[0].keypoints.xy is not None and len(res[0].keypoints.xy) > 0:
                        kpts_xy = res[0].keypoints.xy[0].cpu().numpy()
                        kpts_conf = (
                            res[0].keypoints.conf[0].cpu().numpy()
                            if getattr(res[0].keypoints, "conf", None) is not None
                            else np.ones(len(kpts_xy), dtype=np.float32)
                        )
                        parsed_pose = {}
                        for k_idx, k_name in enumerate(kpt_order):
                            if k_idx < len(kpts_xy):
                                kx, ky = float(kpts_xy[k_idx][0]), float(kpts_xy[k_idx][1])
                                kc = float(kpts_conf[k_idx]) if k_idx < len(kpts_conf) else 1.0
                                if kx > 1.0 and ky > 1.0:
                                    parsed_pose[k_name] = (int(round(kx)), int(round(ky)))
                                    parsed_pose[k_name + "_conf"] = kc
                        s["ai_pred_pose"] = parsed_pose
                    else:
                        s["ai_pred_pose"] = None
                else:
                    s["ai_pred_bbox"] = None
                    s["ai_pred_pose"] = None
            return detected_count, active_count
        except Exception as exc:
            self.log(f"⚠ [Rodent AI] Prediction error: {exc}")
            return 0, 0

    def train_custom_rodent_detector(self, app_ref, video_paths=None, epochs=10, imgsz=256, max_samples_per_video=45):
        """
        1-Click background training pipeline without preview GUI.
        """
        if not self.yolo_available:
            self.log("❌ [Rodent AI Trainer] 'ultralytics' package not available.")
            return None
        self.log("🧠 [Rodent AI Trainer] Harvesting training frames...")
        samples = self.harvest_training_samples(app_ref, video_paths=video_paths, max_samples_per_video=max_samples_per_video)
        if len(samples) < 6:
            self.log(f"⚠ [Rodent AI Trainer] Harvested {len(samples)} frames (need >=6). Make sure videos contain visible mice!")
            return None
        return self.train_rodent_pose_from_samples(app_ref, samples, epochs=epochs, imgsz=imgsz)

    def train_custom_yolo_pose_model(self, app_ref, video_paths=None, epochs=14, imgsz=256, max_samples_per_video=45):
        if not self.yolo_available:
            self.log("❌ [AI Pose Trainer] 'ultralytics' package not available.")
            return None

        if video_paths is None:
            video_paths = [v["path"] for v in getattr(app_ref, "video_data", []) if os.path.exists(v.get("path", ""))]
        if not video_paths:
            self.log("⚠ [AI Pose Trainer] No loaded videos for training.")
            return None

        import torch
        if torch.cuda.is_available():
            train_device = "cuda:0"
        elif sys.platform == "darwin":
            train_device = "cpu"
        else:
            train_device = "cpu"

        dataset_dir = tempfile.mkdtemp(prefix="mouse_yolo_pose_ds_")
        try:
            img_tr = os.path.join(dataset_dir, "images", "train")
            img_va = os.path.join(dataset_dir, "images", "val")
            lbl_tr = os.path.join(dataset_dir, "labels", "train")
            lbl_va = os.path.join(dataset_dir, "labels", "val")
            for d_p in (img_tr, img_va, lbl_tr, lbl_va):
                os.makedirs(d_p, exist_ok=True)

            kpt_order = [
                "nose_pt", "head_pt", "shoulder_pt", "fore_paw_pt",
                "spine_mid", "hip_pt", "hind_paw_pt", "tail_base", "tail_tip"
            ]
            rng = np.random.default_rng(42)
            sample_count = 0
            pair_idx = 0

            self.log(f"🧠 [AI Pose Trainer] Building 9-keypoint rodent dataset from {len(video_paths)} videos...")

            for v_idx, v_path in enumerate(video_paths):
                cap = cv2.VideoCapture(v_path)
                if not cap.isOpened():
                    continue
                auto_res = app_ref.auto_engine.auto_calibrate_from_video(cap, num_bg_samples=24)
                rx, ry, rw, rh = auto_res["rx"], auto_res["ry"], auto_res["rw"], auto_res["rh"]
                dark_t = auto_res["calib_dark_thresh"]
                diff_t = auto_res["calib_diff_thresh"]
                ladder_t = auto_res["calib_ladder_thresh"]
                fault_pct = auto_res["calib_fault_Ratio"]
                fault_y_local = int(rh * (fault_pct / 100.0))
                base_gray = app_ref._compute_clean_background(cap, rx, ry, rw, rh, num_samples=24)
                if base_gray is None:
                    cap.release()
                    continue
                base_smooth = cv2.GaussianBlur(base_gray, (3, 3), 0)
                ladder_m = app_ref._create_ladder_mask(base_gray, ladder_t, fault_y_local=fault_y_local)
                inv_ladder = cv2.bitwise_not(ladder_m)
                fault_curve = np.full(rw, fault_y_local, dtype=np.int32)

                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 300
                step = max(2, total_f // max(45, max_samples_per_video * 3))
                f_idx = 0
                prev_bbox = None
                collected_vid = 0

                while cap.isOpened() and collected_vid < max_samples_per_video:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if f_idx % step != 0:
                        f_idx += 1
                        continue
                    f_idx += 1

                    crop = frame[ry:ry + rh, rx:rx + rw]
                    det, mask, bbox, skin_m = app_ref._detect_mouse_on_crop(
                        crop, base_gray, inv_ladder, rw, rh, dark_t, diff_t,
                        fault_y_local=fault_y_local, previous_bbox=prev_bbox,
                        base_smooth_cached=base_smooth, return_skin=True, use_yolo=False
                    )
                    if not det or bbox is None or mask is None:
                        prev_bbox = None
                        continue
                    prev_bbox = bbox
                    bx, by, bw, bh = bbox
                    if bw < 32 or bh < 22 or bx <= 4 or (bx + bw) >= rw - 4:
                        continue

                    anat = app_ref._extract_rodent_anatomy(
                        mask, fault_curve, bbox, previous_bbox=prev_bbox,
                        move_dir=1.0, crop=crop, skin_map=skin_m
                    )
                    if anat is None or anat.get("torso_width", 0) < 26:
                        continue

                    cx_n = np.clip((bx + bw * 0.5) / float(rw), 0.01, 0.99)
                    cy_n = np.clip((by + bh * 0.5) / float(rh), 0.01, 0.99)
                    bw_n = np.clip(bw / float(rw), 0.02, 0.98)
                    bh_n = np.clip(bh / float(rh), 0.02, 0.98)
                    lbl_parts = [f"0 {cx_n:.6f} {cy_n:.6f} {bw_n:.6f} {bh_n:.6f}"]
                    for k_name in kpt_order:
                        pt = anat.get(k_name, (bx + bw * 0.5, by + bh * 0.5))
                        kx_n = np.clip(float(pt[0]) / float(rw), 0.001, 0.999)
                        ky_n = np.clip(float(pt[1]) / float(rh), 0.001, 0.999)
                        lbl_parts.append(f"{kx_n:.6f} {ky_n:.6f} 2")
                    lbl_line = " ".join(lbl_parts) + "\n"

                    is_val = (pair_idx % 5 == 0)
                    pair_idx += 1
                    target_img_dir = img_va if is_val else img_tr
                    target_lbl_dir = lbl_va if is_val else lbl_tr

                    stem = f"vid{v_idx}_f{f_idx}_clean"
                    cv2.imwrite(os.path.join(target_img_dir, f"{stem}.jpg"), crop)
                    with open(os.path.join(target_lbl_dir, f"{stem}.txt"), "w", encoding="utf-8") as lf:
                        lf.write(lbl_line)
                    sample_count += 1
                    collected_vid += 1

                    if not is_val:
                        aug_crop = crop.copy()
                        num_bars = int(rng.integers(2, 5))
                        for _ in range(num_bars):
                            bar_x = int(rng.integers(max(0, bx + 4), max(bx + 8, min(rw - 6, bx + bw - 4))))
                            bar_w = int(rng.integers(3, 7))
                            y_top = max(0, int(fault_y_local - rng.integers(14, 34)))
                            y_bot = min(rh, int(fault_y_local + rng.integers(16, 36)))
                            glare_val = int(rng.integers(185, 245))
                            edge_val = int(rng.integers(55, 95))
                            cv2.rectangle(aug_crop, (bar_x - 1, y_top), (bar_x + bar_w + 1, y_bot), (edge_val, edge_val, edge_val), -1)
                            cv2.rectangle(aug_crop, (bar_x, y_top), (bar_x + bar_w, y_bot), (glare_val, glare_val, glare_val), -1)
                        stem_aug = f"vid{v_idx}_f{f_idx}_rungaug"
                        cv2.imwrite(os.path.join(img_tr, f"{stem_aug}.jpg"), aug_crop)
                        with open(os.path.join(lbl_tr, f"{stem_aug}.txt"), "w", encoding="utf-8") as lf:
                            lf.write(lbl_line)
                        sample_count += 1

                cap.release()

            if sample_count < 8:
                self.log("⚠ [AI Pose Trainer] Not enough clean frames for training.")
                return None

            yaml_path = os.path.join(dataset_dir, "mouse_pose.yaml")
            yaml_content = (
                f"path: {dataset_dir}\n"
                f"train: images/train\n"
                f"val: images/val\n"
                f"kpt_shape: [9, 3]\n"
                f"flip_idx: [0, 1, 2, 3, 4, 5, 6, 7, 8]\n"
                f"names:\n"
                f"  0: rodent\n"
            )
            with open(yaml_path, "w", encoding="utf-8") as yf:
                yf.write(yaml_content)

            self.log(f"🚀 [AI Pose Trainer] Training YOLOv8n-Pose model ({train_device.upper()}, {epochs} epochs)...")
            base_pose_pt = get_resource_path("yolov8n-pose.pt")
            if not os.path.exists(base_pose_pt):
                base_pose_pt = "yolov8n-pose.pt"

            runs_dir = os.path.join(dataset_dir, "runs")
            train_script = os.path.join(dataset_dir, "run_pose_train.py")
            script_code = (
                "from ultralytics import YOLO\n"
                f"model = YOLO({repr(base_pose_pt)})\n"
                "model.train(\n"
                f"    data={repr(yaml_path)},\n"
                f"    epochs={int(epochs)},\n"
                f"    imgsz={int(imgsz)},\n"
                "    batch=16,\n"
                f"    device={repr(train_device)},\n"
                f"    project={repr(runs_dir)},\n"
                "    name='mouse_pose',\n"
                "    exist_ok=True,\n"
                "    fliplr=0.0,\n"
                "    amp=False,\n"
                "    verbose=False,\n"
                "    plots=False,\n"
                "    workers=0,\n"
                ")\n"
            )
            with open(train_script, "w", encoding="utf-8") as sf:
                sf.write(script_code)

            subprocess.run([sys.executable, train_script], check=False)

            best_pt = os.path.join(runs_dir, "mouse_pose", "weights", "best.pt")
            if not os.path.exists(best_pt):
                best_pt = os.path.join(runs_dir, "mouse_pose", "weights", "last.pt")

            if os.path.exists(best_pt):
                target_pt = os.path.join(SAFE_BASE_DIR, "mouse_pose_ai.pt")
                shutil.copy2(best_pt, target_pt)
                try:
                    local_pt = get_resource_path("mouse_pose_ai.pt")
                    if os.path.abspath(local_pt) != os.path.abspath(target_pt):
                        shutil.copy2(best_pt, local_pt)
                except Exception:
                    pass
                self.log(f"✅ [AI Pose Trainer] Custom 9-keypoint rodent model saved: {target_pt}")
                if hasattr(app_ref, "hybrid_locator"):
                    app_ref.hybrid_locator._init_yolo()
                    if hasattr(app_ref, "_refresh_kpi_summary"):
                        app_ref.root.after(0, app_ref._refresh_kpi_summary)
                return target_pt
            return None
        except Exception as exc:
            self.log(f"❌ [AI Pose Trainer] Training error: {exc}")
            return None
        finally:
            shutil.rmtree(dataset_dir, ignore_errors=True)


# ==============================================================================
# MAIN APPLICATION — PROFESSIONAL SCIENTIFIC WORKSTATION GUI
# ==============================================================================
class PerVideoIDTrackerApp:
    PALETTE = {
        "bg_main": "#0B0F17",       # Deep laboratory obsidian background
        "bg_card": "#131B26",       # Section card panel
        "bg_panel": "#1E293B",      # Elevated control / input surface
        "border": "#334155",        # Subtle structural 1px border
        "text_main": "#F8FAFC",     # Crisp high-contrast primary text
        "text_muted": "#94A3B8",    # Muted slate secondary text
        "blue": "#0284C7",          # Scientific steel-blue
        "blue_hover": "#0369A1",
        "cyan": "#06B6D4",          # Telemetry cyan accent
        "emerald": "#10B981",       # Primary execution emerald
        "emerald_hover": "#059669",
        "emerald_soft": "#14332B",  # Subtle emerald selection
        "teal": "#14B8A6",          # Secondary action teal
        "teal_hover": "#0D9488",
        "danger": "#EF4444",        # Crimson for Stop/Abort
        "danger_hover": "#DC2626",
        "amber": "#F59E0B",         # Warning / alert accent
    }

    def __init__(self, root):
        self.root = root
        self.lang = "hu"
        self.root.title(f"{APP_NAME} v{APP_VERSION} — Scientific Kinematic & Behavioral Workstation")
        self.root.geometry("1260x830")
        self.root.minsize(1060, 720)
        self.root.configure(bg=self.PALETTE["bg_main"])

        apply_window_icon(self.root)

        self.output_base_dir = SAFE_BASE_DIR
        self.video_data = []
        self.is_running = False
        self.completed_videos = 0
        self.pending_results = []
        self._inline_id_entry = None

        self.calib_dark_thresh = 135
        self.calib_diff_thresh = 24
        self.calib_ladder_thresh = 132
        self.calib_fault_Ratio = 72
        self.saved_geometry = None

        self.var_auto_calib = tk.BooleanVar(value=True)
        self.var_yolo_fusion = tk.BooleanVar(value=True)
        self.var_bidirectional = tk.BooleanVar(value=False)
        self.var_lock_lr_direction = tk.BooleanVar(value=True)
        self.var_protocol_runs = tk.StringVar(value="3")
        self.var_enable_review = tk.BooleanVar(value=True)
        self.var_enable_zones = tk.BooleanVar(value=True)
        self.var_enable_kinematics = tk.BooleanVar(value=True)

        # Multi-tiered hardware acceleration detection (Apple Silicon Metal / NVIDIA CUDA / OpenCL)
        self.gpu_device_name = "CPU"
        self.gpu_available = False
        try:
            import torch
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.gpu_available = True
                self.gpu_device_name = "Apple Silicon Metal (MPS)"
            elif torch.cuda.is_available():
                self.gpu_available = True
                self.gpu_device_name = f"NVIDIA CUDA ({torch.cuda.get_device_name(0)})"
            elif cv2.ocl.haveOpenCL():
                self.gpu_available = True
                dev = cv2.ocl.Device.getDefault()
                self.gpu_device_name = f"OpenCL ({dev.name()})"
        except Exception:
            self.gpu_available = cv2.ocl.haveOpenCL()

        self.var_use_gpu = tk.BooleanVar(value=self.gpu_available)
        self.var_use_kalman = tk.BooleanVar(value=True)
        self.var_dlc_superanimal = tk.BooleanVar(value=True)
        self.var_dlc_export_train = tk.BooleanVar(value=False)

        self.var_threads = tk.StringVar(value="4")
        self.var_stride = tk.StringVar(value="1")
        self.var_cooldown = tk.StringVar(value="0.50")
        self.var_min_dist = tk.StringVar(value="30")
        self.var_gate_cm = tk.StringVar(value="60.0")
        self.var_decimal = tk.StringVar(value=". (OriginPro)")

        self.kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.kernel_horiz = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 3))
        self.kernel_upper_bridge = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 7))
        self.kernel_fill = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self.kernel_rung_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self.kernel_sag_guard = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 13))
        self.kernel_blackhat_13 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
        self.kernel_torso_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 7))
        self.kernel_grad_3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

        self.dlc_addon = DLCAddonManager(self.log)
        self.auto_engine = AutoAdaptiveLadderEngine(self.log)
        self.hybrid_locator = ParallelYoloOpenCVEngine(self.log)

        self._setup_styles()
        self._build_ui()
        self._try_autoload_last_profile()
        self._refresh_kpi_cards()

    def tr(self, key, **kwargs):
        text = TRANSLATIONS.get(self.lang, TRANSLATIONS["hu"]).get(key, key)
        return text.format(**kwargs) if kwargs else text

    def toggle_language(self):
        self.lang = "en" if self.lang == "hu" else "hu"
        self.btn_lang.config(text="EN" if self.lang == "en" else "HU")
        self._update_ui_texts()
        self._refresh_kpi_cards()

    def _setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        font_family = "SF Pro Text" if sys.platform == "darwin" else "Segoe UI"
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
            foreground=[("active", P["cyan"])]
        )

        style.configure(
            "Treeview",
            background="#0E141E",
            foreground=P["text_main"],
            rowheight=28,
            fieldbackground="#0E141E",
            borderwidth=0,
            font=(font_family, 9)
        )
        style.configure(
            "Treeview.Heading",
            background=P["bg_panel"],
            foreground=P["text_main"],
            relief="flat",
            padding=(10, 6),
            font=(font_family, 9, "bold")
        )
        style.map(
            "Treeview",
            background=[("selected", P["emerald_soft"])],
            foreground=[("selected", "#A7F3D0")]
        )
        style.map("Treeview.Heading", background=[("active", P["border"])])

        style.configure(
            "Emerald.Horizontal.TProgressbar",
            troughcolor="#0A0E17",
            background=P["emerald"],
            bordercolor=P["border"],
            lightcolor=P["emerald"],
            darkcolor=P["emerald"],
            thickness=8
        )

        btn_specs = {
            "Emerald.TButton": (P["emerald"], P["emerald_hover"], "#FFFFFF", (font_family, 10, "bold")),
            "Teal.TButton":    (P["teal"], P["teal_hover"], "#FFFFFF", (font_family, 9, "bold")),
            "Primary.TButton": (P["blue"], P["blue_hover"], "#FFFFFF", (font_family, 9, "bold")),
            "Ghost.TButton":   (P["bg_panel"], P["border"], P["text_main"], (font_family, 9)),
            "Danger.TButton":  (P["danger"], P["danger_hover"], "#FFFFFF", (font_family, 9, "bold")),
            "SoftRed.TButton": ("#3B181E", "#4C1D24", "#FCA5A5", (font_family, 9)),
        }
        for s_name, (bg_col, active_col, fg_col, fnt) in btn_specs.items():
            style.configure(
                s_name, background=bg_col, foreground=fg_col, font=fnt,
                padding=(11, 6), borderwidth=1, bordercolor=P["border"], relief="flat"
            )
            style.map(
                s_name,
                background=[("active", active_col), ("disabled", "#1E293B")],
                foreground=[("disabled", "#64748B")]
            )

    def _create_section_card(self, parent, title_text, accent_color=None, badge_text=None):
        P = self.PALETTE
        if accent_color is None:
            accent_color = P["blue"]

        outer = tk.Frame(parent, bg=P["border"], padx=1, pady=1)
        inner = tk.Frame(outer, bg=P["bg_card"], padx=14, pady=10)
        inner.pack(fill="both", expand=True)

        header_bar = tk.Frame(inner, bg=P["bg_card"])
        header_bar.pack(fill="x", pady=(0, 6))

        accent_indicator = tk.Frame(header_bar, bg=accent_color, width=3, height=14)
        accent_indicator.pack(side="left", padx=(0, 8))

        lbl = tk.Label(
            header_bar, text=title_text, bg=P["bg_card"], fg=P["text_main"],
            font=(self.ui_font, 10, "bold")
        )
        lbl.pack(side="left")

        badge = None
        if badge_text:
            badge = tk.Label(
                header_bar, text=badge_text, bg=P["bg_panel"], fg=P["text_muted"],
                font=(self.mono_font, 8), padx=6, pady=1
            )
            badge.pack(side="right")

        divider = tk.Frame(inner, bg=P["border"], height=1)
        divider.pack(fill="x", pady=(0, 8))

        return outer, inner, lbl, badge

    def _build_ui(self):
        P = self.PALETTE

        # ── 1. TOP HEADER BAR ───────────────────────────────────────────────
        header = tk.Frame(
            self.root, bg=P["bg_card"], padx=18, pady=10,
            highlightthickness=1, highlightbackground=P["border"]
        )
        header.pack(fill="x")

        header_left = tk.Frame(header, bg=P["bg_card"])
        header_left.pack(side="left", fill="y")

        title_line = tk.Frame(header_left, bg=P["bg_card"])
        title_line.pack(anchor="w")

        tk.Label(
            title_line, text="MOUSEANALYZER PRO", bg=P["bg_card"], fg=P["text_main"],
            font=(self.ui_font, 13, "bold")
        ).pack(side="left", padx=(0, 8))

        tk.Label(
            title_line, text=f"v{APP_VERSION}", bg=P["bg_panel"], fg=P["cyan"],
            font=(self.mono_font, 8, "bold"), padx=6, pady=1
        ).pack(side="left", padx=(0, 10))

        tk.Frame(title_line, bg=P["border"], width=1, height=14).pack(side="left", padx=(0, 10))

        self.lbl_subtitle = tk.Label(
            title_line, text=self.tr("subtitle"),
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)
        )
        self.lbl_subtitle.pack(side="left")

        self.lbl_output_dir = tk.Label(
            header_left,
            text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}",
            bg=P["bg_card"], fg=P["text_muted"], font=(self.mono_font, 8)
        )
        self.lbl_output_dir.pack(anchor="w", pady=(3, 0))

        header_right = tk.Frame(header, bg=P["bg_card"])
        header_right.pack(side="right")

        self.btn_change_dir = ttk.Button(
            header_right, text=self.tr("btn_change_dir"), command=self.choose_output_folder, style="Ghost.TButton"
        )
        self.btn_change_dir.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_change_dir, lambda: self.tr("tt_change_dir"))

        self.btn_open_dir = ttk.Button(
            header_right, text=self.tr("btn_open_dir"), command=self.open_results_folder, style="Ghost.TButton"
        )
        self.btn_open_dir.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_open_dir, lambda: self.tr("tt_open_dir"))

        self.btn_lang = ttk.Button(
            header_right, text="HU", width=4, command=self.toggle_language, style="Primary.TButton"
        )
        self.btn_lang.pack(side="left")

        # ── 2. SYSTEM TELEMETRY STRIP ───────────────────────────────────────
        kpi_strip = tk.Frame(self.root, bg=P["bg_main"], padx=16, pady=8)
        kpi_strip.pack(fill="x")

        engine_tag = "YOLO + 9-Point Articulated Rodent Skeleton" if self.hybrid_locator.yolo_model is not None else "Adaptive Rodent Geometry + Optical Flow"
        self.kpi_vars = {
            "videos": tk.StringVar(value="0"),
            "calib": tk.StringVar(value="-"),
            "engine": tk.StringVar(value=engine_tag),
            "dlc": tk.StringVar(value="SuperAnimal NN" if self.dlc_addon.dlc_available else "Biomechanical Slip Vector")
        }

        self.kpi_title_labels = {}
        kpi_defs = [
            ("videos", "kpi_videos", self.kpi_vars["videos"], P["text_main"]),
            ("calib", "kpi_calib", self.kpi_vars["calib"], P["cyan"]),
            ("engine", "kpi_engine", self.kpi_vars["engine"], P["emerald"]),
            ("dlc", "kpi_dlc", self.kpi_vars["dlc"], P["teal"]),
        ]

        for idx, (k_key, k_tr_key, k_var, k_col) in enumerate(kpi_defs):
            card_wrap = tk.Frame(kpi_strip, bg=P["border"], padx=1, pady=1)
            card_wrap.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 8, 0))
            card = tk.Frame(card_wrap, bg=P["bg_card"], padx=12, pady=6)
            card.pack(fill="both", expand=True)
            lbl_t = tk.Label(
                card, text=self.tr(k_tr_key), bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 8, "bold")
            )
            lbl_t.pack(anchor="w")
            self.kpi_title_labels[k_key] = lbl_t
            tk.Label(
                card, textvariable=k_var, bg=P["bg_card"], fg=k_col, font=(self.mono_font, 10, "bold")
            ).pack(anchor="w", pady=(1, 0))

        # ── 3. CENTRAL SPLIT WORKSPACE ──────────────────────────────────────
        center_workspace = tk.Frame(self.root, bg=P["bg_main"], padx=16, pady=0)
        center_workspace.pack(fill="both", expand=True)

        # LEFT PANEL: RECORDINGS & SUBJECT TABLE
        list_outer, list_card, self.lbl_sec1, self.badge_sec1 = self._create_section_card(
            center_workspace, self.tr("sec1_title"), P["blue"], self.tr("badge_queue")
        )
        list_outer.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=(0, 8))

        toolbar = tk.Frame(list_card, bg=P["bg_card"])
        toolbar.pack(fill="x", pady=(0, 8))

        self.btn_add_vid = ttk.Button(
            toolbar, text=self.tr("btn_add_vid"), command=self.browse_videos, style="Teal.TButton"
        )
        self.btn_add_vid.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_add_vid, lambda: self.tr("tt_add_vid"))

        self.btn_edit_id = ttk.Button(
            toolbar, text=self.tr("btn_edit_id"), command=lambda: self.edit_animal_id(None), style="Ghost.TButton"
        )
        self.btn_edit_id.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_edit_id, lambda: self.tr("tt_edit_id"))

        self.btn_remove_vid = ttk.Button(
            toolbar, text=self.tr("btn_remove_vid"), command=self.remove_selected_video, style="SoftRed.TButton"
        )
        self.btn_remove_vid.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_remove_vid, lambda: self.tr("tt_remove_vid"))

        self.btn_clear_vid = ttk.Button(
            toolbar, text=self.tr("btn_clear_vid"), command=self.clear_videos, style="Ghost.TButton"
        )
        self.btn_clear_vid.pack(side="right")
        ToolTip(self.btn_clear_vid, lambda: self.tr("tt_clear_vid"))

        tree_container = tk.Frame(list_card, bg=P["border"], padx=1, pady=1)
        tree_container.pack(fill="both", expand=True)

        columns = ("filename", "animal_id", "status", "path")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=9, selectmode="browse")
        self.tree.heading("filename", text=self.tr("col_fname"))
        self.tree.heading("animal_id", text=self.tr("col_id"))
        self.tree.heading("status", text=self.tr("col_status"))
        self.tree.heading("path", text=self.tr("col_path"))

        self.tree.column("filename", width=210, anchor="w")
        self.tree.column("animal_id", width=95, anchor="center")
        self.tree.column("status", width=145, anchor="center")
        self.tree.column("path", width=260, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.edit_animal_id)
        self.tree.bind("<Return>", self.edit_animal_id)
        self.tree.bind("<KP_Enter>", self.edit_animal_id)
        self.tree.bind("<F2>", self.edit_animal_id)

        # RIGHT PANEL: PARAMETERS & EXECUTION DOCK
        ctrl_outer, control_card, self.lbl_sec2, self.badge_sec2 = self._create_section_card(
            center_workspace, self.tr("sec2_title"), P["emerald"], self.tr("badge_controls")
        )
        ctrl_outer.configure(width=435)
        ctrl_outer.pack_propagate(False)
        ctrl_outer.pack(side="right", fill="y", pady=(0, 8))

        self.lbl_sub_calib = tk.Label(
            control_card, text=self.tr("sub_calib"), bg=P["bg_card"], fg=P["text_muted"],
            font=(self.ui_font, 8, "bold")
        )
        self.lbl_sub_calib.pack(anchor="w", pady=(0, 4))

        chk_group = tk.Frame(control_card, bg=P["bg_card"])
        chk_group.pack(fill="x", pady=(0, 6))

        self.chk_auto_calib = ttk.Checkbutton(
            chk_group, text=self.tr("chk_auto_calib"), variable=self.var_auto_calib, style="Dark.TCheckbutton"
        )
        self.chk_auto_calib.pack(anchor="w", pady=1)
        ToolTip(self.chk_auto_calib, lambda: self.tr("tt_auto_calib"))

        self.chk_yolo_fusion = ttk.Checkbutton(
            chk_group, text=self.tr("chk_yolo_fusion"), variable=self.var_yolo_fusion, style="Dark.TCheckbutton"
        )
        self.chk_yolo_fusion.pack(anchor="w", pady=1)
        ToolTip(self.chk_yolo_fusion, lambda: self.tr("tt_yolo"))

        self.chk_lock_lr = ttk.Checkbutton(
            chk_group, text=self.tr("chk_lock_lr"), variable=self.var_lock_lr_direction, style="Dark.TCheckbutton"
        )
        self.chk_lock_lr.pack(anchor="w", pady=1)
        ToolTip(self.chk_lock_lr, lambda: self.tr("tt_lock_lr"))

        self.chk_bidirectional = ttk.Checkbutton(
            chk_group, text=self.tr("chk_bidirectional"), variable=self.var_bidirectional, style="Dark.TCheckbutton"
        )
        self.chk_bidirectional.pack(anchor="w", pady=1)
        ToolTip(self.chk_bidirectional, lambda: self.tr("tt_bidirectional"))

        self.chk_rev = ttk.Checkbutton(
            chk_group, text=self.tr("chk_rev"), variable=self.var_enable_review, style="Dark.TCheckbutton"
        )
        self.chk_rev.pack(anchor="w", pady=1)
        ToolTip(self.chk_rev, lambda: self.tr("tt_rev"))

        tk.Frame(control_card, bg=P["border"], height=1).pack(fill="x", pady=(4, 6))

        self.lbl_sub_params = tk.Label(
            control_card, text=self.tr("sub_params"), bg=P["bg_card"], fg=P["text_muted"],
            font=(self.ui_font, 8, "bold")
        )
        self.lbl_sub_params.pack(anchor="w", pady=(0, 4))

        param_grid = tk.Frame(
            control_card, bg=P["bg_panel"], padx=10, pady=8,
            highlightthickness=1, highlightbackground=P["border"]
        )
        param_grid.pack(fill="x", pady=(0, 8))
        param_grid.columnconfigure(0, weight=1)
        param_grid.columnconfigure(2, weight=1)

        self.lbl_gatecm = tk.Label(
            param_grid, text=self.tr("lbl_gatecm"), bg=P["bg_panel"], fg=P["text_main"], font=(self.ui_font, 9)
        )
        self.lbl_gatecm.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.spin_gate_cm = tk.Spinbox(
            param_grid, from_=5.0, to=500.0, increment=1.0, textvariable=self.var_gate_cm, width=6,
            font=(self.mono_font, 9, "bold"), bg=P["bg_main"], fg=P["text_main"],
            insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat",
            highlightthickness=1, highlightbackground=P["border"]
        )
        self.spin_gate_cm.grid(row=0, column=1, sticky="e", padx=(4, 12), pady=(0, 6))
        ToolTip(self.spin_gate_cm, lambda: self.tr("tt_gatecm"))

        self.lbl_cooldown_main = tk.Label(
            param_grid, text=self.tr("lbl_cooldown"), bg=P["bg_panel"], fg=P["text_main"], font=(self.ui_font, 9)
        )
        self.lbl_cooldown_main.grid(row=0, column=2, sticky="w", pady=(0, 6))
        self.spin_cooldown_main = tk.Spinbox(
            param_grid, from_=0.10, to=5.0, increment=0.05, textvariable=self.var_cooldown, width=6,
            font=(self.mono_font, 9, "bold"), bg=P["bg_main"], fg=P["cyan"],
            insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat",
            highlightthickness=1, highlightbackground=P["border"]
        )
        self.spin_cooldown_main.grid(row=0, column=3, sticky="e", padx=(4, 0), pady=(0, 6))
        ToolTip(self.spin_cooldown_main, lambda: self.tr("tt_cooldown"))

        self.lbl_mindist_main = tk.Label(
            param_grid, text=self.tr("lbl_mindist"), bg=P["bg_panel"], fg=P["text_main"], font=(self.ui_font, 9)
        )
        self.lbl_mindist_main.grid(row=1, column=0, sticky="w")
        self.spin_mindist_main = tk.Spinbox(
            param_grid, from_=0, to=200, increment=5, textvariable=self.var_min_dist, width=6,
            font=(self.mono_font, 9, "bold"), bg=P["bg_main"], fg=P["text_main"],
            insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat",
            highlightthickness=1, highlightbackground=P["border"]
        )
        self.spin_mindist_main.grid(row=1, column=1, sticky="e", padx=(4, 12))
        ToolTip(self.spin_mindist_main, lambda: self.tr("tt_mindist"))

        self.lbl_threads_main = tk.Label(
            param_grid, text=self.tr("lbl_threads"), bg=P["bg_panel"], fg=P["text_main"], font=(self.ui_font, 9)
        )
        self.lbl_threads_main.grid(row=1, column=2, sticky="w")
        self.spin_threads_main = tk.Spinbox(
            param_grid, from_=1, to=16, increment=1, textvariable=self.var_threads, width=6,
            font=(self.mono_font, 9, "bold"), bg=P["bg_main"], fg=P["text_main"],
            insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat",
            highlightthickness=1, highlightbackground=P["border"]
        )
        self.spin_threads_main.grid(row=1, column=3, sticky="e", padx=(4, 0))
        ToolTip(self.spin_threads_main, lambda: self.tr("tt_threads"))

        prof_row1 = tk.Frame(control_card, bg=P["bg_card"])
        prof_row1.pack(fill="x", pady=(0, 4))

        self.btn_load_prof_main = ttk.Button(
            prof_row1, text=self.tr("btn_load_prof"), command=self.load_calibration_json, style="Ghost.TButton"
        )
        self.btn_load_prof_main.pack(side="left", fill="x", expand=True, padx=(0, 3))
        ToolTip(self.btn_load_prof_main, lambda: self.tr("tt_load_prof"))

        self.btn_save_prof_main = ttk.Button(
            prof_row1, text=self.tr("btn_save_prof"), command=self.save_calibration_json, style="Ghost.TButton"
        )
        self.btn_save_prof_main.pack(side="right", fill="x", expand=True, padx=(3, 0))
        ToolTip(self.btn_save_prof_main, lambda: self.tr("tt_save_prof"))

        prof_row2 = tk.Frame(control_card, bg=P["bg_card"])
        prof_row2.pack(fill="x", pady=(0, 8))

        self.btn_train_ai = ttk.Button(
            prof_row2, text=self.tr("btn_train_ai"), command=self.train_ai_pose_from_gui, style="Primary.TButton"
        )
        self.btn_train_ai.pack(side="left", fill="x", expand=True, padx=(0, 3))
        ToolTip(self.btn_train_ai, lambda: self.tr("tt_train_ai"))

        self.btn_settings = ttk.Button(
            prof_row2, text=self.tr("btn_settings"), command=self.open_advanced_settings_dialog, style="Ghost.TButton"
        )
        self.btn_settings.pack(side="right", fill="x", expand=True, padx=(3, 0))
        ToolTip(self.btn_settings, lambda: self.tr("tt_settings"))

        tk.Frame(control_card, bg=P["border"], height=1).pack(fill="x", pady=(0, 8))

        self.lbl_sub_exec = tk.Label(
            control_card, text=self.tr("sub_exec"), bg=P["bg_card"], fg=P["text_muted"],
            font=(self.ui_font, 8, "bold")
        )
        self.lbl_sub_exec.pack(anchor="w", pady=(0, 6))

        self.btn_start = ttk.Button(
            control_card, text=self.tr("btn_start"), command=self.start_workflow, style="Emerald.TButton"
        )
        self.btn_start.pack(fill="x", pady=(0, 6))
        ToolTip(self.btn_start, lambda: self.tr("tt_start"))

        exec_sub_row = tk.Frame(control_card, bg=P["bg_card"])
        exec_sub_row.pack(fill="x")

        self.btn_quick_start = ttk.Button(
            exec_sub_row, text=self.tr("btn_quick"), command=self.start_quick_workflow, style="Teal.TButton"
        )
        self.btn_quick_start.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ToolTip(self.btn_quick_start, lambda: self.tr("tt_quick"))

        self.btn_stop = ttk.Button(
            exec_sub_row, text=self.tr("btn_stop"), command=self.stop_analysis, style="Danger.TButton", state="disabled"
        )
        self.btn_stop.pack(side="right")
        ToolTip(self.btn_stop, lambda: self.tr("tt_stop"))

        # ── 4. STATUS, PROGRESS & DIAGNOSTIC LOG ────────────────────────────
        bottom_frame = tk.Frame(self.root, bg=P["bg_main"], padx=16, pady=0)
        bottom_frame.pack(fill="x", pady=(0, 12))

        log_outer, log_card, self.lbl_sec3, self.badge_sec3 = self._create_section_card(
            bottom_frame, self.tr("sec3_title"), P["blue"], self.tr("badge_log")
        )
        log_outer.pack(fill="x")

        prog_strip = tk.Frame(
            log_card, bg=P["bg_panel"], padx=10, pady=6,
            highlightthickness=1, highlightbackground=P["border"]
        )
        prog_strip.pack(fill="x", pady=(0, 6))

        self.progress_lbl = tk.Label(
            prog_strip, text=self.tr("prog_idle", done=0, total=0),
            bg=P["bg_panel"], fg=P["text_main"], font=(self.ui_font, 9, "bold")
        )
        self.progress_lbl.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(
            prog_strip, style="Emerald.Horizontal.TProgressbar", mode="determinate"
        )
        self.progress_bar.pack(fill="x")

        log_border = tk.Frame(log_card, bg=P["border"], padx=1, pady=1)
        log_border.pack(fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(
            log_border, wrap=tk.WORD, font=(self.mono_font, 9),
            height=5, state="disabled", bg="#080C14", fg="#E2E8F0",
            insertbackground=P["cyan"], relief="flat", borderwidth=0, padx=8, pady=6
        )
        self.log_area.pack(fill="both", expand=True)

        self.log(
            f"[{APP_NAME} v{APP_VERSION}] Ready. Continuous 100% movement capture, bidirectional crossing analysis, and non-blocking preview active."
        )


    def open_advanced_settings_dialog(self):
        P = self.PALETTE
        win = tk.Toplevel(self.root)
        win.title(self.tr("settings_title"))
        win.geometry("680x450")
        win.configure(bg=P["bg_card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        container = tk.Frame(win, bg=P["bg_card"], padx=22, pady=18)
        container.pack(fill="both", expand=True)

        tk.Label(
            container, text=self.tr("settings_title"),
            bg=P["bg_card"], fg=P["text_main"], font=(self.ui_font, 11, "bold")
        ).pack(anchor="w", pady=(0, 10))

        chk_panel = tk.Frame(container, bg=P["bg_panel"], padx=14, pady=10, highlightthickness=1, highlightbackground=P["border"])
        chk_panel.pack(fill="x", pady=(0, 12))

        for tr_key, var in [
            ("chk_yolo_fusion", self.var_yolo_fusion),
            ("chk_lock_lr", self.var_lock_lr_direction),
            ("chk_bidirectional", self.var_bidirectional),
            ("chk_zones", self.var_enable_zones),
            ("chk_kin", self.var_enable_kinematics),
            ("chk_gpu", self.var_use_gpu),
            ("chk_kalman", self.var_use_kalman),
            ("chk_dlc_sa", self.var_dlc_superanimal),
            ("chk_dlc_exp", self.var_dlc_export_train),
        ]:
            cb = tk.Checkbutton(
                chk_panel, text=self.tr(tr_key), variable=var,
                bg=P["bg_panel"], fg=P["text_main"], selectcolor=P["bg_main"],
                activebackground=P["bg_panel"], activeforeground=P["cyan"],
                font=(self.ui_font, 9), anchor="w"
            )
            cb.pack(fill="x", pady=2)

        num_panel = tk.Frame(container, bg=P["bg_main"], padx=14, pady=10, highlightthickness=1, highlightbackground=P["border"])
        num_panel.pack(fill="x", pady=(0, 14))

        def add_spin_item(parent, tr_key, var, from_, to_, inc, width=5):
            box = tk.Frame(parent, bg=P["bg_main"])
            box.pack(side="left", padx=(0, 14))
            tk.Label(box, text=self.tr(tr_key), bg=P["bg_main"], fg=P["text_muted"], font=(self.ui_font, 8, "bold")).pack(anchor="w")
            sp = tk.Spinbox(
                box, from_=from_, to=to_, increment=inc, textvariable=var, width=width,
                font=(self.mono_font, 9, "bold"), bg=P["bg_panel"], fg=P["text_main"],
                insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat"
            )
            sp.pack(anchor="w", pady=(2, 0))

        add_spin_item(num_panel, "lbl_runs_target", self.var_protocol_runs, 1, 10, 1, width=3)
        add_spin_item(num_panel, "lbl_threads", self.var_threads, 1, 16, 1, width=4)
        add_spin_item(num_panel, "lbl_stride", self.var_stride, 1, 5, 1, width=4)
        add_spin_item(num_panel, "lbl_cooldown", self.var_cooldown, 0.05, 5.0, 0.05, width=6)
        add_spin_item(num_panel, "lbl_mindist", self.var_min_dist, 0, 200, 5, width=5)

        dec_box = tk.Frame(num_panel, bg=P["bg_main"])
        dec_box.pack(side="left")
        tk.Label(dec_box, text=self.tr("lbl_dec"), bg=P["bg_main"], fg=P["text_muted"], font=(self.ui_font, 8, "bold")).pack(anchor="w")
        combo_dec = ttk.Combobox(dec_box, textvariable=self.var_decimal, values=[". (OriginPro)", ", (HU Excel)"], width=12, state="readonly")
        combo_dec.pack(anchor="w", pady=(2, 0))

        bottom_row = tk.Frame(container, bg=P["bg_card"])
        bottom_row.pack(fill="x")

        ttk.Button(bottom_row, text=self.tr("btn_load_prof"), command=self.load_calibration_json, style="Ghost.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(bottom_row, text=self.tr("btn_save_prof"), command=self.save_calibration_json, style="Ghost.TButton").pack(side="left")
        ttk.Button(bottom_row, text=self.tr("btn_close_settings"), command=win.destroy, style="Emerald.TButton").pack(side="right")

    def _update_ui_texts(self):
        self.root.title(self.tr("app_window_title", app_name=APP_NAME, version=APP_VERSION))
        self.lbl_subtitle.config(text=self.tr("subtitle"))
        self.lbl_output_dir.config(text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}")
        self.btn_change_dir.config(text=self.tr("btn_change_dir"))
        self.btn_open_dir.config(text=self.tr("btn_open_dir"))
        self.btn_settings.config(text=self.tr("btn_settings"))
        self.btn_lang.config(text="EN" if self.lang == "en" else "HU")

        for k_key, tr_key in [("videos", "kpi_videos"), ("calib", "kpi_calib"), ("engine", "kpi_engine"), ("dlc", "kpi_dlc")]:
            self.kpi_title_labels[k_key].config(text=self.tr(tr_key))

        self.lbl_sec1.config(text=self.tr("sec1_title"))
        if hasattr(self, "badge_sec1") and self.badge_sec1:
            self.badge_sec1.config(text=self.tr("badge_queue"))
        self.btn_add_vid.config(text=self.tr("btn_add_vid"))
        self.btn_edit_id.config(text=self.tr("btn_edit_id"))
        self.btn_remove_vid.config(text=self.tr("btn_remove_vid"))
        self.btn_clear_vid.config(text=self.tr("btn_clear_vid"))

        self.tree.heading("filename", text=self.tr("col_fname"))
        self.tree.heading("animal_id", text=self.tr("col_id"))
        self.tree.heading("status", text=self.tr("col_status"))
        self.tree.heading("path", text=self.tr("col_path"))

        self.lbl_sec2.config(text=self.tr("sec2_title"))
        if hasattr(self, "badge_sec2") and self.badge_sec2:
            self.badge_sec2.config(text=self.tr("badge_controls"))
        if hasattr(self, "lbl_sub_calib"):
            self.lbl_sub_calib.config(text=self.tr("sub_calib"))
        if hasattr(self, "lbl_sub_params"):
            self.lbl_sub_params.config(text=self.tr("sub_params"))
        if hasattr(self, "lbl_sub_exec"):
            self.lbl_sub_exec.config(text=self.tr("sub_exec"))
        self.chk_auto_calib.config(text=self.tr("chk_auto_calib"))
        self.chk_yolo_fusion.config(text=self.tr("chk_yolo_fusion"))
        if hasattr(self, "chk_lock_lr"):
            self.chk_lock_lr.config(text=self.tr("chk_lock_lr"))
        self.chk_bidirectional.config(text=self.tr("chk_bidirectional"))
        self.chk_rev.config(text=self.tr("chk_rev"))
        self.lbl_gatecm.config(text=self.tr("lbl_gatecm"))
        if hasattr(self, "lbl_cooldown_main"):
            self.lbl_cooldown_main.config(text=self.tr("lbl_cooldown"))
        if hasattr(self, "lbl_mindist_main"):
            self.lbl_mindist_main.config(text=self.tr("lbl_mindist"))
        if hasattr(self, "lbl_threads_main"):
            self.lbl_threads_main.config(text=self.tr("lbl_threads"))
        if hasattr(self, "btn_load_prof_main"):
            self.btn_load_prof_main.config(text=self.tr("btn_load_prof"))
        if hasattr(self, "btn_save_prof_main"):
            self.btn_save_prof_main.config(text=self.tr("btn_save_prof"))
        if hasattr(self, "btn_train_ai"):
            self.btn_train_ai.config(text=self.tr("btn_train_ai"))

        self.btn_start.config(text=self.tr("btn_start"))
        self.btn_quick_start.config(text=self.tr("btn_quick"))
        self.btn_stop.config(text=self.tr("btn_stop"))
        self.lbl_sec3.config(text=self.tr("sec3_title"))
        if hasattr(self, "badge_sec3") and self.badge_sec3:
            self.badge_sec3.config(text=self.tr("badge_log"))

        if not self.is_running:
            self.progress_lbl.config(text=self.tr("prog_idle", done=self.completed_videos, total=len(self.video_data)))

    def _refresh_kpi_cards(self):
        self.kpi_vars["videos"].set(self.tr("kpi_vid_val", n=len(self.video_data)))
        if self.saved_geometry:
            g = self.saved_geometry
            self.kpi_vars["calib"].set(self.tr("kpi_cal_active", w=g["rw"], h=g["rh"]))
        else:
            self.kpi_vars["calib"].set(self.tr("kpi_cal_none"))
        if getattr(self.hybrid_locator, "is_rodent_pose", False):
            self.kpi_vars["engine"].set(f"YOLOv8 9-Pt Rodent AI ({self.hybrid_locator.device.upper()})")
        elif self.hybrid_locator.yolo_model is not None:
            self.kpi_vars["engine"].set(f"YOLO AI ({self.hybrid_locator.device.upper()}) + OpenCV")
        else:
            self.kpi_vars["engine"].set("9-Pt Skeleton + Elastic ROI")

        if self.gpu_available and self.var_use_gpu.get():
            self.kpi_vars["dlc"].set(f"🟢 {self.gpu_device_name}")
        else:
            self.kpi_vars["dlc"].set("⚪ CPU Mód (Inaktív)")

    _refresh_kpi_summary = _refresh_kpi_cards

    def train_ai_pose_from_gui(self):
        if self.is_running:
            return
        if not self.video_data:
            messagebox.showwarning(self.tr("msg_no_vid_title"), self.tr("msg_no_vid_body"))
            return
        self.open_training_preview_window()

    def open_training_preview_window(self):
        """
        Interactive Rodent AI Training & Dataset Preview Studio:
        - Asynchronously harvests candidate frames with bounding boxes and anatomical keypoints.
        - Split-view laboratory workstation GUI with interactive zoom/pan canvas.
        - Ground truth BBox, contour mask, snout, torso, tail, and paw skeleton overlays.
        - Frame exclusion toggle to prune imperfect crops before fine-tuning.
        - Live training progress bar and console feedback.
        - Post-training verification mode: runs the newly fine-tuned model on preview crops in real time.
        """
        P = self.PALETTE
        preview_win = tk.Toplevel(self.root)
        preview_win.title(f"{APP_NAME} — {self.tr('train_preview_title')}")
        preview_win.geometry("1240x820")
        preview_win.minsize(1050, 680)
        preview_win.configure(bg=P["bg_main"])
        preview_win.transient(self.root)
        preview_win.grab_set()
        preview_win.lift()
        preview_win.focus_force()

        # Top Header Banner
        top_banner = tk.Frame(preview_win, bg=P["bg_card"], padx=18, pady=10, highlightthickness=1, highlightbackground=P["border"])
        top_banner.pack(fill="x")
        tk.Label(
            top_banner,
            text=f"🧠 {self.tr('train_preview_title')}",
            bg=P["bg_card"], fg=P["text_main"], font=(self.ui_font, 13, "bold")
        ).pack(anchor="w")
        tk.Label(
            top_banner,
            text=self.tr("train_preview_banner"),
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)
        ).pack(anchor="w", pady=(2, 0))

        # Main Body
        body = tk.Frame(preview_win, bg=P["bg_main"], padx=14, pady=10)
        body.pack(fill="both", expand=True)

        # Left Column: Dataset Inspection & Canvas
        left_outer, left_panel, _, _ = self._create_section_card(
            body, self.tr("preview_inspector_title"), P["teal"], self.tr("badge_inspector")
        )
        left_outer.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # Left Nav Bar: 2 clean, responsive rows
        nav_box = tk.Frame(left_panel, bg=P["bg_card"])
        nav_box.pack(fill="x", pady=(0, 8))

        nav_row1 = tk.Frame(nav_box, bg=P["bg_card"])
        nav_row1.pack(fill="x", pady=(0, 4))

        nav_row2 = tk.Frame(nav_box, bg=P["bg_card"])
        nav_row2.pack(fill="x")

        samples_list = []
        current_idx = [0]
        view_state = {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0, "drag_start": None}
        photo_ref = [None]
        harvest_stop_event = threading.Event()
        train_stop_event = threading.Event()

        var_zoom_rodent = tk.BooleanVar(value=True)
        var_show_ai = tk.BooleanVar(value=True)

        btn_prev = ttk.Button(nav_row1, text=self.tr("btn_prev_sample"), style="Ghost.TButton")
        btn_prev.pack(side="left", padx=(0, 4))

        lbl_counter = tk.Label(
            nav_row1, text=self.tr("lbl_sample_counter", cur=0, tot=0), bg=P["bg_card"], fg=P["text_main"],
            font=(self.mono_font, 10, "bold"), width=16, anchor="center"
        )
        lbl_counter.pack(side="left", padx=4)

        btn_next = ttk.Button(nav_row1, text=self.tr("btn_next_sample"), style="Ghost.TButton")
        btn_next.pack(side="left", padx=(0, 8))

        btn_exclude = ttk.Button(nav_row1, text=self.tr("btn_exclude_sample"), style="Ghost.TButton")
        btn_exclude.pack(side="left", padx=(0, 8))

        btn_auto_clean = ttk.Button(nav_row1, text=self.tr("btn_auto_clean"), style="Ghost.TButton")
        btn_auto_clean.pack(side="left", padx=(0, 8))
        ToolTip(btn_auto_clean, lambda: self.tr("tt_auto_clean"))

        btn_rescan = ttk.Button(nav_row1, text=self.tr("btn_rescan_samples"), style="Ghost.TButton")
        btn_rescan.pack(side="right")
        ToolTip(btn_rescan, lambda: self.tr("tt_rescan_samples"))

        chk_zoom = tk.Checkbutton(
            nav_row2, text=self.tr("chk_zoom_rodent"), variable=var_zoom_rodent,
            bg=P["bg_card"], fg=P["text_main"], selectcolor=P["bg_main"],
            activebackground=P["bg_card"], activeforeground=P["text_main"],
            font=(self.ui_font, 9)
        )
        chk_zoom.pack(side="left", padx=(0, 12))

        chk_ai = tk.Checkbutton(
            nav_row2, text=self.tr("chk_show_ai"), variable=var_show_ai,
            bg=P["bg_card"], fg=P["text_main"], selectcolor=P["bg_main"],
            activebackground=P["bg_card"], activeforeground=P["text_main"],
            font=(self.ui_font, 9)
        )
        chk_ai.pack(side="left")

        # Canvas View
        canvas_view = tk.Canvas(left_panel, bg=P["bg_main"], highlightthickness=1, highlightbackground=P["border"], cursor="crosshair")
        canvas_view.pack(fill="both", expand=True, pady=(0, 6))

        # Bottom Telemetry Bar
        lbl_sample_info = tk.Label(
            left_panel,
            text=self.tr("status_harvesting"),
            bg=P["bg_card"], fg=P["cyan"], font=(self.mono_font, 9),
            anchor="w", padx=8, pady=4, highlightthickness=1, highlightbackground=P["border"]
        )
        lbl_sample_info.pack(fill="x", pady=(0, 6))

        # Scrubber Slider
        slider_var = tk.DoubleVar(value=1.0)
        slider_samples = ttk.Scale(left_panel, from_=1.0, to=1.0, variable=slider_var, orient="horizontal")
        slider_samples.pack(fill="x")

        # Right Column: Training Dashboard
        right_outer, right_panel, _, _ = self._create_section_card(
            body, self.tr("preview_trainer_title"), P["emerald"], self.tr("badge_trainer")
        )
        right_outer.pack(side="left", fill="y", padx=0)
        right_outer.config(width=340)

        # Telemetry Card
        t_card = tk.LabelFrame(
            right_panel, text=f"📊 {self.tr('lbl_ds_telemetry')}",
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9, "bold"),
            padx=10, pady=8, highlightthickness=1, highlightbackground=P["border"]
        )
        t_card.pack(fill="x", pady=(0, 10))

        def _make_t_row(parent, label_text, default_val, val_fg=P["text_main"]):
            row = tk.Frame(parent, bg=P["bg_card"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label_text, bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 8)).pack(side="left")
            val_lbl = tk.Label(row, text=str(default_val), bg=P["bg_card"], fg=val_fg, font=(self.mono_font, 9, "bold"))
            val_lbl.pack(side="right")
            return val_lbl

        lbl_tot_val = _make_t_row(t_card, self.tr("lbl_tot_samples"), "0")
        lbl_act_val = _make_t_row(t_card, self.tr("lbl_act_samples"), "0", val_fg=P["emerald"])
        lbl_excl_val = _make_t_row(t_card, self.tr("lbl_excl_samples"), "0", val_fg=P["danger"])
        lbl_src_val = _make_t_row(t_card, self.tr("lbl_src_videos"), str(len(self.video_data)))

        # Hyperparameters Card
        p_card = tk.LabelFrame(
            right_panel, text=f"⚙ {self.tr('lbl_train_params')}",
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9, "bold"),
            padx=10, pady=8, highlightthickness=1, highlightbackground=P["border"]
        )
        p_card.pack(fill="x", pady=(0, 10))

        ep_row = tk.Frame(p_card, bg=P["bg_card"])
        ep_row.pack(fill="x", pady=3)
        tk.Label(ep_row, text=self.tr("lbl_epochs"), bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 8)).pack(side="left")
        var_epochs = tk.StringVar(value="10")
        spin_ep = tk.Spinbox(
            ep_row, from_=3, to=50, textvariable=var_epochs, width=5,
            bg=P["bg_main"], fg=P["text_main"], font=(self.mono_font, 9, "bold"),
            highlightthickness=1, highlightbackground=P["border"]
        )
        spin_ep.pack(side="right")

        import torch
        detected_dev = "CPU"
        if torch.backends.mps.is_available():
            detected_dev = "Apple Silicon GPU (MPS)"
        elif torch.cuda.is_available():
            detected_dev = f"NVIDIA CUDA ({torch.cuda.get_device_name(0)})"

        _make_t_row(p_card, self.tr("lbl_device"), detected_dev, val_fg=P["cyan"])
        _make_t_row(p_card, self.tr("lbl_img_size"), "256×256 px")
        _make_t_row(p_card, self.tr("lbl_model_type"), self.tr("val_model_type"))

        # Execution Card
        exec_card = tk.LabelFrame(
            right_panel, text=f"🚀 {self.tr('btn_start_training')}",
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9, "bold"),
            padx=10, pady=8, highlightthickness=1, highlightbackground=P["border"]
        )
        exec_card.pack(fill="both", expand=True, pady=(0, 8))

        btn_train = ttk.Button(exec_card, text=self.tr("btn_start_training"), style="Emerald.TButton")
        btn_train.pack(fill="x", pady=(0, 6))

        prog_bar = ttk.Progressbar(exec_card, orient="horizontal", mode="determinate")
        prog_bar.pack(fill="x", pady=(0, 6))

        lbl_prog_status = tk.Label(
            exec_card, text=self.tr("status_waiting_samples"), bg=P["bg_card"], fg=P["text_muted"],
            font=(self.ui_font, 8), anchor="w"
        )
        lbl_prog_status.pack(fill="x", pady=(0, 4))

        txt_log = tk.Text(
            exec_card, height=7, bg=P["bg_main"], fg=P["text_muted"],
            font=(self.mono_font, 8), highlightthickness=1, highlightbackground=P["border"],
            wrap="word"
        )
        txt_log.pack(fill="both", expand=True, pady=(0, 6))

        btn_test = ttk.Button(exec_card, text=self.tr("btn_test_model"), style="Ghost.TButton")
        btn_test.pack(fill="x", pady=(0, 4))

        btn_close = ttk.Button(right_panel, text=self.tr("btn_close"), command=preview_win.destroy, style="Ghost.TButton")
        btn_close.pack(fill="x", side="bottom")

        def _render_current_sample():
            if not preview_win.winfo_exists():
                return
            if not samples_list or current_idx[0] < 0 or current_idx[0] >= len(samples_list):
                canvas_view.delete("all")
                cw = max(400, canvas_view.winfo_width())
                ch = max(300, canvas_view.winfo_height())
                canvas_view.create_text(
                    cw // 2, ch // 2,
                    text="🔍 Minták keresése a videókból folyamatban...",
                    fill=P["text_muted"], font=(self.ui_font, 11, "bold")
                )
                return

            sample = samples_list[current_idx[0]]
            crop = sample["crop"]
            ch_img, cw_img = crop.shape[:2]
            vis = crop.copy()

            # 1. Ladder line
            f_y = sample.get("fault_y_local", int(ch_img * 0.6))
            cv2.line(vis, (0, f_y), (cw_img, f_y), (60, 70, 85), 1, cv2.LINE_AA)

            # 2. Contour silhouette
            mask = sample.get("mask")
            if mask is not None:
                cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(vis, cnts, -1, (0, 230, 255), 1, cv2.LINE_AA)

            # 3. Ground Truth BBox
            bbox = sample.get("bbox")
            if bbox:
                bx, by, bw, bh = bbox
                cv2.rectangle(vis, (bx, by), (bx + bw, by + bh), (16, 185, 129), 2)
                cv2.putText(vis, "Target BBox", (bx, max(14, by - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (16, 185, 129), 1, cv2.LINE_AA)

            # 4. Skeleton & Anatomy
            anat = sample.get("anatomy")
            if anat:
                spine = anat.get("spine_chain", [])
                for i in range(len(spine) - 1):
                    cv2.line(vis, spine[i], spine[i+1], (6, 182, 212), 2, cv2.LINE_AA)
                tcx, tcy = int(anat.get("torso_cx", 0)), int(anat.get("torso_cy", 0))
                if tcx > 0 and tcy > 0:
                    cv2.circle(vis, (tcx, tcy), 5, (245, 158, 11), -1)
                    cv2.putText(vis, "TORSO", (tcx - 18, tcy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (245, 158, 11), 1)
                n_pt = anat.get("nose_pt")
                if n_pt:
                    cv2.circle(vis, n_pt, 5, (239, 68, 68), -1)
                    cv2.putText(vis, "NOSE", (n_pt[0] + 6, n_pt[1] + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (239, 68, 68), 1)
                t_pt = anat.get("tail_base")
                if t_pt:
                    cv2.circle(vis, t_pt, 5, (59, 130, 246), -1)
                    cv2.putText(vis, "TAIL", (t_pt[0] - 32, t_pt[1] + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (59, 130, 246), 1)
                fp = anat.get("fore_paw_pt")
                hp = anat.get("hind_paw_pt")
                if fp:
                    cv2.circle(vis, fp, 4, (16, 185, 129), -1)
                if hp:
                    cv2.circle(vis, hp, 4, (168, 85, 247), -1)

            # 5. AI Predicted Box & Specialized Paws (ONLY displayed on active, non-excluded samples!)
            if var_show_ai.get() and not sample.get("excluded", False):
                if sample.get("ai_pred_bbox"):
                    px, py, pw, ph, conf = sample["ai_pred_bbox"]
                    cv2.rectangle(vis, (px, py), (px + pw, py + ph), (236, 72, 153), 2)
                    cv2.putText(vis, f"AI: {conf*100:.1f}%", (px, max(14, py - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (236, 72, 153), 1, cv2.LINE_AA)

                ai_pose = sample.get("ai_pred_pose")
                if ai_pose:
                    # AI Limb Lines
                    if "shoulder_pt" in ai_pose and "fore_paw_pt" in ai_pose:
                        cv2.line(vis, ai_pose["shoulder_pt"], ai_pose["fore_paw_pt"], (16, 185, 129), 2, cv2.LINE_AA)
                    if "hip_pt" in ai_pose and "hind_paw_pt" in ai_pose:
                        cv2.line(vis, ai_pose["hip_pt"], ai_pose["hind_paw_pt"], (168, 85, 247), 2, cv2.LINE_AA)

                    # Forepaw badge
                    fp = ai_pose.get("fore_paw_pt")
                    if fp:
                        fp_c = ai_pose.get("fore_paw_pt_conf", 1.0)
                        cv2.circle(vis, fp, 7, (16, 185, 129), 2, cv2.LINE_AA)
                        cv2.circle(vis, fp, 3, (16, 185, 129), -1)
                        cv2.putText(vis, f"🐾 FOREPAW {fp_c*100:.0f}%", (fp[0] + 8, fp[1] + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (16, 185, 129), 1, cv2.LINE_AA)

                    # Hindpaw badge
                    hp = ai_pose.get("hind_paw_pt")
                    if hp:
                        hp_c = ai_pose.get("hind_paw_pt_conf", 1.0)
                        cv2.circle(vis, hp, 7, (168, 85, 247), 2, cv2.LINE_AA)
                        cv2.circle(vis, hp, 3, (168, 85, 247), -1)
                        cv2.putText(vis, f"🐾 HINDPAW {hp_c*100:.0f}%", (hp[0] + 8, hp[1] + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (168, 85, 247), 1, cv2.LINE_AA)

            # 6. Excluded Banner & Warning Overlay
            if sample.get("excluded", False):
                red_tint = np.zeros_like(vis)
                red_tint[:, :] = (20, 20, 140)
                vis = cv2.addWeighted(vis, 0.62, red_tint, 0.38, 0)
                cv2.rectangle(vis, (8, 8), (430, 42), (20, 20, 190), -1)
                cv2.putText(vis, "🚫 KIZÁRVA — A MODELL NEM HASZNÁLJA", (14, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 2, cv2.LINE_AA)

            # Focus on rodent if toggled
            if var_zoom_rodent.get() and bbox:
                bx, by, bw, bh = bbox
                margin_x = max(80, int(bw * 0.7))
                margin_y = max(40, int(bh * 0.6))
                c_x1 = max(0, bx - margin_x)
                c_y1 = max(0, by - margin_y)
                c_x2 = min(cw_img, bx + bw + margin_x)
                c_y2 = min(ch_img, by + bh + margin_y)
                disp = vis[c_y1:c_y2, c_x1:c_x2]
            else:
                disp = vis

            # Zoom & Pan
            z = view_state["zoom"]
            if z > 1.01:
                vh, vw = disp.shape[0] / z, disp.shape[1] / z
                cx = float(disp.shape[1] * 0.5 + view_state["pan_x"])
                cy = float(disp.shape[0] * 0.5 + view_state["pan_y"])
                x1 = int(np.clip(cx - vw * 0.5, 0, disp.shape[1] - vw))
                y1 = int(np.clip(cy - vh * 0.5, 0, disp.shape[0] - vh))
                disp = disp[y1:y1 + int(vh), x1:x1 + int(vw)]

            cw = max(400, canvas_view.winfo_width())
            ch = max(300, canvas_view.winfo_height())
            scale = min(cw / float(disp.shape[1]), ch / float(disp.shape[0]))
            tw = max(10, int(disp.shape[1] * scale))
            th = max(10, int(disp.shape[0] * scale))

            resized = cv2.resize(disp, (tw, th), interpolation=cv2.INTER_LINEAR)
            ok, buf = cv2.imencode(".ppm", resized)
            if ok:
                photo = tk.PhotoImage(data=buf.tobytes())
                photo_ref[0] = photo
                canvas_view.delete("all")
                canvas_view.create_image(cw // 2, ch // 2, image=photo, anchor="center")

            # Update Telemetry & Counts
            s_idx = current_idx[0] + 1
            tot = len(samples_list)
            lbl_counter.config(text=self.tr("lbl_sample_counter", cur=s_idx, tot=tot))
            slider_samples.config(to=max(1, tot))
            slider_var.set(s_idx)

            v_name = sample.get("video_name", "")
            f_num = sample.get("f_idx", 0)
            sec_val = sample.get("sec", 0.0)
            area_val = sample.get("area", 0)
            bw_val, bh_val = sample.get("bbox", (0, 0, 0, 0))[2:4]
            is_ex = sample.get("excluded", False)

            status_str = self.tr("sample_status_excluded") if is_ex else self.tr("sample_status_valid")
            status_fg = P["danger"] if is_ex else P["emerald"]
            lbl_sample_info.config(
                text=f"{v_name} | #{f_num} ({sec_val:.2f}s) | {area_val:,} px | {bw_val}×{bh_val} px | {status_str}",
                fg=status_fg
            )

            btn_exclude.config(
                text=self.tr("btn_include_sample") if is_ex else self.tr("btn_exclude_sample"),
                style="Emerald.TButton" if is_ex else "Ghost.TButton"
            )

            act_count = sum(1 for s in samples_list if not s.get("excluded", False))
            ex_count = len(samples_list) - act_count
            lbl_tot_val.config(text=str(len(samples_list)))
            lbl_act_val.config(text=str(act_count))
            lbl_excl_val.config(text=str(ex_count))

        def _on_sample_harvested(sample, total_collected):
            def _gui_add():
                if not preview_win.winfo_exists():
                    return
                samples_list.append(sample)
                lbl_tot_val.config(text=str(len(samples_list)))
                lbl_act_val.config(text=str(sum(1 for s in samples_list if not s.get("excluded", False))))
                if len(samples_list) == 1:
                    current_idx[0] = 0
                    _render_current_sample()
                else:
                    s_idx = current_idx[0] + 1
                    lbl_counter.config(text=self.tr("lbl_sample_counter", cur=s_idx, tot=len(samples_list)))
                    slider_samples.config(to=len(samples_list))
            preview_win.after(0, _gui_add)

        def _start_harvest():
            samples_list.clear()
            current_idx[0] = 0
            canvas_view.delete("all")
            lbl_sample_info.config(text=self.tr("status_harvesting"), fg=P["cyan"])
            lbl_prog_status.config(text="Minták keresése és kinyerése...", fg=P["text_muted"])
            btn_train.config(state="disabled")

            def _worker():
                try:
                    harvest_stop_event.clear()
                    self.dlc_addon.harvest_training_samples(
                        self,
                        max_samples_per_video=45,
                        progress_cb=_on_sample_harvested,
                        stop_event=harvest_stop_event
                    )
                finally:
                    def _done():
                        if not preview_win.winfo_exists():
                            return
                        if samples_list:
                            lbl_sample_info.config(text=self.tr("status_ready"), fg=P["emerald"])
                            lbl_prog_status.config(text=f"{len(samples_list)} minta kész a betanításra!", fg=P["emerald"])
                            btn_train.config(state="normal")
                            _render_current_sample()
                        else:
                            lbl_sample_info.config(text="⚠ Nem található érvényes egérminta a videókban.", fg=P["amber"])
                            lbl_prog_status.config(text="Nincs elegendő minta a tréninghez.", fg=P["amber"])
                    preview_win.after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        def _start_training():
            active_cnt = sum(1 for s in samples_list if not s.get("excluded", False))
            excl_cnt = len(samples_list) - active_cnt
            if active_cnt < 6:
                messagebox.showwarning(
                    APP_NAME,
                    f"Legalább 6 aktív tanítóminta szükséges a betanításhoz!\n(Jelenleg: {active_cnt} aktív, {excl_cnt} kizárva)",
                    parent=preview_win
                )
                return

            try:
                ep_val = int(var_epochs.get())
            except ValueError:
                ep_val = 10

            btn_train.config(state="disabled")
            btn_rescan.config(state="disabled")
            prog_bar["value"] = 0
            lbl_prog_status.config(text="AI modell előkészítése és tréning...", fg=P["cyan"])

            def _log_append(text):
                def _gui_log():
                    if preview_win.winfo_exists():
                        txt_log.insert("end", str(text) + "\n")
                        txt_log.see("end")
                preview_win.after(0, _gui_log)

            def _train_progress(pct, text):
                def _gui_upd():
                    if preview_win.winfo_exists():
                        prog_bar["value"] = pct
                        lbl_prog_status.config(text=text, fg=P["cyan"] if pct < 100 else P["emerald"])
                        txt_log.insert("end", f"[{pct:.0f}%] {text}\n")
                        txt_log.see("end")
                preview_win.after(0, _gui_upd)

            def _train_worker():
                try:
                    _log_append(f"🧠 [Paw AI Tréning] Betanítás indítása: {active_cnt} aktív minta felhasználásával ({excl_cnt} kizárt minta mellőzve)...")
                    target = self.dlc_addon.train_rodent_pose_from_samples(
                        self, samples_list, epochs=ep_val, progress_cb=_train_progress, stop_event=train_stop_event
                    )
                    if target and os.path.exists(target):
                        _log_append(f"✅ Siker! Modell mentve: {os.path.basename(target)}")
                        _log_append(f"🔍 Betanított modell tesztelése a {active_cnt} aktív mintán...")
                        det_cnt, act_cnt = self.dlc_addon.test_model_on_samples(target, samples_list)
                        omitted_cnt = len(samples_list) - act_cnt
                        _log_append(f"✔ Detektálva {det_cnt} / {act_cnt} aktív mintán! ({omitted_cnt} kizárt minta kihagyva)")
                        def _success_gui():
                            if preview_win.winfo_exists():
                                var_show_ai.set(True)
                                _render_current_sample()
                                messagebox.showinfo(
                                    APP_NAME,
                                    f"✅ Egyéni Rodent Paw Pose AI sikeresen betanítva és aktiválva!\n\n"
                                    f"Modell: {os.path.basename(target)} (9-pontos Mancs & Tartás modell)\n"
                                    f"Tesztelés: {det_cnt} / {act_cnt} aktív mintán sikeres!\n"
                                    f"Kizárt minták: {omitted_cnt} db kizárt minta TELJESEN mellőzve (sem a tréningbe, sem a tesztelésbe nem került be).\n\n"
                                    f"Az előnézeti képeken zöld színnel látható az elülső mancs (🐾 FOREPAW), és lila színnel a hátulsó mancs (🐾 HINDPAW).",
                                    parent=preview_win
                                )
                        preview_win.after(0, _success_gui)
                    else:
                        _log_append("❌ A betanítás nem hozott létre modellt.")
                finally:
                    def _re_enable():
                        if preview_win.winfo_exists():
                            btn_train.config(state="normal")
                            btn_rescan.config(state="normal")
                    preview_win.after(0, _re_enable)

            threading.Thread(target=_train_worker, daemon=True).start()

        def _test_current_model():
            local_pt = get_resource_path("mouse_pose_ai.pt")
            if not os.path.exists(local_pt):
                safe_pt = os.path.join(SAFE_BASE_DIR, "mouse_pose_ai.pt")
                if os.path.exists(safe_pt):
                    local_pt = safe_pt
                else:
                    local_pt = get_resource_path("rodent_detector.pt")
                    if not os.path.exists(local_pt):
                        safe_pt = os.path.join(SAFE_BASE_DIR, "rodent_detector.pt")
                        if os.path.exists(safe_pt):
                            local_pt = safe_pt
                        else:
                            messagebox.showinfo(APP_NAME, "Még nincs betanított AI modell. Indítsa el a tréninget!", parent=preview_win)
                            return
            txt_log.insert("end", f"🔍 Modell tesztelése: {os.path.basename(local_pt)}...\n")
            det_cnt, act_cnt = self.dlc_addon.test_model_on_samples(local_pt, samples_list)
            omitted_cnt = len(samples_list) - act_cnt
            txt_log.insert("end", f"✔ Sikeresen detektálva {det_cnt} / {act_cnt} aktív mintán! ({omitted_cnt} kizárt minta mellőzve)\n")
            txt_log.see("end")
            var_show_ai.set(True)
            _render_current_sample()

        def _prev_sample(event=None):
            if samples_list:
                current_idx[0] = (current_idx[0] - 1) % len(samples_list)
                view_state["zoom"] = 1.0
                view_state["pan_x"] = 0.0
                view_state["pan_y"] = 0.0
                _render_current_sample()

        def _next_sample(event=None):
            if samples_list:
                current_idx[0] = (current_idx[0] + 1) % len(samples_list)
                view_state["zoom"] = 1.0
                view_state["pan_x"] = 0.0
                view_state["pan_y"] = 0.0
                _render_current_sample()

        def _toggle_exclude(event=None):
            if samples_list and 0 <= current_idx[0] < len(samples_list):
                s = samples_list[current_idx[0]]
                s["excluded"] = not s.get("excluded", False)
                if s["excluded"]:
                    s["ai_pred_bbox"] = None
                _render_current_sample()

        def _auto_clean_samples():
            changed = 0
            for s in samples_list:
                # If quality < 65 or aspect < 1.35 or area < 4500
                is_marginal = (s.get("quality", 70) < 65) or (s.get("aspect", 2.0) < 1.35) or (s.get("area", 10000) < 4500)
                if is_marginal and not s.get("excluded", False):
                    s["excluded"] = True
                    s["ai_pred_bbox"] = None
                    changed += 1
            _render_current_sample()
            txt_log.insert("end", f"🧹 {changed} db alacsony minőségű/határeset minta automatikusan kizárva!\n")
            txt_log.see("end")

        def _on_slider(val):
            idx = int(round(float(val))) - 1
            if samples_list and 0 <= idx < len(samples_list) and idx != current_idx[0]:
                current_idx[0] = idx
                view_state["zoom"] = 1.0
                view_state["pan_x"] = 0.0
                view_state["pan_y"] = 0.0
                _render_current_sample()

        def _on_wheel(event):
            factor = 1.25 if (getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0) else (1.0 / 1.25)
            view_state["zoom"] = float(np.clip(view_state["zoom"] * factor, 1.0, 8.0))
            _render_current_sample()

        def _on_drag_start(event):
            view_state["drag_start"] = (event.x, event.y)

        def _on_drag_motion(event):
            if view_state["drag_start"] and view_state["zoom"] > 1.0:
                dx = event.x - view_state["drag_start"][0]
                dy = event.y - view_state["drag_start"][1]
                view_state["drag_start"] = (event.x, event.y)
                view_state["pan_x"] -= dx
                view_state["pan_y"] -= dy
                _render_current_sample()

        btn_prev.config(command=_prev_sample)
        btn_next.config(command=_next_sample)
        btn_exclude.config(command=_toggle_exclude)
        btn_auto_clean.config(command=_auto_clean_samples)
        btn_rescan.config(command=_start_harvest)
        btn_train.config(command=_start_training)
        btn_test.config(command=_test_current_model)
        slider_samples.config(command=_on_slider)

        chk_zoom.config(command=_render_current_sample)
        chk_ai.config(command=_render_current_sample)

        canvas_view.bind("<MouseWheel>", _on_wheel)
        canvas_view.bind("<Button-4>", _on_wheel)
        canvas_view.bind("<Button-5>", _on_wheel)
        canvas_view.bind("<ButtonPress-1>", _on_drag_start)
        canvas_view.bind("<B1-Motion>", _on_drag_motion)
        canvas_view.bind("<Configure>", lambda e: _render_current_sample())

        preview_win.bind("<Left>", _prev_sample)
        preview_win.bind("<Right>", _next_sample)
        preview_win.bind("<space>", _toggle_exclude)
        preview_win.bind("<x>", _toggle_exclude)
        preview_win.bind("<Escape>", lambda e: preview_win.destroy())

        def _on_window_close():
            harvest_stop_event.set()
            train_stop_event.set()
            preview_win.destroy()

        preview_win.protocol("WM_DELETE_WINDOW", _on_window_close)

        preview_win.after(100, _start_harvest)

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
            cooldown_val = float(self.var_cooldown.get())
        except ValueError:
            cooldown_val = 0.50
        try:
            min_dist_val = int(self.var_min_dist.get())
        except ValueError:
            min_dist_val = 30
        try:
            gate_cm_val = float(self.var_gate_cm.get())
        except ValueError:
            gate_cm_val = 60.0
        try:
            stride_val = max(1, int(self.var_stride.get()))
        except ValueError:
            stride_val = 1

        return {
            "profile_version": "3.6",
            "language": self.lang,
            "calib_dark_thresh": self.calib_dark_thresh,
            "calib_diff_thresh": self.calib_diff_thresh,
            "calib_ladder_thresh": self.calib_ladder_thresh,
            "calib_fault_Ratio": self.calib_fault_Ratio,
            "dip_cooldown_sec": cooldown_val,
            "dip_min_dist_px": min_dist_val,
            "gate_dist_cm": gate_cm_val,
            "frame_stride": stride_val,
            "auto_calib": self.var_auto_calib.get(),
            "yolo_fusion": self.var_yolo_fusion.get(),
            "bidirectional": self.var_bidirectional.get(),
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

        if "calib_dark_thresh" in data:
            self.calib_dark_thresh = int(np.clip(data["calib_dark_thresh"], 50, 210))
        if "calib_diff_thresh" in data:
            self.calib_diff_thresh = int(np.clip(data["calib_diff_thresh"], 8, 95))
        if "calib_ladder_thresh" in data:
            self.calib_ladder_thresh = int(np.clip(data["calib_ladder_thresh"], 40, 195))
        if "calib_fault_Ratio" in data:
            self.calib_fault_Ratio = int(np.clip(data["calib_fault_Ratio"], 35, 95))

        if "dip_cooldown_sec" in data:
            self.var_cooldown.set(f"{float(data['dip_cooldown_sec']):.2f}")
        if "dip_min_dist_px" in data:
            self.var_min_dist.set(str(int(data["dip_min_dist_px"])))
        if "gate_dist_cm" in data:
            self.var_gate_cm.set(f"{float(data['gate_dist_cm']):.1f}")
        if "frame_stride" in data:
            self.var_stride.set(str(max(1, int(data["frame_stride"]))))

        for key, var in [
            ("auto_calib", self.var_auto_calib),
            ("yolo_fusion", self.var_yolo_fusion),
            ("bidirectional", self.var_bidirectional),
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
        self._refresh_kpi_cards()

    def _try_autoload_last_profile(self):
        default_path = os.path.join(self.output_base_dir, "utolso_kalibracio.json")
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._apply_profile_dict(data)
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
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(self._build_profile_dict(), f, indent=4, ensure_ascii=False)
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
            data["profile_version"] = "3.6"
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
        try:
            self.root.after(0, _append)
        except (RuntimeError, tk.TclError):
            pass

    def update_row_status(self, uid, status_text):
        def _update():
            if self.tree.exists(uid):
                vals = list(self.tree.item(uid, "values"))
                vals[2] = status_text
                self.tree.item(uid, values=vals)
        try:
            self.root.after(0, _update)
        except (RuntimeError, tk.TclError):
            pass

    def increment_progress(self, total):
        def _inc():
            self.completed_videos += 1
            pct = (self.completed_videos / max(1, total)) * 100
            self.progress_bar["value"] = pct
            self.progress_lbl.config(text=self.tr("prog_run", done=self.completed_videos, total=total, pct=pct))
        try:
            self.root.after(0, _inc)
        except (RuntimeError, tk.TclError):
            pass

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
        if self._inline_id_entry and self._inline_id_entry.winfo_exists():
            try:
                self._inline_id_entry.destroy()
            except Exception:
                pass
            self._inline_id_entry = None
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
        if self._inline_id_entry and self._inline_id_entry.winfo_exists():
            try:
                self._inline_id_entry.destroy()
            except Exception:
                pass
            self._inline_id_entry = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.video_data.clear()
        self._refresh_kpi_cards()
        self.progress_bar["value"] = 0
        self.progress_lbl.config(text=self.tr("prog_idle", done=0, total=0))

    def edit_animal_id(self, event=None, force_dialog=False):
        """
        Interactive Subject ID Editor with comprehensive Enter key support:
        - Triggerable via Enter/Return, numpad KP_Enter, F2, double-click, or toolbar button.
        - Inline cell editing directly inside the table for immediate, seamless modification.
        - Pressing Enter inside the entry commits the change and advances selection to the next row.
        - Pressing Escape cancels editing.
        - Automatic fallback to focused modal dialog if table row is off-screen.
        """
        if self.is_running:
            return "break"

        # If triggered by mouse double-click, resolve the exact row clicked
        if event and hasattr(event, "x") and hasattr(event, "y") and event.widget == self.tree:
            row_id = self.tree.identify_row(event.y)
            if row_id:
                self.tree.selection_set(row_id)
                self.tree.focus(row_id)

        sel = self.tree.selection()
        if not sel:
            children = self.tree.get_children()
            if children:
                self.tree.selection_set(children[0])
                self.tree.focus(children[0])
                sel = [children[0]]
            else:
                messagebox.showinfo("Info", self.tr("msg_select_row"))
                return "break"

        uid = sel[0]
        current_values = list(self.tree.item(uid, "values"))
        cur_id = current_values[1]

        # Clean up any lingering inline editor
        if self._inline_id_entry and self._inline_id_entry.winfo_exists():
            try:
                self._inline_id_entry.destroy()
            except Exception:
                pass
            self._inline_id_entry = None

        bbox = self.tree.bbox(uid, "animal_id")
        if not bbox or bbox[2] <= 0 or force_dialog:
            self._open_modal_edit_id(uid, current_values)
            return "break"

        # --- Inline Cell Editing directly over the Subject ID cell ---
        x, y, w, h = bbox
        entry_h = max(24, h + 4)
        entry_y = max(0, y - 2)
        P = self.PALETTE

        entry = tk.Entry(
            self.tree,
            font=(self.ui_font, 10, "bold"),
            justify="center",
            bg=P["bg_main"],
            fg=P["emerald"],
            insertbackground=P["emerald"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightcolor=P["emerald"]
        )
        entry.insert(0, cur_id)
        entry.select_range(0, tk.END)
        entry.place(x=x, y=entry_y, width=w, height=entry_h)
        entry.focus_force()
        self._inline_id_entry = entry

        is_committing = False

        def commit_change(e=None):
            nonlocal is_committing
            if is_committing:
                return "break"
            is_committing = True

            new_id = entry.get().strip() if entry.winfo_exists() else ""
            if new_id and new_id != cur_id:
                current_values[1] = new_id
                self.tree.item(uid, values=current_values)
                for item in self.video_data:
                    if item["uid"] == uid:
                        item["id"] = new_id
                        break
                self.log(f"Subject ID updated: {current_values[0]} -> #{new_id}")

            if entry.winfo_exists():
                entry.destroy()
            self._inline_id_entry = None
            self.tree.focus_set()

            # Advance selection to the next item for rapid sequential editing with Enter
            next_uid = self.tree.next(uid)
            if next_uid:
                self.tree.selection_set(next_uid)
                self.tree.focus(next_uid)
                self.tree.see(next_uid)
            return "break"

        def cancel_change(e=None):
            nonlocal is_committing
            if is_committing:
                return "break"
            is_committing = True
            if entry.winfo_exists():
                entry.destroy()
            self._inline_id_entry = None
            self.tree.focus_set()
            return "break"

        entry.bind("<Return>", commit_change)
        entry.bind("<KP_Enter>", commit_change)
        entry.bind("<Escape>", cancel_change)
        entry.bind("<FocusOut>", lambda e: commit_change())
        return "break"

    def _open_modal_edit_id(self, uid, current_values):
        P = self.PALETTE
        top = tk.Toplevel(self.root)
        top.title(self.tr("edit_id_title"))
        top.geometry("380x180")
        top.configure(bg=P["bg_card"])
        top.resizable(False, False)
        top.transient(self.root)
        top.grab_set()

        tk.Label(top, text=current_values[0], bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)).pack(pady=(12, 2))
        tk.Label(top, text=self.tr("edit_id_prompt"), bg=P["bg_card"], fg=P["text_main"], font=(self.ui_font, 10, "bold")).pack(pady=2)

        entry = tk.Entry(
            top, font=(self.ui_font, 12, "bold"), justify="center",
            bg=P["bg_main"], fg=P["emerald"], insertbackground=P["emerald"], relief="flat"
        )
        entry.pack(pady=8, padx=35, fill="x", ipady=4)
        entry.insert(0, current_values[1])
        entry.select_range(0, tk.END)

        def save_id(event_key=None):
            new_id = entry.get().strip()
            if new_id:
                self.tree.item(uid, values=(current_values[0], new_id, current_values[2], current_values[3]))
                for item in self.video_data:
                    if item["uid"] == uid:
                        item["id"] = new_id
                        break
                self.log(f"Subject ID updated: {current_values[0]} -> #{new_id}")
                next_uid = self.tree.next(uid)
                if next_uid:
                    self.tree.selection_set(next_uid)
                    self.tree.focus(next_uid)
                    self.tree.see(next_uid)
            top.destroy()

        entry.bind("<Return>", save_id)
        entry.bind("<KP_Enter>", save_id)
        top.bind("<Return>", save_id)
        top.bind("<KP_Enter>", save_id)
        top.bind("<Escape>", lambda e: top.destroy())
        top.after(50, lambda: (entry.focus_force(), entry.select_range(0, tk.END)))

        btn_row = tk.Frame(top, bg=P["bg_card"])
        btn_row.pack(pady=4)
        ttk.Button(btn_row, text=self.tr("btn_cancel"), command=top.destroy, style="Ghost.TButton").pack(side="left", padx=4)
        ttk.Button(btn_row, text=self.tr("btn_save_enter"), command=save_id, style="Emerald.TButton").pack(side="left", padx=4)

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

        self.is_running = True
        self.completed_videos = 0
        self.pending_results.clear()
        self.progress_bar["value"] = 0
        self.btn_start.config(state="disabled")
        self.btn_quick_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        if self.saved_geometry:
            g = self.saved_geometry
            self._launch_processing_thread(
                g["rx"], g["ry"], g["rw"], g["rh"],
                g["left_gate_x"], g["right_gate_x"]
            )
        else:
            first_video = self.video_data[0]["path"]
            cap = open_video_accelerated(first_video, use_hw=self.var_use_gpu.get())
            try:
                calib = self.auto_engine.auto_calibrate_from_video(cap, num_bg_samples=28)
                self.calib_dark_thresh = calib["calib_dark_thresh"]
                self.calib_diff_thresh = calib["calib_diff_thresh"]
                self.calib_ladder_thresh = calib["calib_ladder_thresh"]
                self.calib_fault_Ratio = calib["calib_fault_Ratio"]
                self.saved_geometry = {
                    "rx": calib["rx"], "ry": calib["ry"],
                    "rw": calib["rw"], "rh": calib["rh"],
                    "left_gate_x": calib["left_gate_x"],
                    "right_gate_x": calib["right_gate_x"]
                }
                self._refresh_kpi_cards()
                self._launch_processing_thread(
                    calib["rx"], calib["ry"], calib["rw"], calib["rh"],
                    calib["left_gate_x"], calib["right_gate_x"]
                )
            except Exception as e:
                messagebox.showerror("Auto-Calib Error", str(e))
                self.reset_ui()
            finally:
                cap.release()

    def _compute_clean_background(self, cap, rx, ry, rw, rh, num_samples=28):
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        bg_frames = []

        if total_frames > num_samples:
            indices = np.linspace(0, total_frames - 2, num_samples, dtype=int)
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                r, f = cap.read()
                if r and f is not None:
                    crop = f[ry:ry + rh, rx:rx + rw]
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
                    bg_frames.append(np.squeeze(gray))
        else:
            for _ in range(14):
                r, f = cap.read()
                if r and f is not None:
                    crop = f[ry:ry + rh, rx:rx + rw]
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
                    bg_frames.append(np.squeeze(gray))

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not bg_frames:
            return None
        stack = np.stack(bg_frames, axis=0)
        return AutoAdaptiveLadderEngine.compute_outlier_rejected_bg(stack)

    def _create_ladder_mask(self, base_gray, ladder_thresh, fault_y_local=None):
        if base_gray.ndim == 3:
            base_gray = cv2.cvtColor(base_gray, cv2.COLOR_BGR2GRAY)
        base_gray = np.squeeze(base_gray).astype(np.uint8)
        rh, rw = base_gray.shape[:2]

        if fault_y_local is None:
            fault_y_local = int(rh * 0.72)

        top_clear_y = max(5, int(fault_y_local) - 20)
        bottom_cutoff = min(rh, int(fault_y_local) + 18)

        _, dark_rungs = cv2.threshold(base_gray, ladder_thresh, 255, cv2.THRESH_BINARY_INV)
        blackhat = cv2.morphologyEx(base_gray, cv2.MORPH_BLACKHAT, self.kernel_blackhat_13)
        _, bh_mask = cv2.threshold(blackhat, max(14, int((205 - ladder_thresh) * 0.26)), 255, cv2.THRESH_BINARY)

        raw_rungs = cv2.bitwise_or(dark_rungs, bh_mask)
        raw_rungs[:top_clear_y, :] = 0
        raw_rungs[bottom_cutoff:, :] = 0

        closed_rungs = cv2.morphologyEx(raw_rungs, cv2.MORPH_CLOSE, self.kernel_small)
        contours, _ = cv2.findContours(closed_rungs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        clean_ladder = np.zeros_like(base_gray)

        for c in contours:
            area = cv2.contourArea(c)
            if area < 10:
                continue
            x_c, y_c, w_c, h_c = cv2.boundingRect(c)
            if w_c <= 42 and h_c <= 34 and area <= 850:
                cv2.drawContours(clean_ladder, [c], -1, 255, -1)
            else:
                clean_ladder[y_c:y_c + h_c, x_c:x_c + w_c] = cv2.bitwise_or(
                    clean_ladder[y_c:y_c + h_c, x_c:x_c + w_c],
                    bh_mask[y_c:y_c + h_c, x_c:x_c + w_c]
                )

        ladder_mask = cv2.dilate(clean_ladder, self.kernel_small, iterations=2)
        ladder_mask[:top_clear_y, :] = 0
        ladder_mask[bottom_cutoff:, :] = 0
        return ladder_mask

    @staticmethod
    def _bbox_iou(first, second):
        if first is None or second is None:
            return 0.0
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        left, top = max(ax, bx), max(ay, by)
        right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        intersection = max(0, right - left) * max(0, bottom - top)
        union = aw * ah + bw * bh - intersection
        return intersection / max(1.0, float(union))

    def _select_mouse_contour(self, candidate_masks, gray, base_gray, previous_bbox, anchor_bbox, fault_y_local=None):
        rh, rw = gray.shape[:2]
        if fault_y_local is None:
            fault_y_local = int(rh * 0.72)
        torso_corridor_y = max(14, int(fault_y_local) - 8)
        min_corridor_bottom = max(10, int(torso_corridor_y * 0.32))
        max_valid_torso_top = max(12, int(fault_y_local) - max(45, int(rh * 0.16)))
        min_torso_h = max(24, int(rh * 0.09))

        best_contour = None
        best_mask = None
        best_score = float("-inf")
        for candidate_mask, gate_bonus in candidate_masks:
            contours, _ = cv2.findContours(
                candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 1200 or area > rw * rh * 0.70:
                    continue
                x, y, width, height = cv2.boundingRect(contour)
                upper_h = min(y + height, torso_corridor_y) - y
                aspect_ratio = width / max(1.0, float(height))
                if (
                    width < 35
                    or height < min_torso_h
                    or upper_h < min_torso_h
                    or upper_h < height * 0.40
                    or y >= max_valid_torso_top
                    or (y + height) < min_corridor_bottom
                    or aspect_ratio < 0.38
                    or aspect_ratio > 11.5
                ):
                    continue
                if (y + height * 0.45) >= fault_y_local:
                    continue
                fill_ratio = area / max(1.0, float(width * height))
                if fill_ratio < 0.10:
                    continue

                roi_gray = gray[y:y + height, x:x + width]
                roi_base = base_gray[y:y + height, x:x + width]
                foreground = candidate_mask[y:y + height, x:x + width] > 0
                if np.any(foreground):
                    fg_diff = (
                        roi_base[foreground].astype(np.int16) - roi_gray[foreground].astype(np.int16)
                    )
                    contrast = float(np.percentile(np.abs(fg_diff), 65))
                    darkening = float(np.mean(np.maximum(0, fg_diff)))
                    p85_darkening = float(np.percentile(np.maximum(0, fg_diff), 85))
                else:
                    contrast = 0.0
                    darkening = 0.0
                    p85_darkening = 0.0
                if p85_darkening < 24.0 and previous_bbox is None:
                    continue
                if (contrast < 10.0 or darkening < 7.0) and anchor_bbox is None and previous_bbox is None:
                    continue

                corridor_align = 1.0 - min(1.0, abs(min(y + height, torso_corridor_y) - torso_corridor_y) / max(18.0, float(torso_corridor_y)))

                score = np.log1p(area) + 2.2 * fill_ratio + 0.8 * corridor_align
                score += float(np.clip(contrast / 26.0, -1.0, 2.5)) + gate_bonus
                candidate_bbox = (x, y, width, height)
                score += 2.2 * self._bbox_iou(candidate_bbox, anchor_bbox)

                if previous_bbox is not None:
                    previous_cx = previous_bbox[0] + previous_bbox[2] / 2.0
                    previous_cy = previous_bbox[1] + previous_bbox[3] / 2.0
                    candidate_cx = x + width / 2.0
                    candidate_cy = y + height / 2.0
                    distance = np.hypot(candidate_cx - previous_cx, candidate_cy - previous_cy)
                    distance_scale = max(36.0, min(140.0, rw * 0.18))
                    score += 3.2 * np.exp(-distance / distance_scale)
                    score -= min(3.2, distance / distance_scale)

                if score > best_score:
                    best_score = score
                    best_contour = contour
                    best_mask = candidate_mask
        return best_contour, best_mask

    @staticmethod
    def _compute_skin_chromaticity(crop_bgr):
        """
        Fast biological skin chromaticity index (100x speedup via 8x8 subsampled median baseline).
        Preserves exact chrominance of pink paws, digits, and snout tip.
        """
        if crop_bgr is None or crop_bgr.ndim != 3 or crop_bgr.shape[2] < 3:
            return None
        b_ch = crop_bgr[:, :, 0].astype(np.float32)
        g_ch = crop_bgr[:, :, 1].astype(np.float32)
        r_ch = crop_bgr[:, :, 2].astype(np.float32)

        raw_rg = r_ch - g_ch
        raw_rb = r_ch - b_ch

        # Subsample for ambient baseline computation (0.05ms)
        amb_rg = max(0.0, float(np.median(raw_rg[::8, ::8])) * 0.70)
        amb_rb = max(0.0, float(np.median(raw_rb[::8, ::8])) * 0.70)

        excess_rg = np.maximum(0.0, raw_rg - amb_rg)
        excess_rb = np.maximum(0.0, raw_rb - amb_rb)

        lab = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2LAB)
        a_star = lab[:, :, 1].astype(np.float32) - 128.0
        b_star = lab[:, :, 2].astype(np.float32) - 128.0
        amb_a = max(0.0, float(np.median(a_star[::8, ::8])) * 0.75)
        bio_a = np.maximum(0.0, (a_star - amb_a) - 0.25 * np.maximum(0.0, b_star - 10.0))

        skin_idx = 0.65 * excess_rg + 0.40 * excess_rb + 0.85 * bio_a
        return cv2.GaussianBlur(skin_idx, (3, 3), 0)

    @staticmethod
    def _compute_spectral_rung_suppression_mask(crop_bgr, gray_raw, fault_y_local, skin_index=None):
        rh, rw = gray_raw.shape[:2]
        keep_mask = np.full((rh, rw), 255, dtype=np.uint8)
        y1 = max(8, int(fault_y_local) - 20)
        y2 = min(rh - 8, int(fault_y_local) + 18)
        if y2 <= y1:
            return keep_mask

        if crop_bgr is not None and crop_bgr.ndim == 3 and crop_bgr.shape[2] >= 3:
            band_bgr = crop_bgr[y1:y2, :].astype(np.float32)
            b_c, g_c, r_c = band_bgr[:, :, 0], band_bgr[:, :, 1], band_bgr[:, :, 2]
            chroma_rung = (
                ((b_c - np.maximum(r_c, g_c)) > 22.0)
                | ((g_c - np.maximum(r_c, b_c)) > 22.0)
            )
            if np.any(chroma_rung):
                keep_mask[y1:y2, :][chroma_rung] = 0

        g_f = gray_raw.astype(np.float32)
        band_g = g_f[y1:y2, :]
        above_g = np.maximum(g_f[y1 - 7:y2 - 7, :], g_f[y1 - 9:y2 - 9, :])
        below_g = np.maximum(g_f[y1 + 7:y2 + 7, :], g_f[y1 + 9:y2 + 9, :])

        sandwiched_rung = (
            (above_g > 148.0)
            & (below_g > 148.0)
            & (((0.5 * (above_g + below_g)) - band_g) > 28.0)
            & (band_g > 48.0)
        )
        if skin_index is not None:
            sandwiched_rung = sandwiched_rung & (skin_index[y1:y2, :] < 9.5)

        if np.any(sandwiched_rung):
            keep_mask[y1:y2, :][sandwiched_rung] = 0

        return keep_mask

    def _detect_mouse_on_crop(
        self, crop, base_gray, inv_ladder_mask, rw, rh, dark_t, diff_t,
        fault_y_local=None, use_umat=False, u_base_smooth=None, u_inv_ladder=None,
        mog2_subtractor=None, stream_id=None, frame_idx=None, ai_max_age=3,
        previous_bbox=None, base_smooth_cached=None, return_skin=False, use_yolo=None
    ):
        if fault_y_local is None:
            fault_y_local = int(rh * 0.72)

        gray_raw = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        gray_raw = np.squeeze(gray_raw).astype(np.uint8)
        skin_index = self._compute_skin_chromaticity(crop)

        if skin_index is not None:
            gray_eff = np.clip(gray_raw.astype(np.float32) - 1.8 * skin_index, 0, 255).astype(np.uint8)
        else:
            gray_eff = gray_raw

        gray_raw_smooth = cv2.GaussianBlur(gray_raw, (3, 3), 0)
        gray_eff_smooth = cv2.GaussianBlur(gray_eff, (3, 3), 0)
        base_smooth = base_smooth_cached if base_smooth_cached is not None else cv2.GaussianBlur(base_gray, (3, 3), 0)

        core_bbox, spatial_gate = None, None
        if use_yolo is None:
            try:
                use_yolo = bool(self.var_yolo_fusion.get())
            except (RuntimeError, tk.TclError):
                use_yolo = True
        if use_yolo:
            core_bbox, spatial_gate = self.hybrid_locator.locate_animal_roi_and_mask(
                crop, gray_raw_smooth, base_smooth, inv_ladder_mask, fault_y_local, dark_t,
                diff_t, stream_id=stream_id, frame_idx=frame_idx, ai_max_age=ai_max_age,
                previous_bbox=previous_bbox
            )

        diff_dark = cv2.subtract(base_smooth, gray_raw_smooth)
        diff_abs = cv2.absdiff(base_smooth, gray_raw_smooth)
        if skin_index is not None:
            diff_eff = np.clip(diff_dark.astype(np.float32) + 0.85 * skin_index, 0, 255).astype(np.uint8)
        else:
            diff_eff = diff_dark

        strict_diff_t = max(10, int(diff_t * 0.74))
        low_diff_t = max(5, int(diff_t * 0.35))
        blemish_diff_t = max(strict_diff_t + 14, int(diff_t * 1.55))

        bg_grad = cv2.morphologyEx(base_smooth, cv2.MORPH_GRADIENT, self.kernel_grad_3)
        static_blemish = (base_smooth <= min(215, dark_t + 8)) | (bg_grad >= 16)
        static_blemish = cv2.dilate(
            static_blemish.astype(np.uint8) * 255, self.kernel_small, iterations=1
        ) > 0

        _, diff_mask = cv2.threshold(diff_eff, strict_diff_t, 255, cv2.THRESH_BINARY)
        _, blemish_pass = cv2.threshold(diff_dark, blemish_diff_t, 255, cv2.THRESH_BINARY)
        diff_mask[static_blemish] = blemish_pass[static_blemish]

        _, dark_mask = cv2.threshold(gray_eff_smooth, min(230, dark_t + 8), 255, cv2.THRESH_BINARY_INV)
        raw_mask = cv2.bitwise_and(diff_mask, dark_mask)

        _, strong_abs_mask = cv2.threshold(diff_abs, max(22, int(diff_t * 1.25)), 255, cv2.THRESH_BINARY)
        strong_abs_mask[static_blemish] = blemish_pass[static_blemish]
        _, body_dark_mask = cv2.threshold(gray_raw_smooth, min(220, dark_t + 12), 255, cv2.THRESH_BINARY_INV)
        raw_mask = cv2.bitwise_or(raw_mask, cv2.bitwise_and(strong_abs_mask, body_dark_mask))

        torso_top_zone = max(10, int(fault_y_local) - 16)
        seed_upper = raw_mask[:torso_top_zone, :].copy()
        if previous_bbox is not None:
            px, py, pw, ph = previous_bbox
            px1, px2 = max(0, int(px - 14)), min(rw, int(px + pw + 14))
            py1, py2 = max(0, int(py - 8)), min(torso_top_zone, int(py + ph + 8))
            if px2 > px1 and py2 > py1:
                stat_seed = (
                    (diff_dark[py1:py2, px1:px2] >= low_diff_t)
                    & (gray_raw_smooth[py1:py2, px1:px2] <= dark_t)
                    & (~static_blemish[py1:py2, px1:px2])
                ).astype(np.uint8) * 255
                seed_upper[py1:py2, px1:px2] = cv2.bitwise_or(seed_upper[py1:py2, px1:px2], stat_seed)

        support_upper = (
            (gray_raw_smooth[:torso_top_zone, :] <= dark_t)
            & (
                ((diff_dark[:torso_top_zone, :] >= low_diff_t) & (~static_blemish[:torso_top_zone, :]))
                | (diff_dark[:torso_top_zone, :] >= blemish_diff_t)
            )
        ).astype(np.uint8) * 255
        support_upper = cv2.bitwise_and(support_upper, inv_ladder_mask[:torso_top_zone, :])

        seed_upper_dilated = cv2.dilate(seed_upper, self.kernel_upper_bridge, iterations=3)
        reconstructed_torso = cv2.bitwise_and(support_upper, seed_upper_dilated)
        raw_mask[:torso_top_zone, :] = cv2.bitwise_or(raw_mask[:torso_top_zone, :], reconstructed_torso)

        max_reach_y = min(rh, int(fault_y_local) + max(38, int(rh * 0.24)))
        if max_reach_y < rh:
            raw_mask[max_reach_y:, :] = 0

        spectral_rung_keep = self._compute_spectral_rung_suppression_mask(
            crop, gray_raw_smooth, fault_y_local, skin_index=skin_index
        )
        effective_inv_ladder = cv2.bitwise_and(inv_ladder_mask, spectral_rung_keep)
        fg_occludes_rung = (diff_dark >= max(26, int(diff_t * 1.15))) & (gray_raw_smooth <= min(78, dark_t - 28))
        if skin_index is not None:
            fg_occludes_rung = fg_occludes_rung | (skin_index >= 10.5)
        dynamic_inv_ladder = cv2.bitwise_or(effective_inv_ladder, fg_occludes_rung.astype(np.uint8) * 255)

        raw_mask = cv2.bitwise_and(raw_mask, dynamic_inv_ladder)

        clean_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, self.kernel_small)
        clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_CLOSE, self.kernel_horiz)
        clean_mask = cv2.bitwise_and(clean_mask, dynamic_inv_ladder)

        candidate_masks = []
        if spatial_gate is not None:
            gated_clean = cv2.bitwise_and(clean_mask, spatial_gate)
            candidate_masks.append((gated_clean, 1.25))
        candidate_masks.append((clean_mask, 0.0))

        best_contour, selected_mask = self._select_mouse_contour(
            candidate_masks, gray_raw_smooth, base_smooth, previous_bbox, core_bbox,
            fault_y_local=fault_y_local
        )

        if best_contour is None:
            ai_pose = getattr(self.hybrid_locator, "last_sync_pose", None)
            if use_yolo and getattr(self.hybrid_locator, "is_rodent_pose", False) and ai_pose and "bbox" in ai_pose:
                ai_mask = self.hybrid_locator._build_capsule_mask_from_pose(ai_pose, ai_pose["bbox"], rw, rh)
                ai_cnts, _ = cv2.findContours(ai_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if ai_cnts:
                    best_contour = max(ai_cnts, key=cv2.contourArea)
                    clean_mask = cv2.bitwise_or(clean_mask, ai_mask)
            if best_contour is None:
                if return_skin:
                    return False, None, None, skin_index
                return False, None, None

        attachment_source = cv2.bitwise_and(clean_mask, spatial_gate) if spatial_gate is not None else clean_mask
        contours, _ = cv2.findContours(
            attachment_source, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        final_mouse_mask = np.zeros_like(clean_mask)
        x_c, y_c, w_c, h_c = cv2.boundingRect(best_contour)
        cv2.drawContours(final_mouse_mask, [best_contour], -1, 255, -1)

        col_heights = np.sum(final_mouse_mask[:max(12, int(fault_y_local) - 6), x_c:x_c + w_c] > 0, axis=0)
        thick_cols = np.where(col_heights >= max(6, int(h_c * 0.25)))[0]
        if len(thick_cols) >= 10:
            torso_x1 = x_c + int(thick_cols[0])
            torso_x2 = x_c + int(thick_cols[-1]) + 1
        else:
            torso_x1, torso_x2 = x_c, x_c + w_c
        torso_w = max(16, torso_x2 - torso_x1)

        min_x, min_y = x_c, y_c
        max_x, max_y = x_c + w_c, y_c + h_c

        for c in contours:
            if cv2.boundingRect(c) != (x_c, y_c, w_c, h_c):
                c_area = cv2.contourArea(c)
                if 10 <= c_area < 2200:
                    cx, cy, cw, ch = cv2.boundingRect(c)
                    center_x = cx + cw / 2.0
                    body_x_min = torso_x1 - max(6, int(torso_w * 0.05))
                    body_x_max = torso_x2 + max(8, int(torso_w * 0.08))
                    max_paw_y = min(max_reach_y, max(y_c + h_c + 34, int(fault_y_local) + int(rh * 0.26)))

                    if (
                        (cy + ch) <= torso_top_zone
                        and cy >= y_c
                        and ch <= max(28, int(h_c * 0.45))
                        and (abs(cx + cw - min_x) <= 28 or abs(cx - max_x) <= 28)
                    ):
                        cv2.drawContours(final_mouse_mask, [c], -1, 255, -1)
                        min_x, min_y = min(min_x, cx), min(min_y, cy)
                        max_x, max_y = max(max_x, cx + cw), max(max_y, cy + ch)
                        continue

                    if cw > ch * 1.9 or ch < 4:
                        continue
                    if body_x_min <= center_x <= body_x_max and y_c <= cy <= max_paw_y:
                        cv2.drawContours(final_mouse_mask, [c], -1, 255, -1)
                        min_x = min(min_x, cx)
                        min_y = min(min_y, cy)
                        max_x = max(max_x, cx + cw)
                        max_y = max(max_y, cy + ch)

        upper_cut = max(10, int(fault_y_local) - 16)
        final_mouse_mask[:upper_cut, :] = cv2.morphologyEx(
            final_mouse_mask[:upper_cut, :], cv2.MORPH_CLOSE, self.kernel_upper_bridge
        )
        final_mouse_mask[upper_cut:, :] = cv2.bitwise_and(
            final_mouse_mask[upper_cut:, :], inv_ladder_mask[upper_cut:, :]
        )

        ys, xs = np.where(final_mouse_mask > 0)
        if len(xs) == 0:
            if return_skin:
                return False, None, None, skin_index
            return False, None, None
        min_x, max_x = int(np.min(xs)), int(np.max(xs))
        min_y, max_y = int(np.min(ys)), int(np.max(ys))

        merged_bbox = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
        if return_skin:
            return True, final_mouse_mask, merged_bbox, skin_index
        return True, final_mouse_mask, merged_bbox

    def _quick_check_start_gate(self, crop, base_gray, inv_ladder_mask, x1_loc, x2_loc, dark_t, diff_t):
        sub_crop = crop[:, x1_loc:x2_loc]
        sub_base = base_gray[:, x1_loc:x2_loc]
        sub_inv_lad = inv_ladder_mask[:, x1_loc:x2_loc]

        gray = cv2.cvtColor(sub_crop, cv2.COLOR_BGR2GRAY) if sub_crop.ndim == 3 else sub_crop
        diff = cv2.subtract(sub_base, gray)
        _, diff_mask = cv2.threshold(diff, max(10, int(diff_t * 0.68)), 255, cv2.THRESH_BINARY)
        _, dark_mask = cv2.threshold(gray, min(220, dark_t + 12), 255, cv2.THRESH_BINARY_INV)
        diff_mask = cv2.bitwise_and(diff_mask, dark_mask)
        diff_mask = cv2.bitwise_and(diff_mask, sub_inv_lad)
        return cv2.countNonZero(diff_mask) > 850


    def _extract_rodent_anatomy(
        self, mouse_mask, fault_curve, bbox, previous_bbox=None, move_dir=1.0, crop=None, skin_map=None
    ):
        mh, mw = mouse_mask.shape[:2]
        if bbox is None:
            ys, xs = np.where(mouse_mask > 0)
            if len(xs) == 0:
                return None
            bx, by = int(np.min(xs)), int(np.min(ys))
            bw, bh = int(np.max(xs) - bx + 1), int(np.max(ys) - by + 1)
        else:
            bx, by, bw, bh = bbox

        torso_limit = max(12, min(mh, int(np.min(fault_curve)) - 2))
        bx_end = min(mw, bx + bw)
        upper_mask = mouse_mask[:torso_limit, bx:bx_end].copy()
        if upper_mask.size == 0:
            return None

        if bx <= 3 and upper_mask.shape[1] > 24:
            for c_i in range(min(12, upper_mask.shape[1])):
                ys_c = np.where(upper_mask[:, c_i] > 0)[0]
                if len(ys_c) > 0 and int(np.min(ys_c)) <= 12:
                    upper_mask[:, c_i] = 0
                else:
                    break

        torso_open = cv2.morphologyEx(upper_mask, cv2.MORPH_OPEN, self.kernel_torso_open)
        col_thickness = np.sum(torso_open > 0, axis=0).astype(np.float32)
        if col_thickness.size == 0 or np.max(col_thickness) < 6:
            col_thickness = np.sum(upper_mask > 0, axis=0).astype(np.float32)

        if col_thickness.size >= 5:
            col_smooth = np.convolve(np.pad(col_thickness, (2, 2), mode="edge"), np.ones(5) / 5.0, mode="valid")
        else:
            col_smooth = col_thickness

        max_thick = float(np.max(col_smooth)) if col_smooth.size > 0 else 0.0
        min_torso_thick = max(8.0, max_thick * 0.32)
        peak_col = int(np.argmax(col_smooth)) if col_smooth.size > 0 else 0

        l_idx = peak_col
        gap_cnt = 0
        while l_idx > 0:
            if col_smooth[l_idx - 1] >= min_torso_thick:
                l_idx -= 1
                gap_cnt = 0
            elif gap_cnt < 5 and l_idx - 2 >= 0 and col_smooth[l_idx - 2] >= min_torso_thick:
                l_idx -= 1
                gap_cnt += 1
            else:
                break

        r_idx = peak_col
        gap_cnt = 0
        n_cols = len(col_smooth)
        while r_idx < n_cols - 1:
            if col_smooth[r_idx + 1] >= min_torso_thick:
                r_idx += 1
                gap_cnt = 0
            elif gap_cnt < 5 and r_idx + 2 < n_cols and col_smooth[r_idx + 2] >= min_torso_thick:
                r_idx += 1
                gap_cnt += 1
            else:
                break

        if (r_idx - l_idx + 1) >= 14:
            torso_left_x = bx + int(l_idx)
            torso_right_x = bx + int(r_idx) + 1
        else:
            thick_cols = np.where(col_smooth >= max(6.0, max_thick * 0.25))[0]
            if len(thick_cols) >= 10:
                torso_left_x = bx + int(thick_cols[0])
                torso_right_x = bx + int(thick_cols[-1]) + 1
            else:
                torso_left_x, torso_right_x = bx, bx_end
        torso_width = max(20, torso_right_x - torso_left_x)

        t_x0 = max(0, torso_left_x - bx)
        t_x1 = min(upper_mask.shape[1], torso_right_x - bx)
        left_tail_ext = int(t_x0)
        right_tail_ext = int(upper_mask.shape[1] - t_x1)

        # In standard Left-to-Right protocol, orientation is fixed:
        # Snout (head) is ALWAYS at the right (+X, leading anterior edge)
        # Rump (tail base) is ALWAYS at the left (-X, trailing posterior edge)
        move_dir = 1.0
        rump_x = float(torso_left_x)
        snout_x = float(torso_right_x - 1)
        span_x = max(18.0, snout_x - rump_x)

        torso_crop = upper_mask[:, t_x0:t_x1]
        dist_crop = cv2.distanceTransform((torso_crop > 0).astype(np.uint8), cv2.DIST_L2, 3)

        ty, tx = np.where(torso_crop > 0)
        if len(ty) > 0:
            w_mass = dist_crop[ty, tx] + 0.5
            torso_cx = float(torso_left_x) + float(np.sum(tx * w_mass) / np.sum(w_mass))
            torso_cy = float(np.sum(ty * w_mass) / np.sum(w_mass))
            fallback_y = torso_cy
        else:
            torso_cx = float(torso_left_x + torso_width * 0.5)
            torso_cy = float(by + bh * 0.45)
            fallback_y = torso_cy

        def sample_anatomical_joint(rel_norm, dorsal_bias=0.0, window_frac=0.06):
            gx = int(round(rump_x + rel_norm * span_x))
            lx = int(np.clip(gx - torso_left_x, 0, max(0, torso_crop.shape[1] - 1)))
            half_w = max(2, int(round(torso_width * window_frac)))
            c0 = max(0, lx - half_w)
            c1 = min(torso_crop.shape[1], lx + half_w + 1)
            sub_m = torso_crop[:, c0:c1]
            sub_d = dist_crop[:, c0:c1]
            ys_s, xs_s = np.where(sub_m > 0)
            if len(ys_s) == 0:
                return (int(np.clip(gx, 0, mw - 1)), int(np.clip(round(fallback_y), 0, mh - 1)))
            weights = sub_d[ys_s, xs_s] + 0.5
            medial_y = float(np.sum(ys_s * weights) / np.sum(weights))
            if dorsal_bias > 0.0:
                dorsal_y = float(np.percentile(ys_s, 18))
                medial_y = (1.0 - dorsal_bias) * medial_y + dorsal_bias * dorsal_y
            elif dorsal_bias < 0.0:
                ventral_y = float(np.percentile(ys_s, 82))
                medial_y = (1.0 + dorsal_bias) * medial_y - dorsal_bias * ventral_y
            return (int(np.clip(gx, 0, mw - 1)), int(np.clip(round(medial_y), 0, mh - 1)))

        tail_base = sample_anatomical_joint(0.03, dorsal_bias=0.0)
        hip_pt = sample_anatomical_joint(0.24, dorsal_bias=0.12)
        spine_mid = sample_anatomical_joint(0.47, dorsal_bias=0.30)
        shoulder_pt = sample_anatomical_joint(0.67, dorsal_bias=0.14)
        head_pt = sample_anatomical_joint(0.85, dorsal_bias=0.16)
        nose_pt = sample_anatomical_joint(0.98, dorsal_bias=-0.22, window_frac=0.035)

        ant_x_a = int(round(rump_x + 0.78 * span_x))
        ant_x_b = int(round(rump_x + 1.00 * span_x))
        ax1, ax2 = max(0, min(ant_x_a, ant_x_b)), min(mw, max(ant_x_a, ant_x_b) + 1)
        snout_pitched_down = False
        if ax2 > ax1 and head_pt[1] < mh:
            ant_full = mouse_mask[max(0, head_pt[1]):, ax1:ax2]
            ay_s, ax_s = np.where(ant_full > 0)
            if len(ay_s) >= 8:
                max_ant_y = int(head_pt[1] + np.max(ay_s))
                if max_ant_y >= torso_limit + 4:
                    tip_band = ay_s >= max(0, int(np.percentile(ay_s, 90)) - 2)
                    nose_pt = (
                        int(np.clip(ax1 + round(np.mean(ax_s[tip_band])), 0, mw - 1)),
                        int(np.clip(head_pt[1] + round(np.max(ay_s[tip_band])), 0, mh - 1)),
                    )
                    snout_pitched_down = True
                    crown_pt = sample_anatomical_joint(0.88, dorsal_bias=0.32, window_frac=0.05)
                    if move_dir >= 0:
                        head_pt = (max(crown_pt[0], min(int(snout_x) - 6, nose_pt[0])), crown_pt[1])
                    else:
                        head_pt = (min(crown_pt[0], max(int(snout_x) + 6, nose_pt[0])), crown_pt[1])

        tail_tip = tail_base
        tail_chain = [tail_base]
        if move_dir >= 0 and t_x0 > 8:
            tail_strip = upper_mask[:, :t_x0]
            col_h_tail = np.sum(tail_strip > 0, axis=0)
            t_ys, t_xs = np.where(tail_strip > 0)
            valid_t = (
                (np.abs(t_ys - tail_base[1]) <= 34)
                & (col_h_tail[t_xs] <= max(18, int(max_thick * 0.42)))
                & ((bx + t_xs) >= 4)
            )
            t_ys, t_xs = t_ys[valid_t], t_xs[valid_t]
            if len(t_xs) >= 6:
                min_tx = int(np.min(t_xs))
                if (t_x0 - min_tx) >= 8:
                    pts_t = []
                    for frac in (0.0, 0.35, 0.70):
                        target_x = int(round(min_tx + frac * (t_x0 - min_tx)))
                        band = np.abs(t_xs - target_x) <= 4
                        if np.any(band):
                            pts_t.append((int(bx + target_x), int(round(np.median(t_ys[band])))))
                    if pts_t:
                        tail_tip = pts_t[0]
                        tail_chain = pts_t + [tail_base]
        elif move_dir < 0 and t_x1 < upper_mask.shape[1] - 8:
            tail_strip = upper_mask[:, t_x1:]
            col_h_tail = np.sum(tail_strip > 0, axis=0)
            t_ys, t_xs = np.where(tail_strip > 0)
            valid_t = (
                (np.abs(t_ys - tail_base[1]) <= 34)
                & (col_h_tail[t_xs] <= max(18, int(max_thick * 0.42)))
                & ((bx + t_x1 + t_xs) < mw - 4)
            )
            t_ys, t_xs = t_ys[valid_t], t_xs[valid_t]
            if len(t_xs) >= 6:
                max_tx = int(np.max(t_xs))
                if max_tx >= 8:
                    pts_t = []
                    for frac in (1.0, 0.65, 0.30):
                        target_x = int(round(frac * max_tx))
                        band = np.abs(t_xs - target_x) <= 4
                        if np.any(band):
                            pts_t.append((int(bx + t_x1 + target_x), int(round(np.median(t_ys[band])))))
                    if pts_t:
                        tail_tip = pts_t[0]
                        tail_chain = pts_t + [tail_base]

        def sample_ventral_paw(rel_start, rel_end, parent_joint):
            x_a = int(round(rump_x + rel_start * span_x))
            x_b = int(round(rump_x + rel_end * span_x))
            px1 = max(0, min(x_a, x_b))
            px2 = min(mw, max(x_a, x_b) + 1)
            py1 = max(0, parent_joint[1])
            if px2 <= px1 or py1 >= mh:
                return (parent_joint[0], min(mh - 1, parent_joint[1] + 8))
            sub_limb = mouse_mask[py1:, px1:px2]
            ly, lx = np.where(sub_limb > 0)
            if len(ly) < 3:
                return (parent_joint[0], min(mh - 1, parent_joint[1] + 8))
            p92_y = float(np.percentile(ly, 92))
            bottom_band = ly >= max(0, int(p92_y) - 2)
            paw_x = px1 + int(round(np.mean(lx[bottom_band])))
            paw_y = py1 + int(round(np.max(ly[bottom_band])))
            return (int(np.clip(paw_x, 0, mw - 1)), int(np.clip(paw_y, 0, mh - 1)))

        hind_paw_pt = sample_ventral_paw(0.08, 0.44, hip_pt)
        fore_paw_pt = sample_ventral_paw(0.46, 0.74, shoulder_pt)

        if hasattr(self, "hybrid_locator") and getattr(self.hybrid_locator, "is_rodent_pose", False):
            ai_pose = self.hybrid_locator.get_latest_pose_for_bbox(bx, by, bw, bh, mw, mh)
            if ai_pose is not None:
                ai_nose = ai_pose.get("nose_pt")
                ai_tbase = ai_pose.get("tail_base")
                ai_dir_ok = True
                if ai_nose is not None and ai_tbase is not None:
                    ai_dir = 1.0 if (ai_nose[0] - ai_tbase[0]) >= 0 else -1.0
                    if ai_dir != move_dir:
                        ai_dir_ok = False

                if ai_dir_ok:
                    def _blend_pt(geo_pt, key_name, ai_w=0.35):
                        ap = ai_pose.get(key_name)
                        if ap is None:
                            return geo_pt
                        if abs(ap[0] - geo_pt[0]) > max(35, torso_width * 0.35) or abs(ap[1] - geo_pt[1]) > 32:
                            return geo_pt
                        return (
                            int(np.clip(round((1.0 - ai_w) * geo_pt[0] + ai_w * ap[0]), 0, mw - 1)),
                            int(np.clip(round((1.0 - ai_w) * geo_pt[1] + ai_w * ap[1]), 0, mh - 1)),
                        )

                    tail_base = _blend_pt(tail_base, "tail_base", 0.30)
                    hip_pt = _blend_pt(hip_pt, "hip_pt", 0.35)
                    spine_mid = _blend_pt(spine_mid, "spine_mid", 0.35)
                    shoulder_pt = _blend_pt(shoulder_pt, "shoulder_pt", 0.35)
                    if not snout_pitched_down:
                        head_pt = _blend_pt(head_pt, "head_pt", 0.35)
                        nose_pt = _blend_pt(nose_pt, "nose_pt", 0.35)

                    # Paw-Specialized AI Locking (Forepaw & Hindpaw):
                    # Prioritize deep neural network detections for paws even when dipping below ladder rungs.
                    def _blend_paw(geo_pt, key_name, parent_joint):
                        ap = ai_pose.get(key_name)
                        if ap is None:
                            return geo_pt
                        conf = float(ai_pose.get(key_name + "_conf", 0.5))
                        dx = abs(ap[0] - parent_joint[0])
                        dy = ap[1] - parent_joint[1]
                        # Verify anatomically viable limb reach from parent joint
                        if dx > max(48, torso_width * 0.48) or dy < -10 or dy > 95:
                            return geo_pt
                        if conf >= 0.50:
                            ai_w = 0.80
                        elif conf >= 0.30:
                            ai_w = 0.65
                        else:
                            ai_w = 0.40
                        return (
                            int(np.clip(round((1.0 - ai_w) * geo_pt[0] + ai_w * ap[0]), 0, mw - 1)),
                            int(np.clip(round((1.0 - ai_w) * geo_pt[1] + ai_w * ap[1]), 0, mh - 1)),
                        )

                    hind_paw_pt = _blend_paw(hind_paw_pt, "hind_paw_pt", hip_pt)
                    fore_paw_pt = _blend_paw(fore_paw_pt, "fore_paw_pt", shoulder_pt)
                    if tail_chain:
                        tail_chain[-1] = tail_base

        knee_offset = int(-6 * move_dir)
        elbow_offset = int(-4 * move_dir)
        hind_knee_pt = (
            int(np.clip(round(0.52 * hip_pt[0] + 0.48 * hind_paw_pt[0] + knee_offset), 0, mw - 1)),
            int(np.clip(round(0.45 * hip_pt[1] + 0.55 * hind_paw_pt[1]), 0, mh - 1)),
        )
        fore_elbow_pt = (
            int(np.clip(round(0.52 * shoulder_pt[0] + 0.48 * fore_paw_pt[0] + elbow_offset), 0, mw - 1)),
            int(np.clip(round(0.45 * shoulder_pt[1] + 0.55 * fore_paw_pt[1]), 0, mh - 1)),
        )

        spine_chain = [tail_base, hip_pt, spine_mid, shoulder_pt, head_pt, nose_pt]

        head_pitch_down = bool(snout_pitched_down)
        if nose_pt[1] - shoulder_pt[1] >= 8 and head_pt[1] - spine_mid[1] >= 6:
            head_pitch_down = True

        return {
            "torso_left_x": int(torso_left_x),
            "torso_right_x": int(torso_right_x),
            "torso_width": int(torso_width),
            "torso_cx": float(torso_cx),
            "torso_cy": float(torso_cy),
            "move_dir": float(move_dir),
            "tail_tip": tail_tip,
            "tail_base": tail_base,
            "tail_chain": tail_chain,
            "hip_pt": hip_pt,
            "spine_mid": spine_mid,
            "shoulder_pt": shoulder_pt,
            "head_pt": head_pt,
            "nose_pt": nose_pt,
            "hind_knee_pt": hind_knee_pt,
            "hind_paw_pt": hind_paw_pt,
            "fore_elbow_pt": fore_elbow_pt,
            "fore_paw_pt": fore_paw_pt,
            "spine_chain": spine_chain,
            "head_pitch_down": bool(head_pitch_down),
        }

    @staticmethod
    def _draw_rodent_skeleton(disp, anat, offset_x=0, offset_y=0):
        if anat is None:
            return
        ox, oy = int(offset_x), int(offset_y)

        def sh(pt):
            return (int(pt[0]) + ox, int(pt[1]) + oy)

        t_chain = anat.get("tail_chain")
        if t_chain and len(t_chain) >= 2:
            t_pts = [sh(pt) for pt in t_chain]
            for i_t in range(len(t_pts) - 1):
                if t_pts[i_t] != t_pts[i_t + 1]:
                    cv2.line(disp, t_pts[i_t], t_pts[i_t + 1], (175, 180, 190), 2, cv2.LINE_AA)
            for pt_t in t_pts[:-1]:
                cv2.circle(disp, pt_t, 3, (165, 170, 180), -1, cv2.LINE_AA)

        if "hip_pt" in anat and "hind_paw_pt" in anat:
            p_hip, p_hpaw = sh(anat["hip_pt"]), sh(anat["hind_paw_pt"])
            if "hind_knee_pt" in anat:
                p_hknee = sh(anat["hind_knee_pt"])
                cv2.line(disp, p_hip, p_hknee, (0, 140, 255), 2, cv2.LINE_AA)
                cv2.line(disp, p_hknee, p_hpaw, (0, 140, 255), 2, cv2.LINE_AA)
                cv2.circle(disp, p_hknee, 3, (0, 165, 255), -1, cv2.LINE_AA)
            else:
                cv2.line(disp, p_hip, p_hpaw, (0, 140, 255), 2, cv2.LINE_AA)
            cv2.circle(disp, p_hpaw, 4, (0, 100, 255), -1, cv2.LINE_AA)
            cv2.circle(disp, p_hpaw, 4, (20, 20, 20), 1, cv2.LINE_AA)

        if "shoulder_pt" in anat and "fore_paw_pt" in anat:
            p_sh, p_fpaw = sh(anat["shoulder_pt"]), sh(anat["fore_paw_pt"])
            if "fore_elbow_pt" in anat:
                p_felb = sh(anat["fore_elbow_pt"])
                cv2.line(disp, p_sh, p_felb, (80, 255, 160), 2, cv2.LINE_AA)
                cv2.line(disp, p_felb, p_fpaw, (80, 255, 160), 2, cv2.LINE_AA)
                cv2.circle(disp, p_felb, 3, (80, 255, 160), -1, cv2.LINE_AA)
            else:
                cv2.line(disp, p_sh, p_fpaw, (80, 255, 160), 2, cv2.LINE_AA)
            cv2.circle(disp, p_fpaw, 4, (0, 230, 140), -1, cv2.LINE_AA)
            cv2.circle(disp, p_fpaw, 4, (20, 20, 20), 1, cv2.LINE_AA)

        chain = anat.get("spine_chain")
        if not chain:
            chain = [
                anat.get("tail_base", (0, 0)),
                anat.get("hip_pt", (0, 0)),
                anat.get("shoulder_pt", (0, 0)),
                anat.get("nose_pt", (0, 0)),
            ]
        pts_global = [sh(pt) for pt in chain]
        for i_p in range(len(pts_global) - 1):
            if pts_global[i_p] == pts_global[i_p + 1]:
                continue
            cv2.line(disp, pts_global[i_p], pts_global[i_p + 1], (255, 225, 0), 2, cv2.LINE_AA)

        joint_styles = [
            ("tail_base", (200, 200, 200), 4),
            ("hip_pt", (0, 165, 255), 5),
            ("spine_mid", (255, 200, 0), 4),
            ("shoulder_pt", (0, 255, 255), 5),
            ("head_pt", (255, 120, 255), 4),
            ("nose_pt", (255, 0, 255), 5),
        ]
        for j_key, j_col, j_rad in joint_styles:
            if j_key in anat:
                pt_g = sh(anat[j_key])
                cv2.circle(disp, pt_g, j_rad, j_col, -1, cv2.LINE_AA)
                cv2.circle(disp, pt_g, j_rad, (20, 20, 20), 1, cv2.LINE_AA)

    def _anatomical_dip_mask(
        self, mouse_mask, fault_y_or_curve, bbox, previous_bbox, inv_ladder_mask, anatomy=None
    ):
        mh, mw = mouse_mask.shape[:2]
        if isinstance(fault_y_or_curve, np.ndarray) and fault_y_or_curve.ndim == 1:
            fault_curve = np.clip(fault_y_or_curve[:mw], 0, mh - 1).astype(np.int32)
        else:
            fault_curve = np.full(mw, int(fault_y_or_curve), dtype=np.int32)

        if anatomy is None:
            anatomy = self._extract_rodent_anatomy(mouse_mask, fault_curve, bbox, previous_bbox)
        if anatomy is None:
            return mouse_mask

        t_left = anatomy["torso_left_x"]
        t_right = anatomy["torso_right_x"]
        move_dir = anatomy["move_dir"]

        if move_dir >= 0:
            active_x1 = max(0, t_left - 4)
            active_x2 = min(mw, t_right + 12)
        else:
            active_x1 = max(0, t_left - 12)
            active_x2 = min(mw, t_right + 4)

        spotlight = np.zeros_like(mouse_mask)
        if active_x2 > active_x1:
            spotlight[:, active_x1:active_x2] = 255

        rows = np.arange(mh, dtype=np.int32)[:, None]
        below_fault = (rows >= fault_curve[None, :]).astype(np.uint8) * 255
        paw_zone = cv2.bitwise_and(mouse_mask, cv2.bitwise_and(spotlight, below_fault))

        gated_mask = cv2.bitwise_and(
            mouse_mask, cv2.bitwise_or(cv2.bitwise_not(below_fault), paw_zone)
        )
        return gated_mask

    def _check_real_dip_below_line(
        self, final_mouse_mask, fault_y_or_curve, crop=None, bbox=None,
        previous_bbox=None, inv_ladder_mask=None, move_dir=1.0, return_meta=False,
        skin_map=None, valid_x_bounds=None, base_gray=None
    ):
        mh, mw = final_mouse_mask.shape[:2]
        if isinstance(fault_y_or_curve, np.ndarray) and fault_y_or_curve.ndim == 1:
            fault_curve = np.clip(fault_y_or_curve[:mw], 0, mh - 1).astype(np.int32)
        else:
            fault_curve = np.full(mw, int(fault_y_or_curve), dtype=np.int32)

        if skin_map is None and crop is not None:
            skin_map = self._compute_skin_chromaticity(crop)

        anatomy = self._extract_rodent_anatomy(
            final_mouse_mask, fault_curve, bbox, previous_bbox=previous_bbox,
            move_dir=move_dir, crop=crop, skin_map=skin_map
        )
        if crop is not None and bbox is not None:
            gated_mouse_mask = self._anatomical_dip_mask(
                final_mouse_mask, fault_curve, bbox, previous_bbox, inv_ladder_mask, anatomy=anatomy
            )
        else:
            gated_mouse_mask = final_mouse_mask

        row_grid = np.arange(mh)[:, None]
        below_mask = (row_grid >= fault_curve[None, :mw]).astype(np.uint8) * 255
        if valid_x_bounds is not None:
            vx1, vx2 = max(0, int(valid_x_bounds[0])), min(mw, int(valid_x_bounds[1]))
            if vx1 > 0:
                below_mask[:, :vx1] = 0
            if vx2 < mw:
                below_mask[:, vx2:] = 0
        below_zone = cv2.bitwise_and(gated_mouse_mask, below_mask)

        empty_meta = {
            "dlc_part": "MELLSŐ LÁB (Lábhiba)",
            "dlc_code": "PAW",
            "rel_pos_norm": 0.5,
            "paw_skin_score": 0.0,
            "head_pitch_down": False,
            "anatomy": anatomy,
        }
        if cv2.countNonZero(below_zone) < 12:
            if return_meta:
                return False, 0, 0, 1.0, 0.0, empty_meta
            return False, 0, 0, 1.0, 0.0

        gray_eff = None
        crop_g = None
        if crop is not None:
            crop_g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
            if skin_map is not None:
                gray_eff = np.clip(crop_g.astype(np.float32) - 1.8 * skin_map, 0, 255).astype(np.uint8)
            else:
                gray_eff = crop_g

        sub_contours, _ = cv2.findContours(below_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_candidate = None
        best_priority_score = float("-inf")

        t_left = anatomy["torso_left_x"] if anatomy else (bbox[0] if bbox else 0)
        t_width = max(22.0, float(anatomy["torso_width"] if anatomy else (bbox[2] if bbox else 60)))
        eff_dir = anatomy["move_dir"] if anatomy else move_dir
        head_pitch = anatomy["head_pitch_down"] if anatomy else False

        for sc in sub_contours:
            c_area = cv2.contourArea(sc)
            if c_area < 14:
                continue
            sx, sy, sw, sh = cv2.boundingRect(sc)
            if sw > sh * 2.2:
                continue

            pts = sc.reshape(-1, 2)
            xs = np.clip(pts[:, 0], 0, mw - 1)
            ys = pts[:, 1]
            depths = ys - fault_curve[xs]
            max_idx = int(np.argmax(depths))
            depth_val = int(depths[max_idx])
            if depth_val < 7:
                continue

            dip_x_local = int(xs[max_idx])
            dip_y_local = int(ys[max_idx])

            skin_score = 0.0
            if skin_map is not None:
                patch_skin = skin_map[sy:min(mh, sy + sh), sx:min(mw, sx + sw)]
                if patch_skin.size > 0:
                    skin_score = float(np.percentile(patch_skin, 80))

            if crop_g is not None:
                sub_mask_sc = below_zone[sy:min(mh, sy + sh), sx:min(mw, sx + sw)] > 0
                patch_g = crop_g[sy:min(mh, sy + sh), sx:min(mw, sx + sw)]
                pix_g = patch_g[sub_mask_sc] if np.any(sub_mask_sc) else patch_g.reshape(-1)
                if pix_g.size > 0:
                    p10_g = float(np.percentile(pix_g, 10))
                    p50_g = float(np.percentile(pix_g, 50))
                    if depth_val <= 14 and (p10_g > 78.0 or p50_g > 120.0):
                        continue

                if base_gray is not None and depth_val <= 16:
                    py1, py2 = max(8, sy - 2), min(mh - 8, sy + sh + 2)
                    px1, px2 = max(0, sx - 3), min(mw, sx + sw + 3)
                    if (py2 - py1) >= 4 and (px2 - px1) >= 4:
                        cur_p = crop_g[py1:py2, px1:px2].astype(np.float32)
                        best_rung_mad = 999.0
                        for dy_test in range(-8, 3):
                            by1, by2 = py1 + dy_test, py2 + dy_test
                            if 0 <= by1 and by2 <= mh:
                                bg_p = base_gray[by1:by2, px1:px2].astype(np.float32)
                                mad = float(np.mean(np.abs(cur_p - bg_p)))
                                if mad < best_rung_mad:
                                    best_rung_mad = mad
                        if best_rung_mad < 20.0:
                            continue

            if gray_eff is not None:
                f_y_at_dip = int(fault_curve[dip_x_local])
                cy1, cy2 = max(0, f_y_at_dip - 10), min(mh, f_y_at_dip + 1)
                cx1, cx2 = max(0, dip_x_local - 5), min(mw, dip_x_local + 6)
                if cy2 > cy1 and cx2 > cx1:
                    cross_band = gray_eff[cy1:cy2, cx1:cx2]
                    row_min_g = np.min(cross_band, axis=1)
                    neck_max_g = int(np.max(row_min_g))
                    if neck_max_g > 175:
                        if skin_score < 14.0 or float(np.percentile(row_min_g, 75)) > 170.0:
                            continue

            top_pts_x = xs[ys <= (np.min(ys) + max(2, int(sh * 0.35)))]
            top_w = float(np.max(top_pts_x) - np.min(top_pts_x) + 1) if len(top_pts_x) > 0 else float(sw)
            aspect = max(float(sw), top_w) / max(1.0, float(sh))

            # In Left-to-Right locomotion, anterior (head/forelimb) is strictly towards right (+X)
            rel_pos_norm = float(np.clip((dip_x_local - t_left) / max(1.0, float(t_width)), 0.0, 1.0))

            nose_is_dipping_here = False
            if anatomy is not None and "nose_pt" in anatomy:
                nx, ny = anatomy["nose_pt"]
                if abs(nx - dip_x_local) <= 18 and ny >= int(fault_curve[np.clip(nx, 0, mw - 1)]) - 1:
                    nose_is_dipping_here = True

            if nose_is_dipping_here and rel_pos_norm >= 0.82:
                part_label, part_code = "ORR (Exploráció)", "NOSE"
            else:
                part_label, part_code = DLCAddonManager.classify_dip_features(
                    rel_pos_norm, aspect, float(depth_val), skin_score, head_pitch
                )

            type_bonus = 60.0 if part_code == "PAW" else (10.0 if part_code == "NOSE" else 0.0)
            priority_score = type_bonus + float(depth_val) + 0.15 * skin_score

            if priority_score > best_priority_score:
                best_priority_score = priority_score
                cand_anat = None
                if anatomy is not None:
                    cand_anat = dict(anatomy)
                    if "spine_chain" in anatomy and anatomy["spine_chain"]:
                        cand_anat["spine_chain"] = list(anatomy["spine_chain"])
                    dip_pt_local = (int(dip_x_local), int(dip_y_local))
                    if part_code == "NOSE":
                        cand_anat["nose_pt"] = dip_pt_local
                        if cand_anat.get("spine_chain"):
                            cand_anat["spine_chain"][-1] = dip_pt_local
                    elif "MELLSŐ" in part_label:
                        cand_anat["fore_paw_pt"] = dip_pt_local
                        sh_pt = cand_anat.get("shoulder_pt", dip_pt_local)
                        cand_anat["fore_elbow_pt"] = (
                            int(round(0.52 * sh_pt[0] + 0.48 * dip_pt_local[0] - 4 * eff_dir)),
                            int(round(0.45 * sh_pt[1] + 0.55 * dip_pt_local[1])),
                        )
                    elif "HÁTSÓ" in part_label:
                        cand_anat["hind_paw_pt"] = dip_pt_local
                        hp_pt = cand_anat.get("hip_pt", dip_pt_local)
                        cand_anat["hind_knee_pt"] = (
                            int(round(0.52 * hp_pt[0] + 0.48 * dip_pt_local[0] - 6 * eff_dir)),
                            int(round(0.45 * hp_pt[1] + 0.55 * dip_pt_local[1])),
                        )
                    elif part_code == "HIND_TAIL":
                        cand_anat["tail_base"] = dip_pt_local

                meta = {
                    "dlc_part": part_label,
                    "dlc_code": part_code,
                    "rel_pos_norm": float(rel_pos_norm),
                    "paw_skin_score": float(skin_score),
                    "head_pitch_down": bool(head_pitch or nose_is_dipping_here),
                    "torso_left_x": int(t_left),
                    "torso_width": int(t_width),
                    "move_dir": float(eff_dir),
                    "anatomy": cand_anat,
                }
                best_candidate = (True, dip_x_local, dip_y_local, aspect, float(depth_val), meta)

        if best_candidate is None:
            if return_meta:
                return False, 0, 0, 1.0, 0.0, empty_meta
            return False, 0, 0, 1.0, 0.0

        if return_meta:
            return best_candidate
        return best_candidate[:5]

    def _generate_heatmap_image(
        self, base_frame, trajectory_pts, valid_dips, title_text,
        blend_alpha=0.48, draw_dip_circles_red=False
    ):
        h, w = base_frame.shape[:2]
        acc = np.zeros((h, w), dtype=np.float32)

        if (
            trajectory_pts
            and isinstance(trajectory_pts[0], (tuple, list))
            and len(trajectory_pts[0]) >= 3
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
                x0, y0, t0 = traj[i - 1][:3]
                x1, y1, t1 = traj[i][:3]
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

        v_ref = max(float(np.percentile(all_positive_speeds, 90)), 15.0) if all_positive_speeds else 100.0

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
        cv2.rectangle(result, (leg_x - 10, 12), (w - 15, 52), (15, 23, 42), -1)
        cv2.putText(result, "Path:", (leg_x, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(result, "SLOW (Red)", (leg_x + 60, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 50, 255), 2)
        cv2.putText(result, "->", (leg_x + 165, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1)
        cv2.putText(result, "FAST (Green)", (leg_x + 195, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 255, 50), 2)

        return result

    def _find_best_mouse_preview_frame(self, cap, base_gray, rx, ry, rw, rh, total_frames):
        if total_frames <= 5:
            return 0
        sample_indices = np.linspace(int(total_frames * 0.05), int(total_frames * 0.90), 24, dtype=int)
        best_idx = min(690, total_frames - 1)
        best_score = -1.0

        body_y1 = int(rh * 0.12)
        body_y2 = int(rh * 0.65)
        mid_x1 = int(rw * 0.18)
        mid_x2 = int(rw * 0.80)

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            r, f = cap.read()
            if not r or f is None:
                continue
            crop = f[ry:ry + rh, rx:rx + rw]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
            sub_bg = base_gray[body_y1:body_y2, mid_x1:mid_x2]
            sub_g = gray[body_y1:body_y2, mid_x1:mid_x2]
            diff = cv2.subtract(sub_bg, sub_g)
            mask = (diff > 22) & (sub_g < 115)
            cnt = int(np.count_nonzero(mask))
            if 450 < cnt < (sub_g.size * 0.50):
                score = float(cnt) * float(np.mean(diff[mask]) + 15.0)
                if score > best_score:
                    best_score = score
                    best_idx = int(idx)
        return best_idx

    def setup_and_run_parallel(self):
        first_video = self.video_data[0]["path"]
        cap = open_video_accelerated(first_video, use_hw=self.var_use_gpu.get())
        if not cap.isOpened():
            messagebox.showerror("Error", "Could not open the first video!")
            self.reset_ui()
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            cap.release()
            messagebox.showerror("Error", "Could not read first video frame!")
            self.reset_ui()
            return

        frame_h, frame_w = first_frame.shape[:2]
        start_preview_frame = None

        if self.var_auto_calib.get():
            try:
                calib = self.auto_engine.auto_calibrate_from_video(cap, num_bg_samples=28)
                rx, ry, rw, rh = calib["rx"], calib["ry"], calib["rw"], calib["rh"]
                left_gate_x, right_gate_x = calib["left_gate_x"], calib["right_gate_x"]
                self.calib_dark_thresh = calib["calib_dark_thresh"]
                self.calib_diff_thresh = calib["calib_diff_thresh"]
                self.calib_ladder_thresh = calib["calib_ladder_thresh"]
                self.calib_fault_Ratio = calib["calib_fault_Ratio"]
                start_preview_frame = calib.get("best_preview_frame")
            except Exception as e:
                self.log(f"⚠ Auto-calib fallback ({e})")
                rx, ry, rw, rh = int(frame_w * 0.05), int(frame_h * 0.35), int(frame_w * 0.90), int(frame_h * 0.30)
                left_gate_x, right_gate_x = int(rx + rw * 0.10), int(rx + rw * 0.86)
        else:
            rx, ry, rw, rh = int(frame_w * 0.05), int(frame_h * 0.35), int(frame_w * 0.90), int(frame_h * 0.30)
            left_gate_x, right_gate_x = int(rx + rw * 0.10), int(rx + rw * 0.86)

        base_gray = self._compute_clean_background(cap, rx, ry, rw, rh, num_samples=28)
        if base_gray is None:
            cap.release()
            self.reset_ui()
            return

        if start_preview_frame is None:
            start_preview_frame = self._find_best_mouse_preview_frame(cap, base_gray, rx, ry, rw, rh, total_frames)

        win_calib = self.tr("calib_win_title")
        cv2.namedWindow(win_calib, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_calib, min(1180, frame_w), min(820, frame_h + 120))

        vp_calib = OpenCVZoomPanViewport(frame_w, frame_h)

        def on_trackbar_change(val):
            vp_calib.dirty = True

        tb_frame = self.tr("calib_tb_frame")
        tb_dark = self.tr("calib_tb_dark")
        tb_diff = self.tr("calib_tb_diff")
        tb_ladder = self.tr("calib_tb_ladder")
        tb_fault = self.tr("calib_tb_fault")

        cv2.createTrackbar(tb_frame, win_calib, int(start_preview_frame), max(1, total_frames - 1), on_trackbar_change)
        cv2.createTrackbar(tb_dark, win_calib, self.calib_dark_thresh, 220, on_trackbar_change)
        cv2.createTrackbar(tb_diff, win_calib, self.calib_diff_thresh, 100, on_trackbar_change)
        cv2.createTrackbar(tb_ladder, win_calib, self.calib_ladder_thresh, 200, on_trackbar_change)
        cv2.createTrackbar(tb_fault, win_calib, self.calib_fault_Ratio, 96, on_trackbar_change)

        def calib_mouse_cb(event, x, y, flags, param):
            nonlocal left_gate_x, right_gate_x
            if vp_calib.handle_mouse(event, x, y, flags):
                return
            if event == cv2.EVENT_LBUTTONDOWN:
                ix, _ = vp_calib.screen_to_image(x, y)
                if abs(ix - left_gate_x) <= abs(ix - right_gate_x):
                    left_gate_x = int(np.clip(ix, rx + 5, right_gate_x - 40))
                else:
                    right_gate_x = int(np.clip(ix, left_gate_x + 40, rx + rw - 5))
                vp_calib.dirty = True

        cv2.setMouseCallback(win_calib, calib_mouse_cb)

        last_track_frame = -1
        current_calib_frame = first_frame.copy()
        cached_disp = first_frame.copy()
        last_params = None

        while True:
            # Service Tkinter event loop to prevent OS application hang alerts
            try:
                self.root.update_idletasks()
                self.root.update()
            except Exception:
                pass

            if not is_window_open(win_calib):
                close_opencv_windows()
                cap.release()
                self.reset_ui()
                return

            f_idx = max(0, cv2.getTrackbarPos(tb_frame, win_calib))
            dark_t = max(50, cv2.getTrackbarPos(tb_dark, win_calib))
            diff_t = max(8, cv2.getTrackbarPos(tb_diff, win_calib))
            ladder_t = max(30, cv2.getTrackbarPos(tb_ladder, win_calib))
            fault_pct = max(25, cv2.getTrackbarPos(tb_fault, win_calib))

            curr_params = (f_idx, dark_t, diff_t, ladder_t, fault_pct, left_gate_x, right_gate_x)

            if curr_params != last_params:
                if f_idx != last_track_frame:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                    r, f_read = cap.read()
                    if r and f_read is not None:
                        current_calib_frame = f_read
                    last_track_frame = f_idx

                disp = current_calib_frame.copy()
                crop = disp[ry:ry + rh, rx:rx + rw]

                fault_y_local = int(rh * (fault_pct / 100.0))
                fault_y_global = ry + fault_y_local

                ladder_mask = self._create_ladder_mask(base_gray, ladder_t, fault_y_local=fault_y_local)
                inv_ladder_mask = cv2.bitwise_not(ladder_mask)
                detected, mask, bbox, skin_map = self._detect_mouse_on_crop(
                    crop, base_gray, inv_ladder_mask, rw, rh, dark_t, diff_t,
                    fault_y_local=fault_y_local, return_skin=True
                )

                overlay = np.zeros_like(crop)
                overlay[ladder_mask == 255] = (255, 110, 0)
                if mask is not None:
                    overlay[mask == 255] = (0, 255, 0)
                disp[ry:ry + rh, rx:rx + rw] = cv2.addWeighted(crop, 0.65, overlay, 0.35, 0)

                cv2.line(disp, (rx, fault_y_global), (rx + rw, fault_y_global), (0, 0, 255), 2)

                if detected and bbox is not None and mask is not None:
                    bx, by, bw, bh = bbox
                    cv2.rectangle(disp, (rx + bx, ry + by), (rx + bx + bw, ry + by + bh), (0, 255, 0), 2)

                    is_dip, dip_x_loc, dip_y_loc, _, _, dip_meta = self._check_real_dip_below_line(
                        mask, fault_y_local, crop=crop, bbox=bbox, inv_ladder_mask=inv_ladder_mask,
                        return_meta=True, skin_map=skin_map
                    )
                    anat = dip_meta.get("anatomy") if dip_meta else None
                    if anat is not None:
                        self._draw_rodent_skeleton(disp, anat, offset_x=rx, offset_y=ry)

                    if is_dip:
                        d_code = dip_meta.get("dlc_code", "PAW")
                        d_part = dip_meta.get("dlc_part", "MANCS")
                        dip_col = (0, 0, 255) if d_code == "PAW" else ((255, 220, 0) if d_code == "NOSE" else (180, 105, 255))
                        cv2.circle(disp, (rx + dip_x_loc, ry + dip_y_loc), 12, dip_col, 3)
                        cv2.putText(
                            disp, d_part, (rx + dip_x_loc - 35, ry + dip_y_loc + 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, dip_col, 2
                        )

                cv2.rectangle(disp, (rx, ry), (rx + rw, ry + rh), (255, 140, 0), 2)
                cv2.line(disp, (left_gate_x, ry), (left_gate_x, ry + rh), (50, 255, 50), 2)
                cv2.line(disp, (right_gate_x, ry), (right_gate_x, ry + rh), (50, 50, 255), 2)
                cv2.putText(
                    disp, self.tr("calib_overlay_hint"),
                    (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2
                )

                cached_disp = disp
                last_params = curr_params
                vp_calib.dirty = True

            if vp_calib.dirty:
                cv2.imshow(win_calib, vp_calib.render(cached_disp))
                vp_calib.dirty = False

            key = cv2.waitKey(40) & 0xFF
            if key in (13, 32):
                self.calib_dark_thresh = dark_t
                self.calib_diff_thresh = diff_t
                self.calib_ladder_thresh = ladder_t
                self.calib_fault_Ratio = fault_pct
                break
            elif key in (ord('r'), ord('R')):
                vp_calib.reset()
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
            dip_cooldown_sec = float(self.var_cooldown.get())
        except ValueError:
            dip_cooldown_sec = 0.50

        try:
            dip_min_dist_px = int(self.var_min_dist.get())
        except ValueError:
            dip_min_dist_px = 30

        try:
            gate_dist_cm = max(0.1, float(self.var_gate_cm.get()))
        except ValueError:
            gate_dist_cm = 60.0

        try:
            frame_stride = max(1, int(self.var_stride.get()))
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
            self.var_use_kalman.get(),
            self.var_bidirectional.get(),
            self.var_protocol_runs.get(),
            self.var_lock_lr_direction.get()
        )

        try:
            max_workers = int(self.var_threads.get())
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

        target_runs = 3
        lock_lr = True
        if len(roi_data) >= 22:
            (rx, ry, rw, rh, left_gate_x, right_gate_x, dark_t, diff_t,
             ladder_t, fault_pct, z_active, kin_active,
             dip_cooldown_sec, dip_min_dist_px, gate_dist_cm, px_per_cm,
             frame_stride, use_gpu, use_kalman, bidirectional,
             proto_runs_cfg, lock_lr) = roi_data[:22]
            try:
                target_runs = int(str(proto_runs_cfg).split()[0])
            except Exception:
                target_runs = 3
        elif len(roi_data) >= 20:
            (rx, ry, rw, rh, left_gate_x, right_gate_x, dark_t, diff_t,
             ladder_t, fault_pct, z_active, kin_active,
             dip_cooldown_sec, dip_min_dist_px, gate_dist_cm, px_per_cm,
             frame_stride, use_gpu, use_kalman, bidirectional) = roi_data[:20]
        else:
            (rx, ry, rw, rh, left_gate_x, right_gate_x, dark_t, diff_t,
             ladder_t, fault_pct, z_active, kin_active,
             dip_cooldown_sec, dip_min_dist_px, gate_dist_cm, px_per_cm,
             frame_stride, use_gpu, use_kalman) = roi_data[:19]
            bidirectional = False

        gpu_active = bool(use_gpu and self.gpu_available)
        try:
            cv2.ocl.setUseOpenCL(gpu_active)
        except Exception:
            pass

        try:
            cpu_cores = os.cpu_count() or 4
            cv2.setNumThreads(max(1, cpu_cores // max(1, min(max_workers, total_videos))))
        except Exception:
            pass

        try:
            use_yolo_fusion = bool(self.var_yolo_fusion.get())
        except (RuntimeError, tk.TclError):
            use_yolo_fusion = True

        gpu_tag = f"⚡ GPU: {self.gpu_device_name} (Active)" if gpu_active else "GPU: Inactive (CPU Mode)"
        self.log(
            f"\n🚀 [Workstation Engine Started] Videos: {total_videos} | Workers: {max_workers} | "
            f"Stride: {frame_stride} | Protocol Target: {target_runs} Runs (L->R) | "
            f"Scale: {px_per_cm:.2f} px/cm | {gpu_tag}"
        )

        def process_single_video(item):
            if not self.is_running:
                return

            uid = item["uid"]
            self.hybrid_locator.reset_stream(uid)
            video_path = item["path"]
            video_name = item["name"]
            animal_id = item["id"]

            self.update_row_status(uid, "Init Background...")

            safe_id = "".join(c for c in animal_id if c.isalnum() or c in ("-", "_")) or "1"
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
            if not ret or first_frame is None:
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
            base_gray = self._compute_clean_background(cap, v_rx, v_ry, v_rw, v_rh, num_samples=28)
            if base_gray is None:
                cap.release()
                self.update_row_status(uid, "Error (BG)")
                self.increment_progress(total_videos)
                return

            ladder_mask = self._create_ladder_mask(base_gray, ladder_t, fault_y_local=fault_y_local)
            inv_ladder_mask = cv2.bitwise_not(ladder_mask)
            base_smooth_static = cv2.GaussianBlur(base_gray, (3, 3), 0)

            kalman = MouseKalmanTracker() if use_kalman else None
            rung_pts = self.auto_engine.extract_rung_keypoints(base_gray, max(10, fault_y_local - 12), ladder_t)
            elastic_tracker = ElasticLadderTracker(base_gray, inv_ladder_mask, rung_pts, fault_y_local) if use_kalman else None
            last_bbox_local = None
            bbox_miss_count = 0

            u_base_smooth = None
            u_inv_ladder = None

            stride_pad = 35 * (frame_stride - 1)
            left_gate_min_loc = max(0, (left_gate_x - 130) - v_rx)
            left_gate_max_loc = min(v_rw, (left_gate_x + 220 + stride_pad) - v_rx)

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

            # Initialize 3-Run Protocol Lifecycle
            set_state("WAIT_FOR_RUN_1", 0.0, "Waiting for Run #1 at Left Gate...")

            run_count = 0
            start_time = 0.0
            last_seen_time = 0.0
            last_run_end_sec = -999.0
            run_direction = 1.0  # In L->R protocol, direction is strictly Forward (+1.0)

            dip_events = []
            in_any_dip_event = False
            last_any_dip_sec = -999.0

            freeze_events = []
            micro_hesitation_events = []
            current_still_sec = 0.0
            in_freeze_event = False
            current_freeze_start_sec = 0.0
            current_freeze_x = 0
            current_freeze_y_top = 0
            prev_mouse_x = None

            trajectory = []
            session_trajectory = []
            zone_moving_times = [0.0, 0.0, 0.0]
            video_runs_list = []

            # Memory-safe reader buffer
            reader = AsyncVideoReader(cap, v_rx, v_ry, v_rw, v_rh, stride=frame_stride, queue_size=16)

            try:
                while self.is_running:
                    item_pack = reader.read()
                    if item_pack is None:
                        break

                    frame_idx, frame, crop = item_pack
                    current_sec = frame_idx / fps
                    dt = frame_stride / fps

                    # Gate pre-check: quick spatial check when waiting for a run to enter Left Gate
                    if state.startswith("WAIT_FOR_RUN_"):
                        if elastic_tracker is not None and (frame_idx % 8 == 0):
                            crop_gray_pre = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                            elastic_tracker.update(crop_gray_pre, mouse_bbox_local=None, force_update=True)
                        ref_bg_gate = elastic_tracker.cached_warped_bg if elastic_tracker is not None else base_gray
                        ref_inv_gate = elastic_tracker.cached_warped_inv_ladder if elastic_tracker is not None else inv_ladder_mask

                        left_has_motion = self._quick_check_start_gate(
                            crop, ref_bg_gate, ref_inv_gate, left_gate_min_loc, left_gate_max_loc, dark_t, diff_t
                        )
                        if not left_has_motion:
                            continue

                    # Elastic rung tracking update
                    if elastic_tracker is not None:
                        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        active_base_gray, active_inv_ladder, active_fault_target = elastic_tracker.update(
                            crop_gray, mouse_bbox_local=(last_bbox_local if state.startswith("RUNNING_") else None)
                        )
                        active_base_smooth = (
                            base_smooth_static if active_base_gray is base_gray
                            else cv2.GaussianBlur(active_base_gray, (3, 3), 0)
                        )
                        active_fault_scalar = int(np.median(active_fault_target))
                    else:
                        active_base_gray = base_gray
                        active_inv_ladder = inv_ladder_mask
                        active_fault_target = fault_y_local
                        active_base_smooth = base_smooth_static
                        active_fault_scalar = fault_y_local

                    # Stationary rescue bbox (only during active run)
                    previous_bbox_local = last_bbox_local if state.startswith("RUNNING_") else None

                    mouse_detected, final_mouse_mask, bbox, skin_idx_map = self._detect_mouse_on_crop(
                        crop, active_base_gray, active_inv_ladder, v_rw, v_rh, dark_t, diff_t,
                        fault_y_local=active_fault_scalar,
                        use_umat=gpu_active, u_base_smooth=u_base_smooth, u_inv_ladder=u_inv_ladder,
                        mog2_subtractor=None, stream_id=uid, frame_idx=frame_idx,
                        ai_max_age=max(12, frame_stride * 12), previous_bbox=previous_bbox_local,
                        base_smooth_cached=active_base_smooth, return_skin=True, use_yolo=use_yolo_fusion
                    )

                    mask_area = cv2.countNonZero(final_mouse_mask) if (mouse_detected and final_mouse_mask is not None) else 0

                    if mouse_detected and mask_area >= 1200:
                        last_bbox_local = bbox
                        bbox_miss_count = 0
                    else:
                        bbox_miss_count += 1
                        if bbox_miss_count > max(4, frame_stride * 4):
                            last_bbox_local = None

                    mouse_x_global = None
                    mouse_y_center_global = None
                    mouse_y_top_global = v_ry

                    if mouse_detected and bbox is not None and mask_area >= 1200:
                        x_c, y_c, w_c, h_c = bbox
                        torso_top_lim = max(12, min(v_rh, int(active_fault_scalar) - 6))
                        upper_slice = final_mouse_mask[:torso_top_lim, x_c:min(v_rw, x_c + w_c)]
                        col_h = np.sum(upper_slice > 0, axis=0)
                        max_h_c = int(np.max(col_h)) if col_h.size > 0 else 0
                        thick_c = np.where(col_h >= max(8, int(max_h_c * 0.34)))[0]
                        if len(thick_c) >= 8:
                            t_c0, t_c1 = int(thick_c[0]), int(thick_c[-1]) + 1
                            ys_t, xs_t = np.where(upper_slice[:, t_c0:t_c1] > 0)
                            if len(xs_t) > 0:
                                raw_gx = int(round(v_rx + x_c + t_c0 + float(np.mean(xs_t))))
                                raw_gy = int(round(v_ry + float(np.mean(ys_t))))
                            else:
                                raw_gx = v_rx + x_c + (t_c0 + t_c1) // 2
                                raw_gy = v_ry + y_c + (h_c // 2)
                        else:
                            raw_gx = v_rx + x_c + (w_c // 2)
                            raw_gy = v_ry + y_c + (h_c // 2)

                        if kalman is not None and state.startswith("RUNNING_"):
                            mouse_x_global, mouse_y_center_global = kalman.update(raw_gx, raw_gy)
                        else:
                            mouse_x_global, mouse_y_center_global = raw_gx, raw_gy
                        mouse_y_top_global = v_ry + y_c

                        session_trajectory.append((mouse_x_global, mouse_y_center_global, current_sec))

                    # ──────────────────────────────────────────────────────────
                    # 3-RUN PROTOCOL LIFECYCLE (LEFT -> RIGHT ONLY)
                    # ──────────────────────────────────────────────────────────
                    if state.startswith("WAIT_FOR_RUN_"):
                        target_run_num = int(state.split("_")[-1])
                        # Entry condition: Genuine rodent mass at Left Gate & at least 1.5s since last run
                        if (current_sec - last_run_end_sec >= 1.5) and mouse_detected and mouse_x_global is not None:
                            if mask_area >= 2000 and (left_gate_x - 120 <= mouse_x_global <= left_gate_x + 220 + stride_pad):
                                run_count = target_run_num
                                run_direction = 1.0  # Anchored Left to Right
                                if kalman is not None:
                                    kalman.reset(mouse_x_global, mouse_y_center_global)
                                set_state(f"RUNNING_{run_count}", current_sec, f"Run #{run_count} (L->R) started...")
                                start_time = current_sec
                                last_seen_time = current_sec
                                current_run_roi.fill(255)

                                dip_events = []
                                in_any_dip_event = False
                                last_any_dip_sec = -999.0

                                freeze_events = []
                                micro_hesitation_events = []
                                current_still_sec = 0.0
                                in_freeze_event = False
                                current_freeze_start_sec = current_sec
                                current_freeze_x = mouse_x_global
                                current_freeze_y_top = mouse_y_top_global
                                prev_mouse_x = mouse_x_global

                                trajectory = [(mouse_x_global, mouse_y_center_global, current_sec)]
                                zone_moving_times = [0.0, 0.0, 0.0]

                    elif state.startswith("RUNNING_"):
                        if mouse_detected and mouse_x_global is not None and mask_area >= 1800:
                            step_dt = max(0.0, current_sec - last_seen_time)
                            last_seen_time = current_sec

                            trajectory.append((mouse_x_global, mouse_y_center_global, current_sec))
                            if step_dt < 0.5:
                                if mouse_x_global < z1_boundary:
                                    zone_moving_times[0] += step_dt
                                elif mouse_x_global < z2_boundary:
                                    zone_moving_times[1] += step_dt
                                else:
                                    zone_moving_times[2] += step_dt

                            paint_mask = cv2.morphologyEx(final_mouse_mask, cv2.MORPH_CLOSE, self.kernel_fill)
                            cv2.copyTo(cv2.min(current_run_roi, crop), paint_mask, current_run_roi)

                            valid_ladder_bounds = (
                                max(int(v_rw * 0.030), (left_gate_x - 100) - v_rx),
                                min(int(v_rw * 0.970), (right_gate_x + 100) - v_rx),
                            )
                            # Strict Left-to-Right heading (move_dir=1.0)
                            is_dip, dip_x_loc, dip_y_loc, dip_aspect, dip_depth, dip_meta = self._check_real_dip_below_line(
                                final_mouse_mask, active_fault_target, crop=crop, bbox=bbox,
                                previous_bbox=previous_bbox_local, inv_ladder_mask=active_inv_ladder,
                                move_dir=1.0, return_meta=True, skin_map=skin_idx_map,
                                valid_x_bounds=valid_ladder_bounds, base_gray=active_base_gray
                            )

                            if is_dip:
                                dip_code = dip_meta.get("dlc_code", "PAW")
                                dip_part = dip_meta.get("dlc_part", "MELLSŐ LÁB (Lábhiba)")
                                dip_x_glob = v_rx + dip_x_loc
                                dip_y_glob = v_ry + dip_y_loc

                                body_left_glob = v_rx + bbox[0]
                                body_width_px = max(25, bbox[2])
                                torso_left_glob = v_rx + dip_meta.get("torso_left_x", bbox[0])
                                torso_width_px = max(22, dip_meta.get("torso_width", bbox[2]))

                                eff_cooldown = max(0.32, float(dip_cooldown_sec))
                                eff_min_dist = max(18, int(dip_min_dist_px))
                                peak_score = (
                                    (60.0 if dip_code == "PAW" else (10.0 if dip_code == "NOSE" else 0.0))
                                    + float(dip_depth)
                                    + 0.15 * float(dip_meta.get("paw_skin_score", 0.0))
                                )

                                candidate_event = {
                                    "x": dip_x_glob,
                                    "y": dip_y_glob,
                                    "sec": current_sec,
                                    "dip_aspect": dip_aspect,
                                    "dip_depth": dip_depth,
                                    "body_left_x": body_left_glob,
                                    "body_width": body_width_px,
                                    "torso_left_x": torso_left_glob,
                                    "torso_width": torso_width_px,
                                    "rel_pos_norm": dip_meta.get("rel_pos_norm", 0.5),
                                    "paw_skin_score": dip_meta.get("paw_skin_score", 0.0),
                                    "head_pitch_down": dip_meta.get("head_pitch_down", False),
                                    "move_dir": 1.0,
                                    "anatomy": dip_meta.get("anatomy"),
                                    "roi_offset": (v_rx, v_ry),
                                    "frame_buf": None,
                                    "valid": True,
                                    "save_crop": True,
                                    "dlc_part": dip_part,
                                    "dlc_code": dip_code,
                                    "_peak_score": peak_score,
                                }

                                merge_into_prev = False
                                if dip_events:
                                    prev_ev = dip_events[-1]
                                    dt_prev = current_sec - prev_ev["sec"]
                                    dt_active = current_sec - last_any_dip_sec
                                    dx_prev = abs(dip_x_glob - prev_ev["x"])
                                    if (
                                        in_any_dip_event
                                        or (dt_active < eff_cooldown)
                                        or (dx_prev < max(50, int(eff_min_dist * 1.5)) and dt_prev < max(2.5, eff_cooldown * 4.0))
                                    ):
                                        merge_into_prev = True

                                if merge_into_prev:
                                    in_any_dip_event = True
                                    last_any_dip_sec = current_sec
                                    if peak_score > dip_events[-1].get("_peak_score", -999.0):
                                        candidate_event["frame_buf"] = encode_frame_compressed(frame)
                                        dip_events[-1] = candidate_event
                                else:
                                    in_any_dip_event = True
                                    last_any_dip_sec = current_sec
                                    candidate_event["frame_buf"] = encode_frame_compressed(frame)
                                    dip_events.append(candidate_event)
                            else:
                                in_any_dip_event = False

                            # Stillness & micro-hesitation detector
                            if prev_mouse_x is not None:
                                if abs(mouse_x_global - prev_mouse_x) < (2.5 * frame_stride):
                                    if current_still_sec == 0.0:
                                        current_freeze_start_sec = current_sec
                                        current_freeze_x = mouse_x_global
                                        current_freeze_y_top = mouse_y_top_global
                                    current_still_sec += step_dt

                                    if current_still_sec >= 0.30 and not in_freeze_event:
                                        in_freeze_event = True
                                else:
                                    if in_freeze_event:
                                        f_dur = current_sec - current_freeze_start_sec
                                        freeze_events.append((
                                            current_freeze_start_sec, current_sec, f_dur,
                                            current_freeze_x, current_freeze_y_top
                                        ))
                                    elif 0.08 <= current_still_sec < 0.30:
                                        micro_hesitation_events.append((
                                            current_freeze_start_sec, current_sec, current_still_sec,
                                            current_freeze_x, current_freeze_y_top
                                        ))
                                    current_still_sec = 0.0
                                    in_freeze_event = False
                            prev_mouse_x = mouse_x_global

                            # Check goal arrival at Right Gate
                            mouse_front_edge_x = v_rx + bbox[0] + bbox[2]
                            reached_goal = (mouse_x_global >= right_gate_x - 45) or (mouse_front_edge_x >= right_gate_x + 10)

                            if reached_goal:
                                if in_freeze_event:
                                    f_dur = current_sec - current_freeze_start_sec
                                    freeze_events.append((
                                        current_freeze_start_sec, current_sec, f_dur,
                                        current_freeze_x, current_freeze_y_top
                                    ))
                                    in_freeze_event = False
                                    current_still_sec = 0.0
                                elif 0.08 <= current_still_sec < 0.30:
                                    micro_hesitation_events.append((
                                        current_freeze_start_sec, current_sec, current_still_sec,
                                        current_freeze_x, current_freeze_y_top
                                    ))
                                    current_still_sec = 0.0

                                end_time = current_sec
                                transit_time = end_time - start_time

                                if transit_time > 0.4:
                                    np.minimum(master_roi_canvas, current_run_roi, out=master_roi_canvas)

                                    path_len_px = 0.0
                                    max_speed_px_s = 0.0
                                    step_speeds_cm_s = []
                                    step_dts = []
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
                                            step_speeds_cm_s.append((spd / max(0.01, px_per_cm)))
                                            step_dts.append(step_t)

                                    avg_speed_px_s = (path_len_px / transit_time) if transit_time > 0 else 0.0
                                    path_len_cm = path_len_px / max(0.01, px_per_cm)
                                    avg_speed_cm_s = avg_speed_px_s / max(0.01, px_per_cm)
                                    max_speed_cm_s = max_speed_px_s / max(0.01, px_per_cm)

                                    if len(step_speeds_cm_s) >= 4:
                                        vel_mean = float(np.mean(step_speeds_cm_s))
                                        vel_std = float(np.std(step_speeds_cm_s))
                                        vel_cv = float(vel_std / max(1e-4, vel_mean))
                                    else:
                                        vel_cv = 0.0

                                    if len(step_speeds_cm_s) >= 6:
                                        accels = []
                                        for k in range(1, len(step_speeds_cm_s)):
                                            dt_a = step_dts[k]
                                            if dt_a > 1e-4:
                                                accels.append((step_speeds_cm_s[k] - step_speeds_cm_s[k - 1]) / dt_a)
                                        jerks = []
                                        for k in range(1, len(accels)):
                                            dt_j = step_dts[k]
                                            if dt_j > 1e-4:
                                                jerks.append(abs(accels[k] - accels[k - 1]) / dt_j)
                                        ref_jerk = max(100.0, float(np.mean(step_speeds_cm_s) * 80.0))
                                        mean_jerk = float(np.median(jerks)) if jerks else 0.0
                                        jerk_score = float(np.clip((mean_jerk / ref_jerk) * 35.0, 0.0, 100.0))
                                    else:
                                        jerk_score = 0.0

                                    if len(trajectory) >= 5:
                                        ys_traj = np.array([pt[1] for pt in trajectory], dtype=np.float32)
                                        half_w = min(3, (len(ys_traj) - 1) // 2)
                                        win_k = 2 * half_w + 1
                                        ys_pad = np.pad(ys_traj, (half_w, half_w), mode="edge")
                                        smooth_y = np.convolve(ys_pad, np.ones(win_k, dtype=np.float32) / win_k, mode="valid")
                                        postural_sway_px = float(np.std(ys_traj - smooth_y[:len(ys_traj)]))
                                    else:
                                        postural_sway_px = 0.0

                                    full_clean_canvas = np.full_like(first_frame, 255)
                                    full_clean_canvas[v_ry:v_ry + v_rh, v_rx:v_rx + v_rw] = current_run_roi

                                    video_runs_list.append({
                                        "run_num": run_count,
                                        "direction": "FORWARD",
                                        "start_time": start_time,
                                        "end_time": end_time,
                                        "transit_time": transit_time,
                                        "clean_canvas_buf": encode_frame_compressed(full_clean_canvas),
                                        "dips": list(dip_events),
                                        "freezes": list(freeze_events),
                                        "micro_hesitations": list(micro_hesitation_events),
                                        "vel_cv": vel_cv,
                                        "jerk_score": jerk_score,
                                        "postural_sway_px": postural_sway_px,
                                        "trajectory": list(trajectory),
                                        "zone_times": list(zone_moving_times),
                                        "path_len_px": path_len_px,
                                        "avg_speed_px_s": avg_speed_px_s,
                                        "max_speed_px_s": max_speed_px_s,
                                        "path_len_cm": path_len_cm,
                                        "avg_speed_cm_s": avg_speed_cm_s,
                                        "max_speed_cm_s": max_speed_cm_s
                                    })

                                    paw_cnt_live = sum(1 for d_ev in dip_events if d_ev.get("dlc_code") == "PAW")
                                    nose_cnt_live = sum(1 for d_ev in dip_events if d_ev.get("dlc_code") == "NOSE")
                                    self.log(
                                        f"   ✔ [#{animal_id}] Run #{run_count} (L->R) DONE: "
                                        f"Time={transit_time:.2f}s | PawFaults={paw_cnt_live} | Explorations={nose_cnt_live} | "
                                        f"Speed={avg_speed_cm_s:.1f} cm/s"
                                    )

                                last_run_end_sec = current_sec
                                if run_count >= target_runs:
                                    set_state("SESSION_COMPLETED", current_sec, f"All {target_runs} protocol runs reached!")
                                    break
                                else:
                                    next_target = run_count + 1
                                    set_state(f"WAIT_FOR_RUN_{next_target}", current_sec, f"Run #{run_count} completed. Waiting for Run #{next_target} at Left Gate...")

            finally:
                reader.stop()
                cap.release()
                self.hybrid_locator.reset_stream(uid)

            master_white_canvas = np.full_like(first_frame, 255)
            master_white_canvas[v_ry:v_ry + v_rh, v_rx:v_rx + v_rw] = master_roi_canvas

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
                    "runs": video_runs_list,
                    "session_trajectory": session_trajectory
                })

            self.update_row_status(uid, f"Done ({len(video_runs_list)} runs)")
            self.increment_progress(total_videos)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(process_single_video, video_data))

        if self.is_running and self.pending_results:
            if self.var_dlc_superanimal.get():
                self.dlc_addon.classify_dips_with_superanimal(self.pending_results)
            if self.var_dlc_export_train.get():
                self.dlc_addon.export_training_dataset(
                    self.pending_results, os.path.join(self.output_base_dir, "DLC_Tanitokepek_Export")
                )

        total_dips_found = sum(len(r["dips"]) for res in self.pending_results for r in res["runs"])
        try:
            if self.is_running and self.var_enable_review.get() and total_dips_found > 0:
                self.root.after(0, self.open_review_window)
            else:
                self.root.after(0, self.finalize_and_export_all)
        except (RuntimeError, tk.TclError):
            self.finalize_and_export_all()

    # ==========================================================================
    # INTERACTIVE DIP & POSE INSPECTOR (MODERN SCIENTIFIC THEME)
    # ==========================================================================
    def open_review_window(self):
        P = self.PALETTE
        rev_win = tk.Toplevel(self.root)
        rev_win.title(f"{APP_NAME} — {self.tr('review_title')}")
        rev_win.geometry("1240x820")
        rev_win.configure(bg=P["bg_main"])
        rev_win.transient(self.root)
        rev_win.grab_set()
        rev_win.lift()
        rev_win.focus_force()

        top_banner = tk.Frame(rev_win, bg=P["bg_card"], padx=18, pady=8, highlightthickness=1, highlightbackground=P["border"])
        top_banner.pack(fill="x")
        tk.Label(
            top_banner,
            text=self.tr("review_banner_help"),
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 9)
        ).pack(anchor="w")

        body = tk.Frame(rev_win, bg=P["bg_main"], padx=16, pady=10)
        body.pack(fill="both", expand=True)

        left_outer, left_panel, _, _ = self._create_section_card(
            body, self.tr("events_table_title"), P["blue"], self.tr("badge_events")
        )
        left_outer.pack(side="left", fill="y", padx=(0, 12))

        cols = ("ego", "run", "sec", "part", "valid", "save")
        dip_tree = ttk.Treeview(left_panel, columns=cols, show="headings", height=20, selectmode="browse")
        dip_tree.heading("ego", text=self.tr("col_rev_id"))
        dip_tree.heading("run", text=self.tr("col_rev_run"))
        dip_tree.heading("sec", text=self.tr("col_rev_sec"))
        dip_tree.heading("part", text=self.tr("col_rev_part"))
        dip_tree.heading("valid", text=self.tr("col_rev_valid"))
        dip_tree.heading("save", text=self.tr("col_rev_save"))

        dip_tree.column("ego", width=65, anchor="center")
        dip_tree.column("run", width=60, anchor="center")
        dip_tree.column("sec", width=70, anchor="center")
        dip_tree.column("part", width=170, anchor="center")
        dip_tree.column("valid", width=90, anchor="center")
        dip_tree.column("save", width=70, anchor="center")
        dip_tree.pack(side="left", fill="y")

        sb = ttk.Scrollbar(left_panel, orient="vertical", command=dip_tree.yview)
        sb.pack(side="right", fill="y")
        dip_tree.configure(yscrollcommand=sb.set)

        right_outer, right_panel, _, _ = self._create_section_card(
            body, self.tr("inspector_canvas_title"), P["teal"], self.tr("badge_inspector")
        )
        right_outer.pack(side="left", fill="both", expand=True)

        canvas_view = tk.Canvas(right_panel, bg=P["bg_main"], highlightthickness=0, cursor="crosshair")
        canvas_view.pack(fill="both", expand=True, pady=(0, 8))

        ctrl_box = tk.Frame(right_panel, bg=P["bg_card"])
        ctrl_box.pack(fill="x")

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
                    val_str = self.tr("val_valid") if d["valid"] else self.tr("val_ignored")
                    save_str = self.tr("val_yes") if d["save_crop"] else self.tr("val_no")
                    dip_tree.insert(
                        "", "end", iid=iid,
                        values=(
                            f"#{res['animal_id']}",
                            f"#{r['run_num']}",
                            f"{d['sec']:.2f}s",
                            d.get("dlc_part", "MANCS (Lábhiba)"),
                            val_str,
                            save_str
                        )
                    )

        current_iid = [None]
        photo_ref = [None]

        view_state = {
            "zoom": 1.0,
            "cx": 0.5,
            "cy": 0.5,
            "drag_start": None
        }

        def render_preview(iid=None):
            if iid is None:
                iid = current_iid[0]
            if not iid or iid not in dip_lookup:
                return
            res, r, d = dip_lookup[iid]
            rx, ry, rw, rh, _, _, _, _, _, fault_pct, *_ = res["roi_data"]
            fault_y_glob = ry + int(rh * (fault_pct / 100.0))

            raw_frame = decode_frame_compressed(d["frame_buf"])
            if raw_frame is None:
                return
            disp = raw_frame.copy()
            fh, fw = disp.shape[:2]

            cv2.line(disp, (rx, fault_y_glob), (rx + rw, fault_y_glob), (0, 0, 255), 2)

            anat = d.get("anatomy")
            ox, oy = d.get("roi_offset", (rx, ry))
            if anat is not None:
                self._draw_rodent_skeleton(disp, anat, offset_x=ox, offset_y=oy)

            part_str = d.get("dlc_part", "MANCS (Lábhiba)")
            dx, dy = int(d["x"]), int(d["y"])

            if d["valid"]:
                cv2.circle(disp, (dx, dy), 18, (0, 0, 255), 3)
                status_str = f"VALID ({d['sec']:.2f}s) -> [{part_str}]"
                if d["save_crop"]:
                    status_str += " [SNAPSHOT]"
                cv2.putText(disp, status_str, (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            else:
                cv2.circle(disp, (dx, dy), 18, (128, 128, 128), 2)
                cv2.putText(
                    disp, f"IGNORED ({d['sec']:.2f}s) [{part_str}]",
                    (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (160, 160, 160), 2
                )

            z = view_state["zoom"]
            if z > 1.01:
                vw = max(40.0, fw / z)
                vh = max(30.0, fh / z)
                cx_px = view_state["cx"] * fw
                cy_px = view_state["cy"] * fh
                x1 = int(np.clip(cx_px - vw / 2.0, 0, max(0, fw - vw)))
                y1 = int(np.clip(cy_px - vh / 2.0, 0, max(0, fh - vh)))
                view_state["cx"] = (x1 + vw / 2.0) / float(fw)
                view_state["cy"] = (y1 + vh / 2.0) / float(fh)
                disp = disp[y1:y1 + int(vh), x1:x1 + int(vw)]

            cw = max(480, canvas_view.winfo_width())
            ch = max(320, canvas_view.winfo_height())
            scale = min(cw / float(disp.shape[1]), ch / float(disp.shape[0]))
            tw = max(10, int(disp.shape[1] * scale))
            th = max(10, int(disp.shape[0] * scale))

            resized = cv2.resize(disp, (tw, th), interpolation=cv2.INTER_LINEAR)
            cv2.rectangle(resized, (8, th - 32), (240, th - 8), (18, 22, 28), -1)
            cv2.putText(resized, f"Zoom: {z:.2f}x (Wheel / Drag)", (15, th - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (16, 185, 129), 1)

            ok, buf = cv2.imencode(".ppm", resized)
            if ok:
                photo = tk.PhotoImage(data=buf.tobytes())
                photo_ref[0] = photo
                canvas_view.delete("all")
                canvas_view.create_image(cw // 2, ch // 2, image=photo, anchor="center")

        def on_canvas_wheel(event):
            if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
                factor = 1.25
            else:
                factor = 1.0 / 1.25

            old_z = view_state["zoom"]
            new_z = float(np.clip(old_z * factor, 1.0, 8.0))
            if abs(new_z - old_z) > 1e-3:
                cw = max(1, canvas_view.winfo_width())
                ch = max(1, canvas_view.winfo_height())
                rel_x = (event.x / float(cw)) - 0.5
                rel_y = (event.y / float(ch)) - 0.5
                view_state["cx"] = float(np.clip(view_state["cx"] + rel_x * (1.0 / old_z - 1.0 / new_z), 0.05, 0.95))
                view_state["cy"] = float(np.clip(view_state["cy"] + rel_y * (1.0 / old_z - 1.0 / new_z), 0.05, 0.95))
                view_state["zoom"] = new_z
                render_preview()

        def on_canvas_drag_start(event):
            view_state["drag_start"] = (event.x, event.y, view_state["cx"], view_state["cy"])

        def on_canvas_drag_move(event):
            if view_state["drag_start"] is None or view_state["zoom"] <= 1.01:
                return
            sx, sy, scx, scy = view_state["drag_start"]
            cw = max(1, canvas_view.winfo_width())
            ch = max(1, canvas_view.winfo_height())
            dx_norm = (event.x - sx) / float(cw * view_state["zoom"])
            dy_norm = (event.y - sy) / float(ch * view_state["zoom"])
            view_state["cx"] = float(np.clip(scx - dx_norm, 0.05, 0.95))
            view_state["cy"] = float(np.clip(scy - dy_norm, 0.05, 0.95))
            render_preview()

        def reset_zoom(event=None):
            iid = current_iid[0]
            if iid and iid in dip_lookup:
                _, _, d = dip_lookup[iid]
                raw = decode_frame_compressed(d["frame_buf"])
                if raw is not None:
                    fh, fw = raw.shape[:2]
                    view_state["cx"] = d["x"] / float(fw)
                    view_state["cy"] = d["y"] / float(fh)
            else:
                view_state["cx"], view_state["cy"] = 0.5, 0.5
            view_state["zoom"] = 1.0
            render_preview()
            return "break"

        def zoom_to_dip(factor=2.4):
            iid = current_iid[0]
            if iid and iid in dip_lookup:
                _, _, d = dip_lookup[iid]
                raw = decode_frame_compressed(d["frame_buf"])
                if raw is not None:
                    fh, fw = raw.shape[:2]
                    view_state["cx"] = d["x"] / float(fw)
                    view_state["cy"] = d["y"] / float(fh)
            view_state["zoom"] = factor if view_state["zoom"] < 1.5 else 1.0
            render_preview()
            return "break"

        canvas_view.bind("<MouseWheel>", on_canvas_wheel)
        canvas_view.bind("<Button-4>", on_canvas_wheel)
        canvas_view.bind("<Button-5>", on_canvas_wheel)
        canvas_view.bind("<ButtonPress-1>", on_canvas_drag_start)
        canvas_view.bind("<B1-Motion>", on_canvas_drag_move)
        canvas_view.bind("<ButtonPress-3>", on_canvas_drag_start)
        canvas_view.bind("<B3-Motion>", on_canvas_drag_move)
        canvas_view.bind("<Configure>", lambda e: render_preview())

        def update_tree_row(iid):
            res, r, d = dip_lookup[iid]
            val_str = self.tr("val_valid") if d["valid"] else self.tr("val_ignored")
            save_str = self.tr("val_yes") if d["save_crop"] else self.tr("val_no")
            dip_tree.item(
                iid,
                values=(
                    f"#{res['animal_id']}",
                    f"#{r['run_num']}",
                    f"{d['sec']:.2f}s",
                    d.get("dlc_part", "MANCS (Lábhiba)"),
                    val_str,
                    save_str
                )
            )

        def on_select(event=None):
            sel = dip_tree.selection()
            if not sel:
                return
            iid = sel[0]
            current_iid[0] = iid
            _, _, d = dip_lookup[iid]
            raw = decode_frame_compressed(d["frame_buf"])
            if raw is not None:
                fh, fw = raw.shape[:2]
                view_state["cx"] = d["x"] / float(fw)
                view_state["cy"] = d["y"] / float(fh)
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
            update_tree_row(iid)
            render_preview(iid)
            return "break"

        def hotkey_cycle_part(event=None):
            iid = current_iid[0]
            if not iid:
                return
            _, _, d = dip_lookup[iid]
            part = d.get("dlc_part", "MELLSŐ LÁB (Lábhiba)")
            if "MELLSŐ" in part or part == "MANCS (Lábhiba)":
                d["dlc_code"] = "PAW"
                d["dlc_part"] = "HÁTSÓ LÁB (Lábhiba)"
            elif "HÁTSÓ LÁB" in part:
                d["dlc_code"] = "NOSE"
                d["dlc_part"] = "ORR (Exploráció)"
            elif "ORR" in part:
                d["dlc_code"] = "HIND_TAIL"
                d["dlc_part"] = "FAROK (Billenés)"
            else:
                d["dlc_code"] = "PAW"
                d["dlc_part"] = "MELLSŐ LÁB (Lábhiba)"
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
            update_tree_row(iid)
            render_preview(iid)
            return "break"

        quick_btn_row = tk.Frame(ctrl_box, bg=P["bg_panel"], pady=6, padx=6)
        quick_btn_row.pack(fill="x")

        btn_r_prev = ttk.Button(quick_btn_row, text=self.tr("btn_prev"), command=lambda: step_selection(-1), style="Ghost.TButton")
        btn_r_prev.pack(side="left", padx=(0, 6))
        ToolTip(btn_r_prev, lambda: self.tr("tt_rev_prev"))

        btn_r_next = ttk.Button(quick_btn_row, text=self.tr("btn_next"), command=lambda: step_selection(1), style="Ghost.TButton")
        btn_r_next.pack(side="left", padx=(0, 10))
        ToolTip(btn_r_next, lambda: self.tr("tt_rev_next"))

        btn_r_valid = ttk.Button(quick_btn_row, text=self.tr("btn_toggle_valid"), command=hotkey_toggle_valid, style="SoftRed.TButton")
        btn_r_valid.pack(side="left", padx=(0, 6))
        ToolTip(btn_r_valid, lambda: self.tr("tt_rev_valid"))

        btn_r_part = ttk.Button(quick_btn_row, text=self.tr("btn_cycle_part"), command=hotkey_cycle_part, style="Teal.TButton")
        btn_r_part.pack(side="left", padx=(0, 6))
        ToolTip(btn_r_part, lambda: self.tr("tt_rev_part"))

        btn_r_zoom = ttk.Button(quick_btn_row, text="2.5× [Z]", command=lambda: zoom_to_dip(2.5), style="Ghost.TButton")
        btn_r_zoom.pack(side="left", padx=(0, 6))
        ToolTip(btn_r_zoom, lambda: self.tr("tt_rev_zoom"))

        btn_r_reset = ttk.Button(quick_btn_row, text="1.0× [R]", command=reset_zoom, style="Ghost.TButton")
        btn_r_reset.pack(side="left", padx=(0, 6))
        ToolTip(btn_r_reset, lambda: self.tr("tt_rev_reset"))

        btn_r_crop = ttk.Button(quick_btn_row, text=self.tr("btn_toggle_crop"), command=hotkey_toggle_save, style="Primary.TButton")
        btn_r_crop.pack(side="left")
        ToolTip(btn_r_crop, lambda: self.tr("tt_rev_crop"))

        dip_tree.bind("<<TreeviewSelect>>", on_select)
        if ordered_iids:
            dip_tree.selection_set(ordered_iids[0])
            dip_tree.focus(ordered_iids[0])
            rev_win.after(80, on_select)

        bottom_bar = tk.Frame(rev_win, bg=P["bg_main"], padx=16, pady=8)
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
        for k in ("<s>", "<S>"):
            rev_win.bind(k, hotkey_toggle_save)
        for k in ("<z>", "<Z>"):
            rev_win.bind(k, lambda e: zoom_to_dip(2.5))
        for k in ("<r>", "<R>"):
            rev_win.bind(k, reset_zoom)
        rev_win.bind("<Return>", confirm_and_close)

        btn_r_export = ttk.Button(
            bottom_bar, text=self.tr("btn_confirm_export"),
            command=confirm_and_close, style="Emerald.TButton"
        )
        btn_r_export.pack(side="right")
        ToolTip(btn_r_export, lambda: self.tr("tt_rev_export"))

        rev_win.protocol("WM_DELETE_WINDOW", confirm_and_close)

    # ==========================================================================
    # CSV, HEATMAP & KINEMATICS EXPORT
    # ==========================================================================
    def finalize_and_export_all(self):
        if not self.pending_results:
            self.reset_ui()
            return
        self.log("\n💾 [Export] Finalizing kinematic metrics, velocity heatmaps & CSV tables in background...")
        threading.Thread(target=self._export_worker, daemon=True).start()

    def _fmt_num(self, val, fmt_str="{:.2f}", use_comma=None):
        s = fmt_str.format(val)
        if use_comma is None:
            try:
                use_comma = self.var_decimal.get().startswith(",")
            except (RuntimeError, tk.TclError):
                use_comma = True
        if use_comma:
            return s.replace(".", ",")
        return s

    def _export_worker(self):
        try:
            os.makedirs(self.output_base_dir, exist_ok=True)
            master_csv = os.path.join(self.output_base_dir, "Minden_Egyed_Meresi_Adatai.csv")

            csv_headers = [
                'Egyed_ID', 'Video_Fajl', 'Futas_Sorszam', 'Irany',
                'Belepesi_Ido_mp', 'Kilepesi_Ido_mp',
                'Teljes_Athaladasi_Ido_mp', 'Netto_Mozgasi_Ido_mp',
                'Melynyulasok_Szama', 'Mancs_Labhiba_Db',
                'Mellso_Labhiba_Db', 'Hatso_Labhiba_Db',
                'Enyhe_Megcsuszas_Db', 'Mely_Leleses_Db',
                'Orr_Lenezes_Db', 'Hatso_Farok_Db',
                'Melynyulasok_Idopontjai_mp',
                'Megallasok_Szama', 'Megallasok_OsszIdeje_mp', 'Megallasok_Intervallumai_Tol_Ig',
                'Mikro_Megtorpanas_Db', 'Mikro_Megtorpanas_Ido_mp',
                'Sebesseg_Ingadozas_CV', 'Mozgas_Darabossag_Jerk', 'Testtartas_Imbolygas_px', 'Bizonytalansagi_Index_Pct',
                'Skala_px_per_cm',
                'Megtett_Ut_cm', 'Atlagsebesseg_cm_mp', 'Max_Sebesseg_cm_mp',
                'Megtett_Ut_px', 'Atlagsebesseg_px_mp', 'Max_Sebesseg_px_mp',
                'Start_Zona_Ido_mp', 'Start_Lenyulas_Db', 'Start_Megallas_Db',
                'Kozep_Zona_Ido_mp', 'Kozep_Lenyulas_Db', 'Kozep_Megallas_Db',
                'Cel_Zona_Ido_mp', 'Cel_Lenyulas_Db', 'Cel_Megallas_Db'
            ]

            write_new_master = not os.path.exists(master_csv)
            if not write_new_master:
                try:
                    with open(master_csv, mode='r', encoding='utf-8-sig') as f_chk:
                        first_line = f_chk.readline().strip()
                    if "Bizonytalansagi_Index_Pct" not in first_line:
                        write_new_master = True
                except Exception:
                    write_new_master = True

            if write_new_master:
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
                session_traj = res.get("session_trajectory", [])

                (rx, ry, rw, rh, left_gate_x, right_gate_x, _, _,
                 _, fault_pct, z_active, kin_active, _, _, gate_dist_cm, px_per_cm, *_) = roi_data

                fault_y_local = int(rh * (fault_pct / 100.0))
                zone_width = (right_gate_x - left_gate_x) / 3.0
                z1_boundary = left_gate_x + zone_width
                z2_boundary = left_gate_x + 2.0 * zone_width

                os.makedirs(output_dir, exist_ok=True)
                csv_filename = os.path.join(output_dir, f"egyed_{safe_id}_meresi_adatok.csv")

                all_video_trajectories = []
                all_video_valid_dips = []
                video_csv_rows = []

                for r in runs:
                    run_count = r["run_num"]
                    direction = r.get("direction", "FORWARD")
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
                    fore_paw_faults = sum(
                        1 for d in valid_dips if d.get("dlc_code") == "PAW" and "MELLSŐ" in str(d.get("dlc_part", "")).upper()
                    )
                    hind_paw_faults = sum(
                        1 for d in valid_dips if d.get("dlc_code") == "PAW" and "HÁTSÓ" in str(d.get("dlc_part", "")).upper()
                    )
                    if fore_paw_faults + hind_paw_faults < paw_faults:
                        fore_paw_faults += (paw_faults - (fore_paw_faults + hind_paw_faults))

                    minor_slips_cnt = sum(
                        1 for d in valid_dips if d.get("dlc_code") == "PAW" and float(d.get("dip_depth", 0.0)) < 20.0
                    )
                    deep_falls_cnt = sum(
                        1 for d in valid_dips if d.get("dlc_code") == "PAW" and float(d.get("dip_depth", 0.0)) >= 20.0
                    )
                    nose_peeks = sum(1 for d in valid_dips if d.get("dlc_code") == "NOSE")
                    hind_tails = sum(1 for d in valid_dips if d.get("dlc_code") == "HIND_TAIL")

                    all_video_trajectories.append(trajectory)
                    all_video_valid_dips.extend(valid_dips)

                    freeze_count = len(freeze_events)
                    freeze_sec_total = sum(ev[2] for ev in freeze_events)
                    net_moving_time = max(0.0, transit_time - freeze_sec_total)

                    micro_hes_events = r.get("micro_hesitations", [])
                    micro_hes_cnt = len(micro_hes_events)
                    micro_hes_sec = sum(ev[2] for ev in micro_hes_events)

                    vel_cv = float(r.get("vel_cv", 0.0))
                    jerk_score = float(r.get("jerk_score", 0.0))
                    postural_sway_px = float(r.get("postural_sway_px", 0.0))
                    raw_uncertainty = (
                        14.0 * min(1.5, vel_cv)
                        + 3.5 * micro_hes_cnt
                        + 8.0 * freeze_count
                        + 2.5 * nose_peeks
                        + 2.0 * max(0.0, postural_sway_px - 1.2)
                        + 0.45 * jerk_score
                        + 12.0 * minor_slips_cnt
                        + 22.0 * deep_falls_cnt
                    )
                    uncertainty_pct = float(np.clip(100.0 * np.tanh(raw_uncertainty / 85.0), 0.0, 99.5))

                    for idx_pt, d in enumerate(valid_dips, start=1):
                        if d["save_crop"]:
                            snap = decode_frame_compressed(d["frame_buf"])
                            if snap is not None:
                                cv2.line(snap, (rx, ry + fault_y_local), (rx + rw, ry + fault_y_local), (0, 0, 255), 1)
                                anat = d.get("anatomy")
                                ox, oy = d.get("roi_offset", (rx, ry))
                                if anat is not None:
                                    self._draw_rodent_skeleton(snap, anat, offset_x=ox, offset_y=oy)
                                cv2.circle(snap, (d["x"], d["y"]), 16, (0, 0, 255), 3)
                                part_lbl = d.get("dlc_part", "")
                                cv2.putText(
                                    snap,
                                    f"ID #{animal_id} | Run #{run_count} | Dip #{idx_pt} ({d['sec']:.2f}s) [{part_lbl}]",
                                    (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
                                )
                                snap_path = os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_lenyulas_{idx_pt}.jpg")
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
                        f"ID #{animal_id} | Run #{run_count} ({direction}) | "
                        f"Total: {transit_time:.2f}s | Net: {net_moving_time:.2f}s | "
                        f"Vel: {r['avg_speed_cm_s']:.1f} cm/s"
                    )
                    info_line2 = (
                        f"Dips: {dip_count} (Paw:{paw_faults}[F:{fore_paw_faults}/H:{hind_paw_faults}], Nose:{nose_peeks}) | "
                        f"Freezes: {freeze_count} | Hesit: {micro_hes_cnt} | Uncertainty: {uncertainty_pct:.1f}%"
                    )

                    cv2.rectangle(run_with_faded_ladder, (18, 16), (int(run_with_faded_ladder.shape[1] * 0.96), 72), (255, 255, 255), -1)
                    cv2.rectangle(run_with_faded_ladder, (18, 16), (int(run_with_faded_ladder.shape[1] * 0.96), 72), (0, 0, 0), 1)
                    cv2.putText(run_with_faded_ladder, info_line1, (28, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1)
                    cv2.putText(run_with_faded_ladder, info_line2, (28, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 0, 0), 1)

                    run_img_name = f"egyed_{safe_id}_futas_{run_count}_osszefoglalo.jpg"
                    save_image_unicode(os.path.join(output_dir, run_img_name), run_with_faded_ladder)

                    if kin_active:
                        hm_title = f"ID #{animal_id} Run #{run_count} Heatmap & Speed Profile"
                        run_hm = self._generate_heatmap_image(
                            first_frame, [trajectory], valid_dips, hm_title, blend_alpha=0.48, draw_dip_circles_red=False
                        )
                        save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_heatmap.jpg"), run_hm)

                        run_faded_hm = self._generate_heatmap_image(
                            faded_base_for_hm, [trajectory], valid_dips, hm_title, blend_alpha=0.42, draw_dip_circles_red=True
                        )
                        save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_halvany_heatmap.jpg"), run_faded_hm)

                    fn = self._fmt_num
                    row_data = [
                        animal_id, video_name, run_count, direction,
                        fn(start_time), fn(end_time),
                        fn(transit_time), fn(net_moving_time),
                        dip_count, paw_faults,
                        fore_paw_faults, hind_paw_faults,
                        minor_slips_cnt, deep_falls_cnt,
                        nose_peeks, hind_tails,
                        dip_times_str,
                        freeze_count, fn(freeze_sec_total), freeze_intervals_str,
                        micro_hes_cnt, fn(micro_hes_sec),
                        fn(vel_cv, "{:.3f}"), fn(jerk_score, "{:.1f}"), fn(postural_sway_px, "{:.2f}"), fn(uncertainty_pct, "{:.1f}"),
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
                    video_csv_rows.append(row_data)

                with open(csv_filename, mode='w', newline='', encoding='utf-8-sig') as f_vid:
                    writer_vid = csv.writer(f_vid, delimiter=';')
                    writer_vid.writerow(csv_headers)
                    writer_vid.writerows(video_csv_rows)

                if video_csv_rows:
                    with open(master_csv, mode='a', newline='', encoding='utf-8-sig') as f_master:
                        writer_master = csv.writer(f_master, delimiter=';')
                        writer_master.writerows(video_csv_rows)

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

                # Export continuous 100% whole-session trajectory if session trajectory was tracked
                if session_traj and kin_active:
                    session_hm = self._generate_heatmap_image(
                        first_frame, [session_traj], all_video_valid_dips,
                        f"ID #{animal_id} FULL SESSION Continuous Trajectory (100% Movement)",
                        blend_alpha=0.45, draw_dip_circles_red=True
                    )
                    save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_TELJES_SESSION_heatmap.jpg"), session_hm)

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
            try:
                self.root.after(0, self.reset_ui)
            except (RuntimeError, tk.TclError):
                pass

    def stop_analysis(self):
        self.is_running = False
        self.log("Stopping... closing worker threads cleanly...")

    def reset_ui(self):
        self.is_running = False
        self.btn_start.config(state="normal")
        self.btn_quick_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._refresh_kpi_cards()


def main():
    configure_native_os_identity()
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


if __name__ == "__main__":
    main()
