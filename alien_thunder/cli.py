"""Alien Thunder's command line."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import engine, gmode, hw, profiles
from .i18n import gettext as _


def usage() -> str:
    return _("""alien-thunder                    open the lighting editor
alien-thunder list               list the profiles (* = active)
alien-thunder set <profile>      make a profile the active one and apply it
alien-thunder apply [profile]    apply now (default: the active one) without changing it
alien-thunder status             service and device status
alien-thunder power [profile]    write the power button colors now
alien-thunder gmode [on|off|toggle]
                                 G-Mode, the same as Fn+F1; with no argument, show it
alien-thunder overlay [on|off|show ITEM|hide ITEM|status]
                                 the floating readout bar
alien-thunder network [on|off|status]
                                 the optional desktop network widget
alien-thunder desktop [on|off|status]
                                 sensor gauges on the desktop
alien-thunder import-windows [--list | --id N ...]
                                 import AWCC presets from /mnt/windows
alien-thunder setup              per-user setup after installing a package
alien-thunder daemon             the service (started by systemd --user)""")


def _apply_direct(slug: str, is_active: bool) -> int:
    prof = profiles.load(slug)
    cfg = profiles.load_config()
    eng = engine.Engine(log=lambda m: print(m))
    try:
        eng.apply(prof, power=is_active, force=True, backend=cfg["chassis_backend"])
    except hw.DeviceError as e:
        print(_("error: %s") % e, file=sys.stderr)
        return 1
    finally:
        eng.close()
    if prof["keyboard_effect"]["mode"] == "software":
        print(_("note: software effects need the service (systemctl --user start alien-thunder)"))
    return 0


def cmd_list(_a) -> int:
    act = profiles.active_slug()
    for slug, name in profiles.list_profiles():
        print(f"{'*' if slug == act else ' '} {slug:24s} {name}")
    return 0


def cmd_set(a) -> int:
    slug = profiles.find(a.profile)
    profiles.set_active(slug)
    print(_("active profile: %s") % slug)
    if engine.daemon_running():
        ok = engine.daemon_call("Reload")
        print(_("applied by the service") if ok else _("the service will try again (see 'status')"))
        return 0 if ok else 1
    return _apply_direct(slug, True)


def cmd_apply(a) -> int:
    act = profiles.active_slug()
    slug = profiles.find(a.profile) if a.profile else act
    if not slug:
        print(_("no active profile"), file=sys.stderr)
        return 1
    if engine.daemon_running():
        ok = engine.daemon_call("ApplyProfile", "" if slug == act else slug)
        print(_("applied: %s") % slug if ok else _("failed; the service will try again (see 'status')"))
        return 0 if ok else 1
    return _apply_direct(slug, slug == act)


def cmd_status(_a) -> int:
    info = engine.env_info()
    missing = _("not found")
    print(_("keyboard (0d62:d2b1): %s") % (info["keyboard"] or missing))
    print(_("chassis  (187c:0551): %s") % (info["chassis"] or missing))
    print(_("active profile: %s") % profiles.active_slug())
    if engine.daemon_running():
        st = json.loads(str(engine.daemon_call("Status")))
        print(_("service: running (pid %s)") % st["pid"])
        for k in ("applying", "override", "software_effect", "gmode", "gmode_key", "media_keys", "last_error"):
            print(f"  {k}: {st.get(k)}")
    else:
        print(_("service: stopped"))
    return 0


def cmd_power(a) -> int:
    slug = profiles.find(a.profile) if a.profile else profiles.active_slug()
    if engine.daemon_running():
        return 0 if engine.daemon_call("WritePower", slug) else 1
    eng = engine.Engine()
    try:
        eng.write_power_now(profiles.load(slug), profiles.load_config()["chassis_backend"])
    except hw.DeviceError as e:
        print(_("error: %s") % e, file=sys.stderr)
        return 1
    return 0


def cmd_gmode(a) -> int:
    if a.action:
        if engine.daemon_running():
            on = bool(engine.daemon_call("ToggleGMode") if a.action == "toggle"
                      else engine.daemon_call("SetGMode", a.action == "on"))
        else:  # without the service the switch still works, but F1 keeps its color
            on = a.action == "on" or (a.action == "toggle" and not gmode.is_on())
            gmode.set_profile(gmode.PERFORMANCE if on else "balanced")
    else:
        on = gmode.is_on()
    state = _("on") if on else _("off")
    print(_("G-Mode: %s (power profile: %s)") % (state, gmode.active_profile()))
    return 0


# Puts the widget on the panel that holds the system tray, right before the tray, once.
# addWidget appends at the end; the panel ignores a rewritten AppletOrder, but moving
# the widget by index sticks.
PANEL_SCRIPT = """
let placed = false;
for (const panel of panels())
  for (const w of panel.widgets())
    if (w.type == "alien-thunder") placed = true;
