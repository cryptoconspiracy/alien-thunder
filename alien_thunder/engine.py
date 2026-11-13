"""Sends profiles to the hardware; used by the daemon, the CLI, and the GUI when the daemon is off."""
from __future__ import annotations

import json
import os
import time

from . import effects, gmode, hw, paths, profiles, protocol
from .profiles import hex_to_rgb

ZONES = {"touchpad": protocol.ZONE_TOUCHPAD, "logo": protocol.ZONE_LOGO}
ALIENRGB_TARGET = {"touchpad": "touchpad", "logo": "back"}


def _scale(c, f):
    return tuple(max(0, min(255, int(round(x * f)))) for x in c)


def keyboard_colors(profile: dict) -> dict[int, tuple[int, int, int]]:
    f = profile["brightness"] / 100.0
    return {int(k): _scale(hex_to_rgb(v), f) for k, v in profile["keyboard"].items()}


def zone_colors(profile: dict) -> dict[int, tuple[int, int, int]]:
    """{zone id: color} for the touchpad and the logo, brightness applied; "off" is black."""
    f = profile["brightness"] / 100.0
    out = {}
    for name, zid in ZONES.items():
        z = profile["chassis"][name]
        out[zid] = (0, 0, 0) if z["effect"] == "off" else _scale(hex_to_rgb(z["color"]), f)
    return out


def keyboard_animation(profile: dict) -> effects.Animation | None:
    e = profile["keyboard_effect"]
    if e["effect"] == "static":
        return None
    return effects.Animation(e["effect"], keyboard_colors(profile), e["speed"])


def zone_animations(profile: dict) -> dict[int, effects.Animation]:
    colors = zone_colors(profile)
    out = {}
    for name, zid in ZONES.items():
        z = profile["chassis"][name]
        if z["effect"] not in ("static", "off"):
            out[zid] = effects.Animation(z["effect"], {zid: colors[zid]}, z["speed"],
                                         message=z.get("message", "SOS"), phase=0.5 if zid == protocol.ZONE_LOGO else 0.0)
    return out


