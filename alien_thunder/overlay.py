"""Floating readouts (CPU/GPU temperature, fan speed, memory) that stay above every window.

The readouts sit side by side in one bar, a wlr-layer-shell surface on the overlay layer,
so it stays above fullscreen games too. Its position is a margin from the top-left corner
of the screen it's on: plain Wayland windows can't choose where they go, layer surfaces
can, which is what lets the spot survive a restart. The ✕ on the bar turns the overlay off.

The daemon writes the sensor values; this process only draws them. The position and
which readouts are shown live in ~/.config/alien-thunder/overlay.json, and the panel
widget changes them through `alien-thunder overlay ...`.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

from . import i18n, paths, profiles, sensors

_ = i18n.gettext

OVERLAY_FILE = os.path.join(paths.CONFIG_DIR, "overlay.json")
UNIT = "alien-thunder-overlay.service"
NETWORK_ITEMS = ("download", "upload")
ITEMS = ("cpu_temp", "cpu_load", "gpu_temp", "gpu_mem", "cpu_fan", "gpu_fan", "ram", "ram_gb") + NETWORK_ITEMS


def default_config() -> dict:
    return {"screen": "", "x": 24, "y": 80, "scale": 1.0, "style": "digital",
            "items": {k: k not in NETWORK_ITEMS for k in ITEMS}}


def valid_scale(value) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.5, min(2.5, scale)) if math.isfinite(scale) else 1.0


def load_config() -> dict:
    cfg = default_config()
    try:
        with open(OVERLAY_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return cfg
    cfg["scale"] = valid_scale(saved.get("scale", 1.0))
    if saved.get("style") in ("digital", "analog"):
        cfg["style"] = saved["style"]
    for key in ("screen", "x", "y"):
        if key in saved:
            cfg[key] = saved[key]
    for k, shown in (saved.get("items") or {}).items():
        if k in ITEMS:
            # the first version kept one tile per reading: {"shown": ..., "x": ...}
            cfg["items"][k] = bool(shown.get("shown", True) if isinstance(shown, dict) else shown)
    return cfg


def save_config(cfg: dict) -> None:
    profiles._atomic_write(OVERLAY_FILE, cfg)


def labels() -> dict:
    return {"cpu_temp": _("CPU"), "cpu_load": _("CPU load"), "gpu_temp": _("GPU"), "gpu_mem": _("VRAM"),
            "cpu_fan": _("CPU fan"), "gpu_fan": _("GPU fan"), "ram": _("RAM"), "ram_gb": _("RAM"),
            "download": _("Download"), "upload": _("Upload")}


def main() -> int:
    # A small bar doesn't need the GPU, and staying off it keeps the bar out of a game's way.
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    from PySide6.QtCore import (Property, QFileSystemWatcher, QObject, QPoint, QTimer, QUrl, Signal, Slot,
                                qInstallMessageHandler)
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine

    class Backend(QObject):
        valuesChanged = Signal()
        configChanged = Signal()

        def __init__(self):
            super().__init__()
            self._values = {}
            self._cfg = load_config()
            os.makedirs(paths.CONFIG_DIR, exist_ok=True)
            self.watcher = QFileSystemWatcher([paths.CONFIG_DIR], self)
            self.watcher.directoryChanged.connect(self._reload)
            self.timer = QTimer(self, interval=1000, timeout=self._poll)
            self.timer.start()
            self._poll()

        def _poll(self):
            try:
                with open(sensors.SENSORS_FILE, encoding="utf-8") as f:
                    values = json.load(f)
            except (OSError, ValueError):
                values = {}
            if values != self._values:
                self._values = values
                self.valuesChanged.emit()

        def _reload(self, *_a):
            # Our own saves land here too; they match what we hold, so nothing redraws.
            cfg = load_config()
            if any(cfg[k] != self._cfg[k] for k in ("items", "scale", "style")):
                # Different readings mean a different width; see relaunch().
                self.relaunch()
            if cfg != self._cfg:
                self._cfg = cfg
                self.configChanged.emit()

        @Property("QVariantMap", notify=valuesChanged)
        def values(self):
            return self._values

        @Property("QVariantMap", notify=configChanged)
        def config(self):
            return self._cfg

        @Property("QVariantMap", constant=True)
        def labels(self):
            return labels()

        @Property("QStringList", constant=True)
        def items(self):
            return list(ITEMS)

        @Property("QVariantList", constant=True)
        def screens(self):
            return [{"name": s.name(), "x": s.geometry().x(), "y": s.geometry().y(),
                     "width": s.geometry().width(), "height": s.geometry().height()}
                    for s in QGuiApplication.screens()]

        # LayerShellQt places the surface by its own screen property, not the window's.
        @Slot(str, result=QObject)
        def screenObject(self, name):
            scr = self._screen(name)
            # A QScreen has no parent, and QML takes ownership of parentless objects a
            # method returns: its garbage collector then deleted the application's
            # screen, the bar was left pointing at nothing, and Qt crashed every few
            # minutes, whenever the collector ran.
            QQmlEngine.setObjectOwnership(scr, QQmlEngine.ObjectOwnership.CppOwnership)
            return scr

        @staticmethod
        def _screen(name):
            screens = QGuiApplication.screens()
            return next((s for s in screens if s.name() == name), screens[0])

        # Qt.application.screens hands QML descriptions of the screens, not QScreen
        # objects, so the screen side of placing the bar happens here.
        @Slot(QObject, result="QVariantMap")
        def restore(self, window):
            scr = self._screen(self._cfg["screen"])
            g = scr.geometry()
            x = max(0, min(int(self._cfg["x"]), g.width() - window.width()))
            y = max(0, min(int(self._cfg["y"]), g.height() - window.height()))
            return {"x": x, "y": y, "screen": scr.name(), "ox": g.x(), "oy": g.y()}

        @Slot(QObject, int, int, result="QVariantMap")
        def drop(self, window, gx, gy):
            """Places the bar whose top-left corner was let go at (gx, gy) on the desktop."""
            here = self._screen(self._cfg["screen"])
            center = QPoint(gx + window.width() // 2, gy + window.height() // 2)
            there = QGuiApplication.screenAt(center) or here
            g = there.geometry()
            x = max(0, min(gx - g.x(), g.width() - window.width()))
            y = max(0, min(gy - g.y(), g.height() - window.height()))
            self._cfg.update(screen=there.name(), x=x, y=y)
            save_config(self._cfg)
            return {"x": x, "y": y, "screen": there.name(), "ox": g.x(), "oy": g.y(),
                    "moved": there is not here}

        # A layer surface can't change screens once it exists, and hiding or resizing
        # the bar crashed Qt (the window is left without a screen for a moment). Starting
        # over is cheap and builds the bar on the right screen, at the right size.
        @Slot()
        def relaunch(self):
            print("overlay: starting over (screen, readings or size changed)", file=sys.stderr, flush=True)
            sys.stdout.flush()
            sys.stderr.flush()
            os.execv(sys.executable, [sys.executable] + sys.orig_argv[1:])

        @Slot(float)
        def resize(self, scale):
            scale = valid_scale(scale)
            if scale != self._cfg["scale"]:
                self._cfg["scale"] = scale
                save_config(self._cfg)
                self.relaunch()

        @Slot()
        def close(self):
            # disable, not stop: stopping our own unit from inside would kill us mid-call,
            # and a clean exit is all systemd needs to call the service done.
            subprocess.run(["systemctl", "--user", "disable", UNIT], capture_output=True)
            QGuiApplication.quit()

    # QML errors would otherwise go straight to the journal under a name nobody searches for.
    qInstallMessageHandler(lambda _type, _ctx, msg: print(msg, file=sys.stderr, flush=True))
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Alien Thunder")
    app.setDesktopFileName("alien-thunder")
    app.setQuitOnLastWindowClosed(False)
    icon = os.path.join(os.path.dirname(__file__), "icons", "alien-thunder.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    backend = Backend()
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(os.path.join(os.path.dirname(__file__), "overlay.qml")))
    if not engine.rootObjects():
        return 1

    def note(msg):
        print("overlay: " + msg, file=sys.stderr, flush=True)
    app.screenAdded.connect(lambda s: note("screen added: " + s.name()))
    app.screenRemoved.connect(lambda s: note("screen removed: " + s.name()))
    for w in app.topLevelWindows():
        w.screenChanged.connect(lambda s, w=w: note("window moved to screen: %s" % (s.name() if s else None)))
    return app.exec()


def command(args: list[str]) -> int:
    """alien-thunder overlay [run|on|off|show ITEM|hide ITEM|items LIST [STYLE]|style STYLE|status]"""
    action = args[0] if args else "status"
    if action == "run":
        return main()
    if action in ("on", "off"):
        verb = "enable" if action == "on" else "disable"
        return subprocess.run(["systemctl", "--user", verb, "--now", UNIT]).returncode
    cfg = load_config()
    if action in ("show", "hide") and len(args) == 2 and args[1] in ITEMS:
        cfg["items"][args[1]] = action == "show"
    elif action == "style" and len(args) == 2 and args[1] in ("digital", "analog"):
        cfg["style"] = args[1]
    elif action == "size" and len(args) == 2:
        try:
            percent = int(args[1])
        except ValueError:
            percent = 0
        if not 50 <= percent <= 250:
            print(_("Overlay size must be between 50 and 250 percent."), file=sys.stderr)
            return 2
        cfg["scale"] = percent / 100
    elif action == "items" and len(args) in (2, 3) and (len(args) == 2 or args[2] in ("digital", "analog")):
        # the whole selection at once, so the bar restarts once, not once per reading
        wanted = set(args[1].split(",")) & set(ITEMS)
        style = args[2] if len(args) == 3 else cfg["style"]
        if cfg["items"] == {k: k in wanted for k in ITEMS} and cfg["style"] == style:
            return 0
        cfg["items"] = {k: k in wanted for k in ITEMS}
        cfg["style"] = style
    elif action == "status":
        running = subprocess.run(["systemctl", "--user", "is-active", "-q", UNIT]).returncode == 0
        print(json.dumps({"running": running, **cfg}))
        return 0
    else:
        print(_("usage: alien-thunder overlay [run|on|off|show ITEM|hide ITEM|items ITEM,ITEM,...|status]"), file=sys.stderr)
        print(_("items: %s") % " ".join(ITEMS), file=sys.stderr)
        print("style: digital | analog", file=sys.stderr)
        print("size: 50–250 (%)", file=sys.stderr)
        return 2
    save_config(cfg)
    return 0
