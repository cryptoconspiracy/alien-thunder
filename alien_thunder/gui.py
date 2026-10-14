"""Alien Thunder's lighting editor (PySide6)."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, QSocketNotifier, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPalette,
                           QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                               QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                               QRubberBand, QScrollArea, QSizePolicy, QSlider,
                               QSpinBox, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from . import donate, effects, engine, gmode, hw, layout, mediakeys, profiles
from .i18n import gettext as _
from .i18n import ngettext

APP_NAME = "Alien Thunder"
ACCENT = QColor("#00c8ff")
PALETTE = ["#ff0000", "#ff2900", "#ff8000", "#ffd000", "#80ff00", "#00ff40", "#00ffd0", "#00a0ff",
           "#0020ff", "#8000ff", "#ff00c0", "#ff62e2", "#ffffff", "#ffb070", "#630000", "#000000"]


def app_icon() -> QIcon:
    return QIcon.fromTheme("alien-thunder", QIcon(os.path.join(os.path.dirname(__file__), "icons", "alien-thunder.png")))


def qcolor(h: str | None) -> QColor | None:
    return QColor(h) if h else None


def text_color_for(c: QColor) -> QColor:
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return QColor("#111111") if lum > 140 else QColor("#f2f2f2")


# ====================================================================== widgets
class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color="#ff0000", title=None, parent=None):
        super().__init__(parent)
        self.title = title or _("Pick a color")
        self._color = color
        self.setMinimumSize(QSize(64, 28))
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> str:
        return self._color

    def setColor(self, c: str, emit=False):
        self._color = profiles.norm_hex(c)
        self._refresh()
        if emit:
            self.colorChanged.emit(self._color)

    def _refresh(self):
        c = QColor(self._color)
        self.setStyleSheet(
            f"QPushButton {{ background:{self._color}; color:{text_color_for(c).name()};"
            f" border:1px solid #555; border-radius:4px; padding:3px 8px; }}"
            f"QPushButton:disabled {{ background:#3a3d42; color:#8a8f96; border:1px dashed #666; }}")
        self.setText(self._color.upper())

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, self.title)
        if c.isValid():
            self.setColor(c.name(), emit=True)


class Swatch(QToolButton):
    def __init__(self, color: str, size=22, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(size, size)
        self.setToolTip(color.upper())
        self.setStyleSheet(f"QToolButton {{ background:{color}; border:1px solid #444; border-radius:3px; }}"
                           f"QToolButton:hover {{ border:2px solid {ACCENT.name()}; }}")


class KeyboardView(QWidget):
    selectionChanged = Signal()
    keyActivated = Signal(int)  # double click
    keyPicked = Signal(int)  # eyedropper

    MARGIN = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors: dict[int, QColor] = {}
        self.preview: dict[int, QColor] | None = None
        self.selection: set[int] = set()
        self.banner = ""
        self.pick_mode = False
        self._press = None
        self._press_key = None
        self._base_sel: set[int] = set()
        self._dragging = False
        self._band = QRubberBand(QRubberBand.Rectangle, self)
        self.setMouseTracking(True)
        self.setMinimumSize(640, 280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

    # --------------------------------------------------------- geometry
    def _xf(self):
        w = self.width() - 2 * self.MARGIN
        h = self.height() - 2 * self.MARGIN
        s = min(w / layout.CANVAS_W, h / layout.CANVAS_H)
        ox = self.MARGIN + (w - layout.CANVAS_W * s) / 2
        oy = self.MARGIN + (h - layout.CANVAS_H * s) / 2
        return s, ox, oy

    def key_rect(self, k: layout.Key) -> QRectF:
        s, ox, oy = self._xf()
        x, y, w, h = k.rect
        pad = 2.5
        return QRectF(ox + (x + pad) * s, oy + (y + pad) * s, (w - 2 * pad) * s, (h - 2 * pad) * s)

    def key_at(self, pos) -> int | None:
        for k in layout.KEYS:
            if self.key_rect(k).contains(QPointF(pos)):
                return k.id
        return None

    def sizeHint(self):
        return QSize(1000, 430)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(w * layout.CANVAS_H / layout.CANVAS_W) + 2 * self.MARGIN

    # --------------------------------------------------------- drawing
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s, ox, oy = self._xf()
        deck = QRectF(ox - 8 * s, oy - 8 * s, (layout.CANVAS_W + 16) * s, (layout.KEYS_H + 16) * s)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#15171a"))
        p.drawRoundedRect(deck, 10, 10)
        font = QFont(self.font())
        src = self.preview if self.preview is not None else self.colors
        for k in layout.KEYS:
            r = self.key_rect(k)
            c = src.get(k.id)
            path = QPainterPath()
            rad = 5 * s
            if k.id == 55:  # ISO Enter, an upside-down "L"
                s_ = s
                x, y, w, h = k.rect
                top_h = 52.7
                cut = 11.0
                path.moveTo(ox + (x + 2.5) * s_, oy + (y + 2.5) * s_)
                path.lineTo(ox + (x + w - 2.5) * s_, oy + (y + 2.5) * s_)
                path.lineTo(ox + (x + w - 2.5) * s_, oy + (y + h - 2.5) * s_)
                path.lineTo(ox + (x + cut + 2.5) * s_, oy + (y + h - 2.5) * s_)
                path.lineTo(ox + (x + cut + 2.5) * s_, oy + (y + top_h - 2.5) * s_)
                path.lineTo(ox + (x + 2.5) * s_, oy + (y + top_h - 2.5) * s_)
                path.closeSubpath()
            else:
                path.addRoundedRect(r, rad, rad)
            if c is None:
                p.setBrush(QColor("#2b2e33"))
                p.setPen(QPen(QColor("#555a60"), 1, Qt.DashLine))
            else:
                p.setBrush(c)
                p.setPen(QPen(QColor(0, 0, 0, 160), 1))
            p.drawPath(path)
            if k.id in self.selection:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(ACCENT, max(2.0, 3.2 * s)))
                p.drawPath(path)
                p.setPen(QPen(QColor("white"), 1))
                p.drawPath(path)
            tc = text_color_for(c) if c is not None else QColor("#9aa0a6")
            p.setPen(tc)
            fs = max(6.0, (11 if len(k.label) <= 3 else 9) * s * 1.35)
            font.setPointSizeF(fs * 0.75)
            font.setBold(k.id in self.selection)
            p.setFont(font)
            p.drawText(r, Qt.AlignCenter, k.label)
        # caption for the extras
        font.setBold(False)
        font.setPointSizeF(max(7.0, 9 * s * 1.2) * 0.75)
        p.setFont(font)
        p.setPen(QColor("#8a9099"))
        lx = ox + 6 * 68.0 * s + 6 * s
        p.drawText(QRectF(lx, oy + layout.EXTRA_Y * s, 600 * s, layout.EXTRA_H * s),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   _("← AWCC LEDs with no key on ABNT2 (JP/UK keyboards)"))
        if self.banner:
            p.setPen(QColor("#ffd27a"))
            p.drawText(QRectF(lx, oy + layout.EXTRA_Y * s + layout.EXTRA_H * s * 0.0, 590 * s, layout.EXTRA_H * s),
                       Qt.AlignVCenter | Qt.AlignRight, self.banner)
        p.end()

    # --------------------------------------------------------- mouse
    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        self._press = ev.position().toPoint()
        self._press_key = self.key_at(self._press)
        mods = ev.modifiers()
        self._base_sel = set(self.selection) if mods & (Qt.ControlModifier | Qt.ShiftModifier) else set()
        self._dragging = False

    def mouseMoveEvent(self, ev):
        if self._press is None:
            k = self.key_at(ev.position().toPoint())
            self.setCursor(Qt.CrossCursor if self.pick_mode else
                           (Qt.PointingHandCursor if k is not None else Qt.ArrowCursor))
            return
        pos = ev.position().toPoint()
        if not self._dragging and (pos - self._press).manhattanLength() > 6 and not self.pick_mode:
            self._dragging = True
            self._band.show()
        if self._dragging:
            rect = QRect(self._press, pos).normalized()
            self._band.setGeometry(rect)
            hit = {k.id for k in layout.KEYS if self.key_rect(k).intersects(QRectF(rect))}
            self.selection = self._base_sel | hit
            self.update()
            self.selectionChanged.emit()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or self._press is None:
            return
        if self._dragging:
            self._band.hide()
        else:
            k = self._press_key
            mods = ev.modifiers()
            if self.pick_mode:
                self.pick_mode = False
                self.setCursor(Qt.ArrowCursor)
                if k is not None:
                    self.keyPicked.emit(k)
            elif k is None:
                if not mods & (Qt.ControlModifier | Qt.ShiftModifier):
                    self.selection = set()
            elif mods & Qt.ControlModifier:
                self.selection ^= {k}
            elif mods & Qt.ShiftModifier:
                self.selection |= {k}
            else:
                self.selection = {k}
            self.update()
            self.selectionChanged.emit()
        self._press = None
        self._dragging = False

    def mouseDoubleClickEvent(self, ev):
        k = self.key_at(ev.position().toPoint())
        if k is not None:
            self.selection = {k}
            self.update()
            self.selectionChanged.emit()
            self.keyActivated.emit(k)

    def event(self, ev):
        if ev.type() == ev.Type.ToolTip:
            k = self.key_at(ev.pos())
            if k is not None:
                key = layout.KEY_BY_ID[k]
                c = self.colors.get(k)
                leds = ", ".join(str(x) for x in key.leds)
                extra = "\n" + _("LED with no physical key on ABNT2") if key.extra else ""
                color = c.name().upper() if c else _("no color (not sent)")
                self.setToolTip(_("%s\nLED(s): %s  (AWCC: %s)\nColor: %s") % (key.name, leds, key.awcc, color)
                                + extra)
            else:
                self.setToolTip("")
        return super().event(ev)


class DonationStrip(QWidget):
    """The wallets from donate.py: a QR code each and a button that copies the address."""

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(18)
        icons = os.path.join(os.path.dirname(__file__), "icons")
        for w in donate.WALLETS:
            qr = QLabel()
            qr.setPixmap(QPixmap(os.path.join(icons, w["qr"])).scaled(76, 76, Qt.KeepAspectRatio, Qt.FastTransformation))
            qr.setToolTip(w["address"])
            cell = QHBoxLayout()
            cell.setSpacing(8)
            cell.addWidget(qr)
            col = QVBoxLayout()
            col.setSpacing(3)
            col.addStretch(1)
            col.addWidget(QLabel("<b>%s</b>" % _(w["name"])))
            if w["networks"]:
                nets = QLabel(w["networks"])
                nets.setStyleSheet("color:#9aa0a6;")
                nets.setWordWrap(True)
                nets.setMinimumWidth(420)
                nets.setMaximumWidth(480)
                col.addWidget(nets)
            copy = QPushButton(QIcon.fromTheme("edit-copy"), _("Copy"))
            copy.setToolTip(w["address"])
            copy.clicked.connect(lambda _c=False, a=w["address"], b=copy: self._copy(a, b))
            col.addWidget(copy, 0, Qt.AlignLeft)
            col.addStretch(1)
            cell.addLayout(col)
            row.addLayout(cell)
        row.addStretch(1)

    def _copy(self, address, button):
        QApplication.clipboard().setText(address)
        button.setText(_("Copied"))
        QTimer.singleShot(2000, lambda: button.setText(_("Copy")))


# ====================================================================== window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        for m in profiles.ensure_initialized():
            print(m)
        self.cfg = profiles.load_config()
        self.slug: str | None = None
        self.profile: dict = copy.deepcopy(profiles.DEFAULT_PROFILE)
        self.direct_engine: engine.Engine | None = None
        self.preview_sent = False
        self._loading = False
        self._daemon_ok = None

        self.save_timer = QTimer(self, singleShot=True, interval=700, timeout=self.save_now)
        self.live_timer = QTimer(self, singleShot=True, interval=150, timeout=self.push_live)
        self.anim_timer = QTimer(self, interval=66, timeout=self._animate)
        self.anim_fx = None
        self.anim_t0 = 0.0

        self._build()
        self.reload_profile_list(select=profiles.active_slug())
        self.refresh_daemon_status()
        QTimer(self, interval=5000, timeout=self.refresh_daemon_status).start()

    # ------------------------------------------------------------ building
    def _build(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)

        # profile bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("<b>%s</b>" % _("Profile:")))
        self.cb_profile = QComboBox()
        self.cb_profile.setMinimumWidth(230)
        self.cb_profile.currentIndexChanged.connect(self.on_profile_selected)
        bar.addWidget(self.cb_profile)
        for text, icon, slot, tip in (
                (_("New"), "document-new", self.new_profile, _("Create a new profile")),
                (_("Rename"), "edit-rename", self.rename_profile, _("Rename the profile")),
                (_("Duplicate"), "edit-copy", self.duplicate_profile, _("Duplicate the profile")),
                (_("Delete"), "edit-delete", self.delete_profile, _("Delete the profile")),
                (_("Make active"), "starred", self.activate_profile,
                 _("Make this the lasting profile (applied at login, after suspend, and so on)")),
                (_("Import from Windows…"), "document-import", self.import_windows,
                 _("Import Alienware Command Center presets"))):
            b = QToolButton()
            b.setText(text)
            b.setIcon(QIcon.fromTheme(icon))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar.addWidget(b)
            if icon == "starred":
                self.btn_activate = b
        bar.addStretch(1)
        self.btn_gmode = QPushButton("G-Mode")
        self.btn_gmode.setCheckable(True)
        self.btn_gmode.setToolTip(_("Turbo: fans at full speed and the performance power profile (same as Fn+F1)"))
        self.btn_gmode.setStyleSheet("QPushButton:checked{background:#f0f0f0;color:#111;font-weight:bold;}")
        self.btn_gmode.clicked.connect(self.toggle_gmode)
        bar.addWidget(self.btn_gmode)
        self.lbl_daemon = QLabel()
        bar.addWidget(self.lbl_daemon)
        root.addLayout(bar)

        self.lbl_hint = QLabel()
        self.lbl_hint.setStyleSheet("color:#d9a441;")
        root.addWidget(self.lbl_hint)

        mid = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(DonationStrip())
        self.kb = KeyboardView()
        self.kb.selectionChanged.connect(self.on_selection_changed)
        self.kb.keyActivated.connect(lambda _k: self.pick_color_dialog())
        self.kb.keyPicked.connect(self.on_key_picked)
        left.addWidget(self.kb, 1)
        mid.addLayout(left, 1)

        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(360)
        self.tabs.setMaximumWidth(420)
        self.tabs.addTab(self._scroll(self._tab_colors()), _("Colors"))
        self.tabs.addTab(self._scroll(self._tab_effects()), _("Effects"))
        self.tabs.addTab(self._scroll(self._tab_chassis()), _("Chassis"))
        self.tabs.addTab(self._scroll(self._tab_keys()), _("Keys"))
        self.tabs.addTab(self._scroll(self._tab_options()), _("Options"))
        mid.addWidget(self.tabs)
        root.addLayout(mid, 1)

        bottom = QHBoxLayout()
        self.lbl_sel = QLabel(_("No keys selected"))
        bottom.addWidget(self.lbl_sel)
        bottom.addStretch(1)
        pitch = QLabel(_("Alien Thunder is free and stays free. If it saved you a trip to Windows, a donation keeps it going."))
        pitch.setStyleSheet("color:#9aa0a6;")
        bottom.addWidget(pitch)
        bottom.addStretch(1)
        self.chk_live = QCheckBox(_("Apply live"))
        self.chk_live.setChecked(True)
        self.chk_live.setToolTip(_("Sends changes to the LEDs as you edit"))
        bottom.addWidget(self.chk_live)
        self.lbl_saved = QLabel("")
        self.lbl_saved.setStyleSheet("color:#888;")
        bottom.addWidget(self.lbl_saved)
        self.btn_apply = QPushButton(QIcon.fromTheme("dialog-ok-apply"), _("Apply"))
        self.btn_apply.setDefault(True)
        self.btn_apply.setMinimumWidth(120)
        self.btn_apply.clicked.connect(self.apply_now)
        bottom.addWidget(self.btn_apply)
        root.addLayout(bottom)

        self.setCentralWidget(central)
        self.resize(1480, 640)

        act = QAction(self, shortcut="Ctrl+A", triggered=lambda: self.select_group("All"))
        self.addAction(act)
        act = QAction(self, shortcut="Escape", triggered=lambda: self.set_selection(set()))
        self.addAction(act)
        act = QAction(self, shortcut="Ctrl+I", triggered=self.invert_selection)
        self.addAction(act)

    def _scroll(self, w):
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.NoFrame)
        sa.setWidget(w)
        return sa

    def _tab_colors(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox(_("Color for the selection"))
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        self.btn_color = ColorButton("#ff0000", _("Color of the selected keys"))
        self.btn_color.colorChanged.connect(lambda c: self.apply_color_to_selection(c))
        row.addWidget(self.btn_color, 1)
        b = QPushButton(_("Apply to selection"))
        b.clicked.connect(lambda: self.apply_color_to_selection(self.btn_color.color()))
        row.addWidget(b)
        gl.addLayout(row)
        row = QHBoxLayout()
        b = QPushButton(QIcon.fromTheme("color-picker"), _("Eyedropper"))
        b.setToolTip(_("Click a key to copy its color"))
        b.clicked.connect(self.start_pick)
        row.addWidget(b)
        b = QPushButton(_("Turn selection off"))
        b.setToolTip(_("Sets the selected keys to black (LED off)"))
        b.clicked.connect(lambda: self.apply_color_to_selection("#000000", recent=False))
        row.addWidget(b)
        gl.addLayout(row)

        gl.addWidget(QLabel(_("Palette:")))
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, c in enumerate(PALETTE):
            s = Swatch(c)
            s.clicked.connect(lambda _=False, c=c: self.choose_color(c))
            grid.addWidget(s, i // 8, i % 8)
        gl.addLayout(grid)
        gl.addWidget(QLabel(_("Recent colors:")))
        self.recent_grid = QGridLayout()
        self.recent_grid.setSpacing(4)
        gl.addLayout(self.recent_grid)
        self._refresh_recent()
        v.addWidget(g)

        g = QGroupBox(_("Overall brightness (keyboard and chassis)"))
        gl = QHBoxLayout(g)
        self.sl_bright = QSlider(Qt.Horizontal)
        self.sl_bright.setRange(0, 100)
        self.sl_bright.valueChanged.connect(self.on_brightness)
        self.lbl_bright = QLabel("100%")
        self.lbl_bright.setMinimumWidth(40)
        gl.addWidget(self.sl_bright, 1)
        gl.addWidget(self.lbl_bright)
        v.addWidget(g)

        g = QGroupBox(_("Key sets"))
        gl = QVBoxLayout(g)
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, name in enumerate(layout.GROUPS):
            b = QPushButton(_(name))
            b.setToolTip(_("Click: select • Ctrl+click: add to the selection"))
            b.clicked.connect(lambda _=False, n=name: self.select_group(n))
            grid.addWidget(b, i // 2, i % 2)
        gl.addLayout(grid)
        row = QHBoxLayout()
        b = QPushButton(_("Invert selection"))
        b.clicked.connect(self.invert_selection)
        row.addWidget(b)
        b = QPushButton(_("Clear selection"))
        b.clicked.connect(lambda: self.set_selection(set()))
        row.addWidget(b)
        gl.addLayout(row)
        gl.addWidget(QLabel(_("My groups:")))
        row = QHBoxLayout()
        self.cb_groups = QComboBox()
        row.addWidget(self.cb_groups, 1)
        b = QPushButton(_("Select"))
        b.clicked.connect(self.select_custom_group)
        row.addWidget(b)
        gl.addLayout(row)
        row = QHBoxLayout()
        b = QPushButton(_("Save selection as a group…"))
        b.clicked.connect(self.save_custom_group)
        row.addWidget(b)
        b = QPushButton(_("Delete group"))
        b.clicked.connect(self.delete_custom_group)
        row.addWidget(b)
        gl.addLayout(row)
        self._refresh_groups()
        v.addWidget(g)
        v.addStretch(1)
        return w

    def _tab_effects(self):
        w = QWidget()
        v = QVBoxLayout(w)
        note = QLabel(_("Effects only change how bright each light is; the colors stay the ones you picked. "
                        "The background service draws them at %d fps.") % self.cfg["fps"])
        note.setWordWrap(True)
        note.setStyleSheet("color:#999;")
        v.addWidget(note)
        self.fx_widgets = {}
        for zone, title, choices in (("keyboard", _("Keyboard"), effects.KEYBOARD_EFFECTS),
                                     ("touchpad", _("Touchpad"), effects.ZONE_EFFECTS),
                                     ("logo", _("Alien head (logo on the lid)"), effects.ZONE_EFFECTS)):
            g = QGroupBox(title)
            f = QFormLayout(g)
            cb = QComboBox()
            for k, name in choices.items():
                cb.addItem(_(name), k)
            sl = QSlider(Qt.Horizontal)
            sl.setRange(1, 50)
            f.addRow(_("Effect:"), cb)
            f.addRow(_("Speed:"), sl)
            cb.currentIndexChanged.connect(lambda *_a, z=zone: self.on_fx_changed(z))
            sl.valueChanged.connect(lambda *_a, z=zone: self.on_fx_changed(z))
            self.fx_widgets[zone] = (cb, sl)
            v.addWidget(g)
        v.addStretch(1)
        return w

    def _tab_chassis(self):
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox(_("Colors"))
        f = QFormLayout(g)
        self.zone_color = {}
        for zone, title in (("touchpad", _("Touchpad")), ("logo", _("Alien head (logo on the lid)"))):
            c = ColorButton("#ff2900", title)
            c.colorChanged.connect(lambda *_a, z=zone: self.on_zone_color_changed(z))
            f.addRow(title + ":", c)
            self.zone_color[zone] = c
        v.addWidget(g)
        g = QGroupBox(_("Power button"))
        f = QFormLayout(g)
        self.btn_pw_ac = ColorButton("#ff2900", _("Power button when plugged in"))
        self.btn_pw_bat = ColorButton("#ff2900", _("Power button on battery"))
        self.btn_pw_ac.colorChanged.connect(self.on_power_changed)
        self.btn_pw_bat.colorChanged.connect(self.on_power_changed)
        f.addRow(_("Plugged in (AC):"), self.btn_pw_ac)
        f.addRow(_("On battery:"), self.btn_pw_bat)
        note = QLabel(_("The controller stores how the button behaves, asleep and charging included. "
                        "To avoid writing it over and over, the colors only go out when they change "
                        "and the profile is the active one, never live. Use “Apply” or the button below."))
        note.setWordWrap(True)
        note.setStyleSheet("color:#999;")
        f.addRow(note)
        b = QPushButton(_("Write the button colors now"))
        b.clicked.connect(self.write_power_now)
        f.addRow(b)
        v.addWidget(g)
        v.addStretch(1)
        return w

    def _tab_keys(self):
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox(_("Music keys"))
        gv = QVBoxLayout(g)
        note = QLabel(_("Keys that control whatever is playing music (Spotify, the browser, any player "
                        "Plasma's media controls see). They belong to the profile, like the colors."))
        note.setWordWrap(True)
        note.setStyleSheet("color:#999;")
        gv.addWidget(note)
        self.keys_form = QFormLayout()
        gv.addLayout(self.keys_form)
        self.btn_record = QPushButton(QIcon.fromTheme("media-record"), _("Record a key…"))
        self.btn_record.setToolTip(_("Press it, then the key you want, for example Fn+F3"))
        self.btn_record.clicked.connect(self.start_record)
        gv.addWidget(self.btn_record)
        self.lbl_record = QLabel()
        self.lbl_record.setWordWrap(True)
        gv.addWidget(self.lbl_record)
        v.addWidget(g)
        v.addStretch(1)
        self.record_fd = None
        self.record_notifier = None
        self.record_timer = QTimer(self, singleShot=True, interval=10000,
                                   timeout=lambda: self.stop_record(_("No key in 10 seconds; try again.")))
        return w

    def _refresh_keys(self):
        while self.keys_form.rowCount():
            self.keys_form.removeRow(0)
        if not self.profile["keys"]:
            lbl = QLabel(_("(no keys yet)"))
            lbl.setStyleSheet("color:#999;")
            self.keys_form.addRow(lbl)
        for k in self.profile["keys"]:
            cb = QComboBox()
            for a, name in mediakeys.ACTIONS.items():
                cb.addItem(_(name), a)
            cb.addItem(_("Nothing (remove)"), None)
            cb.setCurrentIndex(max(0, cb.findData(k["action"])))
            cb.currentIndexChanged.connect(lambda _i, cb=cb, scan=k["scan"]: self.on_key_action(scan, cb.currentData()))
            self.keys_form.addRow(mediakeys.key_name(k["scan"]) + ":", cb)

    def on_key_action(self, scan, action):
        keys = self.profile["keys"]
        if action is None:
            keys[:] = [k for k in keys if k["scan"] != scan]
            QTimer.singleShot(0, self._refresh_keys)  # not from inside the combo's own signal
        else:
            for k in keys:
                if k["scan"] == scan:
                    k["action"] = action
        self.changed()

    def start_record(self):
        self.stop_record()
        try:
            self.record_fd = os.open(mediakeys.KEYBOARD, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            self.lbl_record.setText(_("Can't read the keyboard (%s). Your user needs to be in the input group, "
                                      "the same as for Fn+F1.") % e.strerror)
            return
        self.record_notifier = QSocketNotifier(self.record_fd, QSocketNotifier.Read, self)
        self.record_notifier.activated.connect(self._on_record)
        self.record_timer.start()
        self.btn_record.setEnabled(False)
        self.lbl_record.setText(_("Press the key now…"))

    def stop_record(self, message=""):
        self.record_timer.stop()
        if self.record_notifier is not None:
            self.record_notifier.setEnabled(False)
            self.record_notifier.deleteLater()
            self.record_notifier = None
        if self.record_fd is not None:
            os.close(self.record_fd)
            self.record_fd = None
        self.btn_record.setEnabled(True)
        self.lbl_record.setText(message)

    def _on_record(self, *_a):
        try:
            data = os.read(self.record_fd, mediakeys.EVENT.size * 64)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self.stop_record(_("The keyboard went away; try again."))
            return
        for scan, code in mediakeys.presses(data):
            if not mediakeys.bindable(code):
                self.lbl_record.setText(_("That key already does something on Linux, and pressing it would do both. "
                                          "Pick one that does nothing, like Fn+F3 to Fn+F6."))
                continue
            name = mediakeys.key_name(scan)
            if any(k["scan"] == scan for k in self.profile["keys"]):
                self.stop_record(_("%s is already on the list.") % name)
                return
            used = {k["action"] for k in self.profile["keys"]}
            action = next((a for a in mediakeys.ACTIONS if a not in used), "play_pause")
            self.profile["keys"].append({"scan": scan, "action": action})
            self._refresh_keys()
            self.changed()
            self.stop_record(_("%s added; pick what it does above.") % name)
            return

    def _tab_options(self):
        w = QWidget()
        v = QVBoxLayout(w)
        g = QGroupBox(_("Background service"))
        f = QFormLayout(g)
        self.lbl_service = QLabel()
        self.lbl_service.setWordWrap(True)
        self.lbl_service.setMinimumHeight(self.lbl_service.fontMetrics().lineSpacing() * 3)
        self.lbl_service.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        f.addRow(self.lbl_service)
        row = QHBoxLayout()
        b = QPushButton(_("Restart service"))
        b.clicked.connect(lambda: self._systemctl("restart"))
        row.addWidget(b)
        b = QPushButton(_("Reapply active profile"))
        b.clicked.connect(self.reapply_active)
        row.addWidget(b)
        f.addRow(row)
        self.sp_fps = QSpinBox()
        self.sp_fps.setRange(1, 20)
        self.sp_fps.setValue(self.cfg["fps"])
        self.sp_fps.setSuffix(" fps")
        self.sp_fps.valueChanged.connect(self.on_options)
        f.addRow(_("Software effects:"), self.sp_fps)
        self.cb_backend = QComboBox()
        self.cb_backend.addItem(_("hidraw directly (touchpad, logo and effects)"), "hidraw")
        self.cb_backend.addItem(_("alienrgb (compatible, fixed colors only)"), "alienrgb")
        self.cb_backend.setCurrentIndex(0 if self.cfg["chassis_backend"] == "hidraw" else 1)
        self.cb_backend.currentIndexChanged.connect(self.on_options)
        f.addRow(_("Chassis through:"), self.cb_backend)
        v.addWidget(g)
        g = QGroupBox(_("Devices"))
        f = QVBoxLayout(g)
        self.lbl_devs = QLabel()
        self.lbl_devs.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f.addWidget(self.lbl_devs)
        help_ = QLabel(_("Tips: click selects; Ctrl+click toggles; Shift+click adds; drag to select an "
                         "area; double click opens the color picker; Ctrl+A selects everything; "
                         "Ctrl+I inverts; Esc clears.\nCLI: alien-thunder list | set <profile> | apply [profile] | status"))
        help_.setWordWrap(True)
        help_.setStyleSheet("color:#999;")
        f.addWidget(help_)
        v.addWidget(g)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------ profiles
    def reload_profile_list(self, select: str | None = None):
        self._loading = True
        act = profiles.active_slug()
        self.cb_profile.clear()
        for slug, name in profiles.list_profiles():
            self.cb_profile.addItem(("★ " if slug == act else "") + name, slug)
        self._loading = False
        idx = self.cb_profile.findData(select or self.slug or act)
        self.cb_profile.setCurrentIndex(max(0, idx))
        self.on_profile_selected(self.cb_profile.currentIndex())

    def on_profile_selected(self, idx):
        if self._loading or idx < 0:
            return
        slug = self.cb_profile.itemData(idx)
        if slug == self.slug:
            return
        self.save_now()
        try:
            self.profile = profiles.load(slug)
        except profiles.ProfileError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        self.slug = slug
        self.load_into_widgets()
        self.schedule_live()

    def load_into_widgets(self):
        self._loading = True
        p = self.profile
        self.kb.colors = {int(k): QColor(v) for k, v in p["keyboard"].items()}
        for k in layout.KEYS:  # a key shows its main LED's color
            if k.id not in self.kb.colors:
                for led in k.leds[1:]:
                    if str(led) in p["keyboard"]:
                        self.kb.colors[k.id] = QColor(p["keyboard"][str(led)])
        self.sl_bright.setValue(p["brightness"])
        self.lbl_bright.setText(f"{p['brightness']}%")
        for zone, (cb, sl) in self.fx_widgets.items():
            fx = p["keyboard_effect"] if zone == "keyboard" else p["chassis"][zone]
            cb.setCurrentIndex(max(0, cb.findData(fx["effect"])))
            sl.setValue(int(round(fx["speed"] * 10)))
        for zone, c in self.zone_color.items():
            c.setColor(p["chassis"][zone]["color"])
        self.btn_pw_ac.setColor(p["chassis"]["power"]["ac"])
        self.btn_pw_bat.setColor(p["chassis"]["power"]["battery"])
        self._refresh_keys()
        self._loading = False
        self._update_effect_ui()
        self._update_hint()
        self.kb.update()

    def _update_hint(self):
        act = profiles.active_slug()
        self.btn_activate.setEnabled(self.slug != act)
        if self.slug == act:
            self.lbl_hint.setText("")
            self.lbl_hint.hide()
        else:
            self.lbl_hint.setText(_("You're editing a profile that isn't the active one: the LEDs show it only "
                                    "while this window is open. Use “Make active” to keep it."))
            self.lbl_hint.show()

    def _ask_name(self, title, default=""):
        name, ok = QInputDialog.getText(self, title, _("Profile name:"), text=default)
        name = name.strip()
        return name if ok and name else None

    def new_profile(self):
        name = self._ask_name(_("New profile"))
        if name:
            self.save_now()
            slug = profiles.create(name)
            self.reload_profile_list(select=slug)

    def rename_profile(self):
        if not self.slug:
            return
        name = self._ask_name(_("Rename profile"), self.profile["name"])
        if name:
            self.save_now()
            self.slug = profiles.rename(self.slug, name)
            self.profile["name"] = name
            self.reload_profile_list(select=self.slug)

    def duplicate_profile(self):
        if not self.slug:
            return
        name = self._ask_name(_("Duplicate profile"), _("%s (copy)") % self.profile["name"])
        if name:
            self.save_now()
            slug = profiles.duplicate(self.slug, name)
            self.reload_profile_list(select=slug)

    def delete_profile(self):
        if not self.slug:
            return
        if self.slug == profiles.active_slug():
            QMessageBox.information(self, APP_NAME, _("This is the active profile. Make another one active before deleting it."))
            return
        if QMessageBox.question(self, APP_NAME, _("Delete the profile “%s”?") % self.profile["name"]) != QMessageBox.Yes:
            return
        self.save_timer.stop()
        profiles.delete(self.slug)
        self.slug = None
        self.reload_profile_list(select=profiles.active_slug())

    def activate_profile(self):
        if not self.slug:
            return
        self.save_now()
        profiles.set_active(self.slug)
        self.preview_sent = False
        ok = self._daemon("Reload")
        if ok is None:
            self._direct_apply(power=True)
        self.reload_profile_list(select=self.slug)
        self.statusBar().showMessage(_("“%s” is now the active profile") % self.profile["name"], 5000)

    def import_windows(self):
        from . import winimport
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            items = winimport.list_presets()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, APP_NAME, _("Couldn't read the AWCC presets:\n%s") % e)
            return
        finally:
            QApplication.restoreOverrideCursor()
        dlg = QDialog(self)
        dlg.setWindowTitle(_("Import from Windows (Alienware Command Center)"))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(_("Check the presets to import as new profiles "
                               "(the Windows partition is only read):")))
        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.NoSelection)
        for it in items:
            li = QListWidgetItem(f"{it['name']}  —  {it['summary']}")
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Unchecked)
            li.setData(Qt.UserRole, it["id"])
            lst.addItem(li)
        lay.addWidget(lst)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(_("Import"))
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.resize(620, 480)
        if dlg.exec() != QDialog.Accepted:
            return
        chosen = {lst.item(i).data(Qt.UserRole) for i in range(lst.count())
                  if lst.item(i).checkState() == Qt.Checked}
        last = None
        for it in items:
            if it["id"] in chosen:
                last = profiles.create(it["name"] + " (Windows)", it["profile"])
        if last:
            self.save_now()
            self.reload_profile_list(select=last)
            self.statusBar().showMessage(ngettext("%d profile imported", "%d profiles imported", len(chosen))
                                         % len(chosen), 5000)

    # ------------------------------------------------------------ selection / colors
    def set_selection(self, sel: set[int]):
        self.kb.selection = set(sel)
        self.kb.update()
        self.on_selection_changed()

    def on_selection_changed(self):
        n = len(self.kb.selection)
        if n == 0:
            self.lbl_sel.setText(_("No keys selected: click, Ctrl/Shift+click or drag to select"))
        elif n == 1:
            k = layout.KEY_BY_ID[next(iter(self.kb.selection))]
            self.lbl_sel.setText(_("Selected: %s (LED %s)") % (k.name, ", ".join(map(str, k.leds))))
        else:
            self.lbl_sel.setText(ngettext("%d key selected", "%d keys selected", n) % n)

    def select_group(self, name: str):
        ids = set(layout.GROUPS[name])
        if QApplication.keyboardModifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            ids |= self.kb.selection
        self.set_selection(ids)

    def invert_selection(self):
        self.set_selection({k.id for k in layout.KEYS} - self.kb.selection)

    def choose_color(self, c: str):
        self.btn_color.setColor(c)
        self.apply_color_to_selection(c)

    def apply_color_to_selection(self, c: str, recent=True):
        if not self.kb.selection:
            self.statusBar().showMessage("Selecione teclas primeiro", 3000)
            return
        c = profiles.norm_hex(c)
        for kid in self.kb.selection:
            for led in layout.KEY_BY_ID[kid].leds:
                self.profile["keyboard"][str(led)] = c
            self.kb.colors[kid] = QColor(c)
        if recent:
            self._push_recent(c)
        self.kb.update()
        self.changed()

    def pick_color_dialog(self):
        cur = None
        if len(self.kb.selection) == 1:
            cur = self.kb.colors.get(next(iter(self.kb.selection)))
        c = QColorDialog.getColor(cur or QColor(self.btn_color.color()), self, _("Key color"))
        if c.isValid():
            self.btn_color.setColor(c.name())
            self.apply_color_to_selection(c.name())

    def start_pick(self):
        self.kb.pick_mode = True
        self.kb.setCursor(Qt.CrossCursor)
        self.statusBar().showMessage(_("Eyedropper: click a key"), 4000)

    def on_key_picked(self, kid):
        c = self.kb.colors.get(kid)
        if c is not None:
            self.btn_color.setColor(c.name())
            self.statusBar().showMessage(_("Color %s copied from %s") % (c.name().upper(), layout.KEY_BY_ID[kid].name), 4000)

    def _push_recent(self, c):
        rec = [x for x in self.cfg.get("recent_colors", []) if x != c]
        self.cfg["recent_colors"] = ([c] + rec)[:16]
        self._save_cfg_keys("recent_colors")
        self._refresh_recent()

    def _refresh_recent(self):
        while self.recent_grid.count():
            it = self.recent_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        rec = self.cfg.get("recent_colors", [])
        if not rec:
            lbl = QLabel(_("(none yet)"))
            lbl.setStyleSheet("color:#888;")
            self.recent_grid.addWidget(lbl, 0, 0, 1, 8)
        for i, c in enumerate(rec):
            s = Swatch(c)
            s.clicked.connect(lambda _=False, c=c: self.choose_color(c))
            self.recent_grid.addWidget(s, i // 8, i % 8)

    def _save_cfg_keys(self, *keys):
        cfg = profiles.load_config()  # read again so an active profile changed elsewhere survives
        for k in keys:
            cfg[k] = self.cfg[k]
        profiles.save_config(cfg)
        self.cfg = cfg

    def _refresh_groups(self):
        self.cb_groups.clear()
        for name in sorted(self.cfg.get("groups", {})):
            self.cb_groups.addItem(name)

    def select_custom_group(self):
        name = self.cb_groups.currentText()
        ids = set(self.cfg.get("groups", {}).get(name, [])) & set(layout.KEY_BY_ID)
        if ids:
            self.set_selection(ids)

    def save_custom_group(self):
        if not self.kb.selection:
            self.statusBar().showMessage("Selecione teclas primeiro", 3000)
            return
        name, ok = QInputDialog.getText(self, _("Save group"), _("Group name:"))
        if ok and name.strip():
            self.cfg.setdefault("groups", {})[name.strip()] = sorted(self.kb.selection)
            self._save_cfg_keys("groups")
            self._refresh_groups()
            self.cb_groups.setCurrentText(name.strip())

    def delete_custom_group(self):
        name = self.cb_groups.currentText()
        if name and name in self.cfg.get("groups", {}):
            del self.cfg["groups"][name]
            self._save_cfg_keys("groups")
            self._refresh_groups()

    def on_brightness(self, v):
        self.lbl_bright.setText(f"{v}%")
        if self._loading:
            return
        self.profile["brightness"] = v
        self.changed()

    # ------------------------------------------------------------ effects
    def on_fx_changed(self, zone):
        if self._loading:
            return
        cb, sl = self.fx_widgets[zone]
        fx = self.profile["keyboard_effect"] if zone == "keyboard" else self.profile["chassis"][zone]
        fx.update(effect=cb.currentData(), speed=sl.value() / 10.0)
        self._update_effect_ui()
        self.changed()

    def _update_effect_ui(self):
        self._restart_anim()
        self.kb.update()

    def _restart_anim(self):
        try:
            self.anim_fx = engine.keyboard_animation(profiles.normalize(self.profile))
        except (ValueError, profiles.ProfileError):
            self.anim_fx = None
        if self.anim_fx:
            self.anim_t0 = time.monotonic()
            self.anim_timer.setInterval(int(1000 / self.cfg["fps"]))
            self.anim_timer.start()
            return
        self.anim_timer.stop()
        self.kb.preview = None

    def _animate(self):
        if not self.anim_fx or not self.isVisible():
            return
        fr = self.anim_fx.frame(time.monotonic() - self.anim_t0)
        f = max(0.15, self.profile["brightness"] / 100.0)  # keeps the preview readable at low brightness
        prev = {}
        for k in layout.KEYS:
            c = fr.get(k.id)
            if c is not None:
                prev[k.id] = QColor(*(min(255, int(x / f)) for x in c))
        self.kb.preview = prev
        self.kb.update()

    # ------------------------------------------------------------ chassis
    def on_zone_color_changed(self, zone):
        if self._loading:
            return
        self.profile["chassis"][zone]["color"] = self.zone_color[zone].color()
        self.changed()

    def on_power_changed(self, *_a):
        if self._loading:
            return
        self.profile["chassis"]["power"] = {"ac": self.btn_pw_ac.color(), "battery": self.btn_pw_bat.color()}
        self.changed(live=False)
        self.statusBar().showMessage(_("The power button colors are written on Apply (active profile) "
                                       "or with “Write the button colors now”"), 6000)

    def write_power_now(self):
        self.save_now()
        ok = self._daemon("WritePower", self.slug or "")
        if ok is None:
            try:
                self._engine().write_power_now(self.profile, self.cfg["chassis_backend"])
                ok = True
            except hw.DeviceError as e:
                QMessageBox.warning(self, APP_NAME, str(e))
                return
        self.statusBar().showMessage(_("Power button written") if ok else _("Couldn't write the power button"), 5000)

    # ------------------------------------------------------------ options / service
    def on_options(self, *_a):
        self.cfg["fps"] = self.sp_fps.value()
        self.cfg["chassis_backend"] = self.cb_backend.currentData()
        self._save_cfg_keys("fps", "chassis_backend")
        self._update_effect_ui()

    def _systemctl(self, verb):
        r = subprocess.run(["systemctl", "--user", verb, "alien-thunder.service"], capture_output=True, text=True)
        if r.returncode:
            QMessageBox.warning(self, APP_NAME, r.stderr or _("systemctl %s failed") % verb)
        QTimer.singleShot(1500, self.refresh_daemon_status)
        self.preview_sent = False
        QTimer.singleShot(1800, self.schedule_live)

    def reapply_active(self):
        ok = self._daemon("Reload")
        if ok is None:
            slug = profiles.active_slug()
            if slug:
                self._direct_apply(profiles.load(slug), power=True, force=True)
        self.preview_sent = False
        self.statusBar().showMessage(_("Active profile applied again"), 3000)

    def toggle_gmode(self, on):
        ok = self._daemon("SetGMode", bool(on))
        if ok is None:
            try:
                gmode.set_profile(gmode.PERFORMANCE if on else "balanced")
            except Exception as e:  # noqa: BLE001
                self.statusBar().showMessage(f"G-Mode: {e}", 6000)
        QTimer.singleShot(300, self.refresh_daemon_status)

    def refresh_daemon_status(self):
        info = engine.env_info()
        self.btn_gmode.blockSignals(True)
        self.btn_gmode.setChecked(gmode.is_on())
        self.btn_gmode.blockSignals(False)
        running = engine.daemon_running()
        self._daemon_ok = running
        st = {}
        if running:
            try:
                st = json.loads(str(engine.daemon_call("Status", timeout=3)))
            except Exception:  # noqa: BLE001
                st = {}
        if running:
            err = st.get("ultimo_erro")
            self.lbl_daemon.setText(_("● service running") if not err else _("● service: retrying"))
            self.lbl_daemon.setStyleSheet("color:#3fb950;" if not err else "color:#d29922;")
            self.lbl_daemon.setToolTip(err or _("The service keeps the active profile on the LEDs"))
            txt = (_("Running (pid %s). Applying: %s") % (st.get("pid"), st.get("applying"))
                   + (f" [{st.get('override')}]" if st.get("override") else "")
                   + ("\n" + _("Software effect: %s") % st.get("software_effect") if st.get("software_effect") else "")
                   + ("\n" + _("Last error: %s") % err if err else ""))
        else:
            self.lbl_daemon.setText(_("● service stopped"))
            self.lbl_daemon.setStyleSheet("color:#f85149;")
            self.lbl_daemon.setToolTip(_("Without the service the editor applies directly; software effects don't run"))
            txt = _("Stopped. Start it with: systemctl --user enable --now alien-thunder")
        self.lbl_service.setText(txt)
        missing = _("not found")
        self.lbl_devs.setText(_("Keyboard 0d62:d2b1: %s") % (info["keyboard"] or missing) + "\n"
                              + _("AW-ELC 187c:0551: %s") % (info["chassis"] or missing) + "\n"
                              + "alienrgb: " + (_("available") if info["alienrgb"] else _("missing")))

    # ------------------------------------------------------------ apply / save
    def changed(self, live=True):
        if self._loading or not self.slug:
            return
        self.lbl_saved.setText(_("modified…"))
        self.save_timer.start()
        if live:
            self.schedule_live()

    def schedule_live(self):
        if self.chk_live.isChecked():
            self.live_timer.start()

    def save_now(self):
        self.save_timer.stop()
        if self.slug and not self._loading:
            try:
                profiles.save(self.slug, self.profile)
                self.lbl_saved.setText(_("saved"))
            except (OSError, profiles.ProfileError) as e:
                self.lbl_saved.setText(_("save failed"))
                self.statusBar().showMessage(str(e), 8000)

    def _daemon(self, method, *args):
        """Calls the service. Returns None when it isn't there."""
        if not engine.daemon_running():
            return None
        try:
            return bool(engine.daemon_call(method, *args, timeout=25))
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(_("Service: %s") % e, 6000)
            return None

    def _engine(self):
        if self.direct_engine is None:
            self.direct_engine = engine.Engine(log=lambda m: None)
        return self.direct_engine

    def _direct_apply(self, prof=None, power=False, force=False):
        try:
            self._engine().apply(prof or self.profile, power=power, force=force,
                                 backend=self.cfg["chassis_backend"])
            return True
        except hw.DeviceError as e:
            self.statusBar().showMessage(_("Error: %s") % e, 8000)
            return False

    def push_live(self):
        if not self.slug:
            return
        payload = json.dumps(self.profile, ensure_ascii=False)
        ok = self._daemon("Preview", payload)
        if ok is None:
            ok = self._direct_apply(power=False)
        else:
            self.preview_sent = True
        if ok is False:
            self.statusBar().showMessage(_("Couldn't apply (see the Options tab)"), 5000)

    def apply_now(self):
        self.save_now()
        is_active = self.slug == profiles.active_slug()
        ok = self._daemon("Reload" if is_active else "ApplyProfile", *([] if is_active else [self.slug]))
        if ok is None:
            ok = self._direct_apply(power=is_active, force=True)
        else:
            self.preview_sent = not is_active
        msg = _("Applied") if ok else _("Couldn't apply (the service will try again)")
        if ok and not is_active:
            msg += _("; not the active profile, so the active one comes back when you close")
        self.statusBar().showMessage(msg, 5000)

    def closeEvent(self, ev):
        self.save_now()
        self.anim_timer.stop()
        if engine.daemon_running():
            try:
                engine.daemon_call("EndPreview", timeout=10)
            except Exception:  # noqa: BLE001
                pass
        elif self.slug != profiles.active_slug():
            slug = profiles.active_slug()
            if slug:
                self._direct_apply(profiles.load(slug), force=True)
        if self.direct_engine:
            self.direct_engine.close()
        super().closeEvent(ev)


def main(argv=None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("alien-thunder")
    app.setWindowIcon(app_icon())
    w = MainWindow()
    w.show()
    return app.exec()
