Name:           alien-thunder
Version:        1.3.0
Release:        1%{?dist}
Summary:        Per-key RGB, G-Mode and fan and temperature readouts for Alienware laptops
License:        MIT
URL:            https://github.com/cryptoconspiracy/alien-thunder
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  gettext
BuildRequires:  python3
BuildRequires:  systemd-rpm-macros

Requires:       python3
%if 0%{?suse_version}
# openSUSE names Python packages after the interpreter version (python313-...).
BuildRequires:  hicolor-icon-theme
Requires:       %{primary_python}-pyside6
Requires:       %{primary_python}-dbus-python
Requires:       %{primary_python}-gobject
Requires:       typelib-1_0-GUdev-1_0
Requires:       layer-shell-qt6
Requires:       hicolor-icon-theme
Recommends:     libksysguard6-imports
Recommends:     libksysguard6-plugins
%else
Requires:       python3-dbus
Requires:       python3-pyside6
Requires:       python3-gobject
Requires:       libgudev
Requires:       layer-shell-qt
Recommends:     libksysguard
%endif
Recommends:     power-profiles-daemon
Recommends:     plasma-workspace

%description
Alien Thunder brings the Alienware Command Center bits Linux lacks to KDE Plasma:
per-key keyboard lighting with profiles and effects that keep your colors, the
touchpad, alien head and power button lights, G-Mode on Fn+F1, and CPU/GPU
temperature, fan speed and memory readouts on the panel and in a bar that floats
above every window. After installing, each user runs "alien-thunder setup" once.

%prep
%autosetup -n %{name}-%{version}

%build
make locales

%check
make check

%install
make PREFIX=%{_prefix} DESTDIR=%{buildroot} install
rm -f %{buildroot}%{_datadir}/licenses/%{name}/LICENSE

%post
%udev_rules_update

%postun
%udev_rules_update

%files
%license LICENSE
%doc README.md
%{_bindir}/alien-thunder
%{_mandir}/man1/alien-thunder.1*
%{_datadir}/alien-thunder/
%{_userunitdir}/alien-thunder.service
%{_userunitdir}/alien-thunder-overlay.service
%{_udevrulesdir}/70-alien-thunder.rules
%{_datadir}/applications/alien-thunder.desktop
%{_datadir}/metainfo/io.github.cryptoconspiracy.AlienThunder.metainfo.xml
%{_datadir}/icons/hicolor/*/apps/alien-thunder.png
%dir %{_datadir}/plasma
%dir %{_datadir}/plasma/plasmoids
%{_datadir}/plasma/plasmoids/alien-thunder/
%{_datadir}/plasma/plasmoids/alien-thunder-network/

%changelog
* Wed Oct 14 2026 Dan B <unknown@cryptoconspiracy.io> - 1.3.0-1
- Add configurable desktop and panel gauges with smoothed network overlays
- packages/: on Arch, install the downloaded file, since pacman wants a trusted signature for a URL

* Fri Oct 02 2026 Dan B <unknown@cryptoconspiracy.io> - 1.2.2-1
- packages/: a package to download for each distribution, versioned, and openSUSE Leap 16.0
- Debian policy: lintian-clean package, a man page, and the app in /usr/share

* Mon Sep 28 2026 Dan B <unknown@cryptoconspiracy.io> - 1.2.1-1
- AppStream metadata, so GNOME Software and KDE Discover list the app
- make release: publish a version to GitHub, OBS and the AUR from this machine

* Mon Sep 28 2026 Dan B <unknown@cryptoconspiracy.io> - 1.2.0-1
- CPU load, VRAM in use and RAM in GB; choose the readings for the panel and the overlay

* Sat Sep 26 2026 Dan B <unknown@cryptoconspiracy.io> - 1.1.2-1
- The overlay no longer crashes every few minutes

* Fri Sep 25 2026 Dan B <unknown@cryptoconspiracy.io> - 1.1.1-1
- First package
