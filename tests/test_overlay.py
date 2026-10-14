"""Saved overlay sizes remain compatible with existing configurations."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

class OverlayConfigTests(unittest.TestCase):
    def setUp(self):
        # Allow the protocol suite to set its isolated paths before importing them.
        from alien_thunder import overlay
        self.overlay = overlay

    def test_old_config_keeps_position_and_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "overlay.json")
            with open(path, "w") as stream:
                json.dump({"screen": "HDMI-A-1", "x": 784, "y": 0,
                           "items": {"cpu_temp": False}}, stream)
            with patch.object(self.overlay, "OVERLAY_FILE", path):
                config = self.overlay.load_config()
                self.assertEqual(config["scale"], 1.0)
                self.assertEqual(config["style"], "digital")
                self.assertEqual(config["x"], 784)
                self.assertEqual(config["screen"], "HDMI-A-1")
                self.assertFalse(config["items"]["cpu_temp"])
                self.assertFalse(config["items"]["download"])
                self.assertFalse(config["items"]["upload"])
                config["scale"] = 0.75
                self.overlay.save_config(config)
                self.assertEqual(self.overlay.load_config(), config)

    def test_style_and_selection_saved_together_without_losing_size(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.overlay, "OVERLAY_FILE", os.path.join(directory, "overlay.json")):
                config = self.overlay.default_config()
                config.update(scale=0.75, x=400)
                self.overlay.save_config(config)
                self.assertEqual(self.overlay.command(["items", "cpu_temp,ram", "analog"]), 0)
                saved = self.overlay.load_config()
                self.assertEqual(saved["style"], "analog")
                self.assertEqual(saved["scale"], 0.75)
                self.assertEqual(saved["x"], 400)
                self.assertEqual([k for k, v in saved["items"].items() if v], ["cpu_temp", "ram"])
                self.assertEqual(self.overlay.command(["items", "", "digital"]), 0)
                self.assertFalse(any(self.overlay.load_config()["items"].values()))

    def test_network_selection_preserves_sensor_settings_and_position(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.overlay, "OVERLAY_FILE", os.path.join(directory, "overlay.json")):
                config = self.overlay.default_config()
                config.update(style="analog", x=400, scale=0.75)
                self.overlay.save_config(config)
                self.assertEqual(self.overlay.command(["show", "download"]), 0)
                config["items"]["download"] = True
                self.assertEqual(self.overlay.load_config(), config)
                self.assertEqual(self.overlay.command(["show", "upload"]), 0)
                config["items"]["upload"] = True
                self.assertEqual(self.overlay.load_config(), config)
                self.assertEqual(self.overlay.command(["hide", "download"]), 0)
                config["items"]["download"] = False
                self.assertEqual(self.overlay.load_config(), config)

    def test_size_limits_and_invalid_values(self):
        for value, expected in [(0.1, 0.5), (9, 2.5), (1.25, 1.25),
                                (None, 1.0), ("bad", 1.0), (float("nan"), 1.0),
                                (float("inf"), 1.0)]:
            with self.subTest(value=value):
                self.assertEqual(self.overlay.valid_scale(value), expected)

    def test_size_command_preserves_other_settings_and_rejects_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.overlay, "OVERLAY_FILE", os.path.join(directory, "overlay.json")):
                config = self.overlay.default_config()
                config.update(style="analog", x=123, screen="HDMI-A-1")
                config["items"]["cpu_temp"] = False
                self.overlay.save_config(config)
                for percent in (50, 75, 100, 250):
                    self.assertEqual(self.overlay.command(["size", str(percent)]), 0)
                    config["scale"] = percent / 100
                    self.assertEqual(self.overlay.load_config(), config)
                for invalid in ("49", "251", "nan", "100.5", ""):
                    with patch("sys.stderr"):
                        self.assertEqual(self.overlay.command(["size", invalid]), 2)
                    self.assertEqual(self.overlay.load_config(), config)
