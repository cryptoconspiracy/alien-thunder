"""Failures from the desktop integration must not look like a successful toggle."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch

from alien_thunder import network


class NetworkCommandTests(unittest.TestCase):
    def run_command(self, args, result=None, error=None):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(network.shutil, "which", return_value="/usr/bin/qdbus6"), \
                patch.object(network.subprocess, "run", return_value=result, side_effect=error) as run, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = network.command(args)
        return code, output.getvalue(), errors.getvalue(), run

    def test_status_parses_plasma_reply(self):
        result = subprocess.CompletedProcess([], 0, '{"enabled":true,"count":1}\n', "")
        code, out, err, run = self.run_command(["status"], result)
        self.assertEqual(code, 0)
        self.assertIn('"enabled": true', out)
        self.assertEqual(err, "")
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_script_error_is_not_success(self):
        result = subprocess.CompletedProcess([], 0, "Error: No desktop available", "")
        code, out, err, _ = self.run_command(["on"], result)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("No desktop", err)

    def test_timeout_is_reported(self):
        code, _, err, _ = self.run_command(["off"], error=subprocess.TimeoutExpired("qdbus6", 15))
        self.assertEqual(code, 1)
        self.assertIn("timed out", err)

    def test_invalid_action_never_calls_plasma(self):
        code, _, _, run = self.run_command(['on"; malicious()'])
        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_missing_qdbus(self):
        with patch.object(network.shutil, "which", return_value=None), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(network.command(["on"]), 1)

    def test_desktop_toggle_targets_only_desktop_sensor_widgets(self):
        result = subprocess.CompletedProcess([], 0, '{"enabled":true,"count":1}', "")
        with patch.object(network.shutil, "which", return_value="/usr/bin/qdbus6"), \
                patch.object(network.subprocess, "run", return_value=result) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(network.command(["on"], widget="alien-thunder"), 0)
        script = run.call_args.args[0][-1]
        self.assertIn('const type = "alien-thunder";', script)
        self.assertIn("for (const d of desktops())", script)
        self.assertNotIn("panels()", script)
        self.assertIn('matches.length === 0', script)

    def test_unknown_widget_rejected(self):
        with self.assertRaises(ValueError):
            network.script("on", "unexpected-widget")
