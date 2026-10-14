"""Opt-in desktop network widget; Plasma owns its lifetime and saved position."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

WIDGET = "alien-thunder-network"


def script(action: str, widget: str = WIDGET) -> str:
    if action not in ("on", "off", "status"):
        raise ValueError(action)
    if widget not in (WIDGET, "alien-thunder"):
        raise ValueError(widget)
    return """
const action = %s;
const type = %s;
let matches = [];
for (const d of desktops())
    for (const w of d.widgets())
        if (w.type === type) matches.push(w);
if (action === "off") {
    for (const w of matches) w.remove();
    matches = [];
}
if (action === "on" && matches.length === 0) {
    const desktop = desktopForScreen(0);
    if (!desktop) throw new Error("No desktop available");
    const widget = desktop.addWidget(type);
    widget.geometry = type === "alien-thunder"
        ? new QRectF(48, 96, 1200, 198) : new QRectF(48, 96, 460, 560);
    matches.push(widget);
}
print(JSON.stringify({enabled: matches.length > 0, count: matches.length}));
""" % (json.dumps(action), json.dumps(widget))


def command(argv: list[str], widget: str = WIDGET) -> int:
    action = argv[0] if argv else "status"
    if len(argv) > 1 or action not in ("on", "off", "status"):
        name = "network" if widget == WIDGET else "desktop"
        print(f"usage: alien-thunder {name} [on|off|status]", file=sys.stderr)
        return 2
    qdbus = shutil.which("qdbus6")
    if not qdbus:
        print("The desktop widget needs KDE Plasma 6 and qdbus6.", file=sys.stderr)
        return 1
    try:
        result = subprocess.run(
            [qdbus, "org.kde.plasmashell", "/PlasmaShell",
             "org.kde.PlasmaShell.evaluateScript", script(action, widget)],
            capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(str(e), file=sys.stderr)
        return 1
    if result.returncode:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        return 1
    try:
        state = json.loads(result.stdout)
        if not isinstance(state.get("enabled"), bool):
            raise ValueError("Invalid widget status")
    except (ValueError, AttributeError):
        print(result.stdout.strip() or "Plasma did not return the widget status.", file=sys.stderr)
        return 1
    print(json.dumps(state))
    return 0
