<p align="center"><img src="assets/icon-256.png" width="160" alt="Alien Thunder"></p>

<h1 align="center">Alien Thunder</h1>

<p align="center"><b>The Alienware Command Center bits you miss on Linux: per-key lighting, the G-Mode key, and live temperatures and fan speeds, on your panel and floating over your games.</b></p>

---

## The problem

On Windows, Alienware laptops come with the Alienware Command Center. On Linux you
get none of it: the keyboard lights stay whatever color they were, the turbo key
(Fn+F1, G-Mode) does nothing, and there's no quick way to see how hot the CPU is or
how fast the fans are spinning.

## What Alien Thunder does

- **Lighting.** Color every key on its own, light the touchpad, the alien head on the lid
  and the power button, and save it all as profiles. Your profile comes back at login,
  after suspend and when the keyboard reconnects.
- **Effects that keep your colors.** Breathing, pulse, wave and twinkle only change how
  bright each light is, never its color. Keyboard, touchpad and alien head each get
  their own effect and speed.
- **G-Mode.** Fn+F1 works again: fans at full speed and the performance power profile,
  and the F1 key turns white while it's on, like on Windows.
- **Music keys.** The editor's **Keys** tab records Fn+F3 to Fn+F6 and assigns previous,
  stop, play/pause or next to each key, saved with the profile. Previous restarts a
  track after its first three seconds; press again right away to go back a track.
  The service controls MPRIS players, including browsers, and needs the same `input`
  group access as Fn+F1. In Brave, restarting a track also needs the Plasma Integration
  browser extension enabled.
- **Readouts on the panel.** CPU and GPU temperature, CPU load, GPU memory (VRAM) in use,
  both fan speeds and memory in use (in % and in GB), right next to the system tray and
  the clock. You pick which ones in the widget's settings.
- **Overlay.** The same readouts in a small bar that floats above every window, games
  in fullscreen included. Drag it anywhere, on any screen; its ✕ puts it away.
- **Optional network widget.** **Alien Thunder · Network** shows upload and download
  by application on the desktop, updated every two seconds, with a 90-second graph
  behind the application list and animated download/upload speedometers in fluorescent
  orange. A blinking red LED marks traffic at or above 90% of that direction's observed
  peak over those 90 seconds, not the connection's capacity. Each dial displays its automatic scale,
  based on the peak traffic in the graph.
  Enable or disable it with **Network widget** in the panel popup, or run
  `alien-thunder network on` / `alien-thunder network off`. It is also available in
  Plasma's **Add Widgets** list. Sort by either direction and optionally show idle
  applications. Plasma remembers its position and settings across logins.
  Right-click the network widget and choose **Configure Alien Thunder · Network**
  for its own settings: digital/analog style (or follow Alien Thunder), sorting,
  idle applications, the background graph and blinking alerts. These preferences
  apply only to that network widget.
  Its **Support** tab also includes the Bitcoin and EVM donation wallets, QR codes
  and copy buttons, shared with the main widget.
  It uses KDE System Monitor's `org.kde.ksysguard.process` module and
  `ksgrd_network_helper` (from libksysguard), including TCP and UDP; the helper needs
  the distribution's normal `CAP_NET_RAW` capability. The totals cover the listed
  application groups, not every packet on every interface. Processes started from
  a terminal can appear under that terminal, following KDE's application grouping.

## How it looks

### On your panel

<p align="center"><img src="assets/screenshots/panel.png" alt="Alien Thunder on the panel, next to the system tray"></p>

The icon gets a white **G** while G-Mode is on. Temperatures turn yellow at 75 °C and red
at 90 °C. Hover for a summary; click for the rest.

### Click it

<p align="center"><img src="assets/screenshots/popup.png" width="420" alt="Alien Thunder's panel popup"></p>

G-Mode and the overlay are one switch each. **Lighting** opens the lighting editor.

### The overlay

<p align="center"><img src="assets/screenshots/overlay.png" width="640" alt="The readout bar"></p>

Grab the bar anywhere and drop it where you like, on either screen; it remembers the
spot. The ✕ at its end turns the overlay off, and the switch on the panel brings it
back. Untick a reading in the panel popup and the bar gets shorter.
Drag the small triangle in its bottom-right corner to resize the entire bar, including
the text. The percentage appears while dragging; release to apply. The size is saved
across restarts and limited to the current screen. The bar briefly recreates its window
when applying a size to keep layer-shell stable.
The panel popup and **General** settings also provide an **Overlay size** slider
from 50% to 250%, with a reset to 100%.

In **Alien Thunder settings → General → Overlay and network gauges**, choose **Digital**
or **Analog · Audi style**. This one setting changes every reading in the floating bar
and both network totals. The analog style uses dark round dials, white graduations and
red needles with fluorescent orange accents, with the exact reading below. You can also switch styles from the overlay
section of the panel popup. **General → Panel gauge style** independently chooses
digital readings or compact analog dials for the taskbar. **Show on the panel**
selects each sensor plus download and upload; network indicators use the same
ten-second moving average. Compact dials keep the exact value beside the needle.
CPU load, VRAM and RAM readings show a blinking red LED above 90% usage.

