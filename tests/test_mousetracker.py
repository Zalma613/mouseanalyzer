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

    def test_trained_ai_weights_priority_and_analysis_usage(self):
        """Verifies that _init_yolo prefers user-trained weights in SAFE_BASE_DIR over older bundled assets,
        and that trained AI pose keypoints directly drive limb slip detection even when OpenCV mask is faint."""
        with tempfile.TemporaryDirectory() as tmp_safe, \
             tempfile.TemporaryDirectory() as tmp_bundled:
            bundled_pt = os.path.join(tmp_bundled, "mouse_pose_ai.pt")
            trained_pt = os.path.join(tmp_safe, "mouse_pose_ai.pt")
            with open(bundled_pt, "wb") as f:
                f.write(b"OLD_BUNDLED_PT")
            with open(trained_pt, "wb") as f:
                f.write(b"NEW_USER_TRAINED_PT")
            # Ensure user-trained file has a newer mtime than bundled asset
            os.utime(bundled_pt, (1700000000, 1700000000))
            os.utime(trained_pt, (1800000000, 1800000000))

            loaded_paths = []

            class _FakeYOLO:
                task = "pose"
                names = {0: "rodent"}
                def __init__(self, path):
                    loaded_paths.append(os.path.abspath(path))
                def predict(self, *args, **kwargs):
                    return []

            with unittest.mock.patch.object(mt, "SAFE_BASE_DIR", tmp_safe), \
                 unittest.mock.patch.object(mt, "get_resource_path", return_value=bundled_pt), \
                 unittest.mock.patch("ultralytics.YOLO", _FakeYOLO):
                engine = mt.ParallelYoloOpenCVEngine(lambda _: None)
                self.assertEqual(engine.model_path, os.path.abspath(trained_pt))
                self.assertEqual(loaded_paths[-1], os.path.abspath(trained_pt))
                self.assertTrue(engine.is_rodent_pose)

            # Now verify that during analysis, a trained AI paw keypoint below the fault line
            # is blended with high weight (0.92) and reinforces the dip mask to trigger a PAW slip
            app = TestReviewAndRefactoringImprovements._make_headless_detector()
            app.hybrid_locator.is_rodent_pose = True
            rh, rw = 160, 260
            fault_y = 112
            fault_curve = np.full(rw, fault_y, dtype=np.int32)

            # OpenCV mask only has the upper torso above the fault line (paw below rung was missed by raw threshold)
            mouse_mask = np.zeros((rh, rw), dtype=np.uint8)
            mt.cv2.ellipse(mouse_mask, (130, 74), (44, 22), 0, 0, 360, 255, -1)
            bbox = (86, 52, 88, 44)

            # Plant a fresh trained-AI pose prediction on stream "vid_ai" at frame 15 with fore_paw_pt dipping to y=132
            ai_pose = {
                "bbox": bbox,
                "nose_pt": (170, 72), "nose_pt_conf": 0.90,
                "head_pt": (158, 66), "head_pt_conf": 0.88,
                "shoulder_pt": (144, 68), "shoulder_pt_conf": 0.85,
                "fore_paw_pt": (146, 132), "fore_paw_pt_conf": 0.86,
                "spine_mid": (126, 65), "spine_mid_conf": 0.85,
                "hip_pt": (106, 68), "hip_pt_conf": 0.85,
                "hind_paw_pt": (104, 96), "hind_paw_pt_conf": 0.82,
                "tail_base": (90, 72), "tail_base_conf": 0.80,
                "tail_tip": (60, 74), "tail_tip_conf": 0.75,
            }
            app.hybrid_locator._set_thread_pose("vid_ai", ai_pose, frame_idx=15)

            anat = app._extract_rodent_anatomy(
                mouse_mask, fault_curve, bbox, move_dir=1.0, stream_id="vid_ai", frame_idx=15, ai_max_age=5
            )
            self.assertIsNotNone(anat)
            # Because AI fore_paw_pt=(146, 132) is below fault_y=112 with conf=0.86, _blend_paw weights AI at 0.92
            self.assertGreater(anat["fore_paw_pt"][1], fault_y + 12)

            # And _anatomical_dip_mask reinforces paw_zone with the AI limb so _check_real_dip_below_line detects it
            is_dip, dip_x, dip_y, _, dip_depth, dip_meta = app._check_real_dip_below_line(
                mouse_mask, fault_curve, crop=np.full((rh, rw, 3), 40, dtype=np.uint8),
                bbox=bbox, move_dir=1.0, return_meta=True, stream_id="vid_ai", frame_idx=15, ai_max_age=5
            )
            self.assertTrue(is_dip)
            self.assertEqual(dip_meta["dlc_code"], "PAW")
            self.assertEqual(dip_meta["dlc_subcode"], "FOREPAW")
            self.assertGreater(dip_y, fault_y)


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

    def test_responsive_layout_modes_and_hysteresis(self):
        try:
            root = mt.tk.Tk()
            root.withdraw()
        except mt.tk.TclError:
            self.skipTest("Tk display not available in headless environment")
            return

        try:
            with unittest.mock.patch.object(mt.ParallelYoloOpenCVEngine, "_init_yolo", return_value=None):
                app = mt.PerVideoIDTrackerApp(root)

            # Propagation locks must be active to prevent section jumping when child texts change
            self.assertFalse(app.list_outer.pack_propagate())
            self.assertFalse(app.ctrl_outer.pack_propagate())
            for kpi_wrap in app.kpi_card_wraps:
                self.assertFalse(kpi_wrap.pack_propagate())

            # Wide layout (1260x830)
            app._apply_responsive_root(1260, 830)
            self.assertEqual(app._workspace_mode, "split")
            self.assertEqual(app._kpi_mode, "4col")
            self.assertEqual(app._toolbar_mode, "1row")
            self.assertTrue(app._subtitle_visible)
            self.assertEqual(int(app.log_area.cget("height")), 5)

            # Narrow layout (680x540) -> stacks workspace, 2x2 KPI grid, 2-row toolbar, compact log
            app._apply_responsive_root(680, 540)
            self.assertEqual(app._workspace_mode, "stacked")
            self.assertEqual(app._kpi_mode, "2x2")
            self.assertEqual(app._toolbar_mode, "2row")
            self.assertFalse(app._subtitle_visible)
            self.assertEqual(int(app.log_area.cget("height")), 3)

            # Hysteresis zone (895px is between 880 and 910) -> must stay in "stacked" without oscillating
            app._apply_responsive_root(895, 700)
            self.assertEqual(app._workspace_mode, "stacked")

            # Crossing upper threshold (>= 910px) -> transitions back to "split"
            app._apply_responsive_root(940, 780)
            self.assertEqual(app._workspace_mode, "split")
            self.assertEqual(app._kpi_mode, "4col")
            self.assertTrue(app._subtitle_visible)

            # Parameter grid internal responsiveness (1col vs 2col)
            app._update_ctrl_internal_responsiveness(300)
            self.assertEqual(app._param_grid_mode, "1col")
            app._update_ctrl_internal_responsiveness(380)
            self.assertEqual(app._param_grid_mode, "2col")

            # Output directory middle-ellipsis formatting on narrow widths
            app.output_base_dir = "/very/long/laboratory/directory/path/for/mouse/kinematic/experiments/2026_batch_01"
            short_txt = app._format_output_dir_text(max_chars=45)
            self.assertIn("...", short_txt)
            self.assertLessEqual(len(short_txt), 48)

            # Queue control state toggling must disable/enable the actual UI buttons
            app._set_queue_controls_state("disabled")
            for btn_name in (
                "btn_add_vid",
                "btn_add_url",
                "btn_edit_id",
                "btn_remove_vid",
                "btn_clear_vid",
                "btn_load_prof_main",
                "btn_save_prof_main",
                "btn_train_ai",
                "btn_change_dir",
            ):
                btn_widget = getattr(app, btn_name, None)
                self.assertIsNotNone(btn_widget, f"Missing button {btn_name}")
                self.assertIn("disabled", str(btn_widget.cget("state")))

            app._set_queue_controls_state("normal")
            for btn_name in ("btn_add_vid", "btn_add_url", "btn_edit_id", "btn_remove_vid", "btn_clear_vid"):
                btn_widget = getattr(app, btn_name)
                self.assertIn("normal", str(btn_widget.cget("state")))
        finally:
            try:
                root.destroy()
            except mt.tk.TclError:
                pass

    @staticmethod
    def _make_headless_detector():
        app = mt.PerVideoIDTrackerApp.__new__(mt.PerVideoIDTrackerApp)
        app.kernel_small = np.ones((3, 3), np.uint8)
        app.kernel_grad_3 = np.ones((3, 3), np.uint8)
        app.kernel_horiz = np.ones((5, 19), np.uint8)
        app.kernel_upper_bridge = np.ones((5, 29), np.uint8)
        app.kernel_fill = np.ones((7, 7), np.uint8)
        app.kernel_blackhat_13 = mt.cv2.getStructuringElement(mt.cv2.MORPH_RECT, (13, 13))
        app.kernel_torso_open = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 7))
        app._run_flags = {"use_yolo_fusion": False, "lock_lr_active": False, "use_comma": True}
        with unittest.mock.patch.object(mt.ParallelYoloOpenCVEngine, "_init_yolo", return_value=None):
            app.hybrid_locator = mt.ParallelYoloOpenCVEngine(lambda _: None)
        return app

    def test_detect_mouse_preserves_pink_paw_on_rung_and_supports_1d_fault_curve(self):
        app = self._make_headless_detector()
        rh, rw = 160, 260
        fault_y = 112
        fault_curve = np.full(rw, fault_y, dtype=np.int32)

        # Bright background with a dark ladder rung right at fault_y
        base_gray = np.full((rh, rw), 220, dtype=np.uint8)
        base_gray[fault_y - 3:fault_y + 4, 128:136] = 45
        ladder_mask = app._create_ladder_mask(base_gray, ladder_thresh=140, fault_y_local=fault_curve)
        inv_ladder_mask = mt.cv2.bitwise_not(ladder_mask)
        # Ensure the rung is masked out in raw inv_ladder_mask
        self.assertEqual(int(inv_ladder_mask[fault_y, 132]), 0)

        # Simulate a +6 camera exposure shift on the current frame + dark mouse torso + pink paw on & below the rung
        crop = np.full((rh, rw, 3), 226, dtype=np.uint8)
        crop[fault_y - 3:fault_y + 4, 128:136] = (50, 50, 50)
        # Mouse torso above fault line (with a bright fur highlight in the middle to test cavity filling)
        mt.cv2.ellipse(crop, (130, 74), (44, 24), 0, 0, 360, (38, 38, 38), -1)
        mt.cv2.circle(crop, (130, 72), 5, (215, 215, 215), -1)
        # Pink limb extending from ventral torso (y=96) across the rung (fault_y=112) down to y=128
        crop[96:128, 129:136] = (115, 118, 215)

        detected, mask, bbox, skin_map = app._detect_mouse_on_crop(
            crop,
            base_gray,
            inv_ladder_mask,
            rw,
            rh,
            dark_t=155,
            diff_t=24,
            fault_y_local=fault_curve,
            return_skin=True,
            use_yolo=False,
        )
        self.assertTrue(detected)
        self.assertIsNotNone(mask)
        self.assertIsNotNone(bbox)
        self.assertIsNotNone(skin_map)
        # Internal specular highlight cavity at (72, 130) must be filled inside the upper torso
        self.assertGreater(int(mask[72, 130]), 0)
        # Pink paw pixels on the rung (y=fault_y, x=132) and below it (y=124, x=132) must NOT be erased by inv_ladder_mask
        self.assertGreater(int(mask[fault_y, 132]), 0)
        self.assertGreater(int(mask[124, 132]), 0)

        # Shallow pink paw slip (depth ~11-15px below fault_y) must be detected as a real PAW dip
        is_dip, dip_x, dip_y, _aspect, dip_depth, dip_meta = app._check_real_dip_below_line(
            mask,
            fault_curve,
            crop=crop,
            bbox=bbox,
            inv_ladder_mask=inv_ladder_mask,
            move_dir=1.0,
            return_meta=True,
            skin_map=skin_map,
            base_gray=base_gray,
        )
        self.assertTrue(is_dip)
        self.assertEqual(dip_meta["dlc_code"], "PAW")
        self.assertGreaterEqual(dip_depth, 10.0)
        self.assertTrue(126 <= dip_x <= 138)
        self.assertGreater(dip_y, fault_y)

    def test_stale_pose_is_not_reused_as_ghost_mouse(self):
        app = self._make_headless_detector()
        rh, rw = 160, 260
        base_gray = np.full((rh, rw), 220, dtype=np.uint8)
        inv_ladder_mask = np.full((rh, rw), 255, dtype=np.uint8)
        empty_crop = np.full((rh, rw, 3), 220, dtype=np.uint8)

        app.hybrid_locator.is_rodent_pose = True
        stale_pose = {
            "bbox": (80, 50, 80, 40),
            "nose_pt": (155, 70),
            "head_pt": (145, 65),
            "shoulder_pt": (130, 68),
            "spine_mid": (115, 66),
            "hip_pt": (98, 68),
            "tail_base": (85, 70),
            "tail_mid": (70, 70),
            "tail_tip": (55, 70),
            "fore_paw_pt": (130, 92),
            "hind_paw_pt": (98, 92),
            "tail_chain": [(55, 70), (70, 70), (85, 70)],
            "frame_idx": 10,
        }
        app.hybrid_locator._set_thread_pose("vid_1", stale_pose, 10)
        # Also plant a pose on another stream / sync slot to verify no cross-stream leakage
        app.hybrid_locator.last_sync_pose = dict(stale_pose, frame_idx=100)

        # Querying at frame_idx=50 with max_age=5 must reject the stale pose from frame 10
        pose_lookup = app.hybrid_locator.get_latest_pose_for_bbox(
            0, 0, rw, rh, rw, rh, stream_id="vid_1", frame_idx=50, max_age=5
        )
        self.assertIsNone(pose_lookup)

        detected, mask, bbox = app._detect_mouse_on_crop(
            empty_crop,
            base_gray,
            inv_ladder_mask,
            rw,
            rh,
            dark_t=155,
            diff_t=24,
            fault_y_local=112,
            stream_id="vid_1",
            frame_idx=50,
            ai_max_age=5,
            use_yolo=False,
        )
        self.assertFalse(detected)
        self.assertIsNone(mask)
        self.assertIsNone(bbox)

    def test_kalman_tracker_predict_next_and_outlier_rejection(self):
        kf = mt.MouseKalmanTracker()
        x0, y0 = kf.update(100, 80)
        self.assertEqual((x0, y0), (100, 80))
        x1, y1 = kf.update(112, 80)
        pred_x, pred_y = kf.predict_next()
        self.assertGreaterEqual(pred_x, 100)
        self.assertTrue(60 <= pred_y <= 100)
        pred_x_dt, pred_y_dt = kf.predict_next(dt_frames=2)
        self.assertGreaterEqual(pred_x_dt, pred_x)
        self.assertTrue(60 <= pred_y_dt <= 100)

        # Single-frame extreme outlier jump (> 95px) is damped before corrupting the state
        x_jump, _ = kf.update(500, 80, dt_frames=1)
        self.assertLess(x_jump, 300)

    def test_fmt_num_uses_thread_safe_run_flags(self):
        app = mt.PerVideoIDTrackerApp.__new__(mt.PerVideoIDTrackerApp)
        app._run_flags = {"use_comma": False}
        self.assertEqual(app._fmt_num(12.345, "{:.2f}"), "12.35")
        app._run_flags = {"use_comma": True}
        self.assertEqual(app._fmt_num(12.345, "{:.2f}"), "12,35")


