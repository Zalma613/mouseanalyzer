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
APP_ID = "zalma.mouseanalyzer.pro.3.5"
APP_VERSION = "3.5"


# ==============================================================================
# RESOURCE PATH & NATIVE OS BRANDING (macOS Dock/Menu & Windows Taskbar)
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
    """Replaces default 'Python' process branding with 'MouseAnalyzer PRO'."""
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
# SAFE WORKING DIRECTORY SETUP & OPENCL GPU INITIALIZATION
# ==============================================================================
def setup_safe_working_directory(folder_name="MouseAnalyzer_Eredmenyek"):
    docs_dir = os.path.expanduser("~/Documents")
    if not os.path.exists(docs_dir):
        docs_dir = os.path.expanduser("~")
    safe_dir = os.path.join(docs_dir, folder_name)
    os.makedirs(safe_dir, exist_ok=True)
    # Only change cwd when running inside a frozen/read-only bundle
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
# BILINGUAL TRANSLATION & TOOLTIP DICTIONARY (HU / EN)
# ==============================================================================
TRANSLATIONS = {
    "hu": {
        "subtitle": "Párhuzamos YOLO + OpenCV Horizontális Létra Elemző",
        "out_dir_prefix": "Kimenet:",
        "btn_change_dir": "📁 Mappa",
        "btn_open_dir": "📂 Eredmények",
        "btn_settings": "⚙ Speciális Beállítások",
        "kpi_videos": "BETÖLTÖTT VIDEÓK",
        "kpi_calib": "KALIBRÁCIÓ",
        "kpi_engine": "HIBRID MOTOR",
        "kpi_dlc": "ANATÓMIAI MODUL",
        "kpi_vid_val": "{n} db videó",
        "kpi_cal_none": "Automatikus (Zero-Calib)",
        "kpi_cal_active": "Aktív ({w}x{h} px)",
        "sec1_title": "1. Videók és Egyedek",
        "btn_add_vid": "＋ Videók Hozzáadása",
        "btn_edit_id": "✎ ID Szerkesztése",
        "btn_remove_vid": "✕ Eltávolítás",
        "btn_clear_vid": "Lista Ürítése",
        "col_fname": "Videó Fájlnév",
        "col_id": "Egyed ID",
        "col_status": "Állapot",
        "col_path": "Elérési Útvonal",
        "status_waiting": "Várakozik",
        "sec2_title": "2. Futtatás és Vezérlés",
        "chk_rev": "🔍 Lenyúlás-ellenőrző ablak",
        "chk_auto_calib": "🤖 Automatikus létra- és egér-kalibráció",
        "chk_yolo_fusion": "⚡ Párhuzamos YOLO + Anatómiai OpenCV Fúzió",
        "chk_zones": "Pálya szektorokra bontása (Start / Közép / Cél)",
        "chk_kin": "Kinematika (cm/s) + Sebesség-Heatmapek",
        "chk_gpu": "🚀 GPU (OpenCL UMat + HW Dekóder) & Aszinkron Olvasó",
        "chk_kalman": "🎯 Kálmán-szűrő + Elasztikus Létrakövetés",
        "chk_dlc_sa": "🧠 Anatómiai osztályozás (Mellső/Hátsó láb vs. Orr)",
        "chk_dlc_exp": "📸 DLC / YOLO tanítóképek kigyűjtése",
        "lbl_threads": "Szálak:",
        "lbl_stride": "Lépésköz:",
        "lbl_cooldown": "Refrakter (mp):",
        "lbl_mindist": "Min. táv (px):",
        "lbl_gatecm": "Kaputáv (cm):",
        "lbl_dec": "CSV Tizedes:",
        "btn_load_prof": "📂 Profil Betöltése",
        "btn_save_prof": "💾 Profil Mentése",
        "btn_start": "▶  Kalibrálás és Elemzés Indítása",
        "btn_quick": "⚡ Gyors Indítás (Előnézet Nélkül)",
        "btn_stop": "■  Leállítás",
        "prog_idle": "Készültség: {done} / {total} videó",
        "prog_run": "Feldolgozás: {done} / {total} videó ({pct:.0f}%)",
        "sec3_title": "3. Eseménynapló",
        "msg_no_vid_title": "Hiányzó videók",
        "msg_no_vid_body": "Előbb adj hozzá legalább egy videót a listához!",
        "msg_select_row": "Előbb jelölj ki egy sort a táblázatban!",
        "edit_id_title": "Egyed ID Módosítása",
        "edit_id_prompt": "Add meg az új azonosítót:",
        "btn_save_enter": "Mentés (Enter)",
        "settings_title": "Speciális Elemzési és Hardver Beállítások",
        "btn_close_settings": "✔ Beállítások Mentése és Bezárás",
        # Clean, concise Tooltips
        "tt_add_vid": "Videófájlok (.mp4, .avi, .mov, .mkv) hozzáadása a listához.",
        "tt_edit_id": "A kijelölt videó Egyed ID-jának módosítása (dupla kattintással is működik).",
        "tt_remove_vid": "A kijelölt videó eltávolítása a listából.",
        "tt_clear_vid": "A teljes videólista ürítése.",
        "tt_auto_calib": "Automatikusan megkeresi a létrát, a kapukat és az egeret tartalmazó képkockát.",
        "tt_yolo": "A YOLO háttérben fut; az OpenCV gerincbecslése csípő- és vállkereső zónákat jelöl ki a lábhibákhoz.",
        "tt_rev": "A futás végén nagyítható ellenőrző ablakot nyit meg a lenyúlások átnézéséhez.",
        "tt_gatecm": "A Start és Cél kapu közötti valós távolság centiméterben.",
        "tt_settings": "További beállítások: szálak száma, lépésköz, refrakter idő, GPU és CSV formátum.",
        "tt_start": "Megnyitja a nagyítható kalibrációs előnézetet, majd elindítja az elemzést.",
        "tt_quick": "Előnézeti ablak nélkül, azonnal elindítja a kötegelt elemzést.",
        "tt_stop": "Azonnal leállítja a futó elemzést.",
        "tt_change_dir": "Kimeneti mappa módosítása.",
        "tt_open_dir": "Az eredményeket tartalmazó mappa megnyitása.",
    },
    "en": {
        "subtitle": "Parallel YOLO + OpenCV Horizontal Ladder Suite",
        "out_dir_prefix": "Output:",
        "btn_change_dir": "📁 Folder",
        "btn_open_dir": "📂 Results",
        "btn_settings": "⚙ Advanced Settings",
        "kpi_videos": "LOADED VIDEOS",
        "kpi_calib": "CALIBRATION",
        "kpi_engine": "HYBRID ENGINE",
        "kpi_dlc": "ANATOMY MODULE",
        "kpi_vid_val": "{n} videos",
        "kpi_cal_none": "Automatic (Zero-Calib)",
        "kpi_cal_active": "Active ({w}x{h} px)",
        "sec1_title": "1. Videos & Subject IDs",
        "btn_add_vid": "＋ Add Videos",
        "btn_edit_id": "✎ Edit ID",
        "btn_remove_vid": "✕ Remove",
        "btn_clear_vid": "Clear List",
        "col_fname": "Video Filename",
        "col_id": "Subject ID",
        "col_status": "Status",
        "col_path": "File Path",
        "status_waiting": "Queued",
        "sec2_title": "2. Execution & Controls",
        "chk_rev": "🔍 Interactive Dip Inspector",
        "chk_auto_calib": "🤖 Auto-detect ladder & mouse",
        "chk_yolo_fusion": "⚡ Parallel YOLO + Anatomical OpenCV Fusion",
        "chk_zones": "Split track into sectors (Start / Mid / Goal)",
        "chk_kin": "Kinematics (cm/s) + Velocity Heatmaps",
        "chk_gpu": "🚀 GPU (OpenCL UMat + HW Decoder) & Async Reader",
        "chk_kalman": "🎯 Kalman Filter + Elastic Ladder Bending Tracker",
        "chk_dlc_sa": "🧠 Anatomical classification (Fore/Hind Paw vs. Nose)",
        "chk_dlc_exp": "📸 Export Active Learning DLC Training Crops",
        "lbl_threads": "Threads:",
        "lbl_stride": "Stride:",
        "lbl_cooldown": "Refractory (s):",
        "lbl_mindist": "Min. dist (px):",
        "lbl_gatecm": "Gate span (cm):",
        "lbl_dec": "CSV Decimal:",
        "btn_load_prof": "📂 Load Profile",
        "btn_save_prof": "💾 Save Profile",
        "btn_start": "▶  Start Calibration & Analysis",
        "btn_quick": "⚡ Quick Start (Skip Preview)",
        "btn_stop": "■  Stop",
        "prog_idle": "Progress: {done} / {total} videos",
        "prog_run": "Processing: {done} / {total} videos ({pct:.0f}%)",
        "sec3_title": "3. Event Log",
        "msg_no_vid_title": "Missing Videos",
        "msg_no_vid_body": "Please add at least one video to the queue first!",
        "msg_select_row": "Please select a video row in the table first!",
        "edit_id_title": "Edit Subject ID",
        "edit_id_prompt": "Enter new Subject ID:",
        "btn_save_enter": "Save (Enter)",
        "settings_title": "Advanced Analysis & Hardware Settings",
        "btn_close_settings": "✔ Save & Close Settings",
        # Tooltips
        "tt_add_vid": "Add video files (.mp4, .avi, .mov, .mkv) to the batch queue.",
        "tt_edit_id": "Edit Subject ID for the selected row (or double-click row).",
        "tt_remove_vid": "Remove the selected video from the list.",
        "tt_clear_vid": "Clear all videos from the list.",
        "tt_auto_calib": "Automatically detects ladder ROI, gates, and best mouse preview frame.",
        "tt_yolo": "Runs YOLO in the background while OpenCV estimates the trunk axis and gates paw-dip searches to hip and shoulder zones.",
        "tt_rev": "Opens a zoomable inspector window after analysis to review detected foot faults.",
        "tt_gatecm": "Physical distance in centimeters between Start and Goal gates.",
        "tt_settings": "Configure threads, frame stride, refractory period, GPU, and CSV format.",
        "tt_start": "Opens the zoomable calibration preview, then starts batch analysis.",
        "tt_quick": "Skips preview windows and starts batch analysis immediately.",
        "tt_stop": "Gracefully stops all active worker threads.",
        "tt_change_dir": "Change output directory.",
        "tt_open_dir": "Open output results folder.",
    }
}


