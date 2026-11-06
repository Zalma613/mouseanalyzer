import os
import tempfile
import unittest
import unittest.mock
import numpy as np

import MouseTracker as mt


class TestCloudVideoResolverSecurity(unittest.TestCase):
    """Tests SSRF/scheme validation, trusted hostname verification, and URL transformations."""

    def test_trusted_microsoft_host_validation(self):
        # Legitimate Microsoft domains must pass
        self.assertTrue(mt.CloudVideoResolver._is_trusted_microsoft_host("https://contoso.sharepoint.com/sites/lab/video.mp4"))
        self.assertTrue(mt.CloudVideoResolver._is_trusted_microsoft_host("https://onedrive.live.com/download?resid=123"))
        self.assertTrue(mt.CloudVideoResolver._is_trusted_microsoft_host("https://1drv.ms/v/s!Amxyz"))
        self.assertTrue(mt.CloudVideoResolver._is_trusted_microsoft_host("https://teams.microsoft.com/l/file/abc"))

        # Spoofed query strings or subdomains on attacker hosts must be rejected
        self.assertFalse(mt.CloudVideoResolver._is_trusted_microsoft_host("https://evil.example.com/?sharepoint.com=1"))
        self.assertFalse(mt.CloudVideoResolver._is_trusted_microsoft_host("https://sharepoint.com.evil.example.com/video.mp4"))
        self.assertFalse(mt.CloudVideoResolver._is_trusted_microsoft_host("file:///etc/passwd#onedrive.live.com"))
        self.assertFalse(mt.CloudVideoResolver._is_trusted_microsoft_host(""))

    def test_transform_shared_cloud_url(self):
        gdrive_url = "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456/view?usp=sharing"
        transformed = mt.CloudVideoResolver._transform_shared_cloud_url(gdrive_url)
        self.assertEqual(
            transformed,
            "https://drive.google.com/uc?export=download&id=1AbCdEfGhIjKlMnOpQrStUvWxYz123456",
        )

        sp_url = "https://uni.sharepoint.com/:v:/s/NeuroLab/EdummyToken?e=abc123"
        sp_transformed = mt.CloudVideoResolver._transform_shared_cloud_url(sp_url)
        self.assertIn("download=1", sp_transformed)

    def test_non_http_schemes_rejected(self):
        logs = []
        with self.assertRaises(ValueError):
            mt.CloudVideoResolver.resolve_to_local_path("file:///etc/passwd", log_cb=logs.append)
        self.assertTrue(any("Nem támogatott URL séma" in m for m in logs))

    def test_oversized_and_html_login_rejected_without_direct_url_fallback(self):
        # 1. Oversized stream (> MAX_DOWNLOAD_BYTES) must raise RuntimeError and never fall back to direct_url
        class _FakeOversizeResp:
            url = "https://contoso.sharepoint.com/sites/lab/video.mp4?download=1"
            def __init__(self):
                self._sent = False
            def read(self, _sz=-1):
                if not self._sent:
                    self._sent = True
                    return b"x" * 1024
                return b""
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp_cache:
            with unittest.mock.patch.object(mt.CloudVideoResolver, "CACHE_DIR", tmp_cache), \
                 unittest.mock.patch.object(mt.CloudVideoResolver, "MAX_DOWNLOAD_BYTES", 512), \
                 unittest.mock.patch("importlib.util.find_spec", return_value=None), \
                 unittest.mock.patch("urllib.request.urlopen", return_value=_FakeOversizeResp()):
                with self.assertRaises(RuntimeError):
                    mt.CloudVideoResolver.resolve_to_local_path(
                        "https://contoso.sharepoint.com/sites/lab/video.mp4", log_cb=lambda _: None
                    )

        # 2. HTML login response must raise RuntimeError and never fall back to direct_url
        class _FakeHtmlResp:
            url = "https://contoso.sharepoint.com/sites/lab/login.mp4?download=1"
            def __init__(self):
                self._sent = False
            def read(self, _sz=-1):
                if not self._sent:
                    self._sent = True
                    return b"<!DOCTYPE html><html><body>Sign in to your account</body></html>" + (b" " * 110000)
                return b""
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp_cache:
            with unittest.mock.patch.object(mt.CloudVideoResolver, "CACHE_DIR", tmp_cache), \
                 unittest.mock.patch("importlib.util.find_spec", return_value=None), \
                 unittest.mock.patch("urllib.request.urlopen", return_value=_FakeHtmlResp()):
                with self.assertRaises(RuntimeError):
                    mt.CloudVideoResolver.resolve_to_local_path(
                        "https://contoso.sharepoint.com/sites/lab/login.mp4", log_cb=lambda _: None
                    )

        # 3. Redirect handler rejects non-HTTP schemes and private/loopback hosts
        handler = mt._SafeCloudRedirectHandler()
        req = mt.urllib.request.Request("https://contoso.sharepoint.com/video.mp4")
        with self.assertRaises(ValueError):
            handler.redirect_request(req, None, 302, "Found", {}, "file:///etc/passwd")
        with self.assertRaises(ValueError):
            handler.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1:8080/internal")

        # 4. DNS rebinding / hostname resolving to private/loopback IP must be rejected
        fake_addrinfo = [(2, 1, 6, "", ("127.0.0.1", 443))]
        with unittest.mock.patch("socket.getaddrinfo", return_value=fake_addrinfo):
            with self.assertRaises(ValueError):
                mt.CloudVideoResolver._validate_url_target("https://rebind.attacker.example.com/video.mp4")

        # 5. Network failure in urllib must raise RuntimeError and never return raw direct_url to FFmpeg
        with tempfile.TemporaryDirectory() as tmp_cache:
            with unittest.mock.patch.object(mt.CloudVideoResolver, "CACHE_DIR", tmp_cache), \
                 unittest.mock.patch("importlib.util.find_spec", return_value=None), \
                 unittest.mock.patch.object(mt.CloudVideoResolver, "_validate_url_target", return_value=None), \
                 unittest.mock.patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
                with self.assertRaises(RuntimeError):
                    mt.CloudVideoResolver.resolve_to_local_path(
                        "https://contoso.sharepoint.com/sites/lab/unreachable.mp4", log_cb=lambda _: None
                    )


