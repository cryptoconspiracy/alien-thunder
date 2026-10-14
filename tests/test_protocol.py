"""Checks the encoders against packets known to work (from alienfx-perfil and alienrgb).

Run with:  python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

# paths.py reads these at import time; the tests must never touch the real profiles or state.
_SANDBOX = tempfile.mkdtemp(prefix="alien-thunder-tests-")
for _var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR"):
    os.environ[_var] = os.path.join(_SANDBOX, _var.lower())

from alien_thunder import effects, engine, gmode, layout, mediakeys, profiles, protocol, sensors  # noqa: E402
from alien_thunder.profiles import hex_to_rgb  # noqa: E402


def golden(name):
    with open(os.path.join(HERE, "golden", name), encoding="utf-8") as f:
        return json.load(f)


def plan_hex(g, length):
    """Pulls the payloads out of an alienrgb --dry-run --json plan."""
    out = []
    for s in g["plan"]["steps"]:
        if s.get("payload_hex") and s["transfer"] != "hid_feature_read_intent":
            h = s["payload_hex"].replace(" ", "")
            assert len(h) == 2 * length, (s["name"], len(h))
            out.append((s["name"], h))
    return out


class KeyboardV5(unittest.TestCase):
    def test_devops_matches_alienfx_perfil(self):
        g = golden("devops_legacy_profile.json")
        prof = profiles.from_legacy(g["profile"])
        colors = {int(k): hex_to_rgb(v) for k, v in prof["keyboard"].items()}
        mine = [protocol.KB_RESET.hex(), protocol.KB_STATUS.hex()]
        mine += [p.hex() for p in protocol.kb_static_packets(colors)]
        self.assertEqual(mine, g["packets"])

    def test_all_keys_match_alienrgb(self):
        g = golden("kb_all.json")
        steps = plan_hex(g, 64)
        colors = {a["logical_id"]: (a["color"]["r"], a["color"]["g"], a["color"]["b"])
                  for a in g["plan"]["assignments"]}
        mine = [protocol.KB_RESET, protocol.KB_STATUS] + protocol.kb_static_packets(colors)
        self.assertEqual([p.hex() for p in mine], [h for _, h in steps])

    def test_global_effect(self):
        p = protocol.kb_effect_packet("breathing", 5, 2, (1, 2, 3), (4, 5, 6))
        self.assertEqual(p[:16].hex(), "cc80020500000101010101020304050" "6")
        self.assertEqual(p[16:], bytes(48))
        self.assertEqual(protocol.KB_EFFECT_OFF[:9].hex(), "cc8001fe0000010101")
        for name in protocol.KB_HW_EFFECTS:
            protocol.assert_safe_kb(protocol.kb_effect_packet(name, 5, 1, (0, 0, 0), (0, 0, 0)))


class ChassisV4(unittest.TestCase):
    def test_static_touchpad(self):
        steps = plan_hex(golden("touchpad_ff2900.json"), 33)
        mine = protocol.elc_zone_packets({0: {"effect": "static", "color": (0xff, 0x29, 0)}})
        self.assertEqual([p.hex() for p in mine], [h for _, h in steps])

    def test_touchpad_and_logo_same_color(self):
        steps = plan_hex(golden("tp_back.json"), 33)
        c = (0x0a, 0x0b, 0x0c)
        mine = protocol.elc_zone_packets({0: {"effect": "static", "color": c},
                                          2: {"effect": "static", "color": c}})
        self.assertEqual([p.hex() for p in mine], [h for _, h in steps])

    def test_power_matches_alienrgb(self):
        for fn, c in (("power_ff2900.json", (0xff, 0x29, 0)), ("power_12ab34.json", (0x12, 0xab, 0x34))):
            steps = plan_hex(golden(fn), 33)
            mine = protocol.elc_power_packets(c, c)
            self.assertEqual(len(mine), 34)
            self.assertEqual([p.hex() for p in mine], [h for _, h in steps], fn)

    def test_power_ac_and_battery_apart(self):
        ac, bat = (1, 2, 3), (9, 8, 7)
        pk = protocol.elc_power_packets(ac, bat)
        self.assertEqual(len(pk), 34)
        # state 0x5c (AC on): first record is the AC color, type "color"
        i = [n for n, p in enumerate(pk) if p[:6].hex() == "032200010" "05c"][0]
        rec = pk[i + 2]
        self.assertEqual(rec[2:10].hex(), "0003d000fa010203")
        # state 0x5f (battery on): the last records carry the battery color
        i = [n for n, p in enumerate(pk) if p[:6].hex() == "032200010" "05f"][0]
        self.assertEqual(pk[i + 2][10:18].hex(), "0203e80064090807")

    def test_chassis_effects(self):
        z = {0: {"effect": "pulse", "color": (1, 2, 3), "tempo": 100},
             2: {"effect": "spectrum", "color": (0, 0, 0), "tempo": 50}}
        pk = protocol.elc_zone_packets(z)
        self.assertEqual(pk[0], protocol.ELC_REMOVE)
        self.assertEqual(pk[1], protocol.ELC_START)
        self.assertEqual(pk[2][:6].hex(), "032301000100")
        self.assertEqual(pk[3][:10].hex(), "03240107dc0064010203")
        self.assertEqual(pk[4][:6].hex(), "032301000102")
        self.assertEqual(len(pk), 2 + 2 + 3 + 1)  # spectrum: 6 records = 2 packets
        self.assertEqual(pk[-1], protocol.ELC_FINISH_PLAY)

    def test_safety(self):
        all_pk = protocol.elc_power_packets((1, 1, 1), (2, 2, 2))
        for eff in protocol.CHASSIS_EFFECTS:
            all_pk += protocol.elc_zone_packets({0: {"effect": eff, "color": (1, 2, 3), "color2": (4, 5, 6), "tempo": 9}})
        for p in all_pk:
            protocol.assert_safe_elc(p)
            self.assertNotEqual(p[1], 0xFF)
            if p[1] == 0x21:  # general control: never save/default/startup
                self.assertIn(p[3], (1, 3, 4, 5))
        for bad in ([0x03, 0xFF], [0x03, 0x21, 0x00, 0x02, 0xFF, 0xFF], [0x03, 0x21, 0x00, 0x06],
                    [0x03, 0x21, 0x00, 0x07]):
            with self.assertRaises(ValueError):
                protocol.assert_safe_elc(protocol._elc(bad))
        with self.assertRaises(ValueError):
            protocol.assert_safe_kb(protocol._kb([0xCC, 0x95]))


class Layout(unittest.TestCase):
    AWCC = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 24, 25, 26, 27, 28,
            29, 30, 31, 32, 33, 35, 19, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 16,
            59, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 18, 81, 82, 83, 84, 85, 86, 87,
            88, 89, 90, 91, 92, 94, 114, 17, 100, 101, 103, 104, 105, 110, 107, 111, 112, 109, 133,
            134, 135}

    def test_92_awcc_ids(self):
        self.assertEqual(set(layout.AWCC_IDS), self.AWCC)
        self.assertEqual(len([k for k in layout.KEYS if not k.extra]), 86)
        self.assertIn(106, layout.KEY_BY_ID[107].leds)

    def test_groups_are_valid(self):
        for name, ids in layout.GROUPS.items():
            for i in ids:
                self.assertIn(i, layout.KEY_BY_ID, name)


class Profiles(unittest.TestCase):
    def test_legacy_import(self):
        g = golden("devops_legacy_profile.json")
        p = profiles.from_legacy(g["profile"])
        self.assertEqual(p["name"], "Devops")
        self.assertEqual(len(p["keyboard"]), 92)
        self.assertEqual(p["chassis"]["touchpad"]["color"], "#ff2900")
        self.assertEqual(p["chassis"]["power"], {"ac": "#ff2900", "battery": "#ff2900"})
        self.assertEqual(profiles.normalize(p), p)

    def test_version_1_file(self):
        v1 = {"versao": 1, "nome": "Devops", "brilho": 80, "teclado": {"1": "#9900ba", "107": "#fa2800"},
              "efeito_teclado": {"modo": "software", "efeito": "onda_cor", "cor1": "#ff0000", "cor2": "#0000ff",
                                 "modo_cor": 2, "tempo": 5, "velocidade": 1.5},
              "chassi": {"touchpad": {"efeito": "pulso", "cor": "#ff2900", "cor2": "#000000", "tempo": 100},
                         "logo": {"efeito": "apagado", "cor": "#ff2900", "cor2": "#000000", "tempo": 100},
                         "energia": {"ac": "#ff2900", "bateria": "#00ff00"}}}
        p = profiles.normalize(v1)
        self.assertEqual(p["version"], profiles.VERSION)
        self.assertEqual(p["name"], "Devops")
        self.assertEqual(p["brightness"], 80)
        self.assertEqual(p["keyboard"], {"1": "#9900ba", "107": "#fa2800"})
        self.assertEqual(p["keyboard_effect"], {"effect": "wave", "speed": 1.5})
        self.assertEqual(p["chassis"]["touchpad"]["effect"], "pulse")
        self.assertEqual(p["chassis"]["logo"]["effect"], "off")
        self.assertEqual(p["chassis"]["power"], {"ac": "#ff2900", "battery": "#00ff00"})
        self.assertNotIn("nome", p)
        cfg = profiles.from_v1({"versao": 1, "perfil_ativo": "devops", "grupos": {"Minhas": [1, 2]},
                                "chassi_backend": "hidraw"})
        self.assertEqual(cfg["active_profile"], "devops")
        self.assertEqual(cfg["groups"], {"Minhas": [1, 2]})
        self.assertEqual(cfg["chassis_backend"], "hidraw")

    def test_version_2_file(self):
        v2 = {"version": 2, "name": "Old", "keyboard": {"1": "#9900ba"},
              "keyboard_effect": {"mode": "hardware", "effect": "rainbow", "color1": "#ff0000",
                                  "color2": "#0000ff", "color_mode": 3, "tempo": 5, "speed": 2.0},
              "chassis": {"touchpad": {"effect": "morph", "color": "#112233", "color2": "#000000", "tempo": 9},
                          "logo": {"effect": "pulse", "color": "#445566", "color2": "#000000", "tempo": 9}}}
        p = profiles.normalize(v2)
        # rainbow painted over the chosen colors; nothing in version 3 does
        self.assertEqual(p["keyboard_effect"], {"effect": "static", "speed": 2.0})
        self.assertEqual(p["chassis"]["touchpad"], {"effect": "breathing", "color": "#112233", "speed": 1.0})
        self.assertEqual(p["chassis"]["logo"], {"effect": "pulse", "color": "#445566", "speed": 1.0})
        self.assertEqual(p["keyboard"], {"1": "#9900ba"})

    def test_effects_keep_the_colors(self):
        base = {0: (255, 0, 0), 1: (153, 0, 186), 107: (250, 40, 0), 5: (0, 0, 0)}
        for name in effects.KEYBOARD_EFFECTS:
            if name == "static":
                continue
            fx = effects.Animation(name, base, 1.0)
            for t in (0.0, 0.3, 1.7, 2.9, 10.0):
                fr = fx.frame(t)
                self.assertEqual(set(fr), set(base), name)
                for led, c in fr.items():
                    b = base[led]
                    if not any(b):
                        self.assertEqual(c, (0, 0, 0), name)  # an unlit key stays off
                        continue
                    f = max(c) / max(b)
                    for got, want in zip(c, b):  # same hue: every channel scaled by one factor
                        self.assertLessEqual(abs(got - want * f), 1, (name, t, led, c, b))
                protocol.kb_static_packets(fr)


class _Fake:
    """A stand-in device that records the calls instead of talking to hidraw."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a, **k: self.calls.append((name, a))