# ==============================================================================
# FLICKER-FREE SINGLETON ON-HOVER TOOLTIP MANAGER
# ==============================================================================
class ToolTip:
    """
    Flicker-free, screen-clamped singleton tooltip that never steals mouse focus
    or gets stuck on screen.
    """
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
        self.after_id = self.widget.after(450, self._show)

    def _on_motion(self, event=None):
        if event is not None:
            self.last_mouse = (event.x_root, event.y_root)

    def _on_leave(self, event=None):
        # Verify cursor actually left the widget (prevents false Leave events)
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

        # Confirm mouse is still over this widget before popping up
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
            if sys.platform == "darwin":
                tw.wm_attributes("-transparent", False)
        except Exception:
            pass

        outer = tk.Frame(tw, bg="#30363D", padx=1, pady=1)
        outer.pack()
        lbl = tk.Label(
            outer, text=text, justify="left", bg="#161B22", fg="#F0F6FC",
            font=("Segoe UI" if sys.platform == "win32" else "SF Pro Display", 9),
            padx=10, pady=6, wraplength=320
        )
        lbl.pack()

        tw.update_idletasks()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()
        scr_w = tw.winfo_screenwidth()
        scr_h = tw.winfo_screenheight()

        # Position offset below cursor so cursor never touches the tooltip window
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
# OPENCV ZOOM & PAN VIEWPORT HELPER (EVENT-DRIVEN, 0% IDLE CPU)
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

        badge = f"Zoom: {self.zoom:.1f}x (Gorgo=Zoom, JobbGomb=Mozgatas, R=Alaphelyzet)"
        cv2.rectangle(out, (12, self.img_h - 38), (515, self.img_h - 10), (20, 25, 32), -1)
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
    """2D Constant-Velocity Kalman Filter for smoothing rodent center-of-mass trajectories."""
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
# PARALLEL YOLO + OPENCV HYBRID SPATIAL LOCATOR ENGINE
# ==============================================================================
class ParallelYoloOpenCVEngine:
    """
    Runs Ultralytics YOLO (if installed) in parallel / thread-safe mode alongside
    a fast 1D/2D OpenCV Torso-Core Density Locator.
    Provides an exact spatial attention window [x_min, x_max, y_min, y_max] and optional
    segmentation mask around the animal so distant ladder rungs can NEVER turn green!
    """
    def __init__(self, log_callback=print):
        self.log = log_callback
        self.yolo_model = None
        self.yolo_lock = threading.Lock()
        self.device = "cpu"
        self.yolo_executor = None
        self.stream_lock = threading.Lock()
        self.stream_states = {}
        self._yolo_error_logged = False
        self.k_seed_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 9))
        self.k_open_3 = np.ones((3, 3), np.uint8)
        self.k_close_core = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 5))
        self.k_yolo_dilate = np.ones((11, 11), np.uint8)
        self.k_grad_3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        self._ignored_coco_classes = {
            "person", "bicycle", "car", "motorcycle", "bus", "truck", "traffic light",
            "bench", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
            "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
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
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    self.device = "mps"
            except Exception:
                self.device = "cpu"

            for candidate in ("mouse_yolo.pt", "ladder_yolo.pt", "yolov8n-seg.pt", "yolov8n.pt"):
                p = get_resource_path(candidate)
                if os.path.exists(p):
                    self.yolo_model = YOLO(p)
                    self.yolo_executor = ThreadPoolExecutor(
                        max_workers=1, thread_name_prefix="mouse-yolo"
                    )
                    self.log(f"⚡ [Hybrid YOLO+OpenCV] Loaded '{candidate}' on {self.device.upper()}")
                    return
        except Exception:
            self.yolo_model = None

    def _predict_yolo(self, crop_bgr, rw, rh):
        with self.yolo_lock:
            results = self.yolo_model.predict(
                crop_bgr, conf=0.22, verbose=False, device=self.device, imgsz=320
            )
        if not results:
            return None, None

        result = results[0]
        yolo_bbox = None
        yolo_seg_mask = None
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
                if bw < 16 or bh < 8 or bw >= rw * 0.78 or bh >= rh * 0.92:
                    continue
                # Reject detections centered near the bottom table surface
                if (y1 + bh * 0.5) > rh * 0.80:
                    continue
                if is_generic_coco and cls_ids is not None and i < len(cls_ids):
                    cname = str(names.get(int(cls_ids[i]), "")).lower()
                    # Note: in COCO, 'mouse' (id 64) is a computer mouse, but sometimes rodents trigger cat/dog/bird/bear/sheep/mouse;
                    # we only block furniture, tables, screens, people, and bottles.
                    if cname in self._ignored_coco_classes and cname != "mouse":
                        continue
                area = float(bw * bh)
                if area > best_area:
                    best_area = area
                    best_i = i

            if best_i >= 0:
                x1, y1, x2, y2 = [int(value) for value in boxes[best_i]]
                yolo_bbox = (x1, y1, x2 - x1, y2 - y1)
                if result.masks is not None and len(result.masks.data) > best_i:
                    mask_data = result.masks.data[best_i].cpu().numpy()
                    yolo_seg_mask = (cv2.resize(mask_data, (rw, rh)) > 0.35).astype(np.uint8) * 255
        return yolo_bbox, yolo_seg_mask

    def _get_yolo_result(self, crop_bgr, rw, rh, stream_id, frame_idx, max_age):
        if self.yolo_model is None:
            return None, None, max_age + 1

        if stream_id is None or frame_idx is None or self.yolo_executor is None:
            try:
                yolo_bbox, yolo_seg_mask = self._predict_yolo(crop_bgr, rw, rh)
                return yolo_bbox, yolo_seg_mask, 0
            except Exception as exc:
                if not self._yolo_error_logged:
                    self.log(f"⚠ YOLO inference failed; continuing with OpenCV: {exc}")
                    self._yolo_error_logged = True
                return None, None, max_age + 1

        with self.stream_lock:
            state = self.stream_states.setdefault(
                stream_id, {"future": None, "result": None, "frame_idx": -1}
            )
            future = state["future"]
            if future is not None and future.done():
                try:
                    state["result"] = future.result()
                    state["frame_idx"] = state.pop("pending_frame_idx")
                    self._yolo_error_logged = False
                except Exception as exc:
                    if not self._yolo_error_logged:
                        self.log(f"⚠ YOLO inference failed; continuing with OpenCV: {exc}")
                        self._yolo_error_logged = True
                state["future"] = None

            if state["future"] is None:
                state["pending_frame_idx"] = frame_idx
                state["future"] = self.yolo_executor.submit(
                    self._predict_yolo, crop_bgr.copy(), rw, rh
                )

            result_age = frame_idx - state["frame_idx"]
            if result_age <= max_age:
                yolo_bbox, yolo_seg_mask = (
                    state["result"] if state["result"] is not None else (None, None)
                )
                return yolo_bbox, yolo_seg_mask, result_age
            return None, None, result_age

    def reset_stream(self, stream_id):
        with self.stream_lock:
            self.stream_states.pop(stream_id, None)

    def locate_animal_roi_and_mask(
        self, crop_bgr, gray_smooth, base_smooth, inv_ladder_mask, fault_y_local,
        dark_t, diff_t, stream_id=None, frame_idx=None, ai_max_age=3, previous_bbox=None
    ):
        """
        Finds the exact horizontal & vertical location of the rodent torso first
        using Hysteresis Background-Difference + Static Imperfection Suppression +
        Geodesic Reconstruction + Parallel YOLO, then builds a spatial gating mask
        so ONLY pixels belonging to the animal's true location can be included in the
        final OpenCV mask (ignoring table imperfections, static dark walls, and shadows).
        """
        rh, rw = gray_smooth.shape[:2]

        # 1. Hysteresis OpenCV Torso-Core Locator (looks strictly above the ladder rungs)
        torso_bottom = max(15, int(fault_y_local) - 10)
        torso_gray = gray_smooth[:torso_bottom, :]
        torso_base = base_smooth[:torso_bottom, :]
        torso_diff = cv2.subtract(torso_base, torso_gray)
        torso_absdiff = cv2.absdiff(torso_base, torso_gray)

        # Detect static background imperfections (dark knots/scratches/bolts or sharp static edges)
        bg_grad = cv2.morphologyEx(torso_base, cv2.MORPH_GRADIENT, self.k_grad_3)
        static_imperfection = (torso_base <= min(215, dark_t + 8)) | (bg_grad >= 16)
        static_imperfection = cv2.dilate(
            static_imperfection.astype(np.uint8) * 255, self.k_open_3, iterations=1
        ) > 0

        seed_diff_t = max(11, int(diff_t * 0.78))
        low_diff_t = max(6, int(diff_t * 0.38))
        blemish_diff_t = max(seed_diff_t + 14, int(diff_t * 1.55))

        # High-confidence foreground seeds: clearly changed from background AND dark,
        # requiring much stronger difference on pre-existing background imperfections!
        valid_seed_bool = (
            ((torso_diff >= seed_diff_t) & (torso_gray <= min(225, dark_t + 14)) & (~static_imperfection))
            | ((torso_diff >= blemish_diff_t) & (torso_gray <= dark_t))
            | ((torso_absdiff >= max(22, int(diff_t * 1.30))) & (torso_gray <= dark_t) & (~static_imperfection))
        )
        seed_mask = valid_seed_bool.astype(np.uint8) * 255

        # If we have a recent tracked bounding box, allow stationary/freezing rodent pixels inside it
        # (excluding pre-existing static background imperfections so table spots never lock!)
        if previous_bbox is not None:
            px, py, pw, ph = previous_bbox
            px1 = max(0, int(px - 16))
            px2 = min(rw, int(px + pw + 16))
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

        # Candidate body support mask: dark pixels that ALSO differ from the clean background
        # (requires stronger difference on static background blemishes/edges)
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

        # Geodesic morphological reconstruction: keep only support components connected to a valid seed
        seed_dilated = cv2.dilate(seed_mask, self.k_seed_dilate, iterations=2)
        core_mask = cv2.bitwise_and(support_mask, seed_dilated)
        core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_OPEN, self.k_open_3)
        core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_CLOSE, self.k_close_core)

        # 2. Optional Parallel YOLO Box / Segmentation Refinement
        yolo_bbox, yolo_seg_mask, yolo_age = self._get_yolo_result(
            crop_bgr, rw, rh, stream_id, frame_idx, max(3, int(ai_max_age))
        )
        if yolo_age > max(3, int(ai_max_age)):
            yolo_bbox = None
            yolo_seg_mask = None

        # 3. Find dominant torso cluster from core_mask within the ladder walking corridor
        contours, _ = cv2.findContours(core_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_c = None
        max_a = float("-inf")
        min_corridor_bottom = max(10, int(torso_bottom * 0.35))
        max_valid_torso_top = max(12, int(fault_y_local) - max(50, int(rh * 0.18)))
        min_torso_h = max(28, int(rh * 0.105))
        for c in contours:
            a = cv2.contourArea(c)
            if a <= 300:
                continue
            x_c, y_c, w_c, h_c = cv2.boundingRect(c)
            aspect_ratio = w_c / max(1.0, float(h_c))
            fill_ratio = a / max(1.0, float(w_c * h_c))
            # Reject flat rung-edge slivers (y_c >= max_valid_torso_top or h_c < min_torso_h) and vertical wall markers
            if (
                w_c < 24
                or h_c < min_torso_h
                or y_c >= max_valid_torso_top
                or aspect_ratio < 0.45
                or aspect_ratio > 9.5
                or fill_ratio < 0.14
            ):
                continue
            # Reject isolated ceiling/wall artifacts that do not reach the walking corridor above the rungs
            if (y_c + h_c) < min_corridor_bottom:
                continue

            roi_diff = torso_diff[y_c:y_c + h_c, x_c:x_c + w_c]
            mean_diff = float(np.mean(roi_diff)) if roi_diff.size > 0 else 0.0
            p80_diff = float(np.percentile(roi_diff, 80)) if roi_diff.size > 0 else 0.0
            if (mean_diff < max(10.0, diff_t * 0.48) or p80_diff < max(22.0, diff_t * 0.95)) and previous_bbox is None:
                continue

            # Favor contours sitting right on the walking corridor just above the rungs
            corridor_prox = 1.0 - min(1.0, abs((y_c + h_c) - torso_bottom) / max(18.0, float(torso_bottom)))
            score = np.log1p(a) + 2.0 * fill_ratio + min(2.2, mean_diff / 18.0) + 0.85 * corridor_prox
            if yolo_bbox is not None:
                yx, yy, yw, yh = yolo_bbox
                inter_x = max(0, min(x_c + w_c, yx + yw) - max(x_c, yx))
                if inter_x > 0:
                    score += 2.0 * (inter_x / max(1.0, float(max(w_c, yw))))
            if previous_bbox is not None:
                px, py, pw, ph = previous_bbox
                previous_cx = px + pw / 2.0
                previous_cy = py + ph / 2.0
                candidate_cx = x_c + w_c / 2.0
                candidate_cy = y_c + h_c / 2.0
                distance = np.hypot(candidate_cx - previous_cx, candidate_cy - previous_cy)
                distance_scale = max(36.0, min(140.0, rw * 0.18))
                score += 3.0 * np.exp(-distance / distance_scale)
                score -= min(3.2, distance / distance_scale)
            if score > max_a:
                max_a = score
                best_c = c

        if best_c is None and yolo_bbox is None:
            return None, None

        if best_c is not None:
            cx, cy, cw, ch = cv2.boundingRect(best_c)
            # Trim thin tail extensions from the horizontal torso core bounds (cx, cw)
            c_mask = np.zeros_like(core_mask)
            cv2.drawContours(c_mask, [best_c], -1, 255, -1)
            col_heights = np.sum(c_mask[:, cx:cx + cw] > 0, axis=0)
            thick_cols = np.where(col_heights >= max(7, int(ch * 0.28)))[0]
            if len(thick_cols) >= 12:
                core_x1 = cx + int(thick_cols[0])
                core_x2 = cx + int(thick_cols[-1]) + 1
                if (core_x2 - core_x1) >= 16:
                    cx, cw = core_x1, core_x2 - core_x1

            if yolo_bbox is not None:
                yx, yy, yw, yh = yolo_bbox
                # Fuse YOLO bbox only if it is consistent with or refines the torso
                if abs((yx + yw / 2.0) - (cx + cw / 2.0)) < max(cw, yw) * 0.85:
                    cx = min(cx, yx)
                    cy = min(cy, yy)
                    cw = max(cx + cw, yx + yw) - cx
                    ch = max(cy + ch, yy + yh) - cy
        else:
            cx, cy, cw, ch = yolo_bbox

        # Build spatial gate:
        # - Above the rungs (torso & tail): allow full rodent tail extension (+260px) and snout extension
        # - At & below the rungs (paw/nose dip zone): restrict X to the true torso+head footprint [cx - 10 .. cx + cw + 14]!
        spatial_gate = np.zeros((rh, rw), dtype=np.uint8)

        upper_x1 = max(0, cx - 260)
        upper_x2 = min(rw, cx + cw + 260)
        spatial_gate[:torso_bottom, upper_x1:upper_x2] = 255

        # Below-rung zone X-window: covers the true torso+head footprint (hindlimb, forelimb, and snout)
        paw_x1 = max(0, cx - 10)
        paw_x2 = min(rw, cx + cw + 14)
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
        """
        Computes a true static background image without 95th-percentile brightness inflation.
        Rejects dark foreground outliers (frames where the dark rodent passes over a pixel)
        relative to the 88th-percentile reference, then averages the clean background frames
        so static table imperfections and wood/metal textures retain their exact resting intensity.
        """
        if stack.shape[0] <= 2:
            return np.max(stack, axis=0).astype(np.uint8)
        p88 = np.percentile(stack, 88, axis=0)
        clean_mask = stack >= (p88 - 14.0)
        bg_sum = np.sum(stack.astype(np.float32) * clean_mask, axis=0)
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
    def __init__(self, base_gray, base_inv_ladder_mask, init_rung_pts, base_fault_y_local):
        if base_gray.ndim == 3:
            base_gray = cv2.cvtColor(base_gray, cv2.COLOR_BGR2GRAY)
        self.base_gray = np.squeeze(base_gray).astype(np.uint8).copy()
        self.base_inv_ladder = np.squeeze(base_inv_ladder_mask).astype(np.uint8).copy()
        self.base_float = np.float32(self.base_gray)
        self.rh, self.rw = self.base_gray.shape[:2]
        self.hann = cv2.createHanningWindow((self.rw, self.rh), cv2.CV_32F)

        pts_arr = np.asarray(init_rung_pts, dtype=np.float32).reshape(-1, 1, 2)
        self.init_pts = pts_arr.copy()
        self.curr_pts = pts_arr.copy()
        self.prev_gray = self.base_gray.copy()

        pts_2d = pts_arr.reshape(-1, 2)
        mean_rung_y = float(np.median(pts_2d[:, 1])) if len(pts_2d) > 0 else (base_fault_y_local - 12)
        self.fault_offset_px = max(8.0, float(base_fault_y_local - mean_rung_y))
        self.base_fault_y_local = float(base_fault_y_local)

        self.poly_coeffs = np.array([0.0, 0.0, self.base_fault_y_local], dtype=np.float64)
        self.global_dx = 0.0
        self.global_dy = 0.0
        self.step_counter = 0

        self.cached_warped_bg = self.base_gray
        self.cached_warped_inv_ladder = self.base_inv_ladder
        self.cached_fault_curve = np.full(self.rw, int(base_fault_y_local), dtype=np.int32)

        self.lk_params = dict(
            winSize=(13, 13),
            maxLevel=1,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 8, 0.04)
        )

    def update(self, crop_gray, mouse_bbox_local=None):
        self.step_counter += 1
        if self.step_counter % 4 != 1:
            return self.cached_warped_bg, self.cached_warped_inv_ladder, self.cached_fault_curve

        if crop_gray.ndim == 3:
            crop_gray = cv2.cvtColor(crop_gray, cv2.COLOR_BGR2GRAY)
        crop_gray = np.squeeze(crop_gray).astype(np.uint8)

        curr_float = np.float32(crop_gray)
        (shift_x, shift_y), response = cv2.phaseCorrelate(self.base_float, curr_float, self.hann)
        if response > 0.15 and abs(shift_x) < 25 and abs(shift_y) < 25:
            self.global_dx = 0.85 * self.global_dx + 0.15 * shift_x
            self.global_dy = 0.85 * self.global_dy + 0.15 * shift_y

        if len(self.curr_pts) >= 4:
            next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self.prev_gray, crop_gray, self.curr_pts, None, **self.lk_params
            )
            if next_pts is not None and status is not None:
                next_2d = next_pts.reshape(-1, 2)
                init_2d = self.init_pts.reshape(-1, 2)
                good_mask = status.reshape(-1) == 1

                valid_x = []
                valid_y = []

                mx1, my1, mx2, my2 = -1, -1, -1, -1
                if mouse_bbox_local is not None:
                    bx, by, bw, bh = mouse_bbox_local
                    mx1, my1, mx2, my2 = bx - 14, by - 14, bx + bw + 14, by + bh + 14

                for i in range(len(next_2d)):
                    px, py = float(next_2d[i, 0]), float(next_2d[i, 1])
                    ix, iy = float(init_2d[i, 0]), float(init_2d[i, 1])

                    if mx1 <= px <= mx2 and my1 <= py <= my2:
                        next_2d[i, 0] = ix + self.global_dx
                        next_2d[i, 1] = iy + self.global_dy
                        continue

                    if good_mask[i] and abs(px - (ix + self.global_dx)) < 12.0 and abs(py - (iy + self.global_dy)) < 16.0:
                        valid_x.append(px)
                        valid_y.append(py + self.fault_offset_px)
                    else:
                        next_2d[i, 0] = ix + self.global_dx
                        next_2d[i, 1] = iy + self.global_dy

                self.curr_pts = next_2d.reshape(-1, 1, 2).astype(np.float32)

                if len(valid_x) >= 5:
                    try:
                        coeffs = np.polyfit(valid_x, valid_y, deg=2)
                        coeffs[0] = np.clip(coeffs[0], -8e-5, 8e-5)
                        self.poly_coeffs = 0.78 * self.poly_coeffs + 0.22 * coeffs
                    except Exception:
                        pass
                else:
                    self.poly_coeffs = np.array([0.0, 0.0, self.base_fault_y_local + self.global_dy])

        self.prev_gray = crop_gray

        if abs(self.global_dx) < 0.4 and abs(self.global_dy) < 0.4:
            self.cached_warped_bg = self.base_gray
            self.cached_warped_inv_ladder = self.base_inv_ladder
        else:
            M = np.float32([[1, 0, self.global_dx], [0, 1, self.global_dy]])
            self.cached_warped_bg = cv2.warpAffine(self.base_gray, M, (self.rw, self.rh), borderMode=cv2.BORDER_REPLICATE)
            self.cached_warped_inv_ladder = cv2.warpAffine(self.base_inv_ladder, M, (self.rw, self.rh), borderMode=cv2.BORDER_CONSTANT, borderValue=255)

        xs = np.arange(self.rw, dtype=np.float64)
        a, b, c = self.poly_coeffs
        ys = a * (xs ** 2) + b * xs + c
        self.cached_fault_curve = np.clip(ys, 10, self.rh - 2).astype(np.int32)

        return self.cached_warped_bg, self.cached_warped_inv_ladder, self.cached_fault_curve