class TestUnicodeImageIOAndCompression(unittest.TestCase):
    """Tests Unicode path handling and in-memory frame/mask compression."""

    def test_save_and_read_unicode_path(self):
        img = np.zeros((48, 64, 3), dtype=np.uint8)
        img[10:30, 15:45] = (40, 180, 240)
        with tempfile.TemporaryDirectory(prefix="Eger_Arvizturo_Tukorfurogep_") as tmpdir:
            nested = os.path.join(tmpdir, "Kísérlet_ŐŰÁÉÚÓ", "minta_01.png")
            ok = mt.save_image_unicode(nested, img)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(nested))
            loaded = mt.read_image_unicode(nested)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.shape, img.shape)
            np.testing.assert_array_equal(loaded, img)

    def test_compressed_frame_and_mask_roundtrip(self):
        frame = np.full((60, 80, 3), 120, dtype=np.uint8)
        mask = np.zeros((60, 80), dtype=np.uint8)
        mask[20:40, 30:50] = 255

        f_buf = mt.encode_frame_compressed(frame, quality=95)
        m_buf = mt.encode_mask_compressed(mask)
        self.assertIsNotNone(f_buf)
        self.assertIsNotNone(m_buf)

        dec_f = mt.decode_frame_compressed(f_buf)
        dec_m = mt.decode_mask_compressed(m_buf)
        self.assertEqual(dec_f.shape, frame.shape)
        np.testing.assert_array_equal(dec_m, mask)

    def test_get_resource_path_finds_assets(self):
        for asset_name in ("icon.ico", "icon.icns", "mouse_pose_ai.pt"):
            resolved = mt.get_resource_path(asset_name)
            self.assertTrue(os.path.exists(resolved), f"Asset not found via get_resource_path: {asset_name} -> {resolved}")