class GMode(unittest.TestCase):
    def ev(self, typ, code, value):
        return gmode.EVENT.pack(0, 0, typ, code, value)

    def test_key(self):
        syn = self.ev(0, 0, 0)
        scan = self.ev(4, 4, 0x68)
        self.assertTrue(gmode.pressed(scan + self.ev(1, gmode.KEY_PERFORMANCE, 1) + syn))
        self.assertFalse(gmode.pressed(scan + self.ev(1, gmode.KEY_PERFORMANCE, 0) + syn))  # release
        self.assertFalse(gmode.pressed(self.ev(1, gmode.KEY_PERFORMANCE, 2)))  # repeat
        self.assertFalse(gmode.pressed(self.ev(1, 59, 1)))  # F1 without Fn
        self.assertTrue(gmode.pressed(self.ev(1, gmode.KEY_PERFORMANCE, 1) + b"\x00" * 5))

    def apply(self, eng, prof):
        eng.kb, eng.ch = _Fake(), _Fake()
        eng.state.data["keyboard_hw_effect"] = False
        eng.apply(prof)
        return [a[0] for n, a in eng.kb.calls if n == "static"]

    def test_touchpad_effect_uses_static_packets(self):
        prof = profiles.normalize({"chassis": {"touchpad": {"effect": "breathing", "color": "#ff2900"},
                                               "logo": {"effect": "static", "color": "#0000ff"}}})
        eng = engine.Engine(log=lambda m: None)
        eng.kb, eng.ch = _Fake(), _Fake()
        eng.state.data["keyboard_hw_effect"] = False
        eng.apply(prof)
        self.assertTrue(eng.animating)
        eng.sw_t0 -= 2.0  # half a breath later
        eng.sw_tick()
        sent = [pk for name, a in eng.ch.calls if name == "send" for pk in a[0]]
        self.assertGreater(len(sent), 8)
        for pk in sent:
            protocol.assert_safe_elc(pk)
            self.assertNotIn(pk[1], (0x23, 0x24))  # never the controller's own effect actions
        logo = [pk for pk in sent if pk[1] == 0x27 and 2 in pk[7:7 + pk[6]]]
        self.assertTrue(all(pk[2:5] == bytes((0, 0, 255)) for pk in logo))  # the static logo never dims

    def test_f1_white_only_in_gmode(self):
        prof = profiles.normalize(profiles.from_legacy(golden("devops_legacy_profile.json")["profile"]))
        prof["brightness"] = 50
        eng = engine.Engine(log=lambda m: None)
        (off,) = self.apply(eng, prof)
        eng.gmode = True
        (on,) = self.apply(eng, prof)
        self.assertEqual(on[gmode.F1_LED], (128, 128, 128))
        self.assertNotEqual(off[gmode.F1_LED], on[gmode.F1_LED])
        self.assertEqual({k: v for k, v in on.items() if k != gmode.F1_LED},
                         {k: v for k, v in off.items() if k != gmode.F1_LED})
        eng.gmode = False
        (back,) = self.apply(eng, prof)
        self.assertEqual(back, off)


