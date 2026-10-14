"""Profiles (JSON in ~/.config/alien-thunder/profiles) and the global settings."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import unicodedata

from . import effects, mediakeys, paths
from .i18n import gettext as _

DEFAULT_COLOR = "#ff2900"
VERSION = 3

DEFAULT_PROFILE = {
    "version": VERSION,
    "name": "New profile",
    "brightness": 100,
    "keyboard": {},
    "keyboard_effect": {"effect": "static", "speed": 1.0},
    "chassis": {
        "touchpad": {"effect": "static", "color": DEFAULT_COLOR, "speed": 1.0},
        "logo": {"effect": "static", "color": DEFAULT_COLOR, "speed": 1.0},
        "power": {"ac": DEFAULT_COLOR, "battery": DEFAULT_COLOR},
    },
    "keys": [],  # [{"scan": HID usage, "action": one of mediakeys.ACTIONS}]
}

DEFAULT_CONFIG = {
    "version": VERSION,
    "active_profile": None,
    "recent_colors": [],
    "groups": {},
    "fps": 15,
    "chassis_backend": "hidraw",  # hidraw | alienrgb (static colors only)
}

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")

# Version 1 files were written with Portuguese keys and effect names.
V1_KEYS = {
    "versao": "version", "nome": "name", "brilho": "brightness", "teclado": "keyboard",
    "efeito_teclado": "keyboard_effect", "modo": "mode", "efeito": "effect", "cor1": "color1",
    "cor2": "color2", "modo_cor": "color_mode", "velocidade": "speed", "chassi": "chassis",
    "cor": "color", "energia": "power", "bateria": "battery", "perfil_ativo": "active_profile",
    "cores_recentes": "recent_colors", "grupos": "groups", "chassi_backend": "chassis_backend",
}
V1_VALUES = {
    "estatico": "static", "respiracao": "breathing", "onda_lateral": "side_wave",
    "onda_dupla": "double_wave", "pulso": "pulse", "ricochete": "bounce", "arco_iris": "rainbow",
    "respiracao_sw": "breathing_sw", "onda_arco_iris": "rainbow_wave", "espectro_sw": "spectrum_sw",
    "onda_cor": "color_wave", "cintilar": "twinkle", "espectro": "spectrum", "apagado": "off",
}


# Version 2 effects could replace the chosen colors (rainbow, spectrum, hardware effects
# with their own colors). Version 3 effects only dim and brighten, so each old effect
# becomes the closest one that keeps the colors.
V2_KEYBOARD = {
    "breathing": "breathing", "breathing_sw": "breathing", "pulse": "pulse", "morph": "pulse",
    "side_wave": "wave", "double_wave": "wave", "color_wave": "wave", "rainbow_wave": "wave",
    "twinkle": "twinkle",
}
V2_ZONE = {"static": "static", "off": "off", "pulse": "pulse", "breathing": "breathing",
           "morph": "breathing", "spectrum": "breathing"}


class ProfileError(Exception):
    pass


def from_v2(p: dict) -> dict:
    e = p.get("keyboard_effect") or {}
    if "mode" in e:
        effect = "static" if e["mode"] == "static" else V2_KEYBOARD.get(e.get("effect"), "static")
        p["keyboard_effect"] = {"effect": effect, "speed": e.get("speed", 1.0)}
    for z in ("touchpad", "logo"):
        zone = (p.get("chassis") or {}).get(z)
        if isinstance(zone, dict) and ("tempo" in zone or "color2" in zone):
            p["chassis"][z] = {"effect": V2_ZONE.get(zone.get("effect"), "static"),
                               "color": zone.get("color", DEFAULT_COLOR), "speed": 1.0}
    return p


def from_v1(data: dict) -> dict:
    """Renames a version 1 profile or settings file. LED ids and group names are data, not keys."""
    def walk(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            key = V1_KEYS.get(k, k)
            if isinstance(v, dict) and key not in ("keyboard", "groups"):
                v = walk(v)
            elif key in ("mode", "effect") and isinstance(v, str):
                v = V1_VALUES.get(v, v)
            out[key] = v
        return out
    if "versao" not in data:
        return data
    out = walk(data)
    out["version"] = VERSION
    return out


# ------------------------------------------------------------------ helpers
def hex_to_rgb(h: str) -> tuple[int, int, int]:
    if not isinstance(h, str) or not HEX_RE.match(h):
        raise ProfileError(_("invalid color: %r") % h)
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(c) -> str:
    return "#%02x%02x%02x" % tuple(int(x) for x in c)


def norm_hex(h: str) -> str:
    return rgb_to_hex(hex_to_rgb(h))


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:48] or "profile"


def _atomic_write(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst[k] = v
    return dst


# ------------------------------------------------------------------ profile
def normalize(p: dict) -> dict:
    """Checks a profile and fills in the defaults."""
    if not isinstance(p, dict):
        raise ProfileError(_("a profile must be a JSON object"))
    p = from_v2(from_v1(p))
    out = _merge(copy.deepcopy(DEFAULT_PROFILE), {k: v for k, v in p.items() if k != "keyboard"})
    kb = {}
    for k, v in (p.get("keyboard") or {}).items():
        if isinstance(v, dict):  # the old alienfx-perfil format
            v = v.get("cor")
        led = int(k)
        if not 0 <= led < 255:
            raise ProfileError(_("invalid LED id: %s") % k)
        kb[str(led)] = norm_hex(v)
    out["keyboard"] = dict(sorted(kb.items(), key=lambda kv: int(kv[0])))
    out["brightness"] = max(0, min(100, int(out.get("brightness", 100))))
    e = out["keyboard_effect"]
    if e["effect"] not in effects.KEYBOARD_EFFECTS:
        e["effect"] = "static"
    e["speed"] = max(0.1, min(5.0, float(e["speed"])))
    for z in ("touchpad", "logo"):
        zz = out["chassis"][z]
        if zz["effect"] not in effects.ZONE_EFFECTS:
            zz["effect"] = "static"
        zz["color"] = norm_hex(zz["color"])
        zz["speed"] = max(0.1, min(5.0, float(zz["speed"])))
    pw = out["chassis"]["power"]
    pw["ac"], pw["battery"] = norm_hex(pw["ac"]), norm_hex(pw["battery"])
    keys, seen = [], set()
    for k in out["keys"] if isinstance(out["keys"], list) else []:
        try:
            scan = int(k["scan"], 16) if isinstance(k["scan"], str) else int(k["scan"])
        except (KeyError, TypeError, ValueError):
            raise ProfileError(_("invalid key: %r") % (k,)) from None
        if k.get("action") in mediakeys.ACTIONS and scan not in seen:
            seen.add(scan)
            keys.append({"scan": scan, "action": k["action"]})
    out["keys"] = keys
    out["name"] = str(out.get("name") or _("Untitled"))
    out["version"] = VERSION
    return out


def profile_path(slug: str) -> str:
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        raise ProfileError(_("invalid profile file name: %r") % slug)
    return os.path.join(paths.PROFILES_DIR, slug + ".json")


def list_profiles() -> list[tuple[str, str]]:
    """[(slug, name)] sorted by name."""
    out = []
    if os.path.isdir(paths.PROFILES_DIR):
        for fn in os.listdir(paths.PROFILES_DIR):
            if fn.endswith(".json") and not fn.startswith("."):
                slug = fn[:-5]
                try:
                    with open(os.path.join(paths.PROFILES_DIR, fn), encoding="utf-8") as f:
                        data = json.load(f)
                    name = data.get("name") or data.get("nome") or slug
                except (OSError, ValueError):
                    name = slug + " " + _("(unreadable)")
                out.append((slug, name))
    return sorted(out, key=lambda x: x[1].lower())


def load(slug: str) -> dict:
    try:
        with open(profile_path(slug), encoding="utf-8") as f:
            return normalize(json.load(f))
    except FileNotFoundError:
        raise ProfileError(_("profile not found: %s") % slug) from None
    except ValueError as e:
        raise ProfileError(_("profile %s is not valid: %s") % (slug, e)) from None


def save(slug: str, profile: dict) -> None:
    _atomic_write(profile_path(slug), normalize(profile))


def unique_slug(name: str) -> str:
    base = slugify(name)
    slug, n = base, 2
    while os.path.exists(profile_path(slug)):
        slug = f"{base}-{n}"
        n += 1
    return slug


def create(name: str, base: dict | None = None) -> str:
    p = normalize(copy.deepcopy(base) if base else DEFAULT_PROFILE)
    p["name"] = name
    slug = unique_slug(name)
    save(slug, p)
    return slug


def duplicate(slug: str, new_name: str | None = None) -> str:
    p = load(slug)
    return create(new_name or _("%s (copy)") % p["name"], p)


def rename(slug: str, new_name: str) -> str:
    p = load(slug)
    p["name"] = new_name
    new_slug = slugify(new_name)
    if new_slug != slug:
        new_slug = unique_slug(new_name)
        save(new_slug, p)
        cfg = load_config()
        if cfg.get("active_profile") == slug:
            cfg["active_profile"] = new_slug
            save_config(cfg)
        os.unlink(profile_path(slug))
        return new_slug
    save(slug, p)
    return slug


def delete(slug: str) -> None:
    cfg = load_config()
    if cfg.get("active_profile") == slug:
        raise ProfileError(_("the active profile can't be deleted; make another one active first"))
    os.unlink(profile_path(slug))


def find(name_or_slug: str) -> str:
    """Takes a slug or a name, ignoring case."""
    profs = list_profiles()
    for slug, name in profs:
        if name_or_slug == slug:
            return slug
    for slug, name in profs:
        if name_or_slug.lower() in (name.lower(), slugify(name)):
            return slug
    raise ProfileError(_("profile not found: %s") % name_or_slug)


# ------------------------------------------------------------------ settings
def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(paths.CONFIG_FILE, encoding="utf-8") as f:
            cfg.update(from_v1(json.load(f)))
    except (FileNotFoundError, ValueError):
        pass
    cfg["fps"] = max(1, min(20, int(cfg.get("fps", 15))))
    if cfg.get("chassis_backend") not in ("hidraw", "alienrgb"):
        cfg["chassis_backend"] = "hidraw"
    cfg["version"] = VERSION
    return cfg


def save_config(cfg: dict) -> None:
    _atomic_write(paths.CONFIG_FILE, cfg)


def active_slug() -> str | None:
    slug = load_config().get("active_profile")
    if slug and os.path.exists(profile_path(slug)):
        return slug
    return None


def set_active(slug: str) -> None:
    load(slug)  # validates
    cfg = load_config()
    cfg["active_profile"] = slug
    save_config(cfg)


# ------------------------------------------------------------------ migration
def from_legacy(data: dict) -> dict:
    """Converts ~/.config/alienrgb/perfil.json, written by the old alienfx-perfil script."""
    p = copy.deepcopy(DEFAULT_PROFILE)
    p["name"] = re.sub(r"\s*\(importado.*\)$", "", data.get("nome") or "Imported") or "Imported"
    p["keyboard"] = {str(int(k)): norm_hex(v["cor"] if isinstance(v, dict) else v)
                     for k, v in (data.get("teclado") or {}).items()}
    ch = data.get("chassi") or {}
    if "touchpad" in ch:
        p["chassis"]["touchpad"]["color"] = norm_hex(ch["touchpad"])
    if "back" in ch:
        p["chassis"]["logo"]["color"] = norm_hex(ch["back"])
    if "power" in ch:
        p["chassis"]["power"] = {"ac": norm_hex(ch["power"]), "battery": norm_hex(ch["power"])}
    return normalize(p)


def _upgrade_files() -> list[str]:
    """Rewrites older files in the current format once, so what's on disk matches what runs."""
    msgs = []
    try:
        with open(paths.CONFIG_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        if raw.get("version", 1) < VERSION:
            save_config(load_config())
            msgs.append(_("settings upgraded to format %d") % VERSION)
    except (OSError, ValueError):
        pass
    for slug, _name in list_profiles():
        try:
            with open(profile_path(slug), encoding="utf-8") as f:
                if json.load(f).get("version", 1) < VERSION:
                    save(slug, load(slug))
                    msgs.append(_("profile %s upgraded to format %d") % (slug, VERSION))
        except (OSError, ValueError, ProfileError):
            pass
    return msgs


def ensure_initialized() -> list[str]:
    """On the first run, moves the old AlienFX Studio files over and imports the legacy profile."""
    msgs = []
    for old, new in ((paths.OLD_CONFIG_DIR, paths.CONFIG_DIR), (paths.OLD_STATE_DIR, paths.STATE_DIR)):
        if os.path.isdir(old) and not os.path.exists(new):
            os.makedirs(os.path.dirname(new), exist_ok=True)
            os.rename(old, new)
            msgs.append(_("%s moved to %s") % (old, new))
    os.makedirs(paths.PROFILES_DIR, exist_ok=True)
    msgs += _upgrade_files()
    if os.path.exists(paths.CONFIG_FILE) and list_profiles():
        return msgs
    cfg = load_config()
    slug = None
    if os.path.exists(paths.LEGACY_PROFILE):
        try:
            with open(paths.LEGACY_PROFILE, encoding="utf-8") as f:
                legacy = from_legacy(json.load(f))
            slug = create(legacy["name"], legacy)
            msgs.append(_("profile imported from %s: %s (%s)") % (paths.LEGACY_PROFILE, legacy["name"], slug))
        except (OSError, ValueError, ProfileError) as e:
            msgs.append(_("couldn't import the legacy profile: %s") % e)
    if slug is None:
        existing = list_profiles()
        slug = existing[0][0] if existing else create(_("Default"))
    if not cfg.get("active_profile"):
        cfg["active_profile"] = slug
    save_config(cfg)
    return msgs