class TestAnatomicalClassificationAndDipDetection(unittest.TestCase):
    """Tests rodent anatomical classification, IoU, CSV sanitization, and thread pose isolation."""

    def test_classify_dip_features_zones(self):
        # Nose exploration (>= 0.85)
        part, code = mt.DLCAddonManager.classify_dip_features(0.92, 1.0, 12.0)
        self.assertEqual(code, "NOSE")
        self.assertIn("ORR", part)

        # Forepaw fault (0.50 .. 0.80)
        part, code = mt.DLCAddonManager.classify_dip_features(0.68, 1.2, 24.0)
        self.assertEqual(code, "PAW")
        self.assertIn("MELLSŐ", part)

        # Hindpaw fault (0.18 .. 0.50)
        part, code = mt.DLCAddonManager.classify_dip_features(0.32, 1.1, 22.0)
        self.assertEqual(code, "PAW")
        self.assertIn("HÁTSÓ", part)

        # Tail dip (< 0.18)
        part, code = mt.DLCAddonManager.classify_dip_features(0.10, 2.0, 10.0)
        self.assertEqual(code, "HIND_TAIL")
        self.assertIn("FAROK", part)

    def test_classify_dip_with_anatomy_keypoints(self):
        anatomy = {
            "nose_pt": (180, 52),
            "head_pt": (165, 45),
            "shoulder_pt": (140, 42),
            "fore_paw_pt": (145, 78),
            "spine_mid": (110, 38),
            "hip_pt": (75, 40),
            "hind_paw_pt": (70, 80),
            "tail_base": (50, 44),
            "tail_tip": (15, 48),
        }
        # Dip right at fore_paw_pt
        part, code = mt.DLCAddonManager.classify_dip_with_anatomy(
            dip_x=146, dip_y=79, anatomy=anatomy,
            rel_pos_norm=0.65, aspect_ratio=0.8, dip_depth=17.0, skin_score=18.0
        )
        self.assertEqual(code, "PAW")
        self.assertIn("MELLSŐ", part)

        # Dip right at hind_paw_pt
        part, code = mt.DLCAddonManager.classify_dip_with_anatomy(
            dip_x=71, dip_y=81, anatomy=anatomy,
            rel_pos_norm=0.35, aspect_ratio=0.8, dip_depth=19.0, skin_score=18.0
        )
        self.assertEqual(code, "PAW")
        self.assertIn("HÁTSÓ", part)

    def test_classify_dips_with_superanimal_nonzero_roi_offset(self):
        addon = mt.DLCAddonManager(lambda _: None)
        addon.dlc_available = False
        roi_offset = (250, 140)
        # Local ROI anatomy places hind_paw_pt at (70, 80); global dip is at (250+71, 140+81) = (321, 221).
        # Without subtracting roi_offset, global dx=321 would be far from local hind_paw_pt=(70, 80)
        # and rel_pos_norm=0.68 would misclassify it as forepaw instead of hindpaw.
        anatomy = {
            "nose_pt": (180, 52),
            "head_pt": (165, 45),
            "shoulder_pt": (140, 42),
            "fore_paw_pt": (145, 78),
            "spine_mid": (110, 38),
            "hip_pt": (75, 40),
            "hind_paw_pt": (70, 80),
            "tail_base": (50, 44),
            "tail_tip": (15, 48),
        }
        dip_event = {
            "x": roi_offset[0] + 71,
            "y": roi_offset[1] + 81,
            "sec": 1.25,
            "move_dir": 1.0,
            "torso_left_x": roi_offset[0] + 40,
            "torso_width": 100,
            "dip_aspect": 0.8,
            "dip_depth": 19.0,
            "paw_skin_score": 18.0,
            "head_pitch_down": False,
            "anatomy": anatomy,
            "roi_offset": roi_offset,
        }
        pending_results = [{
            "runs": [{
                "trajectory": [(roi_offset[0] + 90, roi_offset[1] + 50, 1.25)],
                "dips": [dip_event],
            }]
        }]
        addon.classify_dips_with_superanimal(pending_results)
        self.assertEqual(dip_event["dlc_code"], "PAW")
        self.assertIn("HÁTSÓ", dip_event["dlc_part"])

    def test_parallel_yolo_thread_pose_isolation(self):
        with unittest.mock.patch.object(mt.ParallelYoloOpenCVEngine, "_init_yolo", return_value=None):
            engine = mt.ParallelYoloOpenCVEngine(lambda _: None)
        engine.is_rodent_pose = True
        pose_vid_a = {"nose_pt": (100, 40), "fore_paw_pt": (90, 75), "bbox": (20, 20, 90, 60)}
        pose_vid_b = {"nose_pt": (300, 40), "fore_paw_pt": (290, 75), "bbox": (220, 20, 90, 60)}

        engine._set_thread_pose("vid_A", pose_vid_a, 10)
        engine._set_thread_pose("vid_B", pose_vid_b, 20)

        # Worker stream poses must never overwrite global last_sync_pose or leak across streams
        self.assertIsNone(engine.last_sync_pose)
        fetched_a = engine.get_latest_pose_for_bbox(22, 22, 88, 58, 640, 200, stream_id="vid_A")
        self.assertIsNotNone(fetched_a)
        self.assertEqual(fetched_a["nose_pt"], (100, 40))

        # Requesting vid_A with vid_B's coordinates must return None (non-overlapping X)
        mismatch = engine.get_latest_pose_for_bbox(220, 20, 90, 60, 640, 200, stream_id="vid_A")
        self.assertIsNone(mismatch)

    def test_csv_formula_injection_sanitization(self):
        sanitize = mt.PerVideoIDTrackerApp._sanitize_csv_cell
        self.assertEqual(sanitize("=cmd|' /C calc'!A0"), "'=cmd|' /C calc'!A0")
        self.assertEqual(sanitize("+SUM(A1:A2)"), "'+SUM(A1:A2)")
        self.assertEqual(sanitize("@SUM(1+1)"), "'@SUM(1+1)")
        self.assertEqual(sanitize("-1+1"), "'-1+1")
        # Leading whitespace and newlines must also be sanitized
        self.assertEqual(sanitize(" =cmd|' /C calc'!A0"), "' =cmd|' /C calc'!A0")
        self.assertEqual(sanitize("   +SUM(A1:A2)"), "'   +SUM(A1:A2)")
        self.assertEqual(sanitize("\n=cmd|' /C calc'!A0"), "'\n=cmd|' /C calc'!A0")
        self.assertEqual(sanitize("\r\n@SUM(1+1)"), "'\r\n@SUM(1+1)")
        self.assertEqual(sanitize("\t-1+1"), "'\t-1+1")
        # Plain negative numbers and normal IDs should pass untouched
        self.assertEqual(sanitize("-12.5"), "-12.5")
        self.assertEqual(sanitize("-12,5"), "-12,5")
        self.assertEqual(sanitize("Mouse_04"), "Mouse_04")
        # Non-finite float literals (-inf, -nan, scientific notation expressions) must be escaped
        self.assertEqual(sanitize("-inf"), "'-inf")
        self.assertEqual(sanitize("-nan"), "'-nan")
        self.assertEqual(sanitize("-Infinity"), "'-Infinity")
        self.assertEqual(sanitize("-1e309"), "'-1e309")

    def test_export_training_dataset_path_traversal_sanitized(self):
        addon = mt.DLCAddonManager(lambda _: None)
        dummy_frame = np.zeros((100, 120, 3), dtype=np.uint8)
        frame_buf = mt.encode_frame_compressed(dummy_frame)
        with tempfile.TemporaryDirectory() as tmpdir:
            target_export = os.path.join(tmpdir, "export_sub")
            pending = [{
                "safe_id": "../../evil_id",
                "animal_id": "../../evil_id",
                "video_name": "../../../evil_video.mp4",
                "runs": [{
                    "run_num": 1,
                    "dips": [{
                        "valid": True,
                        "frame_buf": frame_buf,
                        "x": 50,
                        "y": 50,
                        "sec": 1.5,
                        "dlc_part": "MANCS",
                        "dlc_code": "PAW",
                    }],
                }],
            }]
            count = addon.export_training_dataset(pending, target_export)
            self.assertEqual(count, 1)
            crops_dir = os.path.join(target_export, "1_Dinamikus_Eger_Kivagasok_Crop")
            exported_files = os.listdir(crops_dir)
            self.assertEqual(len(exported_files), 1)
            self.assertNotIn("..", exported_files[0])
            self.assertTrue(exported_files[0].startswith("egyed_evil_id_evil_video_"))

    def test_bbox_iou(self):
        iou_same = mt.PerVideoIDTrackerApp._bbox_iou((10, 10, 50, 50), (10, 10, 50, 50))
        self.assertAlmostEqual(iou_same, 1.0, places=5)
        iou_disjoint = mt.PerVideoIDTrackerApp._bbox_iou((0, 0, 20, 20), (100, 100, 20, 20))
        self.assertAlmostEqual(iou_disjoint, 0.0, places=5)