class MediaKeys(unittest.TestCase):
    def ev(self, typ, code, value):
        return mediakeys.EVENT.pack(0, 0, typ, code, value)

    def press(self, scan, code=mediakeys.KEY_UNKNOWN, value=1):
        return self.ev(4, 4, scan) + self.ev(1, code, value) + self.ev(0, 0, 0)

    def test_presses(self):
        # what the m16 R2's USB keyboard sends for Fn+F3: the HID usage, then KEY_UNKNOWN
        self.assertEqual(mediakeys.presses(self.press(0xC0052)), [(0xC0052, 240)])
        self.assertEqual(mediakeys.presses(self.press(0xC0052, value=0)), [])  # release
        self.assertEqual(mediakeys.presses(self.press(0xC0052, value=2)), [])  # repeat
        self.assertEqual(mediakeys.presses(self.press(0xC0053) + self.press(0xC0055)),
                         [(0xC0053, 240), (0xC0055, 240)])
        # a scan from an earlier report never sticks to a key without one
        self.assertEqual(mediakeys.presses(self.press(0xC0054) + self.ev(1, 240, 1)), [(0xC0054, 240)])
        self.assertTrue(mediakeys.bindable(240))
        self.assertFalse(mediakeys.bindable(61))  # plain F3 already does something

    def test_profile_keys(self):
        self.assertEqual(profiles.normalize({})["keys"], [])
        p = profiles.normalize({"keys": [{"scan": "0xc0052", "action": "previous"},
                                         {"scan": 0xC0052, "action": "next"},  # same key twice
                                         {"scan": 0xC0053, "action": "launch_rockets"},
                                         {"scan": 0xC0055, "action": "next"}]})
        self.assertEqual(p["keys"], [{"scan": 0xC0052, "action": "previous"}, {"scan": 0xC0055, "action": "next"}])
        self.assertEqual(profiles.normalize(p), p)
        self.assertEqual(profiles.normalize({"keys": mediakeys.EXAMPLE})["keys"], mediakeys.EXAMPLE)
        self.assertEqual(mediakeys.action_for(p, 0xC0055), "next")
        self.assertIsNone(mediakeys.action_for(p, 0xC0054))
        with self.assertRaises(profiles.ProfileError):
            profiles.normalize({"keys": [{"action": "next"}]})

    def test_player_choice(self):
        calls, position = [], [0]

        class Obj:
            def __init__(self, name, status):
                self.name, self.status = name, status

            def Get(self, _iface, prop, **_k):
                if self.status is None:
                    raise RuntimeError("gone")
                return {"PlaybackStatus": self.status, "CanSeek": True, "Position": position[0]}[prop]

            def get_dbus_method(self, method, _iface):
                return lambda *a, **_k: calls.append((self.name, method) + a)

        class Bus:
            players = {"org.mpris.MediaPlayer2.vlc": "Paused", "org.mpris.MediaPlayer2.brave": "Playing",
                       "org.mpris.MediaPlayer2.dead": None, "org.kde.other": "Playing"}

            def list_names(self):
                return list(self.players)

            def get_object(self, name, _path):
                return Obj(name, self.players[name])

        bus = Bus()
        self.assertEqual(mediakeys.send("play_pause", bus), "org.mpris.MediaPlayer2.brave")
        self.assertEqual(calls, [("org.mpris.MediaPlayer2.brave", "PlayPause")])
        # previous: back to the start first, and a second press right after goes back a track
        position[0] = 42_000_000
        mediakeys.send("previous", bus)
        self.assertEqual(calls[-1], ("org.mpris.MediaPlayer2.brave", "Seek", -42_000_000))
        position[0] = 400_000
        mediakeys.send("previous", bus)
        self.assertEqual(calls[-1], ("org.mpris.MediaPlayer2.brave", "Previous"))
        bus.players["org.mpris.MediaPlayer2.brave"] = "Stopped"
        self.assertEqual(mediakeys.player(bus), "org.mpris.MediaPlayer2.vlc")
        bus.players = {}
        self.assertIsNone(mediakeys.send("next", bus))

    def test_native_browser_preferred_when_both_playing(self):
        class Obj:
            def __init__(self, status):
                self.status = status

            def Get(self, _iface, _prop, **_kwargs):
                return self.status

        class Bus:
            players = {"org.mpris.MediaPlayer2.brave.instance123": "Playing",
                       "org.mpris.MediaPlayer2.plasma-browser-integration": "Playing"}

            def list_names(self):
                return list(self.players)

            def get_object(self, name, _path):
                return Obj(self.players[name])

        bus = Bus()
        browser = "org.mpris.MediaPlayer2.brave.instance123"
        integration = "org.mpris.MediaPlayer2.plasma-browser-integration"
        self.assertEqual(mediakeys.player(bus), browser)
        bus.players = dict(reversed(list(bus.players.items())))
        self.assertEqual(mediakeys.player(bus), browser)
        bus.players[browser] = "Paused"
        self.assertEqual(mediakeys.player(bus), integration)
        bus.players[browser] = "Playing"
        bus.players[integration] = "Paused"
        self.assertEqual(mediakeys.player(bus), browser)
        del bus.players[integration]
        self.assertEqual(mediakeys.player(bus), browser)

    def test_browser_seek_uses_matching_integration_only(self):
        calls = []
        browser = "org.mpris.MediaPlayer2.brave.instance123"
        integration = "org.mpris.MediaPlayer2.plasma-browser-integration"

        class Obj:
            def __init__(self, name):
                self.name = name
                self.position = 42_000_000
                self.pid = 123

            def Get(self, _iface, prop, **_kwargs):
                return {"PlaybackStatus": "Playing", "CanSeek": True,
                        "Position": self.position, "Metadata": {"kde:pid": self.pid}}[prop]

            def get_dbus_method(self, method, _iface):
                return lambda *a, **_kwargs: calls.append((self.name, method) + a)

        class Bus:
            def __init__(self):
                self.players = {integration: Obj(integration), browser: Obj(browser)}

            def list_names(self):
                return list(self.players)

            def get_object(self, name, _path):
                return self.players[name]

        bus = Bus()
        mediakeys.send("previous", bus)
        self.assertEqual(calls[-1], (integration, "Seek", -42_000_000))
        # Native position can be stale after KDE seeks; read KDE's position again.
        bus.players[integration].position = 400_000
        mediakeys.send("previous", bus)
        self.assertEqual(calls[-1], (browser, "Previous"))
        for action, method in (("next", "Next"), ("play_pause", "PlayPause"), ("stop", "Stop")):
            mediakeys.send(action, bus)
            self.assertEqual(calls[-1], (browser, method))
        bus.players[integration].pid = 456  # another browser must not be controlled
        mediakeys.send("previous", bus)
        self.assertEqual(calls[-1], (browser, "Seek", -42_000_000))
        del bus.players[integration]
        mediakeys.send("previous", bus)
        self.assertEqual(calls[-1], (browser, "Seek", -42_000_000))


class Sensors(unittest.TestCase):
    def test_sleeping_gpu_is_left_alone(self):
        gpu = os.path.join(_SANDBOX, "gpu")
        os.makedirs(os.path.join(gpu, "power"), exist_ok=True)
        with open(os.path.join(gpu, "power", "runtime_status"), "w") as f:
            f.write("suspended\n")
        # returns before loading NVML, so the test passes on machines without it too
        self.assertIsNone(sensors.gpu_memory_percent(gpu))
        self.assertIsNone(sensors.gpu_memory_percent(None))

    def test_cpu_load_needs_two_reads(self):
        s = sensors.Sensors()
        self.assertIsNone(s._cpu_load())
        load = s._cpu_load()
        self.assertTrue(load is None or 0 <= load <= 100)


if __name__ == "__main__":
    unittest.main()