class State:
    """The little that has to survive a restart (~/.local/state/alien-thunder/state.json)."""

    def __init__(self):
        self.data = {"power_written": None, "keyboard_hw_effect": False}
        try:
            with open(paths.STATE_FILE, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            self._from_v1()

    def _from_v1(self):
        # Carrying the power colors over matters: without them the next start would
        # write the power button again, and that one goes to the controller's flash.
        try:
            with open(paths.OLD_STATE_FILE, encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, ValueError):
            return
        pw = old.get("energia_gravada")
        self.data["power_written"] = {"ac": pw["ac"], "battery": pw["bateria"]} if pw else None
        self.data["keyboard_hw_effect"] = bool(old.get("teclado_efeito_hw"))
        self.save()
        os.unlink(paths.OLD_STATE_FILE)

    def save(self):
        profiles._atomic_write(paths.STATE_FILE, self.data)


class Engine:
    def __init__(self, log=print):
        self.log = log
        self.kb = hw.KeyboardV5()
        self.ch = hw.ChassisV4()
        self.alienrgb = hw.AlienrgbChassis()
        self.state = State()
        self.last_kb = None
        self.last_ch = None
        self.sw: effects.Animation | None = None
        self.sw_zones: dict[int, effects.Animation] = {}
        self.fan_zones: set[int] = set()
        self.audio_zones: set[int] = set()
        self.fan_rpm: int | None = None
        self.zone_base: dict[int, tuple[int, int, int]] = {}
        self.last_zone_frame = None
        self.sw_t0 = time.monotonic()
        self.gmode = False
        self.f1: tuple[int, int, int] | None = None

    def _overlay(self, colors: dict) -> dict:
        if self.f1 is None:
            return colors
        return {**colors, gmode.F1_LED: self.f1}

    @property
    def animating(self) -> bool:
        return self.sw is not None or bool(self.sw_zones)

    # ------------------------------------------------------------ parts
    def invalidate(self):
        self.last_kb = self.last_ch = self.last_zone_frame = None
        self.kb.close()
        self.ch.close()

    def _apply_keyboard(self, profile: dict):
        with hw.hw_lock():
            # Earlier versions could leave a hardware effect running on the keyboard's
            # controller, and it would paint over the per-key colors until switched off.
            if self.state.data["keyboard_hw_effect"]:
                self.kb.effect_off()
                self.state.data["keyboard_hw_effect"] = False
                self.state.save()
                self.log("keyboard: hardware effect off")
            self.sw = keyboard_animation(profile)
            if self.sw is not None:
                self.kb.static(self._overlay(self.sw.frame(time.monotonic() - self.sw_t0)))
                self.log(f"keyboard: effect '{self.sw.name}'")
            else:
                colors = self._overlay(keyboard_colors(profile))
                self.kb.static(colors)
                self.log(f"keyboard: {len(colors)} LEDs set")

    def _apply_chassis(self, profile: dict, backend: str):
        colors = zone_colors(profile)
        if backend == "alienrgb":
            self.sw_zones = {}
            self.fan_zones = set()
            self.audio_zones = set()
            for name, zid in ZONES.items():
                if profile["chassis"][name]["effect"] not in ("static", "off"):
                    self.log(f"{name}: effects need the hidraw backend; using a fixed color")
                self.alienrgb.set_zone(ALIENRGB_TARGET[name], profiles.rgb_to_hex(colors[zid]))
            self.log("chassis: set through alienrgb")
            return
        # The controller's own chassis effects never worked here, so animated zones are
        # redrawn frame by frame with the same static-color packets that do.
        self.zone_base = colors
        self.sw_zones = zone_animations(profile)
        self.fan_zones = {zid for name, zid in ZONES.items()
                          if profile["chassis"][name].get("fan_reactive")
                          and profile["chassis"][name]["effect"] == "breathing"}
        self.audio_zones = {zid for name, zid in ZONES.items()
                            if profile["chassis"][name]["effect"] == "audio"}
        t = time.monotonic() - self.sw_t0
        self._apply_fan_speed(t)
        self._send_zones(self._zone_frame(t))
        self.log("chassis: touchpad and logo set"
                 + (f" (effects: {', '.join(a.name for a in self.sw_zones.values())})" if self.sw_zones else ""))

    def _zone_frame(self, t: float) -> dict[int, tuple[int, int, int]]:
        frame = dict(self.zone_base)
        for zid, anim in self.sw_zones.items():
            if zid in self.fan_zones and self.fan_rpm is not None and self.fan_rpm <= 0:
                frame[zid] = (0, 0, 0)
                continue
            frame.update(anim.frame(t))
        return frame

    def _apply_fan_speed(self, t: float):
        if self.fan_rpm is None:
            return
        speed = effects.fan_breath_speed(self.fan_rpm)
        if speed is not None:
            for zid in self.fan_zones:
                anim = self.sw_zones.get(zid)
                if anim is not None:
                    anim.set_speed(t, speed)

    def set_fan_rpm(self, cpu_rpm: int | None, gpu_rpm: int | None):
        """Uses the faster fan so either CPU or GPU load is visible on the chassis."""
        readings = [rpm for rpm in (cpu_rpm, gpu_rpm) if rpm is not None]
        rpm = max(readings) if readings else None
        if rpm == self.fan_rpm:
            return
        self.fan_rpm = rpm
        self._apply_fan_speed(time.monotonic() - self.sw_t0)
        self.last_zone_frame = None

    def set_audio_level(self, level: float):
        for zid in self.audio_zones:
            anim = self.sw_zones.get(zid)
            if anim is not None:
                anim.set_level(level)

    def _send_zones(self, frame: dict[int, tuple[int, int, int]], lock_timeout: float = 10.0):
        if frame == self.last_zone_frame:
            return
        with hw.hw_lock(timeout=lock_timeout):
            self.ch.send(protocol.elc_zone_packets({z: {"effect": "static", "color": c} for z, c in frame.items()}))
            self.ch.wait_ready()
        self.last_zone_frame = frame

    def _apply_power(self, profile: dict, backend: str, force: bool):
        pw = profile["chassis"]["power"]
        want = {"ac": pw["ac"], "battery": pw["battery"]}
        if not force and self.state.data.get("power_written") == want:
            return
        if backend == "alienrgb" and pw["ac"] == pw["battery"]:
            self.alienrgb.power(pw["ac"])
        else:
            with hw.hw_lock():
                self.ch.send(protocol.elc_power_packets(hex_to_rgb(pw["ac"]), hex_to_rgb(pw["battery"])))
                self.ch.wait_ready()
        self.state.data["power_written"] = want
        self.state.save()
        self.log(f"power button written: AC {pw['ac']} / battery {pw['battery']}")

    # ------------------------------------------------------------ publico
    def apply(self, profile: dict, *, power: bool = False, force: bool = False,
              backend: str = "hidraw") -> None:
        """Sends keyboard and chassis, skipping parts that match the last send unless force.

        power=True only for the ACTIVE profile: writes the power button when its colors
        changed since the last write. A failure in one part doesn't stop the others; at
        the end a DeviceError sums them up, and the daemon tries again.
        """
        profile = profiles.normalize(profile)
        errors = []
        # G-Mode paints F1 white over the profile, effects included.
        self.f1 = _scale(gmode.WHITE, profile["brightness"] / 100.0) if self.gmode else None
        kb_key = json.dumps([profile["keyboard"], profile["keyboard_effect"], profile["brightness"], self.gmode],
                            sort_keys=True)
        if force or kb_key != self.last_kb:
            try:
                self.last_kb = None
                self._apply_keyboard(profile)
                self.last_kb = kb_key
            except hw.DeviceError as e:
                errors.append(str(e))
        ch_key = json.dumps([profile["chassis"]["touchpad"], profile["chassis"]["logo"],
                             profile["brightness"], backend], sort_keys=True)
        if force or ch_key != self.last_ch:
            try:
                self.last_ch = None
                self.last_zone_frame = None
                self._apply_chassis(profile, backend)
                self.last_ch = ch_key
            except hw.DeviceError as e:
                errors.append(str(e))
        if power:
            try:
                self._apply_power(profile, backend, force=False)
            except hw.DeviceError as e:
                errors.append(str(e))
        if errors:
            raise hw.DeviceError("; ".join(errors))

    def write_power_now(self, profile: dict, backend: str = "hidraw"):
        self._apply_power(profiles.normalize(profile), backend, force=True)

    def sw_tick(self):
        """Sends one frame of whatever is animated; the daemon's timer calls this."""
        t = time.monotonic() - self.sw_t0
        if self.sw is not None:
            frame = self._overlay(self.sw.frame(t))
            with hw.hw_lock(timeout=0.5):
                self.kb.static(frame, retries=2)
        if self.sw_zones:
            self._send_zones(self._zone_frame(t), lock_timeout=0.5)

    def close(self):
        self.kb.close()
        self.ch.close()


def daemon_running() -> bool:
    if hw.DRYRUN:
        return False
    try:
        import dbus
        return dbus.SessionBus().name_has_owner(paths.DBUS_NAME)
    except Exception:
        return False


def daemon_call(method: str, *args, timeout: float = 20.0):
    import dbus
    obj = dbus.SessionBus().get_object(paths.DBUS_NAME, paths.DBUS_PATH)
    return getattr(obj, method)(*args, dbus_interface=paths.DBUS_IFACE, timeout=timeout)


def env_info() -> dict:
    return {"keyboard": hw.find_keyboard(), "chassis": hw.find_chassis(),
            "alienrgb": os.access(paths.ALIENRGB_BIN, os.X_OK)}