class TestAutoAdaptiveLadderEngine(unittest.TestCase):
    """Tests background outlier rejection and rung keypoint extraction."""

    def test_compute_outlier_rejected_bg(self):
        engine = mt.AutoAdaptiveLadderEngine(lambda _: None)
        base = np.full((60, 120), 200, dtype=np.uint8)
        frames = []
        for i in range(10):
            f = base.copy()
            # Transient dark mouse blob moving across frame
            x0 = (i * 10) % 90
            f[15:35, x0:x0 + 20] = 30
            frames.append(f)

        clean_bg = engine.compute_outlier_rejected_bg(frames)
        self.assertEqual(clean_bg.shape, (60, 120))
        # Dark transient mouse blobs should be rejected, leaving bright background ~200
        self.assertGreaterEqual(float(np.median(clean_bg)), 195.0)

    def test_auto_calibrate_resets_video_capture_to_frame_zero(self):
        engine = mt.AutoAdaptiveLadderEngine(lambda _: None)

        class _FakeCap:
            def __init__(self):
                self.pos = 0
                self.frame = np.full((240, 640, 3), 210, dtype=np.uint8)
                self.frame[115:125, 60:580] = 60

            def get(self, prop):
                if prop == mt.cv2.CAP_PROP_FRAME_COUNT:
                    return 120
                return 30.0

            def set(self, prop, val):
                if prop == mt.cv2.CAP_PROP_POS_FRAMES:
                    self.pos = int(val)

            def read(self):
                self.pos += 1
                return True, self.frame.copy()

        cap = _FakeCap()
        res = engine.auto_calibrate_from_video(cap, num_bg_samples=8)
        self.assertIn("roi_bg", res)
        self.assertEqual(cap.pos, 0, "auto_calibrate_from_video must rewind VideoCapture to frame 0")


