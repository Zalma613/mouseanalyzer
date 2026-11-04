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


if __name__ == "__main__":
    unittest.main()
