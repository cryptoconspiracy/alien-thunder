"""Non-blocking level meter for the current PipeWire/PulseAudio output."""
from __future__ import annotations

import os
import subprocess
import time


class DefaultOutput:
    def __init__(self):
        self.proc = None
        self.target = ""
        self.last_target_check = 0.0
        self.last_start = 0.0
        self._level = 0.0
        self._floor = 0.0
        self._ceiling = 0.0

    @staticmethod
    def _active_sink() -> str:
        try:
            sinks = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True, timeout=2)
            inputs = subprocess.run(["pactl", "list", "short", "sink-inputs"], capture_output=True, text=True, timeout=2)
        except OSError:
            return ""
        if sinks.returncode == 0 and inputs.returncode == 0:
            names = {line.split("\t", 2)[0]: line.split("\t", 2)[1]
                     for line in sinks.stdout.splitlines() if len(line.split("\t", 2)) >= 2}
            for line in inputs.stdout.splitlines():
                fields = line.split("\t")
                if len(fields) >= 2 and fields[1] in names:
                    return names[fields[1]]
        try:
            default = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, timeout=2)
        except OSError:
            return ""
        return default.stdout.strip() if default.returncode == 0 else ""

    def _start(self, target: str):
        self.last_start = time.monotonic()
        self.close()
        if not target:
            return
        try:
            self.proc = subprocess.Popen(["pw-cat", "--record", "--raw", "--target", target + ".monitor",
                                          "--format", "s16", "--rate", "48000", "--channels", "1", "-"],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            os.set_blocking(self.proc.stdout.fileno(), False)
            self.target = target
        except (OSError, AttributeError):
            self.close()

    def level(self) -> float:
        now = time.monotonic()
        if now - self.last_target_check > 1:
            self.last_target_check = now
            target = self._active_sink()
            if target != self.target:
                self._start(target)
        if (self.proc is None or self.proc.poll() is not None) and now - self.last_start > 2:
            self._start(self._active_sink())
        data = b""
        if self.proc is not None and self.proc.stdout is not None:
            try:
                while len(data) < 16384:
                    chunk = os.read(self.proc.stdout.fileno(), 4096)
                    if not chunk:
                        break
                    data += chunk
            except BlockingIOError:
                pass
        if len(data) >= 2:
            samples = memoryview(data[:len(data) // 2 * 2]).cast("h")
            rms = (sum(sample * sample for sample in samples) / len(samples)) ** .5 / 32768
            # Learn the quiet programme level slowly, then react only to audio above it.
            # This avoids a quiet video soundtrack leaving the chassis permanently lit.
            if not self._floor:
                self._floor = rms
            elif rms < self._floor:
                self._floor = self._floor * .8 + rms * .2
            else:
                self._floor = self._floor * .998 + rms * .002
            self._ceiling = max(rms, self._ceiling * .992, self._floor * 1.3)
            gate = self._floor * 1.2
            target = max(0.0, (rms - gate) / max(.0005, self._ceiling - gate)) ** .6
            # Attack immediately; let a peak decay for a few frames so speech does
            # not disappear between individual audio buffers.
            self._level = max(target, self._level * .72)
        else:
            self._level *= .82
        return self._level

    def close(self):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=1)
            self.proc = None
        self.target = ""
