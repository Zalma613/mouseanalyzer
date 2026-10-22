# 🐁 Mouse Tracking PROMAX + DeepLabCut Addon

A high-performance, multi-threaded desktop application with a Graphical User Interface (GUI) for automated behavioral tracking and kinematic analysis of rodents in staircase/ladder testing environments. This software combines optimized OpenCV video processing with optional **DeepLabCut (SuperAnimal-Quadruped)** AI-powered anatomical keypoint estimation.

---

## ✨ Key Features

* **🚀 Hardware Acceleration & Async Prefetch:** OpenCV OpenCL (GPU) support, hardware-accelerated video decoding, and background prefetch threading for maximum performance.
* **🎯 Precise Event Tracking:** 
  * Automatic Start and Goal gate detection with zone splitting (Start / Center / Goal).
  * Detection of true nose and paw dips (*foot faults*) with refractory periods and minimum distance filtering.
  * Freezing events and movement duration tracking.
* **🧠 DeepLabCut & AI Keypoint Analysis (Addon):**
  * Optional *SuperAnimal-Quadruped* integration to automatically classify nose exploration, paw slips, and tail/hindlimb events.
  * Active Learning module for automated training dataset exportation.
* **📊 Detailed Visualization & Export:**
  * Interactive review window with quick keyboard shortcuts (e.g., `[T]` to switch body parts, `[SPACE]` to toggle valid status).
  * Dynamic 2D Heatmaps with velocity-graded trajectory color-coding.
  * Comprehensive individual and summary CSV reports (with precise timestamps, speeds, and error classifications)[cite: 2].
  * JSON-based calibration profile management[cite: 2].

---

## 💾 Installation & Standalone Binaries

If you are using the pre-compiled standalone version (`.exe` for Windows or `.dmg` for macOS):

### Windows (`.exe`)
1. Download the latest `MouseTracker.exe` release.
2. Simply double-click the executable to launch the application. *(No Python installation required!)*

### macOS (`.dmg`)
1. Download the `MouseTracker.dmg` file.
2. Open the disk image and drag the application into your **Applications** folder.
3. *Note for macOS users:* If Gatekeeper blocks the app upon first launch, right-click (or control-click) the app icon, select **Open**, and confirm.

---

## 🛠️ Requirements (For Running from Python Source)

If you prefer running the raw script (`MouseTracker.py`), ensure you have Python installed along with the required libraries:
```bash
pip install opencv-python numpy pandas tables