class TestWindowsPlatformCompatibility(unittest.TestCase):
    """Tests Windows-specific runtime paths (win32 identity/DPI, iconbitmap, APPDATA, _MEIPASS, CUDA, startfile)."""

    def test_windows_native_os_identity_and_high_dpi(self):
        fake_windll = unittest.mock.MagicMock()
        with (
            unittest.mock.patch.object(mt.sys, "platform", "win32"),
            unittest.mock.patch.object(mt.ctypes, "windll", fake_windll, create=True),
        ):
            mt.configure_native_os_identity()
            fake_windll.shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(mt.APP_ID)
            fake_windll.shcore.SetProcessDpiAwareness.assert_called_once_with(1)

        # Fallback to user32.SetProcessDPIAware() when shcore raises OSError
        fake_windll_fallback = unittest.mock.MagicMock()
        fake_windll_fallback.shcore.SetProcessDpiAwareness.side_effect = OSError("shcore unavailable")
        with (
            unittest.mock.patch.object(mt.sys, "platform", "win32"),
            unittest.mock.patch.object(mt.ctypes, "windll", fake_windll_fallback, create=True),
        ):
            mt.configure_native_os_identity()
            fake_windll_fallback.user32.SetProcessDPIAware.assert_called_once()

    def test_windows_apply_window_icon_and_unicode_fallback(self):
        fake_root = unittest.mock.MagicMock()
        with unittest.mock.patch.object(mt.sys, "platform", "win32"):
            mt.apply_window_icon(fake_root)
            fake_root.iconbitmap.assert_called_once()
            arg_ico = fake_root.iconbitmap.call_args.kwargs.get("default", "")
            self.assertTrue(arg_ico.endswith("icon.ico"))

        # Test fallback when iconbitmap raises TclError on a path with Hungarian accents
        with tempfile.TemporaryDirectory(prefix="Mérés_Ékezetes_") as tmp_dir:
            unicode_ico = os.path.join(tmp_dir, "icon.ico")
            dummy_img = np.full((32, 32, 3), 128, dtype=np.uint8)
            _ok, png_buf = mt.cv2.imencode(".png", dummy_img)
            png_buf.tofile(unicode_ico)
            fake_root_fb = unittest.mock.MagicMock()
            fake_root_fb.iconbitmap.side_effect = mt.tk.TclError("iconbitmap failed")
            with (
                unittest.mock.patch.object(mt.sys, "platform", "win32"),
                unittest.mock.patch.object(mt, "get_resource_path", return_value=unicode_ico),
                unittest.mock.patch.object(mt.tk, "PhotoImage", return_value="fake_photo") as mock_photo,
            ):
                mt.apply_window_icon(fake_root_fb)
                mock_photo.assert_called_once()
                fake_root_fb.iconphoto.assert_called_once_with(True, "fake_photo")

    def test_windows_appdata_yolo_config_and_meipass_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            win_appdata = os.path.join(tmpdir, "AppData", "Roaming")
            meipass_dir = os.path.join(tmpdir, "_MEI12345")
            os.makedirs(os.path.join(meipass_dir, "assets"), exist_ok=True)
            bundled_ico = os.path.join(meipass_dir, "assets", "icon.ico")
            with open(bundled_ico, "wb") as f:
                f.write(b"fake_ico_data")

            with (
                unittest.mock.patch.dict(os.environ, {"APPDATA": win_appdata}, clear=False),
                unittest.mock.patch.object(mt.sys, "_MEIPASS", meipass_dir, create=True),
                unittest.mock.patch.object(mt.sys, "platform", "win32"),
            ):
                os.environ.pop("YOLO_CONFIG_DIR", None)
                u_dir = mt._ensure_writable_yolo_config_dir()
                self.assertEqual(str(u_dir), os.path.join(win_appdata, "Ultralytics"))
                self.assertEqual(os.environ.get("YOLO_CONFIG_DIR"), os.path.join(win_appdata, "Ultralytics"))
                resolved_ico = mt.get_resource_path("icon.ico")
                self.assertEqual(resolved_ico, bundled_ico)

    def test_windows_open_results_folder_and_onedrive_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = mt.PerVideoIDTrackerApp.__new__(mt.PerVideoIDTrackerApp)
            app.output_base_dir = os.path.join(tmpdir, "Kimenet_Árvíztűrő")
            mock_startfile = unittest.mock.MagicMock()
            with (
                unittest.mock.patch.object(mt.sys, "platform", "win32"),
                unittest.mock.patch.object(mt.os, "startfile", mock_startfile, create=True),
            ):
                app.open_results_folder()
                mock_startfile.assert_called_once_with(os.path.abspath(app.output_base_dir))

            # Verify OneDrive/Documents fallback when ~/Documents is absent on Windows
            fake_home = os.path.join(tmpdir, "WinUser")
            onedrive_docs = os.path.join(fake_home, "OneDrive", "Documents")
            os.makedirs(onedrive_docs, exist_ok=True)
            with unittest.mock.patch.object(mt.os.path, "expanduser", return_value=fake_home):
                safe_dir = mt.get_safe_base_dir("MouseAnalyzer_Eredmenyek")
                self.assertEqual(safe_dir, os.path.join(onedrive_docs, "MouseAnalyzer_Eredmenyek"))
                self.assertTrue(os.path.isdir(safe_dir))

    def test_windows_cuda_compute_device_detection(self):
        fake_torch = unittest.mock.MagicMock()
        fake_torch.backends.mps.is_available.return_value = False
        fake_torch.cuda.is_available.return_value = True
        fake_torch.cuda.device_count.return_value = 1
        fake_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4070"
        with (
            unittest.mock.patch.object(mt.sys, "platform", "win32"),
            unittest.mock.patch.object(mt, "_CACHED_COMPUTE_DEVICE", None),
            unittest.mock.patch.object(mt, "_get_torch", return_value=fake_torch),
        ):
            dev_info = mt.get_optimal_compute_device()
            self.assertEqual(dev_info["device"], "cuda:0")
            self.assertEqual(dev_info["type"], "cuda")
            self.assertTrue(dev_info["has_gpu"])
            self.assertIn("RTX 4070", dev_info["name"])

    def test_end_to_end_exe_simulation_pipeline_and_export(self):
        """Simulates a frozen Windows .exe run across a synthetic rodent ladder video from start gate to CSV/heatmap export."""
        with tempfile.TemporaryDirectory(prefix="ExeSim_E2E_") as tmpdir:
            video_path = os.path.join(tmpdir, "Sim_Mouse_01.mp4")
            output_dir = os.path.join(tmpdir, "MouseAnalyzer_Eredmenyek")
            os.makedirs(output_dir, exist_ok=True)

            width, height, fps = 640, 240, 30
            rx, ry, rw, rh = 40, 40, 560, 160
            fault_y = ry + 112  # y=152

            fourcc = mt.cv2.VideoWriter_fourcc(*"mp4v")
            writer = mt.cv2.VideoWriter(video_path, fourcc, fps, (width, height))
            self.assertTrue(writer.isOpened())

            def _bg_frame():
                frm = np.full((height, width, 3), 225, dtype=np.uint8)
                mt.cv2.line(frm, (rx, fault_y + 2), (rx + rw, fault_y + 2), (160, 160, 160), 2)
                for rung_x in range(rx + 20, rx + rw - 10, 28):
                    mt.cv2.rectangle(frm, (rung_x - 3, fault_y - 3), (rung_x + 3, fault_y + 4), (55, 55, 55), -1)
                return frm

            for _ in range(50):
                writer.write(_bg_frame())

            xs = (
                np.linspace(100, 280, 36).astype(int).tolist()
                + [280] * 12
                + np.linspace(286, 555, 48).astype(int).tolist()
            )
            for mx in xs:
                frm = _bg_frame()
                torso_cy = fault_y - 28
                mt.cv2.ellipse(frm, (mx, torso_cy), (46, 22), 0, 0, 360, (32, 32, 32), -1)
                mt.cv2.ellipse(frm, (mx + 42, torso_cy + 3), (18, 13), 10, 0, 360, (36, 36, 36), -1)
                mt.cv2.circle(frm, (mx + 58, torso_cy + 5), 4, (130, 135, 225), -1)
                mt.cv2.rectangle(frm, (mx - 24, fault_y - 12), (mx - 16, fault_y - 2), (118, 122, 215), -1)
                if 365 <= mx <= 395:
                    paw_x = mx + 18
                    mt.cv2.rectangle(frm, (paw_x - 4, fault_y - 16), (paw_x + 4, fault_y + 22), (112, 115, 218), -1)
                else:
                    mt.cv2.rectangle(frm, (mx + 14, fault_y - 12), (mx + 22, fault_y - 2), (118, 122, 215), -1)
                writer.write(frm)

            for _ in range(10):
                writer.write(_bg_frame())
            writer.release()

            app = mt.PerVideoIDTrackerApp.__new__(mt.PerVideoIDTrackerApp)
            app.lang = "hu"
            app.output_base_dir = output_dir
            app.is_running = True
            app.pending_results = []
            app.gpu_available = False
            app.gpu_device_name = "CPU"
            app.kernel_small = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (3, 3))
            app.kernel_horiz = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (11, 3))
            app.kernel_upper_bridge = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (15, 7))
            app.kernel_fill = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 7))
            app.kernel_rung_close = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 7))
            app.kernel_sag_guard = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 13))
            app.kernel_blackhat_13 = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (13, 13))
            app.kernel_torso_open = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (9, 7))
            app.kernel_grad_3 = mt.cv2.getStructuringElement(mt.cv2.MORPH_RECT, (3, 3))
            app.log = lambda _msg: None
            app.update_row_status = lambda _uid, _st: None
            app.increment_progress = lambda _tot: None
            app.reset_ui = lambda: None
            app.root = unittest.mock.MagicMock()

            with unittest.mock.patch.object(mt.ParallelYoloOpenCVEngine, "_init_yolo", return_value=None):
                app.hybrid_locator = mt.ParallelYoloOpenCVEngine(app.log)
            app.auto_engine = mt.AutoAdaptiveLadderEngine(app.log)
            app.dlc_addon = mt.DLCAddonManager(app.log)
            app.dlc_addon.dlc_available = False

            app._run_flags = {
                "use_gpu": False,
                "auto_calib": False,
                "use_yolo_fusion": False,
                "dlc_superanimal": True,
                "dlc_export_train": False,
                "enable_review": False,
                "lock_lr_active": True,
                "use_comma": True,
            }

            roi_cfg = mt.ROIConfig(
                rx=rx, ry=ry, rw=rw, rh=rh,
                left_gate_x=95, right_gate_x=545,
                dark_t=155, diff_t=24, ladder_t=130, fault_pct=70,
                z_active=True, kin_active=True,
                dip_cooldown_sec=0.40, dip_min_dist_px=25,
                gate_dist_cm=60.0, px_per_cm=(545 - 95) / 60.0,
                frame_stride=1, use_gpu=False, use_kalman=True,
                bidirectional=False, protocol_runs="1", lock_lr=True,
            )

            video_queue = [{"uid": "v1", "name": "Sim_Mouse_01.mp4", "id": "Mouse_Sim_01", "path": video_path}]
            app.execute_parallel_processing(video_queue, roi_cfg, max_workers=1)
            self.assertEqual(len(app.pending_results), 1)
            self.assertEqual(len(app.pending_results[0]["runs"]), 1)

            app._export_worker()
            master_csv = os.path.join(output_dir, "Minden_Egyed_Meresi_Adatai.csv")
            self.assertTrue(os.path.exists(master_csv))
            subj_dir = os.path.join(output_dir, "Egyed_Mouse_Sim_01_eredmenyek")
            self.assertTrue(os.path.exists(os.path.join(subj_dir, "egyed_Mouse_Sim_01_meresi_adatok.csv")))
            self.assertTrue(os.path.exists(os.path.join(subj_dir, "egyed_Mouse_Sim_01_futas_1_heatmap.jpg")))
            self.assertTrue(os.path.exists(os.path.join(subj_dir, "egyed_Mouse_Sim_01_futas_1_lenyulas_1.jpg")))

    def test_per_video_calibration_workflow_and_custom_calib_application(self):
        """Verifies that var_per_video_calib prompts for each video (or applies to remaining) and process_single_video uses each video's custom_calib."""
        with tempfile.TemporaryDirectory(prefix="PerVidCalib_") as tmpdir:
            v1_path = os.path.join(tmpdir, "Vid_1.mp4")
            v2_path = os.path.join(tmpdir, "Vid_2.mp4")
            v3_path = os.path.join(tmpdir, "Vid_3.mp4")
            output_dir = os.path.join(tmpdir, "Out")
            os.makedirs(output_dir, exist_ok=True)

            width, height, fps = 640, 240, 30
            fourcc = mt.cv2.VideoWriter_fourcc(*"mp4v")
            for vp in (v1_path, v2_path, v3_path):
                writer = mt.cv2.VideoWriter(vp, fourcc, fps, (width, height))
                frm = np.full((height, width, 3), 220, dtype=np.uint8)
                for _ in range(15):
                    writer.write(frm)
                writer.release()

            app = mt.PerVideoIDTrackerApp.__new__(mt.PerVideoIDTrackerApp)
            app.lang = "en"
            app.output_base_dir = output_dir
            app.is_running = True
            app.pending_results = []
            app.gpu_available = False
            app.gpu_device_name = "CPU"
            app.calib_dark_thresh = 135
            app.calib_diff_thresh = 24
            app.calib_ladder_thresh = 132
            app.calib_fault_Ratio = 72
            app.saved_geometry = None
            app.var_per_video_calib = unittest.mock.MagicMock(get=lambda: True)
            app.var_auto_calib = unittest.mock.MagicMock(get=lambda: False)
            app.var_use_gpu = unittest.mock.MagicMock(get=lambda: False)
            app.var_yolo_fusion = unittest.mock.MagicMock(get=lambda: False)
            app.var_bidirectional = unittest.mock.MagicMock(get=lambda: False)
            app.var_lock_lr_direction = unittest.mock.MagicMock(get=lambda: True)
            app.var_protocol_runs = unittest.mock.MagicMock(get=lambda: "1")
            app.var_enable_review = unittest.mock.MagicMock(get=lambda: False)
            app.var_enable_zones = unittest.mock.MagicMock(get=lambda: True)
            app.var_enable_kinematics = unittest.mock.MagicMock(get=lambda: True)
            app.var_use_kalman = unittest.mock.MagicMock(get=lambda: True)
            app.var_dlc_superanimal = unittest.mock.MagicMock(get=lambda: False)
            app.var_dlc_export_train = unittest.mock.MagicMock(get=lambda: False)
            app.var_threads = unittest.mock.MagicMock(get=lambda: "1")
            app.var_stride = unittest.mock.MagicMock(get=lambda: "1")
            app.var_cooldown = unittest.mock.MagicMock(get=lambda: "0.50")
            app.var_min_dist = unittest.mock.MagicMock(get=lambda: "30")
            app.var_gate_cm = unittest.mock.MagicMock(get=lambda: "60.0")
            app.var_decimal = unittest.mock.MagicMock(get=lambda: ". (OriginPro)")

            app.kernel_small = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (3, 3))
            app.kernel_horiz = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (11, 3))
            app.kernel_upper_bridge = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (15, 7))
            app.kernel_fill = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 7))
            app.kernel_rung_close = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 7))
            app.kernel_sag_guard = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (7, 13))
            app.kernel_blackhat_13 = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (13, 13))
            app.kernel_torso_open = mt.cv2.getStructuringElement(mt.cv2.MORPH_ELLIPSE, (9, 7))
            app.kernel_grad_3 = mt.cv2.getStructuringElement(mt.cv2.MORPH_RECT, (3, 3))
            app.log = lambda _msg: None
            app.update_row_status = lambda _uid, _st: None
            app.increment_progress = lambda _tot: None
            app.reset_ui = lambda: None
            app._refresh_kpi_cards = lambda: None
            app._build_profile_dict = lambda: {"per_video_calib": True}
            app.root = unittest.mock.MagicMock()

            with unittest.mock.patch.object(mt.ParallelYoloOpenCVEngine, "_init_yolo", return_value=None):
                app.hybrid_locator = mt.ParallelYoloOpenCVEngine(app.log)
            app.auto_engine = mt.AutoAdaptiveLadderEngine(app.log)
            app.dlc_addon = mt.DLCAddonManager(app.log)
            app.dlc_addon.dlc_available = False

            app.video_data = [
                {"uid": "u1", "name": "Vid_1.mp4", "id": "101", "path": v1_path},
                {"uid": "u2", "name": "Vid_2.mp4", "id": "102", "path": v2_path},
                {"uid": "u3", "name": "Vid_3.mp4", "id": "103", "path": v3_path},
            ]

            calib_calls = []

            def _fake_interactive_calibrate(video_item, idx, total_cal, prev_calib=None):
                calib_calls.append((video_item["uid"], idx, total_cal))
                if idx == 1:
                    return ({
                        "rx": 30, "ry": 40, "rw": 550, "rh": 150,
                        "left_gate_x": 85, "right_gate_x": 515,
                        "dark_t": 140, "diff_t": 22, "ladder_t": 125, "fault_pct": 68,
                        "base_gray": np.full((150, 550), 220, dtype=np.uint8),
                    }, False)
                # On video 2, user adjusts gates and presses 'A' (apply_to_remaining=True)
                return ({
                    "rx": 45, "ry": 50, "rw": 520, "rh": 140,
                    "left_gate_x": 110, "right_gate_x": 490,
                    "dark_t": 150, "diff_t": 28, "ladder_t": 135, "fault_pct": 74,
                    "base_gray": np.full((140, 520), 220, dtype=np.uint8),
                }, True)

            with unittest.mock.patch.object(app, "_interactive_calibrate_video", side_effect=_fake_interactive_calibrate), \
                 unittest.mock.patch.object(app, "_launch_processing_thread") as mock_launch:
                app.setup_and_run_parallel()
                # Only called for u1 and u2 because u2 returned apply_to_remaining=True
                self.assertEqual(calib_calls, [("u1", 1, 3), ("u2", 2, 3)])
                mock_launch.assert_called_once_with(30, 40, 550, 150, 85, 515)

            self.assertEqual(app.video_data[0]["custom_calib"]["left_gate_x"], 85)
            self.assertEqual(app.video_data[1]["custom_calib"]["left_gate_x"], 110)
            # Video 3 inherited Video 2's custom calibration (without Video 2's base_gray)
            self.assertEqual(app.video_data[2]["custom_calib"]["left_gate_x"], 110)
            self.assertEqual(app.video_data[2]["custom_calib"]["fault_pct"], 74)
            self.assertNotIn("base_gray", app.video_data[2]["custom_calib"])

            # Now execute parallel processing and verify each video's pending_result has its own roi_data
            roi_cfg = mt.ROIConfig(
                rx=30, ry=40, rw=550, rh=150,
                left_gate_x=85, right_gate_x=515,
                dark_t=140, diff_t=22, ladder_t=125, fault_pct=68,
                z_active=True, kin_active=True,
                dip_cooldown_sec=0.50, dip_min_dist_px=30,
                gate_dist_cm=60.0, px_per_cm=(515 - 85) / 60.0,
                frame_stride=1, use_gpu=False, use_kalman=True,
                bidirectional=False, protocol_runs="1", lock_lr=True,
            )
            app._run_flags = {
                "use_gpu": False, "auto_calib": False, "use_yolo_fusion": False,
                "dlc_superanimal": False, "dlc_export_train": False,
                "enable_review": False, "lock_lr_active": True, "use_comma": False,
            }
            app.execute_parallel_processing(app.video_data, roi_cfg, max_workers=1)
            self.assertEqual(len(app.pending_results), 3)
            res_by_uid = {r["uid"]: r["roi_data"] for r in app.pending_results}
            self.assertEqual(res_by_uid["u1"][:6], (30, 40, 550, 150, 85, 515))
            self.assertEqual(res_by_uid["u2"][:6], (45, 50, 520, 140, 110, 490))
            self.assertEqual(res_by_uid["u3"][:6], (45, 50, 520, 140, 110, 490))


if __name__ == "__main__":
    unittest.main()
