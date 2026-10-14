"""Media keys: Fn+F3 to Fn+F6 drive the music player, as AWCC macros did on Windows.

On the m16 R2 those keys come from the USB keyboard (0d62:d2b1), all four as KEY_UNKNOWN
(240). Only the HID usage in the MSC_SCAN event right before tells them apart (0xc0052 to
0xc0055), so no Plasma shortcut can bind them. The service reads them from /dev/input (the
input group, like Fn+F1) and sends the profile's action to the player over MPRIS.
"""
from __future__ import annotations

import struct

from .i18n import N_

KEYBOARD = "/dev/input/by-id/usb-DELL_Technologies_Keyboard-event-kbd"
EVENT = struct.Struct("llHHi")  # struct input_event on 64-bit
EV_SYN, EV_KEY, EV_MSC = 0, 1, 4
MSC_SCAN = 4
KEY_UNKNOWN = 240

ACTIONS = {
    "previous": N_("Previous track"),
    "stop": N_("Stop"),
    "play_pause": N_("Play/pause"),
    "next": N_("Next track"),
}
MPRIS_METHOD = {"previous": "Previous", "stop": "Stop", "play_pause": "PlayPause", "next": "Next"}

KNOWN = {0xC0052: "Fn+F3", 0xC0053: "Fn+F4", 0xC0054: "Fn+F5", 0xC0055: "Fn+F6"}
EXAMPLE = [{"scan": 0xC0052, "action": "previous"}, {"scan": 0xC0053, "action": "stop"},
           {"scan": 0xC0054, "action": "play_pause"}, {"scan": 0xC0055, "action": "next"}]

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_PLAYER = "org.mpris.MediaPlayer2.Player"
PROPS = "org.freedesktop.DBus.Properties"
RESTART_AFTER_US = 3_000_000  # past this point "previous" goes back to the start, like any player


def presses(data: bytes) -> list[tuple[int, int]]:
    """(scan code, key code) of each key press in an evdev read (releases and repeats left out)."""
    out, scan = [], 0
    usable = len(data) - len(data) % EVENT.size
    for _s, _us, typ, code, value in EVENT.iter_unpack(data[:usable]):
        if typ == EV_MSC and code == MSC_SCAN:
            scan = value & 0xFFFFFFFF
        elif typ == EV_KEY:
            if value == 1 and scan:
                out.append((scan, code))
        elif typ == EV_SYN:
            scan = 0
    return out


def bindable(code: int) -> bool:
    """Only keys Linux ignores: the service can't stop a key from reaching the focused window,
    so binding one that already types or does something would do both."""
    return code == KEY_UNKNOWN


def key_name(scan: int) -> str:
    return KNOWN.get(scan, "0x%x" % scan)


def action_for(profile: dict | None, scan: int) -> str | None:
    for k in (profile or {}).get("keys", []):
        if k["scan"] == scan:
            return k["action"]
    return None


def player(bus) -> str | None:
    """The player to talk to: one that's playing, else one that's paused, else any."""
    names = [str(n) for n in bus.list_names() if str(n).startswith(MPRIS_PREFIX)]
    # Prefer the browser's native track controls on ties: KDE's integration may
    # expose the audio element without the site's next/previous callbacks.
    names.sort(key=lambda name: name == MPRIS_PREFIX + "plasma-browser-integration")
    rank = {"Playing": 0, "Paused": 1}
    best, best_rank = None, 3
    for name in names:
        try:
            status = str(_get(bus.get_object(name, MPRIS_PATH), "PlaybackStatus"))
        except Exception:  # noqa: BLE001  a player that went away or doesn't answer
            continue
        r = rank.get(status, 2)
        if r < best_rank:
            best, best_rank = name, r
    return best


def _get(obj, prop):
    return obj.Get(MPRIS_PLAYER, prop, dbus_interface=PROPS, timeout=0.5)


def _restarts(obj) -> bool:
    """True when "previous" should go back to the start of the track instead: the track has
    played past RESTART_AFTER_US. A second press right after lands under it and goes back a track."""
    try:
        return bool(_get(obj, "CanSeek")) and int(_get(obj, "Position")) > RESTART_AFTER_US
    except Exception:  # noqa: BLE001  a player without Position just goes back a track
        return False


def _seek_target(bus, name, obj):
    # Chromium/Brave can advertise CanSeek yet silently ignore Seek. KDE can seek
    # the audio element directly. Only use it when it belongs to this browser PID.
    _prefix, sep, pid = name.rpartition(".instance")
    if sep and pid.isdigit():
        try:
            integration = bus.get_object(MPRIS_PREFIX + "plasma-browser-integration", MPRIS_PATH)
            if (int(_get(integration, "Metadata").get("kde:pid", -1)) == int(pid)
                    and bool(_get(integration, "CanSeek"))):
                return integration
        except Exception:  # noqa: BLE001  integration absent or no longer serving this browser
            pass
    return obj


def send(action: str, bus) -> str | None:
    """Sends the action to the player; returns the player's bus name, or None if there's none."""
    name = player(bus)
    if name:
        obj = bus.get_object(name, MPRIS_PATH)
        seek_obj = _seek_target(bus, name, obj) if action == "previous" else obj
        if action == "previous" and _restarts(seek_obj):
            # relative, since browsers leave mpris:trackid empty and SetPosition needs it;
            # MPRIS clamps a seek before the start to 0
            seek_obj.get_dbus_method("Seek", MPRIS_PLAYER)(-int(_get(seek_obj, "Position")), timeout=0.5)
        else:
            obj.get_dbus_method(MPRIS_METHOD[action], MPRIS_PLAYER)(timeout=0.5)
    return name