class TestUltralyticsOfflineAndTrainerHardening(unittest.TestCase):
    """Tests HTTP 416 Arial.ttf guard, offline YOLO settings, check_font monkeypatch,
    POSIX path normalization, missing base weight validation, dynamic batching,
    diagnostic directory preservation, and zero-division guards."""

    def _make_active_samples(self, count=6):
        crop = np.full((80, 160, 3), 120, dtype=np.uint8)
        mask = np.zeros((80, 160), dtype=np.uint8)
        crop_buf = mt.encode_frame_compressed(crop)
        mask_buf = mt.encode_mask_compressed(mask)
        samples = []
        for i in range(count):
            samples.append({
                "uid": f"s_{i}",
                "crop_buf": crop_buf,
                "mask_buf": mask_buf,
                "bbox": (20, 15, 60, 35),
                "anatomy": {"nose_pt": (75, 30), "fore_paw_pt": (55, 48), "hind_paw_pt": (30, 48)},
                "excluded": False,
            })
        return samples

    def test_ensure_ultralytics_font_purges_corrupt_and_seeds_bundled(self):
        with tempfile.TemporaryDirectory() as tmp_appdata, \
             tempfile.TemporaryDirectory() as tmp_assets:
            u_dir = os.path.join(tmp_appdata, "Ultralytics")
            os.makedirs(u_dir, exist_ok=True)
            corrupt_font = os.path.join(u_dir, "Arial.ttf")
            # Create a 0-byte corrupted partial download file
            with open(corrupt_font, "wb") as f:
                f.write(b"")

            bundled_font = os.path.join(tmp_assets, "Arial.ttf")
            valid_payload = b"TTF_VALID_FONT_DATA_" * 600  # 12,000 bytes (>= 10 KB)
            with open(bundled_font, "wb") as f:
                f.write(valid_payload)

            with unittest.mock.patch.dict(os.environ, {"APPDATA": tmp_appdata}), \
                 unittest.mock.patch.object(mt, "_WINDOWS_SYSTEM_ARIAL_FONT", os.path.join(tmp_assets, "no_win_arial.ttf")), \
                 unittest.mock.patch.object(mt, "get_resource_path", return_value=bundled_font):
                mt.ensure_ultralytics_font()

            self.assertTrue(os.path.exists(corrupt_font))
            self.assertEqual(os.path.getsize(corrupt_font), len(valid_payload))

    def test_check_font_monkeypatch_catches_http_416_error(self):
        import ultralytics.utils.checks as u_checks
        orig = u_checks.check_font
        try:
            def _failing_check_font(*args, **kwargs):
                raise RuntimeError("416 Client Error: Range Not Satisfiable for url: Arial.ttf")

            u_checks.check_font = _failing_check_font
            mt.ensure_ultralytics_font()
            # Must not raise RuntimeError; must return None cleanly
            res = u_checks.check_font("Arial.ttf")
            self.assertIsNone(res)
        finally:
            u_checks.check_font = orig

    def test_allowlist_ultralytics_torch_globals_registers_models(self):
        import torch
        from ultralytics.nn.tasks import PoseModel, DetectionModel
        with unittest.mock.patch.object(torch.serialization, "add_safe_globals") as mock_add:
            mt._allowlist_ultralytics_torch_globals()
            mock_add.assert_called_once_with([PoseModel, DetectionModel])

    def test_missing_base_weights_aborts_cleanly_without_network_download(self):
        addon = mt.DLCAddonManager(lambda _: None)
        samples = self._make_active_samples(6)
        progress_msgs = []

        with tempfile.TemporaryDirectory() as empty_dir:
            missing_pt = os.path.join(empty_dir, "nonexistent.pt")
            with unittest.mock.patch.object(mt, "get_resource_path", return_value=missing_pt), \
                 unittest.mock.patch.object(mt, "SAFE_BASE_DIR", empty_dir), \
                 unittest.mock.patch("ultralytics.YOLO") as mock_yolo:
                res_det = addon.train_rodent_detector_from_samples(
                    None, samples, epochs=1, progress_cb=lambda p, m: progress_msgs.append((p, m))
                )
                self.assertIsNone(res_det)
                mock_yolo.assert_not_called()
                self.assertTrue(any("nem található" in m for _, m in progress_msgs))

                progress_msgs.clear()
                res_pose = addon.train_rodent_pose_from_samples(
                    None, samples, epochs=1, progress_cb=lambda p, m: progress_msgs.append((p, m))
                )
                self.assertIsNone(res_pose)
                mock_yolo.assert_not_called()
                self.assertTrue(any("nem található" in m for _, m in progress_msgs))

    def test_detector_dynamic_batch_posix_yaml_and_cleanup_vs_preservation(self):
        addon = mt.DLCAddonManager(lambda _: None)
        samples = self._make_active_samples(6)

        # Include a corrupt 0-dimension sample to verify zero-division guard
        corrupt_sample = dict(samples[0])
        corrupt_sample["uid"] = "corrupt_0"
        samples_with_corrupt = [corrupt_sample] + samples
        orig_unpack = mt.unpack_sample_images

        def _fake_unpack(s):
            if s.get("uid") == "corrupt_0":
                return np.zeros((0, 0, 3), dtype=np.uint8), None
            return orig_unpack(s)

        # 1. Verify failure preserves dataset_dir for diagnostics and calls gc.collect()
        created_dirs = []
        orig_mkdtemp = tempfile.mkdtemp

        def _tracking_mkdtemp(*args, **kwargs):
            d = orig_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        class _FailingYOLO:
            def __init__(self, pt):
                self.pt = pt
            def add_callback(self, *args, **kwargs):
                pass
            def train(self, **kwargs):
                raise RuntimeError("Simulated training failure")

        with tempfile.TemporaryDirectory() as tmp_base:
            dummy_pt = os.path.join(tmp_base, "yolov8n.pt")
            with open(dummy_pt, "wb") as f:
                f.write(b"DUMMY_PT")

            with unittest.mock.patch("tempfile.mkdtemp", side_effect=_tracking_mkdtemp), \
                 unittest.mock.patch.object(mt, "unpack_sample_images", side_effect=_fake_unpack), \
                 unittest.mock.patch.object(mt, "get_resource_path", return_value=dummy_pt), \
                 unittest.mock.patch.object(mt, "SAFE_BASE_DIR", tmp_base), \
                 unittest.mock.patch("ultralytics.YOLO", _FailingYOLO), \
                 unittest.mock.patch("gc.collect") as mock_gc:
                res = addon.train_rodent_detector_from_samples(None, samples_with_corrupt, epochs=1)
                self.assertIsNone(res)
                mock_gc.assert_called()
                self.assertEqual(len(created_dirs), 1)
                preserved_dir = created_dirs[0]
                self.assertTrue(os.path.exists(preserved_dir), "Failed run must preserve dataset_dir for diagnostics")
                yaml_file = os.path.join(preserved_dir, "rodent.yaml")
                self.assertTrue(os.path.exists(yaml_file))
                with open(yaml_file, "r", encoding="utf-8") as yf:
                    yaml_text = yf.read()
                self.assertNotIn("//", yaml_text.split("path:")[1].splitlines()[0])
                mt.shutil.rmtree(preserved_dir, ignore_errors=True)

        # 2. Verify successful run uses dynamic batch=6 (not 16) and cleans up dataset_dir
        created_dirs.clear()
        recorded_train_kwargs = {}

        class _SuccessYOLO:
            def __init__(self, pt):
                self.pt = pt
            def add_callback(self, *args, **kwargs):
                pass
            def train(self, **kwargs):
                recorded_train_kwargs.update(kwargs)
                weights_dir = os.path.join(kwargs["project"], kwargs["name"], "weights")
                os.makedirs(weights_dir, exist_ok=True)
                with open(os.path.join(weights_dir, "best.pt"), "wb") as wf:
                    wf.write(b"TRAINED_WEIGHTS")

        with tempfile.TemporaryDirectory() as tmp_base:
            dummy_pt = os.path.join(tmp_base, "yolov8n.pt")
            with open(dummy_pt, "wb") as f:
                f.write(b"DUMMY_PT")

            with unittest.mock.patch("tempfile.mkdtemp", side_effect=_tracking_mkdtemp), \
                 unittest.mock.patch.object(mt, "unpack_sample_images", side_effect=_fake_unpack), \
                 unittest.mock.patch.object(mt, "get_resource_path", return_value=dummy_pt), \
                 unittest.mock.patch.object(mt, "SAFE_BASE_DIR", tmp_base), \
                 unittest.mock.patch("ultralytics.YOLO", _SuccessYOLO):
                res = addon.train_rodent_detector_from_samples(None, samples_with_corrupt, epochs=2)
                self.assertIsNotNone(res)
                self.assertTrue(os.path.exists(res))
                # Active samples = 7 (1 corrupt skipped + 6 valid), so dynamic batch = min(16, max(2, 7)) = 7
                self.assertEqual(recorded_train_kwargs.get("batch"), 7)
                self.assertEqual(len(created_dirs), 1)
                self.assertFalse(os.path.exists(created_dirs[0]), "Successful run must clean up dataset_dir")

    def test_pose_trainer_zero_div_guard_posix_yaml_and_cleanup_vs_preservation(self):
        addon = mt.DLCAddonManager(lambda _: None)
        samples = self._make_active_samples(6)
        corrupt_sample = dict(samples[0])
        corrupt_sample["uid"] = "corrupt_pose_0"
        samples_with_corrupt = [corrupt_sample] + samples
        orig_unpack = mt.unpack_sample_images

        def _fake_unpack(s):
            if s.get("uid") == "corrupt_pose_0":
                return np.zeros((100, 0, 3), dtype=np.uint8), None
            return orig_unpack(s)

        created_dirs = []
        orig_mkdtemp = tempfile.mkdtemp

        def _tracking_mkdtemp(*args, **kwargs):
            d = orig_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        class _SuccessPoseYOLO:
            def __init__(self, pt):
                self.pt = pt
            def add_callback(self, *args, **kwargs):
                pass
            def train(self, **kwargs):
                with open(kwargs["data"], "r", encoding="utf-8") as yf:
                    yaml_text = yf.read()
                assert "//" not in yaml_text.split("path:")[1].splitlines()[0]
                weights_dir = os.path.join(kwargs["project"], kwargs["name"], "weights")
                os.makedirs(weights_dir, exist_ok=True)
                with open(os.path.join(weights_dir, "best.pt"), "wb") as wf:
                    wf.write(b"TRAINED_POSE_WEIGHTS")

        with tempfile.TemporaryDirectory() as tmp_base:
            dummy_pt = os.path.join(tmp_base, "mouse_pose_ai.pt")
            with open(dummy_pt, "wb") as f:
                f.write(b"DUMMY_POSE_PT")

            with unittest.mock.patch("tempfile.mkdtemp", side_effect=_tracking_mkdtemp), \
                 unittest.mock.patch.object(mt, "unpack_sample_images", side_effect=_fake_unpack), \
                 unittest.mock.patch.object(mt, "get_resource_path", return_value=dummy_pt), \
                 unittest.mock.patch.object(mt, "SAFE_BASE_DIR", tmp_base), \
                 unittest.mock.patch("ultralytics.YOLO", _SuccessPoseYOLO):
                res = addon.train_rodent_pose_from_samples(None, samples_with_corrupt, epochs=1)
                self.assertIsNotNone(res)
                self.assertTrue(os.path.exists(res))
                self.assertEqual(len(created_dirs), 1)
                self.assertFalse(os.path.exists(created_dirs[0]))


