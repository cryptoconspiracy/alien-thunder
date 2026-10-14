"""The user service. It keeps the active profile on the LEDs and does the rest in the background.

- applies the active profile at login, retrying with backoff;
- applies it again after suspend or hibernate (login1 PrepareForSleep(false), system bus);
- applies it again when config.json or the active profile's file changes (GFileMonitor);
- applies it again when the keyboard or the AW-ELC come back (hidraw uevents through
  GUdev, plus a check every 20 s);
- runs the software effects (a GLib timer, up to 20 fps) and stops cleanly on SIGTERM;
- G-Mode: Fn+F1 toggles the performance power profile, and F1 stays white while it's
  on, whether the switch came from the key or from Plasma's applet (see gmode.py);
- media keys: Fn+F3 to Fn+F6 send the active profile's action to the music player over
  MPRIS (see mediakeys.py);
- writes the sensor readings for the panel widget and the overlay every 2 s;
- serves io.github.AlienThunder on the session bus for the GUI and the CLI.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time

import dbus
import dbus.mainloop.glib
import dbus.service
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

try:
    gi.require_version("GUdev", "1.0")
    from gi.repository import GUdev  # noqa: E402
except (ValueError, ImportError):  # no libgudev: only the periodic check is left
    GUdev = None

from . import engine as engine_mod  # noqa: E402
from . import gmode, hw, mediakeys, paths, profiles, sensors  # noqa: E402

BACKOFF = (1, 2, 3, 5, 8, 13, 20, 30)


def log(msg: str):
    print(msg, flush=True)


class Daemon(dbus.service.Object):
    def __init__(self, bus_name, loop: GLib.MainLoop):
        super().__init__(bus_name, paths.DBUS_PATH)
        self.loop = loop
        self.engine = engine_mod.Engine(log=log)
        self.cfg = profiles.load_config()
        self.override: dict | None = None  # {"kind": "preview"|"profile", "profile": dict, "slug": str|None}
        self.retry_id = 0
        self.retry_n = 0
        self.debounce_id = 0
        self.sw_id = 0
        self.last_error = ""
        self.last_ok = 0.0
        self.sleeping = False
        self.devs = self._devs()
        self.monitors = []
        self.udev = None
        self.system = None
        self.power_profile = None
        self.before_gmode = "balanced"
        self.key_fd = None
        self.key_watch = 0
        self.key_error = ""
        self.media_fd = None
        self.media_watch = 0
        self.media_error = ""
        self.session = None
        self.sensors = sensors.Sensors()

    # ------------------------------------------------------------ helpers
    def _devs(self):
        return (hw.find_keyboard(), hw.find_chassis())

    def current(self) -> tuple[dict | None, bool]:
        """(profile to apply, whether it is the active one)"""
        if self.override:
            return self.override["profile"], False
        slug = profiles.active_slug()
        if not slug:
            return None, False
        try:
            return profiles.load(slug), True
        except profiles.ProfileError as e:
            self.last_error = str(e)
            log(f"error: {e}")
            return None, False

    # ------------------------------------------------------------ applying
    def apply(self, force: bool = False, reason: str = "") -> bool:
        if self.sleeping:
            return False
        prof, is_active = self.current()
        if prof is None:
            self.stop_sw()
            return False
        if reason:
            log(f"applying '{prof['name']}' ({reason})")
        try:
            self.engine.apply(prof, power=is_active, force=force, backend=self.cfg["chassis_backend"])
        except hw.DeviceError as e:
            self.last_error = str(e)
            log(f"failed: {e}")
            self.schedule_retry()
            self.update_sw()
            return False
        self.last_error = ""
        self.last_ok = time.time()
        self.retry_n = 0
        if self.retry_id:
            GLib.source_remove(self.retry_id)
            self.retry_id = 0
        self.update_sw()
        return True

    def schedule_retry(self):
        if self.retry_id:
            return
        delay = BACKOFF[min(self.retry_n, len(BACKOFF) - 1)]
        self.retry_n += 1
        log(f"trying again in {delay}s")

        def _cb():
            self.retry_id = 0
            self.apply(force=False, reason="retry")
            return False

        self.retry_id = GLib.timeout_add_seconds(delay, _cb)

    def schedule_apply(self, force: bool, reason: str, delay_ms: int = 300):
        if self.debounce_id:
            GLib.source_remove(self.debounce_id)
        state = {"force": force}

        def _cb():
            self.debounce_id = 0
            self.apply(force=state["force"], reason=reason)
            return False

        self.debounce_id = GLib.timeout_add(delay_ms, _cb)

    # ------------------------------------------------------------ software effects
    def update_sw(self):
        if self.engine.animating and not self.sleeping:
            if not self.sw_id:
                interval = int(1000 / self.cfg["fps"])
                self.sw_id = GLib.timeout_add(interval, self._sw_tick)
        else:
            self.stop_sw()

    def stop_sw(self):
        if self.sw_id:
            GLib.source_remove(self.sw_id)
            self.sw_id = 0

    def _sw_tick(self):
        if not self.engine.animating or self.sleeping:
            self.sw_id = 0
            return False
        try:
            self.engine.sw_tick()
        except hw.DeviceError as e:
            self.last_error = str(e)
            log(f"software effect paused: {e}")
            self.sw_id = 0
            self.engine.invalidate()
            self.schedule_retry()
            return False
        return True

    # ------------------------------------------------------------ events
    def on_prepare_for_sleep(self, going_down):
        if going_down:
            log("suspending: pausing")
            self.sleeping = True
            self.stop_sw()
            self.engine.invalidate()
        else:
            log("resuming from suspend")
            self.sleeping = False
            self.engine.invalidate()
            self.retry_n = 0
            self.schedule_apply(force=True, reason="back from suspend", delay_ms=1500)

    @staticmethod
    def _event_name(gfile, other, event) -> str:
        # atomic writes (tmp + rename): the final name comes in "other"
        if event == Gio.FileMonitorEvent.RENAMED and other is not None:
            gfile = other
        return gfile.get_basename() or ""

    def on_config_dir_changed(self, _mon, gfile, other, event):
        if event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                         Gio.FileMonitorEvent.MOVED_IN, Gio.FileMonitorEvent.RENAMED,
                         Gio.FileMonitorEvent.DELETED):
            return
        name = self._event_name(gfile, other, event)
        if name.startswith("."):
            return
        if name == "config.json":
            old = self.cfg
            self.cfg = profiles.load_config()
            if old.get("active_profile") != self.cfg.get("active_profile"):
                self.override = None
                self.schedule_apply(False, "active profile changed")
            elif old.get("fps") != self.cfg.get("fps") or old.get("chassis_backend") != self.cfg.get("chassis_backend"):
                self.stop_sw()
                self.schedule_apply(True, "settings changed")

    def on_profiles_changed(self, _mon, gfile, other, event):
        if event not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                         Gio.FileMonitorEvent.MOVED_IN, Gio.FileMonitorEvent.RENAMED):
            return
        name = self._event_name(gfile, other, event)
        if not name.endswith(".json") or name.startswith("."):
            return
        slug = name[:-5]
        watched = self.override.get("slug") if self.override else profiles.active_slug()
        if slug == watched:
            if self.override and self.override.get("slug"):
                try:
                    self.override["profile"] = profiles.load(slug)
                except profiles.ProfileError:
                    return
            self.schedule_apply(False, "profile edited")

    def on_uevent(self, _client, action, _device):
        # udev has set the uaccess ACLs by the time the event arrives; give it a moment anyway
        if action in ("add", "remove", "bind", "change"):
            GLib.timeout_add(700, self._check_devs)

    def _check_devs(self):
        devs = self._devs()
        if devs != self.devs:
            gained = any(d and d != o for d, o in zip(devs, self.devs))
            self.devs = devs
            self.engine.invalidate()
            if gained:
                self.retry_n = 0
                self.schedule_apply(True, "device reconnected", delay_ms=800)
        return False

    def _periodic(self):
        # a cheap safety net in case a /dev event gets lost
        self._check_devs()
        if self.key_fd is None:
            self.open_gmode_key()
        if self.media_fd is None:
            self.open_media_keys()
        return True

    def _publish_sensors(self):
        values = self.sensors.read()
        if any(values[k] is None for k in self.sensors.files):
            self.sensors.rescan()
        values["gmode"] = self.engine.gmode
        try:
            sensors.publish(values)
        except OSError as e:
            log(f"sensors: {e}")
        return True

    # ------------------------------------------------------------ G-Mode
    def on_power_profile(self, profile: str | None):
        if profile is None or profile == self.power_profile:
            return
        if profile == gmode.PERFORMANCE and self.power_profile:
            self.before_gmode = self.power_profile
        self.power_profile = profile
        on = profile == gmode.PERFORMANCE
        if on != self.engine.gmode:
            self.engine.gmode = on
            self._publish_sensors()
            self.schedule_apply(False, "G-Mode on" if on else "G-Mode off", delay_ms=50)

    def on_power_properties(self, iface, changed, _invalidated):
        if "ActiveProfile" in changed:
            self.on_power_profile(str(changed["ActiveProfile"]))

    def set_gmode(self, on: bool) -> bool:
        target = gmode.PERFORMANCE if on else self.before_gmode
        try:
            gmode.set_profile(target, self.system)
        except dbus.exceptions.DBusException as e:
            self.last_error = f"G-Mode: {e.get_dbus_message()}"
            log(self.last_error)
            return self.engine.gmode
        self.on_power_profile(target)
        return on

    def open_gmode_key(self):
        try:
            self.key_fd = os.open(gmode.KEYBOARD, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            if str(e) != self.key_error:
                self.key_error = str(e)
                log(f"G-Mode key unavailable: {e}")
            return
        self.key_error = ""
        self.key_watch = GLib.io_add_watch(self.key_fd, GLib.PRIORITY_DEFAULT,
                                           GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_key)

    def _on_key(self, fd, cond):
        data = b""
        if cond & GLib.IO_IN:
            try:
                data = os.read(fd, gmode.EVENT.size * 64)
            except BlockingIOError:
                return True
            except OSError:
                data = b""
        if not data:  # the keyboard went away; _periodic opens it again
            os.close(fd)
            self.key_fd = None
            self.key_watch = 0
            return False
        if gmode.pressed(data):
            self.set_gmode(not self.engine.gmode)
        return True

    # ------------------------------------------------------------ media keys
    def open_media_keys(self):
        try:
            self.media_fd = os.open(mediakeys.KEYBOARD, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            if str(e) != self.media_error:
                self.media_error = str(e)
                log(f"media keys unavailable: {e}")
            return
        self.media_error = ""
        self.media_watch = GLib.io_add_watch(self.media_fd, GLib.PRIORITY_DEFAULT,
                                             GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_media_key)

    def _on_media_key(self, fd, cond):
        data = b""
        if cond & GLib.IO_IN:
            try:
                data = os.read(fd, mediakeys.EVENT.size * 64)
            except BlockingIOError:
                return True
            except OSError:
                data = b""
        if not data:  # the keyboard went away; _periodic opens it again
            os.close(fd)
            self.media_fd = None
            self.media_watch = 0
            return False
        scans = mediakeys.presses(data)
        if scans:
            prof, _active = self.current()
            for scan, _code in scans:
                action = mediakeys.action_for(prof, scan)
                if action:
                    try:
                        if not mediakeys.send(action, self.session):
                            log(f"{mediakeys.key_name(scan)}: no music player open")
                    except dbus.exceptions.DBusException as e:
                        log(f"{mediakeys.key_name(scan)}: {e.get_dbus_message()}")
        return True

    def setup(self):
        system = self.system = dbus.SystemBus()
        system.add_signal_receiver(self.on_prepare_for_sleep, signal_name="PrepareForSleep",
                                   dbus_interface="org.freedesktop.login1.Manager",
                                   bus_name="org.freedesktop.login1", path="/org/freedesktop/login1")
        system.add_signal_receiver(self.on_power_properties, signal_name="PropertiesChanged",
                                   dbus_interface="org.freedesktop.DBus.Properties",
                                   bus_name=gmode.PP_NAME, path=gmode.PP_PATH)
        self.on_power_profile(gmode.active_profile(system))
        self.open_gmode_key()
        self.session = dbus.SessionBus()
        self.open_media_keys()
        if GUdev is not None:
            self.udev = GUdev.Client.new(["hidraw"])
            self.udev.connect("uevent", self.on_uevent)
        for path, cb in ((paths.CONFIG_DIR, self.on_config_dir_changed),
                         (paths.PROFILES_DIR, self.on_profiles_changed)):
            mon = Gio.File.new_for_path(path).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            mon.connect("changed", cb)
            self.monitors.append(mon)
        GLib.timeout_add_seconds(20, self._periodic)
        self._publish_sensors()
        GLib.timeout_add_seconds(2, self._publish_sensors)
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, self.quit)
        GLib.idle_add(lambda: (self.apply(force=True, reason="start"), False)[1])

    def quit(self):
        log("shutting down")
        self.stop_sw()
        if self.key_fd is not None:
            GLib.source_remove(self.key_watch)
            os.close(self.key_fd)
        if self.media_fd is not None:
            GLib.source_remove(self.media_watch)
            os.close(self.media_fd)
        self.engine.close()
        self.loop.quit()
        return False

    # ------------------------------------------------------------ D-Bus
    @dbus.service.method(paths.DBUS_IFACE, in_signature="", out_signature="b")
    def Reload(self):
        self.cfg = profiles.load_config()
        self.override = None
        self.retry_n = 0
        return self.apply(force=True, reason="reload")

    @dbus.service.method(paths.DBUS_IFACE, in_signature="s", out_signature="b")
    def ApplyProfile(self, slug):
        self.cfg = profiles.load_config()
        slug = str(slug)
        if not slug or slug == profiles.active_slug():
            self.override = None
        else:
            self.override = {"kind": "profile", "slug": slug, "profile": profiles.load(slug)}
        return self.apply(force=True, reason="external request")

    @dbus.service.method(paths.DBUS_IFACE, in_signature="s", out_signature="b")
    def Preview(self, profile_json):
        prof = profiles.normalize(json.loads(str(profile_json)))
        self.override = {"kind": "preview", "slug": None, "profile": prof}
        return self.apply(force=False)

    @dbus.service.method(paths.DBUS_IFACE, in_signature="", out_signature="b")
    def EndPreview(self):
        if self.override is None:
            return True
        self.override = None
        return self.apply(force=False, reason="preview ended")

    @dbus.service.method(paths.DBUS_IFACE, in_signature="s", out_signature="b")
    def WritePower(self, slug):
        prof = profiles.load(str(slug)) if slug else profiles.load(profiles.active_slug())
        try:
            self.engine.write_power_now(prof, self.cfg["chassis_backend"])
        except hw.DeviceError as e:
            self.last_error = str(e)
            return False
        return True

    @dbus.service.method(paths.DBUS_IFACE, in_signature="b", out_signature="b")
    def SetGMode(self, on):
        return self.set_gmode(bool(on))

    @dbus.service.method(paths.DBUS_IFACE, in_signature="", out_signature="b")
    def ToggleGMode(self):
        return self.set_gmode(not self.engine.gmode)

    @dbus.service.method(paths.DBUS_IFACE, in_signature="", out_signature="s")
    def Status(self):
        prof, is_active = self.current()
        return json.dumps({
            "pid": os.getpid(),
            "active_profile": profiles.active_slug(),
            "applying": prof["name"] if prof else None,
            "override": self.override["kind"] if self.override else None,
            "software_effect": ", ".join(
                ([self.engine.sw.name] if self.engine.sw else []) + [a.name for a in self.engine.sw_zones.values()]
            ) or None,
            "fps": self.cfg["fps"],
            "gmode": self.engine.gmode,
            "power_profile": self.power_profile,
            "gmode_key": self.key_error or "ok",
            "media_keys": self.media_error or "ok",
            "keyboard": self.devs[0],
            "chassis": self.devs[1],
            "last_error": self.last_error,
            "last_ok": self.last_ok,
        }, ensure_ascii=False)


def main():
    for msg in profiles.ensure_initialized():
        log(msg)
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    session = dbus.SessionBus()
    try:
        name = dbus.service.BusName(paths.DBUS_NAME, session, do_not_queue=True)
    except dbus.exceptions.NameExistsException:
        log("an Alien Thunder daemon is already running")
        return 1
    d = Daemon(name, loop)
    d.bus_name_ref = name
    d.setup()
    log("alien-thunder daemon started")
    loop.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
