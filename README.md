# 🐁 MouseAnalyzer PRO (v3.6)

A high-performance, multi-threaded scientific desktop workstation for automated horizontal ladder behavioral tracking, foot-fault (*paw slip*) classification, and kinematic analysis of rodents. Combines sub-pixel OpenCV morphological segmentation, Kalman & elastic ladder-sag tracking, and a specialized **9-Keypoint Rodent Pose AI (`mouse_pose_ai.pt`)**.

---

## ✨ Key Features

* **🚀 Hardware Acceleration & Async Prefetch:**
  * Automatic compute device detection supporting **Apple Silicon Metal (MPS)**, **NVIDIA CUDA**, and **OpenCL (UMat)** alongside multi-threaded `AsyncVideoReader` frame prefetching.
* **🦴 9-Keypoint Rodent Pose AI & Anatomical Dip Classification:**
  * Real-time dual-engine inference (`ParallelYoloOpenCVEngine`) combining custom 9-keypoint pose estimation (*Snout, Head, Shoulder, Forepaw, Spine, Hip, Hindpaw, Tail Base, Tail Tip*) with sub-pixel morphological segmentation and pink-skin chromaticity scoring.
  * Automatically distinguishes **Forepaw faults**, **Hindpaw faults**, **Snout explorations**, and **Tail dips**, while categorizing slips into minor slips vs. deep falls.
  * Optional **DeepLabCut (*SuperAnimal-Quadruped*)** addon integration and Active Learning training dataset export.
* **🎯 Robust Protocol & Gate Lifecycle:**
  * Automatic adaptive ladder ROI, rung keypoint, and Start/Goal gate calibration (`AutoAdaptiveLadderEngine`).
  * Multi-run protocol state machine (`WAIT_FOR_RUN_1` $\to$ `RUNNING_1` $\to \dots \to$ `SESSION_COMPLETED`) with optional Left-to-Right heading lock or bidirectional tracking.
  * Tracks transit time, net moving time, freezing intervals, micro-hesitations, velocity CV, jerk score, postural sway, and composite uncertainty index (%).
* **🧠 Interactive AI Training & Preview Studio:**
  * Built-in dataset harvester & interactive keypoint annotator (`🧠 AI Training & Preview`) to inspect candidate frames, drag/place manual paw/snout/tail keypoints, exclude blurred frames, and fine-tune `mouse_pose_ai.pt` in-process.
* **🔍 Interactive Event Inspector & Colorblind-Safe Exports:**
  * Post-analysis review workstation with zoom/pan, 1-click body-part reclassification (`[1]` Forepaw, `[2]` Hindpaw, `[3]` Snout, `[4]` Tail), `Shift+Click` point relocation, and `[Space]` validity toggling.
  * Generates colorblind-accessible (Magenta $\to$ Amber $\to$ Cyan) velocity-graded trajectory heatmaps and formula-sanitized individual & master CSV reports (`Minden_Egyed_Meresi_Adatai.csv`).
* **🌐 Cloud & Teams Video Support:**
  * Supports local video files (`.mp4`, `.avi`, `.mov`, `.mkv`), synced Microsoft Teams / OneDrive Files On-Demand placeholders, and direct cloud video URLs with SSRF & size-cap protection.

---

## 📁 Repository Structure

```text
├── .github/workflows/build.yml   # Automated CI test suite & Windows/macOS release builder
├── assets/
│   ├── icon.icns                 # macOS application bundle icon
│   ├── icon.ico                  # Windows executable & window icon
│   └── mouse_pose_ai.pt          # Pre-trained 9-keypoint Rodent Pose YOLOv8 model
├── tests/
│   └── test_mousetracker.py      # Automated unit & security test suite
├── LICENSE                       # MIT License
├── MouseTracker.py               # Main application source
└── README.md                     # Documentation
```

---

## 💾 Installation & Standalone Binaries

Pre-compiled standalone releases (`.exe` for Windows and `.dmg` for macOS) are built automatically on version tags via GitHub Actions:

### Windows (`.exe`)
1. Download `MouseAnalyzer_PRO.exe` from the latest GitHub Release.
2. Double-click to launch *(no Python installation required)*.

### macOS (`.dmg`)
1. Download `MouseAnalyzer_PRO_macOS.dmg` from the latest GitHub Release.
2. Open the disk image and drag **MouseAnalyzer PRO** into your **Applications** folder.
3. *Note:* If macOS Gatekeeper prompts on first launch, right-click (or Control-click) the app icon and select **Open**.

---

## 🛠️ Running from Source & Tests

Ensure Python 3.10+ is installed, then install the dependencies:

```bash
pip install opencv-python numpy numba ultralytics torch torchvision pillow yt-dlp
```

Launch the workstation:

```bash
python MouseTracker.py
```

Run the automated unit and security test suite:

```bash
python -m unittest discover -s tests -v
```