if (!placed)
  for (const panel of panels()) {
    const tray = panel.widgets().find(w => w.type == "org.kde.plasma.systemtray");
    if (!tray) continue;
    const w = panel.addWidget("alien-thunder");
    w.index = tray.index;
    print("added");
    break;
  }
"""


def cmd_setup(_a) -> int:
    """What a package can't do as root: the user's service, the panel, and a permissions check."""
    import grp
    import shutil
    import subprocess
    ok = True
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    if subprocess.run(["systemctl", "--user", "enable", "--now", "alien-thunder.service"]).returncode == 0:
        print(_("service: running, and it starts with every login"))
    else:
        ok = False
    qdbus = shutil.which("qdbus6")
    if qdbus:
        r = subprocess.run([qdbus, "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript",
                            PANEL_SCRIPT], capture_output=True, text=True)
        if r.returncode == 0:
            print(_("panel: the widget is next to the system tray") if "added" in r.stdout
                  else _("panel: the widget was already there"))
        else:
            print(_("panel: right-click the panel, Add Widgets, and pick Alien Thunder"))
    info = engine.env_info()
    for path in (info["keyboard"], info["chassis"]):
        if path and not os.access(path, os.R_OK | os.W_OK):
            ok = False
            print(_("lighting: no access to %s; log out and back in so the udev rule applies") % path)
    if not info["keyboard"] and not info["chassis"]:
        print(_("lighting: no Alienware keyboard or AW-ELC controller found on this computer"))
    if not os.access(gmode.KEYBOARD, os.R_OK):
        ok = False
        user = os.environ.get("USER", "")
        in_group = user in grp.getgrnam("input").gr_mem if "input" in {g.gr_name for g in grp.getgrall()} else False
        if in_group:
            print(_("G-Mode key: log out and back in so the input group applies"))
        else:
            print(_("G-Mode key: Fn+F1 needs your user in the input group:"))
            print("  sudo usermod -aG input " + user)
    return 0 if ok else 1


def cmd_import(a) -> int:
    from . import winimport
    items = winimport.list_presets()
    if a.list or not a.id:
        for it in items:
            print(f"{it['id']:14s} {it['name'][:34]:34s} {it['summary']}")
        return 0
    for it in items:
        if it["id"] in a.id:
            slug = profiles.create(it["name"] + " (Windows)", it["profile"])
            print(_("imported: %s") % slug)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("gui", "--gui"):
        from . import gui
        return gui.main()
    if argv[0] == "daemon":
        from . import daemon
        return daemon.main()
    if argv[0] == "overlay":
        from . import overlay
        return overlay.command(argv[1:])
    if argv[0] == "network":
        from . import network
        return network.command(argv[1:])
    if argv[0] == "desktop":
        from . import network
        return network.command(argv[1:], widget="alien-thunder")
    p = argparse.ArgumentParser(prog="alien-thunder", usage=usage())
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("set")
    s.add_argument("profile")
    s = sub.add_parser("apply")
    s.add_argument("profile", nargs="?")
    sub.add_parser("status")
    s = sub.add_parser("power")
    s.add_argument("profile", nargs="?")
    s = sub.add_parser("gmode")
    s.add_argument("action", nargs="?", choices=("on", "off", "toggle"))
    sub.add_parser("setup")
    s = sub.add_parser("import-windows")
    s.add_argument("--list", action="store_true")
    s.add_argument("--id", nargs="*", help=_("ids as shown by --list (user:number)"))
    a = p.parse_args(argv)
    for msg in profiles.ensure_initialized():
        print(msg)
    try:
        return {"list": cmd_list, "set": cmd_set, "apply": cmd_apply, "status": cmd_status,
                "power": cmd_power, "gmode": cmd_gmode, "setup": cmd_setup,
                "import-windows": cmd_import}[a.cmd](a)
    except profiles.ProfileError as e:
        print(_("error: %s") % e, file=sys.stderr)
        return 1