Turn on **Desktop gauges** in the panel popup (or run `alien-thunder desktop on`)
to add the gauges to your desktop; turn it off with the same switch or
`alien-thunder desktop off`. Plasma saves their position and size. You can also
add **Alien Thunder** through Plasma's **Add Widgets** to use the same digital or
analog readings on the desktop. **General → Show on the desktop** selects readings
independently for each widget, without changing the panel or floating bar. Choose
**Desktop gauge style** for its own analog or digital display. **Desktop orientation**
chooses a horizontal strip (the default, like the overlay) or a vertical stack.
Resizing in Plasma's edit mode scales the whole strip. Download and upload
can be included in this desktop bar too.

Select **Download** and **Upload** under **Show in the overlay** to put network
gauges in the floating bar, in either digital or analog style. The network widget
has these switches too; selecting one there also turns the overlay on. From the
terminal, use `alien-thunder overlay show download` (or `upload`), then
`alien-thunder overlay on`. Network readings use the same application totals and
90-second automatic scale as the desktop network widget, independently of whether
that widget is open. They are off by default and require KDE's network collector.
All network gauges use a moving average of the last ten seconds (five samples),
including their numeric readings. Scale and peak alerts follow these smoothed
values. The application list and its graph keep the original two-second readings.

### The lighting editor

<p align="center"><img src="assets/screenshots/editor.png" alt="The lighting editor"></p>

Click keys to select them (Ctrl+click toggles, drag selects an area), pick a color, and
the keyboard changes as you edit.

<p align="center"><img src="assets/screenshots/effects.png" width="360" alt="The Effects tab"></p>

The **Effects** tab has one effect and one speed for the keyboard, one for the touchpad
and one for the alien head; the background service draws them, and they only dim and
brighten the colors you picked. **Import from Windows** reads the
presets you made in the Alienware Command Center, if your Windows partition is
mounted at `/mnt/windows`; it only reads, it never writes there.

## Install

### Download a package

Open the [**packages**](packages/) folder, find your Linux, download the file and open
it with your software center, or paste the line under it into a terminal. There are
packages for Fedora 43 and 44, openSUSE Tumbleweed and Leap 16.0, Debian 13, Ubuntu
25.10 and 26.04, and Arch with the systems built on it. Older Ubuntu and Debian releases
lack PySide6 and the Plasma 6 pieces Alien Thunder needs.

After installing, run `alien-thunder setup` once as your own user (not root): it turns
the service on, puts the widget next to the system tray and tells you if anything is
missing.

### From the repository, with updates

A downloaded package stays at its version. The signed repository on the openSUSE Build
Service brings new versions with your system updates.

**Fedora 43 and 44**

```bash
sudo dnf config-manager addrepo --from-repofile=https://download.opensuse.org/repositories/home:/cryptoconspiracy/Fedora_$(rpm -E %fedora)/home:cryptoconspiracy.repo
sudo dnf install alien-thunder
```

**openSUSE Tumbleweed and Leap 16.0**: set `repo` to `openSUSE_Tumbleweed` or `openSUSE_Leap_16.0`.

```bash
repo=openSUSE_Tumbleweed
sudo zypper addrepo -f https://download.opensuse.org/repositories/home:/cryptoconspiracy/$repo/home:cryptoconspiracy.repo
sudo zypper install alien-thunder
```

**Debian 13, Ubuntu 25.10 and 26.04**: set `repo` to `Debian_13`, `xUbuntu_25.10` or `xUbuntu_26.04`.

```bash
repo=Debian_13
curl -fsSL https://download.opensuse.org/repositories/home:/cryptoconspiracy/$repo/Release.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/alien-thunder.gpg >/dev/null
echo "deb https://download.opensuse.org/repositories/home:/cryptoconspiracy/$repo/ /" | sudo tee /etc/apt/sources.list.d/alien-thunder.list
sudo apt update && sudo apt install alien-thunder
```

**Arch and Arch-based**: the AUR package follows when AUR registration reopens; until then, the signed repository:

```bash
curl -fsSL https://download.opensuse.org/repositories/home:/cryptoconspiracy/Fedora_44/repodata/repomd.xml.key | sudo pacman-key --add -
sudo pacman-key --lsign-key 72E3A26E8377B7E2BFB5E9F1ADD09EAE97167CA4
printf '[home_cryptoconspiracy_Arch]\nServer = https://download.opensuse.org/repositories/home:/cryptoconspiracy/Arch/$arch\n' | sudo tee -a /etc/pacman.conf
sudo pacman -Sy alien-thunder
```

Fn+F1 needs your user in the `input` group: `sudo usermod -aG input $USER`, then log out and back in.

### From source

```bash
git clone https://github.com/cryptoconspiracy/alien-thunder.git
cd alien-thunder
./install.sh
```

Nothing needs root. If a package is missing (PySide6, python-dbus, python-gobject,
layer-shell-qt, gettext), the installer says which and asks before installing it. It
puts the widget on your panel right before the system tray, starts the background
service, and adds **Alien Thunder** to the app menu.