class TestReviewAndRefactoringImprovements(unittest.TestCase):
    def test_roi_config_dataclass_and_legacy_sequence_compatibility(self):
        cfg = mt.ROIConfig(
            rx=10, ry=20, rw=400, rh=200,
            left_gate_x=50, right_gate_x=350,
            dark_t=120, diff_t=25,
            ladder_t=105, fault_pct=70,
            z_active=True, kin_active=True,
            dip_cooldown_sec=0.45, dip_min_dist_px=28,
            gate_dist_cm=60.0, px_per_cm=5.0,
            frame_stride=2, use_gpu=False, use_kalman=True,
            bidirectional=True, protocol_runs="5 Runs", lock_lr=False
        )
        self.assertEqual(len(cfg), 22)
        self.assertEqual(cfg.target_runs, 5)
        self.assertEqual(cfg[:4], (10, 20, 400, 200))
        self.assertIs(mt.ROIConfig.from_sequence(cfg), cfg)

        # Legacy 19-element tuple compatibility
        legacy_19 = cfg.as_tuple()[:19]
        parsed_19 = mt.ROIConfig.from_sequence(legacy_19)
        self.assertEqual(parsed_19.rx, 10)
        self.assertFalse(parsed_19.bidirectional)
        self.assertEqual(parsed_19.target_runs, 3)
        self.assertTrue(parsed_19.lock_lr)

        # Legacy 20-element tuple compatibility
        legacy_20 = cfg.as_tuple()[:20]
        parsed_20 = mt.ROIConfig.from_sequence(legacy_20)
        self.assertTrue(parsed_20.bidirectional)
        self.assertEqual(parsed_20.target_runs, 3)

    def test_resolve_limb_subtype_language_independent(self):
        resolve = mt.DLCAddonManager.resolve_limb_subtype
        self.assertEqual(resolve("PAW", "MELLSŐ LÁB (Lábhiba)"), "FOREPAW")
        self.assertEqual(resolve("PAW", "HÁTSÓ LÁB (Lábhiba)"), "HINDPAW")
        self.assertEqual(resolve("PAW", "Forelimb slip", None), "FOREPAW")
        self.assertEqual(resolve("PAW", "Hindpaw slip", None), "HINDPAW")
        self.assertEqual(resolve("PAW", "Custom Label", "HINDPAW"), "HINDPAW")
        self.assertEqual(resolve("PAW", "Custom Label", "FOREPAW"), "FOREPAW")
        self.assertEqual(resolve("NOSE", "ORR (Exploráció)"), "NOSE")
        self.assertEqual(resolve("HIND_TAIL", "FAROK (Billenés)"), "HIND_TAIL")

    def test_dns_rebinding_peer_socket_validation(self):
        class _FakeSocket:
            def __init__(self, peer_ip):
                self._peer_ip = peer_ip
            def getpeername(self):
                return (self._peer_ip, 443)

        class _FakeRaw:
            def __init__(self, sock):
                self._sock = sock

        class _FakeFp:
            def __init__(self, sock):
                self.raw = _FakeRaw(sock)

        class _FakeResp:
            def __init__(self, peer_ip):
                self.fp = _FakeFp(_FakeSocket(peer_ip))
                self.closed = False
            def close(self):
                self.closed = True

        # Safe public IP passes
        safe_resp = _FakeResp("93.184.216.34")
        mt.CloudVideoResolver._validate_peer_socket(safe_resp)
        self.assertFalse(safe_resp.closed)

        # DNS rebinding to loopback / private IP after initial resolution is blocked and closed
        for unsafe_ip in ("127.0.0.1", "10.0.0.1", "169.254.169.254"):
            rebinding_resp = _FakeResp(unsafe_ip)
            with self.assertRaises(ValueError):
                mt.CloudVideoResolver._validate_peer_socket(rebinding_resp)
            self.assertTrue(rebinding_resp.closed)


if __name__ == "__main__":
    unittest.main()
