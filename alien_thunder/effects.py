"""Lighting effects, drawn by the daemon at 40 to 50 fps.

Every effect only changes how bright each light is. The colors are always the ones the
profile picked: a key set to purple breathes in purple, and a key left unset stays off.
"""
from __future__ import annotations

import math
import random

from . import layout
from .i18n import N_

Rgb = tuple[int, int, int]

KEYBOARD_EFFECTS = {
    "static": N_("Static"),
    "breathing": N_("Breathing"),
    "pulse": N_("Pulse"),
    "wave": N_("Wave"),
    "twinkle": N_("Twinkle"),
}
ZONE_EFFECTS = {
    "static": N_("Static"),
    "breathing": N_("Breathing"),
    "pulse": N_("Pulse"),
    "morse": N_("Morse code"),
    "ambulance": N_("Ambulance"),
    "police": N_("Police"),
    "audio": N_("Follow default audio"),
    "off": N_("Off"),
}

_X = {led: layout.rel_x(led) for led in layout.ALL_LEDS}
BREATH_CYCLE_SECONDS = 12.0


def _scale(c: Rgb, f: float) -> Rgb:
    return tuple(max(0, min(255, int(round(x * f)))) for x in c)  # type: ignore[return-value]


def breathing(t: float, speed: float) -> float:
    """A slow, continuous fade rather than a quick pulse.

    At the default speed a full inhale/exhale lasts twelve seconds.  That gives the
    controller enough intermediate PWM levels to make the transition look natural.
    """
    phase = 2 * math.pi * t * speed / BREATH_CYCLE_SECONDS
    return 0.06 + 0.94 * (0.5 + 0.5 * math.cos(phase))


def fan_breath_speed(rpm: int) -> float | None:
    """Breathing speed for the faster chassis fan; None means LEDs off."""
    if rpm <= 0:
        return None
    if rpm <= 2000:
        return 0.35
    if rpm <= 3000:
        return 0.7
    if rpm <= 4600:
        return 1.2
    if rpm <= 5000:
        return 2.4
    return 4.8


def pulse(t: float, speed: float) -> float:
    phase = (t * speed / 1.2) % 1.0
    return 0.12 + 0.88 * math.exp(-6.0 * phase)


_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.",
    "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.",
    "o": "---", "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-", "u": "..-",
    "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..", "0": "-----", "1": ".----",
    "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...", "8": "---..",
    "9": "----.",
}


def _morse_timeline(message: str) -> list[tuple[bool, int]]:
    """On/off durations in standard Morse time units, repeating forever."""
    timeline: list[tuple[bool, int]] = []
    words = [word for word in message.lower().split() if word]
    for word_index, word in enumerate(words):
        letters = [code for char in word if (code := _MORSE.get(char))]
        for letter_index, code in enumerate(letters):
            for symbol_index, symbol in enumerate(code):
                timeline.append((True, 1 if symbol == "." else 3))
                if symbol_index != len(code) - 1:
                    timeline.append((False, 1))
            if letter_index != len(letters) - 1:
                timeline.append((False, 3))
        if word_index != len(words) - 1:
            timeline.append((False, 7))
    if timeline:
        timeline.append((False, 3))  # gap before the repeated transmission
    return timeline or [(False, 1)]


class Animation:
    """A running effect over a set of lights: {id: color} in, {id: dimmed color} out."""

    def __init__(self, effect: str, base: dict[int, Rgb], speed: float, *, message: str = "", phase: float = 0.0):
        if effect not in (KEYBOARD_EFFECTS | ZONE_EFFECTS) or effect in ("static", "off"):
            raise ValueError(f"not an animated effect: {effect}")
        self.name = effect
        self.base = dict(base)
        self.speed = max(0.1, min(5.0, float(speed)))
        self._clock_offset = 0.0
        self._sparks: dict[int, float] = {}
        self._last_t: float | None = None
        self._rng = random.Random(1234)
        self._morse = _morse_timeline(message)
        self.phase = phase
        self.level = 0.0

    def set_speed(self, t: float, speed: float):
        """Changes speed without making the current brightness jump."""
        speed = max(0.1, min(5.0, float(speed)))
        if speed == self.speed:
            return
        self._clock_offset = (t + self._clock_offset) * self.speed / speed - t
        self.speed = speed

    def set_level(self, level: float):
        """Audio is always driven directly by the default output, never by Speed."""
        self.level = max(0.0, min(1.0, float(level)))

    def frame(self, t: float) -> dict[int, Rgb]:
        t += self._clock_offset
        if self.name == "breathing":
            f = breathing(t, self.speed)
            return {led: _scale(c, f) for led, c in self.base.items()}
        if self.name == "pulse":
            f = pulse(t, self.speed)
            return {led: _scale(c, f) for led, c in self.base.items()}
        if self.name == "morse":
            unit = 0.18 / self.speed
            at = (t % (sum(duration for _, duration in self._morse) * unit)) / unit
            for on, duration in self._morse:
                if at < duration:
                    return {led: _scale(c, 1.0 if on else 0.0) for led, c in self.base.items()}
                at -= duration
        if self.name == "ambulance":
            beat = (t * self.speed + self.phase) % 1.5
            f = 1.0 if beat < 0.12 or 0.24 <= beat < 0.36 else 0.0
            return {led: _scale(c, f) for led, c in self.base.items()}
        if self.name == "police":
            beat = (t * self.speed * 3 + self.phase) % 1.0
            return {led: _scale(c, 1.0 if beat < 0.22 else 0.0) for led, c in self.base.items()}
        if self.name == "audio":
            return {led: _scale(c, 0.04 + 0.96 * self.level) for led, c in self.base.items()}
        if self.name == "wave":
            pos = (t * 0.35 * self.speed) % 1.4 - 0.2
            return {led: _scale(c, 0.2 + 0.8 * max(0.0, 1.0 - abs(_X.get(led, 0.5) - pos) / 0.18))
                    for led, c in self.base.items()}
        return self._twinkle(t)

    def _twinkle(self, t: float) -> dict[int, Rgb]:
        dt = 0.05 if self._last_t is None else max(0.0, min(0.5, t - self._last_t))
        self._last_t = t
        for led in list(self._sparks):
            self._sparks[led] -= 1.6 * self.speed * dt
            if self._sparks[led] <= 0:
                del self._sparks[led]
        lit = [led for led, c in self.base.items() if any(c)]
        # about four new sparks a second, times the speed
        if lit and self._rng.random() < min(1.0, 4.0 * self.speed * dt):
            self._sparks[self._rng.choice(lit)] = 1.0
        return {led: _scale(c, 0.3 + 0.7 * self._sparks.get(led, 0.0)) for led, c in self.base.items()}
