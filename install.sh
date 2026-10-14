#!/bin/bash

# Installs Alien Thunder for the current user, no sudo unless packages are missing,
# and it asks first. The command links to this checkout, so a git pull updates it.
# Plasma only loads widgets installed through kpackagetool6, so the widget is copied
# again on every run.
#
#   ./install.sh            ask before installing packages, run the tests
#   ./install.sh --yes      don't ask
#   ./install.sh --no-test  skip the tests

set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
bin=${XDG_BIN_HOME:-$HOME/.local/bin}
data=${XDG_DATA_HOME:-$HOME/.local/share}
units=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user

assume_yes=false
run_tests=true
for arg in "$@"; do
  case $arg in
    --yes) assume_yes=true ;;
    --no-test) run_tests=false ;;
  esac
done

confirm() {
  $assume_yes && return 0
  [[ -t 0 ]] || return 1
  read -rp "$1 [Y/n] " answer
  [[ ${answer,,} != n* ]]
}

# The system Python on purpose: PySide6, dbus and gobject come from the distribution.
missing=()
/usr/bin/python3 -c "import PySide6.QtWidgets, PySide6.QtQml" 2>/dev/null || missing+=(pyside6)
/usr/bin/python3 -c "import dbus" 2>/dev/null || missing+=(python-dbus)
/usr/bin/python3 -c "import gi; gi.require_version('Gio', '2.0')" 2>/dev/null || missing+=(python-gobject)
[[ -d /usr/lib/qt6/qml/org/kde/layershell ]] || missing+=(layer-shell-qt)
command -v msgfmt >/dev/null || missing+=(gettext)
if ((${#missing[@]})); then
  if command -v pacman >/dev/null; then
    echo "Alien Thunder needs: ${missing[*]}"
    echo "  sudo pacman -S --needed ${missing[*]}"
    confirm "Install them now?" && sudo pacman -S --needed --noconfirm "${missing[@]}" || {
      echo "Run that command and then ./install.sh again." >&2
      exit 1
    }
  else
    echo "Alien Thunder needs these (Arch package names): ${missing[*]}" >&2
    echo "Install your distribution's equivalents and run this again." >&2
    exit 1
  fi
fi
command -v powerprofilesctl >/dev/null ||
  echo "Note: G-Mode switches the power profile through power-profiles-daemon, which isn't installed."

if $run_tests; then
  echo ">> tests"
  (cd "$repo" && /usr/bin/python3 -m unittest discover -s tests -q)
fi

# Leftovers from earlier versions: AlienFX Studio, and the copy the old installer
# made in ~/.local/share. Profiles and settings are kept; the app moves them itself.
if [[ -e $units/alienfx-studio.service || -d $data/alienfx-studio ]]; then
  echo ">> removing AlienFX Studio (profiles move to ~/.config/alien-thunder)"
  systemctl --user disable --now alienfx-studio.service 2>/dev/null || true
  rm -f "$units/alienfx-studio.service" "$bin/alienfx-studio" "$data/applications/alienfx-studio.desktop"
  rm -rf "$data/alienfx-studio"
fi
rm -rf "$data/alien-thunder"

echo ">> translations"
cp "$repo/plasma/alien-thunder-network/contents/ui/NetworkData.qml" "$repo/alien_thunder/"
for po in "$repo"/po/*/alien-thunder.po; do
  lang=$(basename "$(dirname "$po")")
  mkdir -p "$repo/alien_thunder/locale/$lang/LC_MESSAGES"
  msgfmt -o "$repo/alien_thunder/locale/$lang/LC_MESSAGES/alien-thunder.mo" "$po"
done

echo ">> command, icons and menu entry"
mkdir -p "$bin" "$data/applications"
ln -sfn "$repo/bin/alien-thunder" "$bin/alien-thunder"
for size in 16 22 24 32 48 64 128 256; do
  install -Dm644 "$repo/assets/icon-$size.png" "$data/icons/hicolor/${size}x${size}/apps/alien-thunder.png"
done
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$data/icons/hicolor" 2>/dev/null || true
sed "s|^Exec=alien-thunder|Exec=$bin/alien-thunder|" "$repo/data/alien-thunder.desktop" >"$data/applications/alien-thunder.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$data/applications" || true

echo ">> profiles"
"$bin/alien-thunder" list

echo ">> services"
mkdir -p "$units"
install -m644 "$repo/data/alien-thunder.service" "$repo/data/alien-thunder-overlay.service" "$units/"
if systemctl --user is-enabled -q alienfx-perfil.service 2>/dev/null; then
  echo "   turning off the old alienfx-perfil.service (replaced)"
  systemctl --user disable alienfx-perfil.service
fi
systemctl --user daemon-reload
systemctl --user restart alien-thunder.service 2>/dev/null || true
# The overlay is opt-in, from the panel widget; only restart it if it's already on.
systemctl --user is-active -q alien-thunder-overlay.service && systemctl --user restart alien-thunder-overlay.service

if command -v kpackagetool6 >/dev/null; then
  echo ">> panel and optional network widgets"
  widgets_changed=false
  for widget_id in alien-thunder alien-thunder-network; do
  widget=$repo/plasma/$widget_id
  if [[ $widget_id == alien-thunder-network ]]; then
    cp "$repo/plasma/alien-thunder/contents/ui/configSupport.qml" "$widget/contents/ui/"
    mkdir -p "$widget/contents/images"
    cp "$repo"/plasma/alien-thunder/contents/images/donate-*.png "$widget/contents/images/"
  fi
  cp "$repo/alien_thunder/AnalogDial.qml" "$repo/alien_thunder/AlertLed.qml" "$widget/contents/ui/"
  if [[ $widget_id == alien-thunder ]]; then
    cp "$repo/alien_thunder/BarContent.qml" "$repo/alien_thunder/NetworkData.qml" "$widget/contents/ui/"
  fi
  for po in "$repo"/po/*/plasma_applet_$widget_id.po; do
    lang=$(basename "$(dirname "$po")")
    mkdir -p "$widget/contents/locale/$lang/LC_MESSAGES"
    msgfmt -o "$widget/contents/locale/$lang/LC_MESSAGES/plasma_applet_$widget_id.mo" "$po"
  done
  installed=$data/plasma/plasmoids/$widget_id
  if [[ -d $installed ]]; then
    # kpackagetool6 --upgrade removes the widget before reinstalling it, and the
    # panel drops anything that disappears, even for a moment.
    diff -rq "$widget" "$installed" >/dev/null 2>&1 || widgets_changed=true
    cp -rT "$widget" "$installed"
  else
    kpackagetool6 --type Plasma/Applet --install "$widget" >/dev/null
  fi
  done
  # Loaded widgets need a single shell restart after both packages are copied.
  if $widgets_changed && systemctl --user is-active -q plasma-plasmashell.service; then
    echo "   restarting plasmashell so it picks up the updated widgets"
    systemctl --user restart plasma-plasmashell.service
  fi
fi

# The lighting controllers need a udev rule so the logged-in user can reach them.
rule=/etc/udev/rules.d/70-alien-thunder.rules
if ! cmp -s "$repo/data/70-alien-thunder.rules" "$rule" && [[ ! -e /usr/lib/udev/rules.d/70-alien-thunder.rules ]]; then
  echo ">> udev rule for the keyboard and chassis lighting"
  echo "  sudo install -m644 data/70-alien-thunder.rules $rule && sudo udevadm control --reload && sudo udevadm trigger"
  if confirm "Install it now?"; then
    sudo install -m644 "$repo/data/70-alien-thunder.rules" "$rule"
    sudo udevadm control --reload
    sudo udevadm trigger --subsystem-match=hidraw
  fi
fi

echo ">> your session"
"$bin/alien-thunder" setup || true

echo "Alien Thunder installed. Open the lighting editor from the menu or with: alien-thunder"
