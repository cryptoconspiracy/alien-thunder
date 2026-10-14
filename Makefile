# System-wide install, for distribution packages:  make && make DESTDIR=... install
# For a per-user install from this checkout, use ./install.sh instead.

PREFIX ?= /usr
DESTDIR ?=
LIBDIR = $(DESTDIR)$(PREFIX)/share/alien-thunder
SHARE = $(DESTDIR)$(PREFIX)/share
WIDGET = plasma/alien-thunder

LANGS = $(patsubst po/%/,%,$(wildcard po/*/))

all: locales

locales:
	cp plasma/alien-thunder-network/contents/ui/NetworkData.qml alien_thunder/
	cp alien_thunder/BarContent.qml alien_thunder/NetworkData.qml $(WIDGET)/contents/ui/
	cp $(WIDGET)/contents/ui/configSupport.qml plasma/alien-thunder-network/contents/ui/
	mkdir -p plasma/alien-thunder-network/contents/images
	cp $(WIDGET)/contents/images/donate-*.png plasma/alien-thunder-network/contents/images/
	for widget in alien-thunder alien-thunder-network; do \
	  cp alien_thunder/AnalogDial.qml alien_thunder/AlertLed.qml plasma/$$widget/contents/ui/; \
	done
	for lang in $(LANGS); do \
	  mkdir -p alien_thunder/locale/$$lang/LC_MESSAGES $(WIDGET)/contents/locale/$$lang/LC_MESSAGES; \
	  msgfmt -o alien_thunder/locale/$$lang/LC_MESSAGES/alien-thunder.mo po/$$lang/alien-thunder.po; \
	  msgfmt -o $(WIDGET)/contents/locale/$$lang/LC_MESSAGES/plasma_applet_alien-thunder.mo po/$$lang/plasma_applet_alien-thunder.po; \
	  mkdir -p plasma/alien-thunder-network/contents/locale/$$lang/LC_MESSAGES; \
	  msgfmt -o plasma/alien-thunder-network/contents/locale/$$lang/LC_MESSAGES/plasma_applet_alien-thunder-network.mo po/$$lang/plasma_applet_alien-thunder-network.po; \
	done

check:
	/usr/bin/python3 -m unittest discover -s tests -q

# Optional UI checks on a machine with Qt Quick Test and KDE's network collector.
check-qml: locales
	QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software /usr/lib/qt6/bin/qmltestrunner -input tests/qml

install: locales
	install -d $(LIBDIR)
	cp -r alien_thunder $(LIBDIR)/
	find $(LIBDIR) -name __pycache__ -type d -prune -exec rm -rf {} +
	install -Dm755 bin/alien-thunder $(DESTDIR)$(PREFIX)/bin/alien-thunder
	for unit in alien-thunder alien-thunder-overlay; do \
	  sed 's|%h/.local/bin/alien-thunder|$(PREFIX)/bin/alien-thunder|' data/$$unit.service \
	    | install -Dm644 /dev/stdin $(DESTDIR)$(PREFIX)/lib/systemd/user/$$unit.service; \
	done
	install -Dm644 data/70-alien-thunder.rules $(DESTDIR)$(PREFIX)/lib/udev/rules.d/70-alien-thunder.rules
	install -Dm644 data/alien-thunder.desktop $(SHARE)/applications/alien-thunder.desktop
	install -Dm644 data/io.github.cryptoconspiracy.AlienThunder.metainfo.xml $(SHARE)/metainfo/io.github.cryptoconspiracy.AlienThunder.metainfo.xml
	for size in 16 22 24 32 48 64 128 256; do \
	  install -Dm644 assets/icon-$$size.png $(SHARE)/icons/hicolor/$${size}x$${size}/apps/alien-thunder.png; \
	done
	install -d $(SHARE)/plasma/plasmoids
	cp -r $(WIDGET) $(SHARE)/plasma/plasmoids/
	cp -r plasma/alien-thunder-network $(SHARE)/plasma/plasmoids/
	install -Dm644 data/alien-thunder.1 $(SHARE)/man/man1/alien-thunder.1
	install -Dm644 LICENSE $(SHARE)/licenses/alien-thunder/LICENSE

# Publishes VERSION to GitHub, the OBS repositories and (once there's an account) the AUR.
release:
	@test -n "$(VERSION)" || { echo "usage: make release VERSION=1.2.3 [DRY_RUN=1]"; exit 1; }
	DRY_RUN=$(DRY_RUN) packaging/release.sh $(VERSION)

# The last step of a release on its own, to resume one that stopped while OBS was building.
packages:
	@test -n "$(VERSION)" || { echo "usage: make packages VERSION=1.2.3"; exit 1; }
	packaging/packages.sh --commit $(VERSION)

.PHONY: all locales check check-qml install release packages