# ==============================================================================
# DEEPLABCUT / YOLO / BBOX-NORMALIZED POSE CLASSIFIER
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

        self.log(f"[Active Learning] {exported_count} db tanítókép kimentve: {os.path.abspath(base_folder)}")
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
        self.log("🧠 [Anatómiai Osztályozás] Lenyúlások elemzése (Mellső/Hátsó Láb vs. Orr vs. Farok)...")
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
        Distinguishes true limb foot-faults (Forelimb / Hindlimb slips) from
        anterior Nose/Snout exploration and posterior Tail dips.
        `rel_pos_norm` is normalized [0..1] along the tail-trimmed torso+head core
        (0.0 = rump/hip base, 1.0 = snout tip).
        """
        # 1. Anterior Snout / Nose Exploration Zone
        if rel_pos_norm >= 0.75 or (rel_pos_norm >= 0.68 and head_pitch_down):
            # Unmistakable pink paw skin (skin_score >= 12.0) or narrow deep extension under the shoulder/neck is a forepaw slip
            is_distinct_forepaw = (
                rel_pos_norm < 0.86
                and (
                    skin_score >= 12.0
                    or (not head_pitch_down and aspect_ratio < 0.72 and dip_depth >= 14.0 and skin_score >= 9.5)
                )
            )
            if not is_distinct_forepaw:
                return "ORR (Exploráció)", "NOSE"

        # 2. Posterior Tail / Rump Zone
        if rel_pos_norm < 0.10 or (rel_pos_norm < 0.26 and aspect_ratio > 1.45 and dip_depth < 15.0):
            return "FAROK (Billenés)", "HIND_TAIL"

        # 3. Hindlimb vs. Forelimb Foot-Fault Zone
        if rel_pos_norm < 0.46:
            return "HÁTSÓ LÁB (Lábhiba)", "PAW"
        return "MELLSŐ LÁB (Lábhiba)", "PAW"


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
        self.root.geometry("1180x780")
        self.root.minsize(980, 680)
        self.root.configure(bg=self.PALETTE["bg_main"])

        apply_window_icon(self.root)

        self.output_base_dir = SAFE_BASE_DIR
        self.video_data = []
        self.is_running = False
        self.completed_videos = 0
        self.pending_results = []

        self.calib_dark_thresh = 135
        self.calib_diff_thresh = 24
        self.calib_ladder_thresh = 132
        self.calib_fault_Ratio = 74
        self.saved_geometry = None

        self.var_auto_calib = tk.BooleanVar(value=True)
        self.var_yolo_fusion = tk.BooleanVar(value=True)
        self.var_enable_review = tk.BooleanVar(value=True)
        self.var_enable_zones = tk.BooleanVar(value=True)
        self.var_enable_kinematics = tk.BooleanVar(value=True)
        self.var_use_gpu = tk.BooleanVar(value=True)
        self.var_use_kalman = tk.BooleanVar(value=True)
        self.var_dlc_superanimal = tk.BooleanVar(value=True)
        self.var_dlc_export_train = tk.BooleanVar(value=False)

        self.var_threads = tk.StringVar(value="4")
        self.var_stride = tk.StringVar(value="1")
        self.var_cooldown = tk.StringVar(value="0.50")
        self.var_min_dist = tk.StringVar(value="25")
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

        self.gpu_available = cv2.ocl.haveOpenCL()
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
        self.btn_lang.config(text="🌐 EN" if self.lang == "en" else "🌐 HU")
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
            font=(font_family, 10, "bold"),
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
            rowheight=30,
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
                s_name, background=bg_col, foreground=fg_col, font=fnt,
                padding=(12, 7), borderwidth=0, relief="flat"
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
            title_row, text=title_text, bg=P["bg_card"], fg=P["text_main"],
            font=(self.ui_font, 10, "bold")
        )
        lbl.pack(side="left")

        return outer, inner, lbl

    def _build_ui(self):
        P = self.PALETTE

        # ── TOP HEADER BAR ──────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=P["bg_card"], padx=20, pady=10, highlightthickness=1, highlightbackground=P["border"])
        header.pack(fill="x")

        header_left = tk.Frame(header, bg=P["bg_card"])
        header_left.pack(side="left", fill="y")

        title_line = tk.Frame(header_left, bg=P["bg_card"])
        title_line.pack(anchor="w")

        tk.Label(
            title_line, text="🦊 MOUSEANALYZER PRO", bg=P["bg_card"], fg=P["emerald"],
            font=(self.ui_font, 14, "bold")
        ).pack(side="left", padx=(0, 8))

        self.lbl_subtitle = tk.Label(
            title_line, text=self.tr("subtitle"),
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 11)
        )
        self.lbl_subtitle.pack(side="left")

        self.lbl_output_dir = tk.Label(
            header_left,
            text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}",
            bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 8)
        )
        self.lbl_output_dir.pack(anchor="w", pady=(2, 0))

        header_right = tk.Frame(header, bg=P["bg_card"])
        header_right.pack(side="right")

        self.btn_lang = ttk.Button(header_right, text="🌐 HU", command=self.toggle_language, style="Primary.TButton")
        self.btn_lang.pack(side="left", padx=(0, 6))

        self.btn_change_dir = ttk.Button(header_right, text=self.tr("btn_change_dir"), command=self.choose_output_folder, style="Ghost.TButton")
        self.btn_change_dir.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_change_dir, lambda: self.tr("tt_change_dir"))

        self.btn_open_dir = ttk.Button(header_right, text=self.tr("btn_open_dir"), command=self.open_results_folder, style="Wood.TButton")
        self.btn_open_dir.pack(side="left")
        ToolTip(self.btn_open_dir, lambda: self.tr("tt_open_dir"))

        # ── COMPACT KPI METRIC STRIP ────────────────────────────────────────
        kpi_strip = tk.Frame(self.root, bg=P["bg_main"], padx=20, pady=6)
        kpi_strip.pack(fill="x")

        yolo_tag = "YOLO+OpenCV GPU" if self.hybrid_locator.yolo_model is not None else "Spatial-Core + OpenCV GPU"
        self.kpi_vars = {
            "videos": tk.StringVar(value="0"),
            "calib": tk.StringVar(value="-"),
            "engine": tk.StringVar(value=yolo_tag),
            "dlc": tk.StringVar(value="SuperAnimal NN" if self.dlc_addon.dlc_available else "BBox + Vector AI")
        }

        self.kpi_title_labels = {}
        kpi_defs = [
            ("videos", "kpi_videos", self.kpi_vars["videos"], P["emerald"]),
            ("calib", "kpi_calib", self.kpi_vars["calib"], P["wood_amber"]),
            ("engine", "kpi_engine", self.kpi_vars["engine"], "#38BDF8"),
            ("dlc", "kpi_dlc", self.kpi_vars["dlc"], "#A78BFA"),
        ]

        for idx, (k_key, k_tr_key, k_var, k_col) in enumerate(kpi_defs):
            card = tk.Frame(kpi_strip, bg=P["bg_card"], padx=12, pady=6, highlightthickness=1, highlightbackground=P["border"])
            card.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 6, 0))
            lbl_t = tk.Label(card, text=self.tr(k_tr_key), bg=P["bg_card"], fg=P["text_muted"], font=(self.ui_font, 8, "bold"))
            lbl_t.pack(anchor="w")
            self.kpi_title_labels[k_key] = lbl_t
            tk.Label(card, textvariable=k_var, bg=P["bg_card"], fg=k_col, font=(self.ui_font, 10, "bold")).pack(anchor="w")

        # ── MAIN WORKSPACE CONTAINER ────────────────────────────────────────
        main_frame = tk.Frame(self.root, bg=P["bg_main"], padx=20, pady=2)
        main_frame.pack(fill="both", expand=True)

        # 1. VIDEO QUEUE CARD
        list_outer, list_card, self.lbl_sec1 = self._create_section_card(main_frame, self.tr("sec1_title"), P["emerald"])
        list_outer.pack(fill="both", expand=True, pady=(0, 8))

        toolbar = tk.Frame(list_card, bg=P["bg_card"])
        toolbar.pack(fill="x", pady=(0, 8))

        self.btn_add_vid = ttk.Button(toolbar, text=self.tr("btn_add_vid"), command=self.browse_videos, style="Emerald.TButton")
        self.btn_add_vid.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_add_vid, lambda: self.tr("tt_add_vid"))

        self.btn_edit_id = ttk.Button(toolbar, text=self.tr("btn_edit_id"), command=lambda: self.edit_animal_id(None), style="Ghost.TButton")
        self.btn_edit_id.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_edit_id, lambda: self.tr("tt_edit_id"))

        self.btn_remove_vid = ttk.Button(toolbar, text=self.tr("btn_remove_vid"), command=self.remove_selected_video, style="SoftRed.TButton")
        self.btn_remove_vid.pack(side="left", padx=(0, 6))
        ToolTip(self.btn_remove_vid, lambda: self.tr("tt_remove_vid"))

        self.btn_clear_vid = ttk.Button(toolbar, text=self.tr("btn_clear_vid"), command=self.clear_videos, style="Ghost.TButton")
        self.btn_clear_vid.pack(side="right")
        ToolTip(self.btn_clear_vid, lambda: self.tr("tt_clear_vid"))

        tree_container = tk.Frame(list_card, bg=P["border"], padx=1, pady=1)
        tree_container.pack(fill="both", expand=True)

        columns = ("filename", "animal_id", "status", "path")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=6, selectmode="browse")
        self.tree.heading("filename", text=self.tr("col_fname"))
        self.tree.heading("animal_id", text=self.tr("col_id"))
        self.tree.heading("status", text=self.tr("col_status"))
        self.tree.heading("path", text=self.tr("col_path"))

        self.tree.column("filename", width=260, anchor="w")
        self.tree.column("animal_id", width=140, anchor="center")
        self.tree.column("status", width=180, anchor="center")
        self.tree.column("path", width=320, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", self.edit_animal_id)

        # 2. CLEAN STREAMLINED EXECUTION & SETTINGS BAR
        ctrl_outer, control_card, self.lbl_sec2 = self._create_section_card(main_frame, self.tr("sec2_title"), P["wood_amber"])
        ctrl_outer.pack(fill="x", pady=(0, 8))

        top_ctrl_row = tk.Frame(control_card, bg=P["bg_card"])
        top_ctrl_row.pack(fill="x", pady=(0, 8))

        self.chk_auto_calib = ttk.Checkbutton(
            top_ctrl_row, text=self.tr("chk_auto_calib"), variable=self.var_auto_calib, style="Dark.TCheckbutton"
        )
        self.chk_auto_calib.pack(side="left", padx=(0, 14))
        ToolTip(self.chk_auto_calib, lambda: self.tr("tt_auto_calib"))

        self.chk_yolo_fusion = ttk.Checkbutton(
            top_ctrl_row, text=self.tr("chk_yolo_fusion"), variable=self.var_yolo_fusion, style="Dark.TCheckbutton"
        )
        self.chk_yolo_fusion.pack(side="left", padx=(0, 14))
        ToolTip(self.chk_yolo_fusion, lambda: self.tr("tt_yolo"))

        self.chk_rev = ttk.Checkbutton(
            top_ctrl_row, text=self.tr("chk_rev"), variable=self.var_enable_review, style="Dark.TCheckbutton"
        )
        self.chk_rev.pack(side="left", padx=(0, 14))
        ToolTip(self.chk_rev, lambda: self.tr("tt_rev"))

        self.lbl_gatecm = tk.Label(top_ctrl_row, text=self.tr("lbl_gatecm"), bg=P["bg_card"], fg=P["emerald"], font=(self.ui_font, 9, "bold"))
        self.lbl_gatecm.pack(side="left")
        self.spin_gate_cm = tk.Spinbox(
            top_ctrl_row, from_=5.0, to=500.0, increment=1.0, textvariable=self.var_gate_cm, width=5,
            font=(self.ui_font, 10, "bold"), bg=P["bg_panel"], fg=P["text_main"],
            insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat"
        )
        self.spin_gate_cm.pack(side="left", padx=(4, 10))
        ToolTip(self.spin_gate_cm, lambda: self.tr("tt_gatecm"))

        self.btn_settings = ttk.Button(
            top_ctrl_row, text=self.tr("btn_settings"), command=self.open_advanced_settings_dialog, style="Ghost.TButton"
        )
        self.btn_settings.pack(side="right")
        ToolTip(self.btn_settings, lambda: self.tr("tt_settings"))

        # Action Launch Row
        ctrl_top = tk.Frame(control_card, bg=P["bg_card"])
        ctrl_top.pack(fill="x")

        self.btn_start = ttk.Button(ctrl_top, text=self.tr("btn_start"), command=self.start_workflow, style="Emerald.TButton")
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ToolTip(self.btn_start, lambda: self.tr("tt_start"))

        self.btn_quick_start = ttk.Button(
            ctrl_top, text=self.tr("btn_quick"), command=self.start_quick_workflow, style="Teal.TButton"
        )
        self.btn_quick_start.pack(side="left", expand=True, fill="x", padx=6)
        ToolTip(self.btn_quick_start, lambda: self.tr("tt_quick"))

        self.btn_stop = ttk.Button(ctrl_top, text=self.tr("btn_stop"), command=self.stop_analysis, style="Danger.TButton", state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 0))
        ToolTip(self.btn_stop, lambda: self.tr("tt_stop"))

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
        log_outer, log_card, self.lbl_sec3 = self._create_section_card(main_frame, self.tr("sec3_title"), "#38BDF8")
        log_outer.pack(fill="both", expand=True, pady=(0, 8))

        self.log_area = scrolledtext.ScrolledText(
            log_card, wrap=tk.WORD, font=(self.mono_font, 9),
            height=5, state="disabled", bg=P["bg_main"], fg="#E2E8F0",
            insertbackground=P["emerald"], relief="flat", borderwidth=0
        )
        self.log_area.pack(fill="both", expand=True)

        self.log(
            f"{APP_NAME} v{APP_VERSION} Ready! | Async YOLO + Anatomical OpenCV Dip Gating Active."
        )

    # ==========================================================================
    # COLLAPSIBLE / POPUP ADVANCED SETTINGS WINDOW
    # ==========================================================================
    def open_advanced_settings_dialog(self):
        P = self.PALETTE
        win = tk.Toplevel(self.root)
        win.title(self.tr("settings_title"))
        win.geometry("680x440")
        win.configure(bg=P["bg_card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        container = tk.Frame(win, bg=P["bg_card"], padx=22, pady=18)
        container.pack(fill="both", expand=True)

        tk.Label(
            container, text=self.tr("settings_title"),
            bg=P["bg_card"], fg=P["emerald"], font=(self.ui_font, 12, "bold")
        ).pack(anchor="w", pady=(0, 12))

        chk_panel = tk.Frame(container, bg=P["bg_panel"], padx=14, pady=12, highlightthickness=1, highlightbackground=P["border"])
        chk_panel.pack(fill="x", pady=(0, 14))

        for tr_key, var, col in [
            ("chk_yolo_fusion", self.var_yolo_fusion, P["emerald"]),
            ("chk_zones", self.var_enable_zones, P["text_main"]),
            ("chk_kin", self.var_enable_kinematics, P["text_main"]),
            ("chk_gpu", self.var_use_gpu, "#38BDF8"),
            ("chk_kalman", self.var_use_kalman, "#6EE7B7"),
            ("chk_dlc_sa", self.var_dlc_superanimal, "#A78BFA"),
            ("chk_dlc_exp", self.var_dlc_export_train, "#FBBF24"),
        ]:
            cb = tk.Checkbutton(
                chk_panel, text=self.tr(tr_key), variable=var,
                bg=P["bg_panel"], fg=col, selectcolor=P["bg_main"],
                activebackground=P["bg_panel"], activeforeground=col,
                font=(self.ui_font, 9, "bold"), anchor="w"
            )
            cb.pack(fill="x", pady=2)

        num_panel = tk.Frame(container, bg=P["bg_main"], padx=14, pady=12, highlightthickness=1, highlightbackground=P["border"])
        num_panel.pack(fill="x", pady=(0, 14))

        def add_spin_item(parent, tr_key, var, from_, to_, inc, width=5):
            box = tk.Frame(parent, bg=P["bg_main"])
            box.pack(side="left", padx=(0, 14))
            tk.Label(box, text=self.tr(tr_key), bg=P["bg_main"], fg=P["text_muted"], font=(self.ui_font, 8, "bold")).pack(anchor="w")
            sp = tk.Spinbox(
                box, from_=from_, to=to_, increment=inc, textvariable=var, width=width,
                font=(self.ui_font, 10, "bold"), bg=P["bg_panel"], fg=P["text_main"],
                insertbackground=P["text_main"], buttonbackground=P["border"], relief="flat"
            )
            sp.pack(anchor="w", pady=(2, 0))

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
        self.lbl_subtitle.config(text=self.tr("subtitle"))
        self.lbl_output_dir.config(text=f"{self.tr('out_dir_prefix')} {self.output_base_dir}")
        self.btn_change_dir.config(text=self.tr("btn_change_dir"))
        self.btn_open_dir.config(text=self.tr("btn_open_dir"))
        self.btn_settings.config(text=self.tr("btn_settings"))

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
        self.chk_auto_calib.config(text=self.tr("chk_auto_calib"))
        self.chk_yolo_fusion.config(text=self.tr("chk_yolo_fusion"))
        self.chk_rev.config(text=self.tr("chk_rev"))
        self.lbl_gatecm.config(text=self.tr("lbl_gatecm"))

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
            cooldown_val = float(self.var_cooldown.get())
        except ValueError:
            cooldown_val = 0.50
        try:
            min_dist_val = int(self.var_min_dist.get())
        except ValueError:
            min_dist_val = 25
        try:
            gate_cm_val = float(self.var_gate_cm.get())
        except ValueError:
            gate_cm_val = 60.0
        try:
            stride_val = max(1, int(self.var_stride.get()))
        except ValueError:
            stride_val = 1

        return {
            "profile_version": "3.5",
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
            data["profile_version"] = "3.5"
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
        top.geometry("360x165")
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
        ttk.Button(top, text=self.tr("btn_save_enter"), command=save_id, style="Emerald.TButton").pack(pady=4)

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

    # ==========================================================================
    # PARALLEL YOLO + OPENCV SEGMENTATION WITH STRICT RUNG PROTECTION
    # ==========================================================================
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
        """
        Creates a rock-solid blue ladder mask covering the metallic rods and their bottom tips.
        Leaves the upper mouse torso corridor (>20px above fault line) completely clear.
        """
        if base_gray.ndim == 3:
            base_gray = cv2.cvtColor(base_gray, cv2.COLOR_BGR2GRAY)
        base_gray = np.squeeze(base_gray).astype(np.uint8)
        rh, rw = base_gray.shape[:2]

        _, dark_rungs = cv2.threshold(base_gray, ladder_thresh, 255, cv2.THRESH_BINARY_INV)

        blackhat = cv2.morphologyEx(base_gray, cv2.MORPH_BLACKHAT, self.kernel_blackhat_13)
        _, bh_mask = cv2.threshold(blackhat, max(15, int((205 - ladder_thresh) * 0.28)), 255, cv2.THRESH_BINARY)

        edges = cv2.Canny(base_gray, 45, 125)

        raw_rungs = cv2.bitwise_or(dark_rungs, cv2.bitwise_or(bh_mask, edges))
        closed_rungs = cv2.morphologyEx(raw_rungs, cv2.MORPH_CLOSE, self.kernel_rung_close)

        contours, _ = cv2.findContours(closed_rungs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        clean_ladder = np.zeros_like(base_gray)
        max_rung_start_y = int(fault_y_local + 4) if fault_y_local is not None else int(rh * 0.82)

        for c in contours:
            if cv2.contourArea(c) >= 18:
                x_c, y_c, w_c, h_c = cv2.boundingRect(c)
                if h_c > 38 and w_c < 18:
                    continue
                if y_c <= max_rung_start_y:
                    cv2.drawContours(clean_ladder, [c], -1, 255, -1)

        ladder_mask = cv2.dilate(clean_ladder, self.kernel_sag_guard, iterations=1)

        if fault_y_local is not None:
            upper_rod_y = max(5, int(fault_y_local) - max(42, int(rh * 0.155)))
            top_clear_y = max(5, int(fault_y_local) - 22)
            bottom_cutoff = min(rh, int(fault_y_local) + 22)
            upper_rods_tight = cv2.dilate(clean_ladder, self.kernel_small, iterations=1)
            ladder_mask[:upper_rod_y, :] = 0
            ladder_mask[upper_rod_y:top_clear_y, :] = upper_rods_tight[upper_rod_y:top_clear_y, :]
            ladder_mask[bottom_cutoff:, :] = 0
        else:
            top_clear_y = max(5, int(rh * 0.45))
            ladder_mask[:top_clear_y, :] = 0

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
        torso_corridor_y = max(14, int(fault_y_local) - 10)
        min_corridor_bottom = max(10, int(torso_corridor_y * 0.34))
        max_valid_torso_top = max(12, int(fault_y_local) - max(50, int(rh * 0.18)))
        min_torso_h = max(28, int(rh * 0.105))

        best_contour = None
        best_mask = None
        best_score = float("-inf")
        for candidate_mask, gate_bonus in candidate_masks:
            contours, _ = cv2.findContours(
                candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 300 or area > rw * rh * 0.65:
                    continue
                x, y, width, height = cv2.boundingRect(contour)
                upper_h = min(y + height, torso_corridor_y) - y
                aspect_ratio = width / max(1.0, float(height))
                # Reject flat rung-edge slivers, shadows hanging below rungs, and thin artifacts
                if (
                    width < 24
                    or height < min_torso_h
                    or upper_h < min_torso_h
                    or upper_h < height * 0.45
                    or y >= max_valid_torso_top
                    or (y + height) < min_corridor_bottom
                    or aspect_ratio < 0.42
                    or aspect_ratio > 10.5
                ):
                    continue
                # A real rodent torso has substantial body mass above the fault line
                if (y + height * 0.45) >= fault_y_local:
                    continue
                fill_ratio = area / max(1.0, float(width * height))
                if fill_ratio < 0.12:
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
                if p85_darkening < 26.0 and previous_bbox is None:
                    continue

                # Reject low-contrast ghost contours or table imperfections
                if (contrast < 11.0 or darkening < 7.5) and anchor_bbox is None and previous_bbox is None:
                    continue

                # Walking corridor vertical alignment bonus (animal walks right above the rungs)
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
        Computes a normalized pink/skin chromaticity index for rodent paws & snout tips
        without distorting background grayscale subtraction.
        """
        if crop_bgr is None or crop_bgr.ndim != 3 or crop_bgr.shape[2] < 3:
            return None
        b_ch = crop_bgr[:, :, 0].astype(np.float32)
        g_ch = crop_bgr[:, :, 1].astype(np.float32)
        r_ch = crop_bgr[:, :, 2].astype(np.float32)
        skin_idx = np.maximum(0.0, r_ch - g_ch) + 0.65 * np.maximum(0.0, r_ch - b_ch)
        return cv2.GaussianBlur(skin_idx, (3, 3), 0)

    def _detect_mouse_on_crop(
        self, crop, base_gray, inv_ladder_mask, rw, rh, dark_t, diff_t,
        fault_y_local=None, use_umat=False, u_base_smooth=None, u_inv_ladder=None,
        mog2_subtractor=None, stream_id=None, frame_idx=None, ai_max_age=3,
        previous_bbox=None, base_smooth_cached=None, return_skin=False, use_yolo=None
    ):
        """
        Parallel YOLO + Hysteresis Geodesic OpenCV Segmentation with Strict Rung & Table Imperfection Protection:
        1. Keeps pure grayscale (`gray_raw`) matched to `base_gray` so warm lighting never causes false diffs,
           while using `skin_index` specifically to rescue pink paws and snout tips.
        2. Suppresses pre-existing static background imperfections (dark knots, scratches, bolts, table edges)
           so they cannot self-reinforce or masquerade as the animal.
        3. Uses Hysteresis Geodesic Reconstruction so ONLY dark pixels physically connected to a genuine
           foreground/motion seed survive.
        4. Strictly enforces `inv_ladder_mask` at and near the rungs and masks out table surface noise below the dip zone.
        """
        if fault_y_local is None:
            fault_y_local = int(rh * 0.72)

        gray_raw = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        gray_raw = np.squeeze(gray_raw).astype(np.uint8)
        skin_index = self._compute_skin_chromaticity(crop)

        # Effective darkness map enhances pink paws/digits without corrupting background subtraction
        if skin_index is not None:
            gray_eff = np.clip(gray_raw.astype(np.float32) - 1.8 * skin_index, 0, 255).astype(np.uint8)
        else:
            gray_eff = gray_raw

        gray_raw_smooth = cv2.GaussianBlur(gray_raw, (3, 3), 0)
        gray_eff_smooth = cv2.GaussianBlur(gray_eff, (3, 3), 0)
        base_smooth = base_smooth_cached if base_smooth_cached is not None else cv2.GaussianBlur(base_gray, (3, 3), 0)

        # STEP 1: Locate animal & build spatial gate (YOLO + Hysteresis OpenCV Torso Core)
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

        # STEP 2: Compute pixel-level mouse mask with Static Imperfection Guard
        diff_dark = cv2.subtract(base_smooth, gray_raw_smooth)
        diff_abs = cv2.absdiff(base_smooth, gray_raw_smooth)
        if skin_index is not None:
            # Boost foreground difference where pink paw skin appears against the background
            diff_eff = np.clip(diff_dark.astype(np.float32) + 0.85 * skin_index, 0, 255).astype(np.uint8)
        else:
            diff_eff = diff_dark

        strict_diff_t = max(10, int(diff_t * 0.74))
        low_diff_t = max(6, int(diff_t * 0.36))
        blemish_diff_t = max(strict_diff_t + 14, int(diff_t * 1.55))

        # Identify pre-existing static dark spots / high-gradient imperfections in the empty background
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

        # Also capture high-contrast foreground (e.g., agouti/light fur edge) where background is clean
        _, strong_abs_mask = cv2.threshold(diff_abs, max(22, int(diff_t * 1.25)), 255, cv2.THRESH_BINARY)
        strong_abs_mask[static_blemish] = blemish_pass[static_blemish]
        _, body_dark_mask = cv2.threshold(gray_raw_smooth, min(220, dark_t + 12), 255, cv2.THRESH_BINARY_INV)
        raw_mask = cv2.bitwise_or(raw_mask, cv2.bitwise_and(strong_abs_mask, body_dark_mask))

        # Upper torso zone (strictly above the rungs): Hysteresis Geodesic Fur & Tail Reconstruction
        # Reconstruct dark torso/tail pixels connected to genuine foreground seeds while blocking static blemishes
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

        # Suppress deep table surface below the maximum possible paw reach (fault_y_local + 48px)
        max_reach_y = min(rh, int(fault_y_local) + max(38, int(rh * 0.24)))
        if max_reach_y < rh:
            raw_mask[max_reach_y:, :] = 0

        # STRICT RUNG PROTECTION: Subtract the ladder mask unconditionally!
        raw_mask = cv2.bitwise_and(raw_mask, inv_ladder_mask)

        clean_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, self.kernel_small)
        clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_CLOSE, self.kernel_horiz)
        clean_mask = cv2.bitwise_and(clean_mask, inv_ladder_mask)

        # Build candidate masks: prioritize spatially gated mask
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
            if return_skin:
                return False, None, None, skin_index
            return False, None, None

        # For paw & tail attachment, restrict to spatial_gate if available so distant noise is never attached
        attachment_source = cv2.bitwise_and(clean_mask, spatial_gate) if spatial_gate is not None else clean_mask
        contours, _ = cv2.findContours(
            attachment_source, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        final_mouse_mask = np.zeros_like(clean_mask)
        x_c, y_c, w_c, h_c = cv2.boundingRect(best_contour)
        cv2.drawContours(final_mouse_mask, [best_contour], -1, 255, -1)

        # Estimate tail-trimmed torso horizontal span for accurate paw attachment
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

        # Attach genuine paw slips beneath the torso+head core AND contiguous tail segments above the rungs
        for c in contours:
            if cv2.boundingRect(c) != (x_c, y_c, w_c, h_c):
                c_area = cv2.contourArea(c)
                if 10 <= c_area < 2200:
                    cx, cy, cw, ch = cv2.boundingRect(c)
                    center_x = cx + cw / 2.0
                    body_x_min = torso_x1 - max(6, int(torso_w * 0.05))
                    body_x_max = torso_x2 + max(8, int(torso_w * 0.08))
                    max_paw_y = min(max_reach_y, max(y_c + h_c + 34, int(fault_y_local) + int(rh * 0.26)))
                    # 1. Tail segment above the ladder rungs adjacent to the body bounding box
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
                    # 2. Paw / snout dip under the torso+head core (ignore flat horizontal shelf reflections)
                    if cw > ch * 1.9 or ch < 4:
                        continue
                    if body_x_min <= center_x <= body_x_max and y_c <= cy <= max_paw_y:
                        cv2.drawContours(final_mouse_mask, [c], -1, 255, -1)
                        min_x = min(min_x, cx)
                        min_y = min(min_y, cy)
                        max_x = max(max_x, cx + cw)
                        max_y = max(max_y, cy + ch)

        # Smooth ONLY the upper torso (above the rungs) so the mouse body is solid green,
        # while the rung/fault zone stays 100% faithful to `inv_ladder_mask`!
        upper_cut = max(10, int(fault_y_local) - 16)
        final_mouse_mask[:upper_cut, :] = cv2.morphologyEx(
            final_mouse_mask[:upper_cut, :], cv2.MORPH_CLOSE, self.kernel_upper_bridge
        )
        final_mouse_mask[upper_cut:, :] = cv2.bitwise_and(
            final_mouse_mask[upper_cut:, :], inv_ladder_mask[upper_cut:, :]
        )

        # Recompute tight bounding box from the cleaned final_mouse_mask
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
        return cv2.countNonZero(diff_mask) > 110

    def _extract_rodent_anatomy(self, mouse_mask, fault_curve, bbox, previous_bbox=None, move_dir=1.0):
        """
        Extracts a high-precision articulated rodent skeleton and tail-trimmed Torso+Head Core
        using Distance-Transform Medial Ridge tracking, Dorsal/Ventral contour envelopes, and
        automatic Tail-vs-Snout orientation detection:
        - Axial Spine Chain: `tail_tip` -> `tail_mid` -> `tail_base` -> `hip_pt` -> `spine_mid` -> `shoulder_pt` -> `head_pt` -> `nose_pt`
        - Ventral Limb Keypoints: `hind_paw_pt` (under hip corridor) & `fore_paw_pt` (under shoulder corridor)
        - `torso_left_x`, `torso_width` (unaffected by long thin tail)
        - `head_pitch_down` (True when the snout/head pitches downward toward the ladder gaps)
        """
        mh, mw = mouse_mask.shape[:2]
        if bbox is None:
            ys, xs = np.where(mouse_mask > 0)
            if len(xs) == 0:
                return None
            bx, by = int(np.min(xs)), int(np.min(ys))
            bw, bh = int(np.max(xs) - bx + 1), int(np.max(ys) - by + 1)
        else:
            bx, by, bw, bh = bbox

        has_motion_dir = False
        if previous_bbox is not None:
            prev_cx = previous_bbox[0] + previous_bbox[2] / 2.0
            curr_cx = bx + bw / 2.0
            if abs(curr_cx - prev_cx) > 2.5:
                move_dir = 1.0 if (curr_cx - prev_cx) >= 0 else -1.0
                has_motion_dir = True

        torso_limit = max(12, min(mh, int(np.min(fault_curve)) - 2))
        bx_end = min(mw, bx + bw)
        upper_mask = mouse_mask[:torso_limit, bx:bx_end]
        if upper_mask.size == 0:
            return None

        # Separate thick Torso+Head from thin Tail using morphological opening + vertical column thickness
        torso_open = cv2.morphologyEx(upper_mask, cv2.MORPH_OPEN, self.kernel_torso_open)
        col_thickness = np.sum(torso_open > 0, axis=0)
        if col_thickness.size == 0 or np.max(col_thickness) < 6:
            col_thickness = np.sum(upper_mask > 0, axis=0)

        min_torso_thick = max(6, int(np.max(col_thickness) * 0.28)) if col_thickness.size > 0 else 6
        thick_cols = np.where(col_thickness >= min_torso_thick)[0]

        if len(thick_cols) >= 10:
            torso_left_x = bx + int(thick_cols[0])
            torso_right_x = bx + int(thick_cols[-1]) + 1
        else:
            torso_left_x = bx
            torso_right_x = bx_end
        torso_width = max(20, torso_right_x - torso_left_x)

        # Automatic Morphological Tail-vs-Snout Orientation Detection:
        # A thin tail extending from the left of the torso core means the animal faces RIGHT (+1.0);
        # a thin tail extending from the right of the torso core means the animal faces LEFT (-1.0)!
        t_x0 = max(0, torso_left_x - bx)
        t_x1 = min(upper_mask.shape[1], torso_right_x - bx)
        left_tail_ext = int(t_x0)
        right_tail_ext = int(upper_mask.shape[1] - t_x1)

        if abs(left_tail_ext - right_tail_ext) >= 42:
            morph_dir = 1.0 if left_tail_ext > right_tail_ext else -1.0
            # Only override an active motion direction when a true long tail (>68px) extends behind the torso
            if not has_motion_dir or abs(left_tail_ext - right_tail_ext) >= 68:
                move_dir = morph_dir
        elif not has_motion_dir and (t_x1 - t_x0) >= 24:
            # Fallback when tail is hidden: compare left vs. right third thickness (rump is thicker than snout)
            third = max(6, (t_x1 - t_x0) // 3)
            left_mass = float(np.mean(col_thickness[t_x0:t_x0 + third]))
            right_mass = float(np.mean(col_thickness[t_x1 - third:t_x1]))
            if abs(left_mass - right_mass) > 3.5:
                move_dir = 1.0 if left_mass > right_mass else -1.0

        # Compute Distance-Transform Medial Ridge inside the tail-trimmed torso+head core
        torso_crop = upper_mask[:, t_x0:t_x1]
        dist_crop = cv2.distanceTransform((torso_crop > 0).astype(np.uint8), cv2.DIST_L2, 3)

        ty, tx = np.where(torso_crop > 0)
        fallback_y = float(np.mean(ty)) if len(ty) > 0 else float(by + bh * 0.45)

        if move_dir >= 0:
            rump_x = float(torso_left_x)
            snout_x = float(torso_right_x - 1)
        else:
            rump_x = float(torso_right_x - 1)
            snout_x = float(torso_left_x)
        span_x = snout_x - rump_x

        def sample_anatomical_joint(rel_norm, dorsal_bias=0.0, window_frac=0.06):
            """Samples the distance-transform weighted medial spine Y at normalized torso position `rel_norm` [0=rump .. 1=snout]."""
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
        hip_pt = sample_anatomical_joint(0.24, dorsal_bias=0.08)
        spine_mid = sample_anatomical_joint(0.46, dorsal_bias=0.28)
        shoulder_pt = sample_anatomical_joint(0.64, dorsal_bias=0.08)
        head_pt = sample_anatomical_joint(0.82, dorsal_bias=0.0)
        nose_pt = sample_anatomical_joint(0.98, dorsal_bias=-0.22, window_frac=0.035)

        # If the anterior head/snout pitches downward into the rung gaps, track nose_pt down to the snout tip
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

        # True posterior tail tip & mid-tail keypoints (if tail extends behind torso_left_x / torso_right_x)
        tail_tip = tail_base
        tail_mid = tail_base
        if move_dir >= 0 and t_x0 > 4:
            tail_strip = upper_mask[:, :t_x0]
            t_ys, t_xs = np.where(tail_strip > 0)
            if len(t_xs) >= 4:
                min_tx = int(np.min(t_xs))
                tip_ys = t_ys[t_xs <= min_tx + 4]
                tail_tip = (int(bx + min_tx), int(round(np.mean(tip_ys))))
                mid_tx = (min_tx + t_x0) // 2
                mid_ys = t_ys[np.abs(t_xs - mid_tx) <= 4]
                if len(mid_ys) > 0:
                    tail_mid = (int(bx + mid_tx), int(round(np.mean(mid_ys))))
                else:
                    tail_mid = ((tail_tip[0] + tail_base[0]) // 2, (tail_tip[1] + tail_base[1]) // 2)
        elif move_dir < 0 and t_x1 < upper_mask.shape[1] - 4:
            tail_strip = upper_mask[:, t_x1:]
            t_ys, t_xs = np.where(tail_strip > 0)
            if len(t_xs) >= 4:
                max_tx = int(np.max(t_xs))
                tip_ys = t_ys[t_xs >= max_tx - 4]
                tail_tip = (int(bx + t_x1 + max_tx), int(round(np.mean(tip_ys))))
                mid_tx = max_tx // 2
                mid_ys = t_ys[np.abs(t_xs - mid_tx) <= 4]
                if len(mid_ys) > 0:
                    tail_mid = (int(bx + t_x1 + mid_tx), int(round(np.mean(mid_ys))))
                else:
                    tail_mid = ((tail_tip[0] + tail_base[0]) // 2, (tail_tip[1] + tail_base[1]) // 2)

        # Ventral Forelimb & Hindlimb Keypoints (tracks paws on the rungs and during slips below the rungs)
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
        fore_paw_pt = sample_ventral_paw(0.45, 0.73, shoulder_pt)

        spine_chain = [tail_tip, tail_mid, tail_base, hip_pt, spine_mid, shoulder_pt, head_pt, nose_pt]

        # Check if the anterior head/snout region pitches downward compared to the thoracic/shoulder line
        head_pitch_down = bool(snout_pitched_down)
        if (nose_pt[1] - shoulder_pt[1] >= 4 and head_pt[1] - spine_mid[1] >= 4) or len(tx) > 20:
            if len(tx) > 20:
                rel_x = (tx / max(1.0, float(torso_width))) if move_dir >= 0 else (1.0 - tx / max(1.0, float(torso_width)))
                mid_mask = (rel_x >= 0.30) & (rel_x <= 0.65)
                ant_mask = rel_x >= 0.78
                if np.any(mid_mask) and np.any(ant_mask):
                    mid_bottom_y = float(np.percentile(ty[mid_mask], 85))
                    ant_bottom_y = float(np.percentile(ty[ant_mask], 85))
                    ant_top_y = float(np.percentile(ty[ant_mask], 15))
                    mid_top_y = float(np.percentile(ty[mid_mask], 15))
                    if (ant_bottom_y - mid_bottom_y >= 4.2) and (ant_top_y - mid_top_y >= 3.2):
                        head_pitch_down = True

        return {
            "torso_left_x": int(torso_left_x),
            "torso_right_x": int(torso_right_x),
            "torso_width": int(torso_width),
            "move_dir": float(move_dir),
            "tail_tip": tail_tip,
            "tail_base": tail_base,
            "hip_pt": hip_pt,
            "spine_mid": spine_mid,
            "shoulder_pt": shoulder_pt,
            "head_pt": head_pt,
            "nose_pt": nose_pt,
            "hind_paw_pt": hind_paw_pt,
            "fore_paw_pt": fore_paw_pt,
            "spine_chain": spine_chain,
            "head_pitch_down": bool(head_pitch_down),
        }

    @staticmethod
    def _draw_rodent_skeleton(disp, anat, offset_x=0, offset_y=0):
        """Renders the articulated 9-point rodent skeleton (tail, arched spine, head, snout, forelimb, hindlimb)."""
        if anat is None:
            return
        ox, oy = int(offset_x), int(offset_y)

        def sh(pt):
            return (int(pt[0]) + ox, int(pt[1]) + oy)

        # 1. Draw Hindlimb & Forelimb vectors first (underneath spine joints)
        if "hip_pt" in anat and "hind_paw_pt" in anat:
            p_hip, p_hpaw = sh(anat["hip_pt"]), sh(anat["hind_paw_pt"])
            cv2.line(disp, p_hip, p_hpaw, (0, 140, 255), 2, cv2.LINE_AA)
            cv2.circle(disp, p_hpaw, 4, (0, 100, 255), -1, cv2.LINE_AA)
        if "shoulder_pt" in anat and "fore_paw_pt" in anat:
            p_sh, p_fpaw = sh(anat["shoulder_pt"]), sh(anat["fore_paw_pt"])
            cv2.line(disp, p_sh, p_fpaw, (80, 255, 160), 2, cv2.LINE_AA)
            cv2.circle(disp, p_fpaw, 4, (0, 230, 140), -1, cv2.LINE_AA)

        # 2. Draw Axial Spine Chain (TailTip -> TailBase -> Hip -> SpineMid -> Shoulder -> Head -> Nose)
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
            bone_col = (185, 185, 185) if i_p == 0 and len(pts_global) >= 6 else (255, 225, 0)
            cv2.line(disp, pts_global[i_p], pts_global[i_p + 1], bone_col, 2, cv2.LINE_AA)

        # 3. Draw Joint Keypoints
        joint_styles = [
            ("tail_tip", (160, 160, 160), 3),
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
        """
        Gates the below-rung mask to the active torso+head corridor (excluding the tail behind the rump)
        without creating a blind spot between the hindlimb and forelimb zones.
        """
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

        # Allow the continuous limb + snout corridor under the tail-trimmed body,
        # while cutting off the tail behind the rump so tail sag never triggers false foot faults.
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
        skin_map=None, valid_x_bounds=None
    ):
        """
        Detects and anatomically classifies below-line events in real time:
        - Rejects flat horizontal plexiglass reflections (`sw > sh * 2.0`) and detached rod tips.
        - Extracts anatomical position along the tail-trimmed torso core, paw skin chromaticity,
          and head pitch to immediately distinguish PAW slips (`MELLSŐ/HÁTSÓ LÁB`) from
          NOSE exploration (`ORR (Exploráció)`) and `HIND_TAIL`.
        - Prioritizes genuine PAW slips if both a nose poke and a paw slip occur simultaneously!
        """
        mh, mw = final_mouse_mask.shape[:2]
        if isinstance(fault_y_or_curve, np.ndarray) and fault_y_or_curve.ndim == 1:
            fault_curve = np.clip(fault_y_or_curve[:mw], 0, mh - 1).astype(np.int32)
        else:
            fault_curve = np.full(mw, int(fault_y_or_curve), dtype=np.int32)

        anatomy = self._extract_rodent_anatomy(
            final_mouse_mask, fault_curve, bbox, previous_bbox=previous_bbox, move_dir=move_dir
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
            "dlc_part": "MANCS (Lábhiba)",
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

        if skin_map is None and crop is not None:
            skin_map = self._compute_skin_chromaticity(crop)
        gray_eff = None
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
            if c_area < 12:
                continue
            sx, sy, sw, sh = cv2.boundingRect(sc)
            # Reject flat horizontal shelf/edge artifacts!
            if sw > sh * 2.0:
                continue

            pts = sc.reshape(-1, 2)
            xs = np.clip(pts[:, 0], 0, mw - 1)
            ys = pts[:, 1]
            depths = ys - fault_curve[xs]
            max_idx = int(np.argmax(depths))
            depth_val = int(depths[max_idx])
            if depth_val < 5:
                continue

            dip_x_local = int(xs[max_idx])
            dip_y_local = int(ys[max_idx])

            skin_score = 0.0
            if skin_map is not None:
                patch_skin = skin_map[sy:min(mh, sy + sh), sx:min(mw, sx + sw)]
                if patch_skin.size > 0:
                    skin_score = float(np.percentile(patch_skin, 80))

            # Verify vertical continuity across the fault line (rejects floating rod tips / blemishes separated by bright air)
            if gray_eff is not None:
                f_y_at_dip = int(fault_curve[dip_x_local])
                cy1, cy2 = max(0, f_y_at_dip - 10), min(mh, f_y_at_dip + 1)
                cx1, cx2 = max(0, dip_x_local - 5), min(mw, dip_x_local + 6)
                if cy2 > cy1 and cx2 > cx1:
                    cross_band = gray_eff[cy1:cy2, cx1:cx2]
                    row_min_g = np.min(cross_band, axis=1)
                    neck_max_g = int(np.max(row_min_g))
                    if neck_max_g > 170:
                        if skin_score < 14.0 or float(np.percentile(row_min_g, 75)) > 165.0:
                            continue

            # Check wedge shape (nose pokes are wider at the fault line than at the tip)
            top_pts_x = xs[ys <= ( np.min(ys) + max(2, int(sh * 0.35)) )]
            top_w = float(np.max(top_pts_x) - np.min(top_pts_x) + 1) if len(top_pts_x) > 0 else float(sw)
            aspect = max(float(sw), top_w) / max(1.0, float(sh))

            if eff_dir >= 0:
                rel_pos_norm = (dip_x_local - t_left) / t_width
            else:
                rel_pos_norm = ((t_left + t_width) - dip_x_local) / t_width

            part_label, part_code = DLCAddonManager.classify_dip_features(
                rel_pos_norm, aspect, float(depth_val), skin_score, head_pitch
            )

            # Prioritize true PAW foot faults over simultaneous nose/tail pokes
            type_bonus = 25.0 if part_code == "PAW" else (5.0 if part_code == "NOSE" else 0.0)
            priority_score = type_bonus + float(depth_val) + 0.15 * skin_score

            if priority_score > best_priority_score:
                best_priority_score = priority_score
                meta = {
                    "dlc_part": part_label,
                    "dlc_code": part_code,
                    "rel_pos_norm": float(rel_pos_norm),
                    "paw_skin_score": float(skin_score),
                    "head_pitch_down": bool(head_pitch),
                    "torso_left_x": int(t_left),
                    "torso_width": int(t_width),
                    "move_dir": float(eff_dir),
                    "anatomy": anatomy,
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
        cv2.rectangle(result, (leg_x - 10, 12), (w - 15, 52), (30, 30, 30), -1)
        cv2.putText(result, "Path:", (leg_x, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(result, "SLOW (Red)", (leg_x + 60, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 50, 255), 2)
        cv2.putText(result, "->", (leg_x + 165, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1)
        cv2.putText(result, "FAST (Green)", (leg_x + 195, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (50, 255, 50), 2)

        return result

    # ==========================================================================
    # EVENT-DRIVEN CALIBRATION WINDOW (0% IDLE CPU / NO OVERHEATING)
    # ==========================================================================
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
            vp_roi = OpenCVZoomPanViewport(frame_w, frame_h)
            win_roi = "1. Select ROI (Drag Left=Box, Wheel=Zoom, RightDrag=Pan, ENTER=Confirm)"
            cv2.namedWindow(win_roi, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(win_roi, min(1150, frame_w), min(750, frame_h))

            roi_pts = [None, None]
            drawing_roi = [False]

            def roi_mouse_cb(event, x, y, flags, param):
                if vp_roi.handle_mouse(event, x, y, flags):
                    return
                ix, iy = vp_roi.screen_to_image(x, y)
                if event == cv2.EVENT_LBUTTONDOWN:
                    drawing_roi[0] = True
                    roi_pts[0] = (ix, iy)
                    roi_pts[1] = (ix, iy)
                    vp_roi.dirty = True
                elif event == cv2.EVENT_MOUSEMOVE and drawing_roi[0]:
                    roi_pts[1] = (ix, iy)
                    vp_roi.dirty = True
                elif event == cv2.EVENT_LBUTTONUP:
                    drawing_roi[0] = False
                    roi_pts[1] = (ix, iy)
                    vp_roi.dirty = True

            cv2.setMouseCallback(win_roi, roi_mouse_cb)
            while True:
                if not is_window_open(win_roi):
                    break
                if vp_roi.dirty:
                    canvas = first_frame.copy()
                    cv2.putText(
                        canvas, "Drag Left Mouse = ROI Box | Mouse Wheel = Zoom | ENTER = Confirm",
                        (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2
                    )
                    if roi_pts[0] and roi_pts[1]:
                        cv2.rectangle(canvas, roi_pts[0], roi_pts[1], (0, 255, 180), 2)
                    cv2.imshow(win_roi, vp_roi.render(canvas))
                    vp_roi.dirty = False

                k = cv2.waitKey(50) & 0xFF
                if k in (13, 32):
                    break
                elif k in (ord('r'), ord('R')):
                    vp_roi.reset()
                elif k == 27:
                    close_opencv_windows()
                    cap.release()
                    self.reset_ui()
                    return
            close_opencv_windows()

            if roi_pts[0] and roi_pts[1]:
                x1, y1 = roi_pts[0]
                x2, y2 = roi_pts[1]
                rx, ry = min(x1, x2), min(y1, y2)
                rw, rh = abs(x2 - x1), abs(y2 - y1)
            else:
                rx, ry, rw, rh = 0, 0, 0, 0
            if rw < 40 or rh < 30:
                rx, ry, rw, rh = 0, 0, frame_w, frame_h

            left_gate_x = int(rx + rw * 0.10)
            right_gate_x = int(rx + rw * 0.86)

        base_gray = self._compute_clean_background(cap, rx, ry, rw, rh, num_samples=28)
        if base_gray is None:
            cap.release()
            self.reset_ui()
            return

        if start_preview_frame is None:
            start_preview_frame = self._find_best_mouse_preview_frame(cap, base_gray, rx, ry, rw, rh, total_frames)

        win_calib = "Calibration Preview (Wheel=Zoom, RightDrag=Pan, LeftClick=Move Gate, ENTER=Start)"
        cv2.namedWindow(win_calib, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_calib, min(1180, frame_w), min(820, frame_h + 120))

        vp_calib = OpenCVZoomPanViewport(frame_w, frame_h)

        def on_trackbar_change(val):
            vp_calib.dirty = True

        cv2.createTrackbar("Frame", win_calib, int(start_preview_frame), max(1, total_frames - 1), on_trackbar_change)
        cv2.createTrackbar("Brightness", win_calib, self.calib_dark_thresh, 220, on_trackbar_change)
        cv2.createTrackbar("Motion Diff", win_calib, self.calib_diff_thresh, 100, on_trackbar_change)
        cv2.createTrackbar("Rung Mask", win_calib, self.calib_ladder_thresh, 200, on_trackbar_change)
        cv2.createTrackbar("Fault Line %", win_calib, self.calib_fault_Ratio, 96, on_trackbar_change)

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
            if not is_window_open(win_calib):
                close_opencv_windows()
                cap.release()
                self.reset_ui()
                return

            f_idx = max(0, cv2.getTrackbarPos("Frame", win_calib))
            dark_t = max(50, cv2.getTrackbarPos("Brightness", win_calib))
            diff_t = max(8, cv2.getTrackbarPos("Motion Diff", win_calib))
            ladder_t = max(30, cv2.getTrackbarPos("Rung Mask", win_calib))
            fault_pct = max(25, cv2.getTrackbarPos("Fault Line %", win_calib))

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
                cv2.line(disp, (left_gate_x, ry), (left_gate_x, ry + rh), (255, 50, 50), 2)
                cv2.line(disp, (right_gate_x, ry), (right_gate_x, ry + rh), (255, 50, 50), 2)
                cv2.putText(
                    disp, "BLUE=Strict Rung Guard | GREEN=YOLO+OpenCV Mouse | RED=Fault Line | ENTER=Start",
                    (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2
                )

                cached_disp = disp
                last_params = curr_params
                vp_calib.dirty = True

            if vp_calib.dirty:
                cv2.imshow(win_calib, vp_calib.render(cached_disp))
                vp_calib.dirty = False

            key = cv2.waitKey(60) & 0xFF
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
            dip_min_dist_px = 25

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
            self.var_use_kalman.get()
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

    # ==========================================================================
    # GPU-ACCELERATED PARALLEL VIDEO ANALYSIS (UMat + CACHED LADDER MASK)
    # ==========================================================================
    def execute_parallel_processing(self, video_data, roi_data, max_workers):
        lock = threading.Lock()
        total_videos = len(video_data)

        (rx, ry, rw, rh, left_gate_x, right_gate_x, dark_t, diff_t,
         ladder_t, fault_pct, z_active, kin_active,
         dip_cooldown_sec, dip_min_dist_px, gate_dist_cm, px_per_cm, frame_stride, use_gpu, use_kalman) = roi_data

        gpu_active = bool(use_gpu and self.gpu_available)
        cv2.ocl.setUseOpenCL(gpu_active)

        try:
            cpu_cores = os.cpu_count() or 4
            cv2.setNumThreads(max(1, cpu_cores // max(1, min(max_workers, total_videos))))
        except Exception:
            pass

        try:
            use_yolo_fusion = bool(self.var_yolo_fusion.get())
        except (RuntimeError, tk.TclError):
            use_yolo_fusion = True

        self.log(
            f"\n---> TURBO Engine started ({max_workers} threads, Stride={frame_stride}, "
            f"GPU OpenCL={'ON' if gpu_active else 'OFF'}, YOLO+OpenCV Spatial Gate={'ON' if use_yolo_fusion else 'OFF'}) | Scale: {px_per_cm:.2f} px/cm"
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
            in_dip_event_by_type = {"PAW": False, "NOSE": False, "HIND_TAIL": False}
            last_dip_sec_by_type = {"PAW": -999.0, "NOSE": -999.0, "HIND_TAIL": -999.0}
            last_dip_x_by_type = {"PAW": -999, "NOSE": -999, "HIND_TAIL": -999}

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

                    if elastic_tracker is not None and state == "RUNNING":
                        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        active_base_gray, active_inv_ladder, active_fault_target = elastic_tracker.update(
                            crop_gray, mouse_bbox_local=last_bbox_local
                        )
                        active_base_smooth = (
                            base_smooth_static if active_base_gray is base_gray
                            else cv2.GaussianBlur(active_base_gray, (3, 3), 0)
                        )
                    else:
                        active_base_gray = base_gray
                        active_inv_ladder = inv_ladder_mask
                        active_fault_target = fault_y_local
                        active_base_smooth = base_smooth_static

                    # Only use previous_bbox stationary rescue during an active run so static table spots never self-lock
                    previous_bbox_local = last_bbox_local if state == "RUNNING" else None
                    mouse_detected, final_mouse_mask, bbox, skin_idx_map = self._detect_mouse_on_crop(
                        crop, active_base_gray, active_inv_ladder, v_rw, v_rh, dark_t, diff_t,
                        fault_y_local=fault_y_local,
                        use_umat=gpu_active, u_base_smooth=u_base_smooth, u_inv_ladder=u_inv_ladder,
                        mog2_subtractor=None, stream_id=uid, frame_idx=frame_idx,
                        ai_max_age=max(12, frame_stride * 12), previous_bbox=previous_bbox_local,
                        base_smooth_cached=active_base_smooth, return_skin=True, use_yolo=use_yolo_fusion
                    )
                    if mouse_detected:
                        last_bbox_local = bbox
                        bbox_miss_count = 0
                    else:
                        bbox_miss_count += 1
                        if bbox_miss_count > max(4, frame_stride * 4):
                            last_bbox_local = None

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
                            in_dip_event_by_type = {"PAW": False, "NOSE": False, "HIND_TAIL": False}
                            last_dip_sec_by_type = {"PAW": -999.0, "NOSE": -999.0, "HIND_TAIL": -999.0}
                            last_dip_x_by_type = {"PAW": -999, "NOSE": -999, "HIND_TAIL": -999}

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
                            cv2.copyTo(cv2.min(current_run_roi, crop), paint_mask, current_run_roi)

                            # Estimate current locomotion direction from recent trajectory
                            curr_move_dir = 1.0
                            if len(trajectory) >= 2:
                                recent_dx = trajectory[-1][0] - trajectory[max(0, len(trajectory) - 6)][0]
                                if abs(recent_dx) > 3:
                                    curr_move_dir = 1.0 if recent_dx > 0 else -1.0

                            valid_ladder_bounds = (
                                max(int(v_rw * 0.050), (left_gate_x - 95) - v_rx),
                                min(int(v_rw * 0.915), (right_gate_x + 95) - v_rx),
                            )
                            is_dip, dip_x_loc, dip_y_loc, dip_aspect, dip_depth, dip_meta = self._check_real_dip_below_line(
                                final_mouse_mask, active_fault_target, crop=crop, bbox=bbox,
                                previous_bbox=previous_bbox_local, inv_ladder_mask=active_inv_ladder,
                                move_dir=curr_move_dir, return_meta=True, skin_map=skin_idx_map,
                                valid_x_bounds=valid_ladder_bounds
                            )
                            if is_dip:
                                dip_code = dip_meta.get("dlc_code", "PAW")
                                dip_part = dip_meta.get("dlc_part", "MANCS (Lábhiba)")
                                for other_k in in_dip_event_by_type:
                                    if other_k != dip_code:
                                        in_dip_event_by_type[other_k] = False

                                dip_x_glob = v_rx + dip_x_loc
                                dip_y_glob = v_ry + dip_y_loc
                                time_since_last_dip = current_sec - last_dip_sec_by_type.get(dip_code, -999.0)
                                dist_from_last_dip = abs(dip_x_glob - last_dip_x_by_type.get(dip_code, -999))

                                if (not in_dip_event_by_type.get(dip_code, False)) and (time_since_last_dip >= dip_cooldown_sec) and (
                                    dist_from_last_dip >= dip_min_dist_px or time_since_last_dip >= dip_cooldown_sec * 1.8
                                ):
                                    in_dip_event_by_type[dip_code] = True
                                    last_dip_sec_by_type[dip_code] = current_sec
                                    last_dip_x_by_type[dip_code] = dip_x_glob

                                    body_left_glob = v_rx + bbox[0]
                                    body_width_px = max(25, bbox[2])
                                    torso_left_glob = v_rx + dip_meta.get("torso_left_x", bbox[0])
                                    torso_width_px = max(22, dip_meta.get("torso_width", bbox[2]))

                                    dip_events.append({
                                        "x": dip_x_glob,
                                        "y": dip_y_glob,
                                        "sec": current_sec,
                                        "dip_aspect": dip_aspect,
                                        "dip_depth": dip_depth,
                                        "body_left_x": body_left_glob,
                                        "body_width": body_width_px,
                                        "torso_left_x": torso_left_glob,
                                        "torso_width": torso_width_px,
                                        "paw_skin_score": dip_meta.get("paw_skin_score", 0.0),
                                        "head_pitch_down": dip_meta.get("head_pitch_down", False),
                                        "move_dir": dip_meta.get("move_dir", curr_move_dir),
                                        "anatomy": dip_meta.get("anatomy"),
                                        "roi_offset": (v_rx, v_ry),
                                        "frame_buf": encode_frame_compressed(frame),
                                        "valid": True,
                                        "save_crop": False,
                                        "dlc_part": dip_part,
                                        "dlc_code": dip_code
                                    })
                            else:
                                for k_type in in_dip_event_by_type:
                                    in_dip_event_by_type[k_type] = False

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

                            mouse_front_edge_x = v_rx + bbox[0] + bbox[2]
                            if mouse_x_global >= right_gate_x or (mouse_front_edge_x >= right_gate_x + 15 and mouse_x_global >= right_gate_x - 35):
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
                                    full_clean_canvas[v_ry:v_ry + v_rh, v_rx:v_rx + v_rw] = current_run_roi

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

                                    paw_cnt_live = sum(1 for d_ev in dip_events if d_ev.get("dlc_code") == "PAW")
                                    nose_cnt_live = sum(1 for d_ev in dip_events if d_ev.get("dlc_code") == "NOSE")
                                    self.log(
                                        f"   ✔ [#{animal_id}] Run #{run_count} DONE: "
                                        f"Time={transit_time:.2f}s | PawFaults={paw_cnt_live} | Explorations={nose_cnt_live} | "
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
                                run_count = max(0, run_count - 1)
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
        try:
            if self.is_running and self.var_enable_review.get() and total_dips_found > 0:
                self.root.after(0, self.open_review_window)
            else:
                self.root.after(0, self.finalize_and_export_all)
        except (RuntimeError, tk.TclError):
            self.finalize_and_export_all()

    # ==========================================================================
    # INTERACTIVE DIP INSPECTOR WITH SCROLL-WHEEL ZOOM & DRAG PAN
    # ==========================================================================
    def open_review_window(self):
        P = self.PALETTE
        rev_win = tk.Toplevel(self.root)
        rev_win.title(f"{APP_NAME} — Interactive Dip & Pose Inspector (Scroll = Zoom)")
        rev_win.geometry("1220x800")
        rev_win.configure(bg=P["bg_main"])
        rev_win.transient(self.root)
        rev_win.grab_set()
        rev_win.lift()
        rev_win.focus_force()

        top_banner = tk.Frame(rev_win, bg=P["bg_card"], padx=18, pady=8, highlightthickness=1, highlightbackground=P["border"])
        top_banner.pack(fill="x")
        tk.Label(
            top_banner,
            text="🖱 GÖRGŐ = Belenagyítás (Zoom)  |  Bal Egérgomb Húzás = Kép Mozgatása  |  [R] = Zoom Alaphelyzet  |  [SPACE] = Érvényes/Törölt  |  [T] = Testrész Váltás  |  [ENTER] = Mentés",
            bg=P["bg_card"], fg=P["emerald"], font=(self.ui_font, 9, "bold")
        ).pack(anchor="w")

        body = tk.Frame(rev_win, bg=P["bg_main"], padx=16, pady=10)
        body.pack(fill="both", expand=True)

        left_outer, left_panel, _ = self._create_section_card(body, "Detektált Lenyúlások", P["emerald"])
        left_outer.pack(side="left", fill="y", padx=(0, 12))

        cols = ("ego", "run", "sec", "part", "valid", "save")
        dip_tree = ttk.Treeview(left_panel, columns=cols, show="headings", height=20, selectmode="browse")
        dip_tree.heading("ego", text="ID")
        dip_tree.heading("run", text="Futás")
        dip_tree.heading("sec", text="Idő (s)")
        dip_tree.heading("part", text="Testrész [T]")
        dip_tree.heading("valid", text="Érvényes?")
        dip_tree.heading("save", text="JPG?")

        dip_tree.column("ego", width=55, anchor="center")
        dip_tree.column("run", width=50, anchor="center")
        dip_tree.column("sec", width=65, anchor="center")
        dip_tree.column("part", width=155, anchor="center")
        dip_tree.column("valid", width=75, anchor="center")
        dip_tree.column("save", width=60, anchor="center")
        dip_tree.pack(side="left", fill="y")

        sb = ttk.Scrollbar(left_panel, orient="vertical", command=dip_tree.yview)
        sb.pack(side="right", fill="y")
        dip_tree.configure(yscrollcommand=sb.set)

        right_outer, right_panel, _ = self._create_section_card(body, "Képkocka Vizsgáló (Görgős Nagyítással)", P["wood_amber"])
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
                    dip_tree.insert(
                        "", "end", iid=iid,
                        values=(
                            f"#{res['animal_id']}",
                            f"#{r['run_num']}",
                            f"{d['sec']:.2f}s",
                            d.get("dlc_part", "MANCS (Lábhiba)"),
                            "IGEN" if d["valid"] else "TÖRÖLVE",
                            "Igen" if d["save_crop"] else "Nem"
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
            dip_tree.item(
                iid,
                values=(
                    f"#{res['animal_id']}",
                    f"#{r['run_num']}",
                    f"{d['sec']:.2f}s",
                    d.get("dlc_part", "MANCS (Lábhiba)"),
                    "IGEN" if d["valid"] else "TÖRÖLVE",
                    "Igen" if d["save_crop"] else "Nem"
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

        ttk.Button(quick_btn_row, text="◀ Előző [↑/A]", command=lambda: step_selection(-1), style="Ghost.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="Következő [↓/D] ▶", command=lambda: step_selection(1), style="Ghost.TButton").pack(side="left", padx=(0, 10))
        ttk.Button(quick_btn_row, text="⭕ Érvényes [Space]", command=hotkey_toggle_valid, style="SoftRed.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="🐾 Testrész [T]", command=hotkey_cycle_part, style="Teal.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="🔍 Fókusz Zoom [Z]", command=lambda: zoom_to_dip(2.5), style="Ghost.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="↺ 1x [R]", command=reset_zoom, style="Ghost.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(quick_btn_row, text="💾 Képmentés [S]", command=hotkey_toggle_save, style="Primary.TButton").pack(side="left")

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

        ttk.Button(
            bottom_bar, text="✔  Ellenőrzés Kész & Eredmények Exportálása [ENTER]",
            command=confirm_and_close, style="Emerald.TButton"
        ).pack(side="right")

        rev_win.protocol("WM_DELETE_WINDOW", confirm_and_close)

    # ==========================================================================
    # CSV & HEATMAP EXPORT
    # ==========================================================================
    def finalize_and_export_all(self):
        if not self.pending_results:
            self.reset_ui()
            return
        self.log("\n💾 Exporting CSV tables and velocity heatmaps in background...")
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
                video_csv_rows = []

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

                    save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_tiszta_{transit_time:.2f}s.jpg"), clean_canvas)
                    save_image_unicode(os.path.join(output_dir, f"egyed_{safe_id}_futas_{run_count}_halvany_{transit_time:.2f}s.jpg"), run_with_faded_ladder)

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