The installer also offers to add a udev rule (it needs your password once) so your
user can reach the lighting controllers, and Fn+F1 needs your user in the `input` group;
`alien-thunder setup` tells you if either is missing.

### Packagers

`make && make DESTDIR=... install` puts everything under `/usr`: the app, the panel
widget, the user services, the udev rule and the icons. Each user then runs
`alien-thunder setup` once, which turns the service on and puts the widget on the panel.

### Releasing (maintainers)

`make release VERSION=1.2.3` bumps the version everywhere, tags it, publishes the GitHub
release with the widget, updates the AUR recipe and the openSUSE Build Service packages,
waits for the builds, and copies them into `packages/VERSION` for the download page.
`DRY_RUN=1` does it all in a throwaway clone without publishing.

### Updating

```bash
git pull && ./install.sh
```

### Removing

```bash
./uninstall.sh
```

Your lighting profiles stay in `~/.config/alien-thunder`.

## Will it work on my computer?

It was built on, and has only been tested on, an **Alienware m16 R2 with the Brazilian
(ABNT2) keyboard**, on Arch-based Linux with **KDE Plasma 6 on Wayland**.

- **Lighting** talks to two USB devices: the keyboard (0d62:d2b1) and the AW-ELC
  chassis controller (187c:0551). Other Alienware laptops with those same controllers
  may work; the key map is the ABNT2 one.
- **G-Mode** relies on the kernel's `alienware-wmi` driver, which turns G-Mode on when
  the power profile goes to *performance*, and on power-profiles-daemon. The key is
  read from `/dev/input`, so your user has to be in the `input` group.
- **Temperatures and fans** come from `alienware_wmi` and `coretemp`. The GPU reading is
  the laptop's embedded controller, not the NVIDIA driver, so checking it every two
  seconds doesn't wake a sleeping GPU.
- **The overlay** needs a Wayland compositor with the layer-shell protocol (KWin has it).
- **The panel widget** needs KDE Plasma 6.

## Language

Alien Thunder is in English and Brazilian Portuguese, and follows your system's
language. If your system is set to Portuguese but that locale isn't generated, KDE
falls back to English, and so does Alien Thunder, so the two always match.

## For the curious: the command line

```text
alien-thunder                    open the lighting editor
alien-thunder list               list the profiles (* = active)
alien-thunder set <profile>      make a profile the active one and apply it
alien-thunder status             service and device status
alien-thunder gmode [on|off|toggle]
alien-thunder overlay [on|off|show ITEM|hide ITEM|status]
```

`ITEM` is one of `cpu_temp`, `gpu_temp`, `cpu_fan`, `gpu_fan`, `ram`.

## What's new

### 1.2

- CPU load, GPU memory (VRAM) in use and RAM in GB, on the panel and in the overlay.
  VRAM is only read while the NVIDIA GPU is already awake, so it never wakes one that
  is sleeping.
- The widget's settings choose the readings for the panel and for the overlay.
- The overlay no longer closes by itself (1.1.2).

### 1.1

- Now called Alien Thunder (it was AlienFX Studio). Profiles move over by themselves.
- G-Mode on Fn+F1, with the white F1 key.
- Effects for the keyboard, the touchpad and the alien head, each on its own, and none
  of them changes your colors. The effects that did (rainbow, spectrum, the keyboard's
  hardware effects) are gone; saved profiles switch to the closest one that keeps colors.
- Temperatures, fan speeds and memory on the panel, and the floating readout bar.
- English and Brazilian Portuguese.

## Support the project

Alien Thunder is free and stays free. If it saved you from booting into Windows just to
change your keyboard colors, a donation keeps it going.

<table align="center"><tr>
<td align="center"><b>Bitcoin</b><br><img src="assets/donate/btc.png" width="180" alt="Bitcoin donation QR code"></td>
<td align="center"><b>EVM networks</b><br><img src="assets/donate/evm.png" width="180" alt="EVM donation QR code"></td>
</tr></table>

Scan a code, or copy the address with the button at the right of its box.

**Bitcoin**

```text
bc1q2nqp9d8lc0u6z7v9ag4u52sv9g9afepgyyrwu4
```

**EVM networks**: the same address on Ethereum, Optimism, BNB Chain, Gnosis, Polygon,
Base, Arbitrum One, Avalanche and Unichain.

```text
0x930CD3e9de6F2dB03709667C9799d073b34FEaCc
```

The same codes are in the panel widget's settings, under **Support**, and above the keyboard in the lighting editor, each with a Copy button.

## Credits

- The lighting protocols come from [alienfx-tools](https://github.com/T-Troll/alienfx-tools)
  by T-Troll (MIT), and were checked byte for byte against alienrgb.
- The key layout comes from the Alienware Command Center's own drawing of the ABNT2 keyboard.
- G-Mode and the fan readings rely on the Linux kernel's `alienware-wmi` driver.
- The overlay uses KDE's [LayerShellQt](https://invent.kde.org/plasma/layer-shell-qt).

Made by Dan B. MIT license.
