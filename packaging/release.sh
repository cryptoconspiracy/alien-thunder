#!/bin/bash
# Publishes a new version everywhere, from this computer:
#
#   make release VERSION=1.2.1            bump, tag, GitHub release, AUR hash, OBS, packages/VERSION
#   make release VERSION=1.2.1 DRY_RUN=1  the same in a throwaway clone, nothing leaves the machine
#
# It uses the gh and osc logins of this machine; no password is stored anywhere else.
# The changelog is the list of commit subjects since the last tag.

set -euo pipefail

version=${1:?usage: packaging/release.sh VERSION}
dry=${DRY_RUN:-0}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
gh_repo=cryptoconspiracy/alien-thunder
obs_prj=home:cryptoconspiracy
obs_pkg=alien-thunder
osc=(osc -A https://api.opensuse.org)

step() { echo; echo ">> $*"; }
fail() { echo "release: $*" >&2; exit 1; }

[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "VERSION must look like 1.2.3"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [[ $dry == 1 ]]; then
  step "dry run: working in a throwaway clone"
  git clone -q "$repo" "$work/src"
  cd "$work/src"
else
  cd "$repo"
  [[ -z $(git status --porcelain) ]] || fail "uncommitted changes; commit or stash them first"
  [[ $(git branch --show-current) == main ]] || fail "not on main"
  git fetch -q origin
  [[ $(git rev-parse HEAD) == $(git rev-parse origin/main) ]] || fail "main differs from origin/main; pull or push first"
fi
git rev-parse -q --verify "refs/tags/v$version" >/dev/null && fail "tag v$version already exists"

step "tests"
make -s check

last=$(git describe --tags --abbrev=0 2>/dev/null || true)
mapfile -t changes < <(git log --no-merges --format=%s ${last:+"$last"..HEAD} | grep -vE '^(AUR package|Packages:|README|[0-9]+\.[0-9]+\.[0-9]+)' || true)
((${#changes[@]})) || changes=("Maintenance release")
today_rpm=$(LC_ALL=C date '+%a %b %d %Y')
today_deb=$(LC_ALL=C date -R)
author="Dan B <unknown@cryptoconspiracy.io>"

step "version $version in the app, the widget and the packages"
sed -i "s/^__version__ = \".*\"/__version__ = \"$version\"/" alien_thunder/__init__.py
sed -i "s/\"Version\": \"[^\"]*\"/\"Version\": \"$version\"/" plasma/*/metadata.json
sed -i "s/^Version:        .*/Version:        $version/" packaging/rpm/alien-thunder.spec
{
  printf '* %s %s - %s-1\n' "$today_rpm" "$author" "$version"
  printf -- '- %s\n' "${changes[@]}"
  echo
} > "$work/rpmlog"
sed -i "/^%changelog$/r $work/rpmlog" packaging/rpm/alien-thunder.spec
{
  printf 'alien-thunder (%s-1) unstable; urgency=medium\n\n' "$version"
  printf '  * %s\n' "${changes[@]}"
  printf '\n -- %s  %s\n\n' "$author" "$today_deb"
  cat packaging/debian/changelog
} > "$work/deblog"
cp "$work/deblog" packaging/debian/changelog
sed -i "s/^pkgver=.*/pkgver=$version/; s/^pkgrel=.*/pkgrel=1/" packaging/aur/PKGBUILD
# GNOME Software and Discover show the latest <release> as the version and its notes.
metainfo=data/io.github.cryptoconspiracy.AlienThunder.metainfo.xml
{
  printf '    <release version="%s" date="%s">\n      <description>\n        <ul>\n' "$version" "$(date +%F)"
  for c in "${changes[@]}"; do
    c=${c//&/&amp;}; c=${c//</&lt;}; c=${c//>/&gt;}
    printf '          <li>%s</li>\n' "$c"
  done
  printf '        </ul>\n      </description>\n    </release>\n'
} > "$work/release.xml"
sed -i "/<releases>/r $work/release.xml" "$metainfo"
appstreamcli validate --no-net "$metainfo" >/dev/null || fail "the AppStream file doesn't validate after adding the release"
git add -A
git commit -q -m "$version"
git tag -a "v$version" -m "Alien Thunder $version"

step "panel widget for the release and the KDE Store"
make -s locales
(cd plasma/alien-thunder && zip -qr "$work/alien-thunder-$version.plasmoid" .)
(cd plasma/alien-thunder-network && zip -qr "$work/alien-thunder-network-$version.plasmoid" .)
notes="$(printf -- '- %s\n' "${changes[@]}")

The two \`.plasmoid\` files are the sensor and network widgets for the KDE Store; they need the app installed."

if [[ $dry == 1 ]]; then
  git archive --prefix="alien-thunder-$version/" "v$version" | gzip -n > "$work/alien-thunder-$version.tar.gz"
  echo "   would push main and v$version, and publish a GitHub release with:"
  echo "$notes" | sed 's/^/     /'
else
  step "push and GitHub release"
  git push -q origin main "v$version"
  gh release create "v$version" "$work/alien-thunder-$version.plasmoid" "$work/alien-thunder-network-$version.plasmoid" --repo "$gh_repo" \
    --title "Alien Thunder $version" --notes "$notes" >/dev/null
  curl -fsSL -o "$work/alien-thunder-$version.tar.gz" \
    "https://github.com/$gh_repo/archive/refs/tags/v$version.tar.gz"
fi
sum=$(sha256sum "$work/alien-thunder-$version.tar.gz" | cut -d' ' -f1)

step "AUR recipe: checksum $sum"
sed -i "s/^sha256sums=('.*')/sha256sums=('$sum')/" packaging/aur/PKGBUILD
(cd packaging/aur && makepkg --printsrcinfo > .SRCINFO)
git add packaging/aur
git commit -q -m "AUR package: $version"
[[ $dry == 1 ]] || git push -q origin main

step "openSUSE Build Service ($obs_prj/$obs_pkg)"
(cd "$work" && "${osc[@]}" co "$obs_prj" "$obs_pkg" -o obs >/dev/null)
obs=$work/obs
for f in "$obs"/alien-thunder-*.tar.gz; do [[ -e $f ]] && (cd "$obs" && "${osc[@]}" rm "$(basename "$f")" >/dev/null); done
cp "$work/alien-thunder-$version.tar.gz" packaging/rpm/alien-thunder.spec packaging/aur/alien-thunder.install "$obs/"
# OBS builds offline from the files it holds, so the recipe points at the uploaded tarball.
sed 's|^source=(.*)|source=("$pkgname-$pkgver.tar.gz")|' packaging/aur/PKGBUILD > "$obs/PKGBUILD"
mkdir -p "$work/deb" && cp -r packaging/debian "$work/deb/debian" && rm -rf "$work/deb/debian/source"
tar -C "$work/deb" -czf "$obs/debian.tar.gz" debian
sed -i "s/^Version: .*/Version: $version-1/; s/^DEBTRANSFORM-TAR: .*/DEBTRANSFORM-TAR: alien-thunder-$version.tar.gz/" "$obs/alien-thunder.dsc"
(cd "$obs" && "${osc[@]}" add "alien-thunder-$version.tar.gz" >/dev/null && "${osc[@]}" status)
if [[ $dry == 1 ]]; then
  echo "   would commit the above to OBS"
else
  (cd "$obs" && "${osc[@]}" commit -m "alien-thunder $version" >/dev/null)
  step "waiting for the OBS builds"
  for _ in $(seq 1 120); do
    results=$("${osc[@]}" results "$obs_prj" "$obs_pkg")
    grep -qE 'building|scheduled|dispatching|finished|signing|blocked|\*|unknown' <<<"$results" || break
    sleep 20
  done
  echo "$results"
  grep -qE 'failed|unresolvable|broken' <<<"$results" && fail "an OBS build failed: ${osc[*]} buildlog $obs_prj $obs_pkg <repo> x86_64"

  step "packages/$version: the built packages, one per distribution, for people who'd rather download a file"
  packaging/packages.sh "$version"
  git add packages
  git commit -q -m "Packages: $version"
  git push -q origin main
fi

step "AUR"
if ssh -o BatchMode=yes -o ConnectTimeout=10 aur@aur.archlinux.org help >/dev/null 2>&1; then
  git clone -q ssh://aur@aur.archlinux.org/alien-thunder.git "$work/aur"
  cp packaging/aur/{PKGBUILD,.SRCINFO,alien-thunder.install} "$work/aur/"
  (cd "$work/aur" && git add -A && git commit -q -m "$version" && { [[ $dry == 1 ]] && echo "   would push to the AUR" || git push -q; })
else
  echo "   skipped: no AUR login on this machine yet"
fi

step "done"
echo "KDE Store: upload $work/alien-thunder-$version.plasmoid by hand at https://store.kde.org/product/add"
if [[ $dry != 1 ]]; then
  mkdir -p "$HOME/Downloads/alien-thunder-kde-store"
  cp "$work/alien-thunder-$version.plasmoid" "$HOME/Downloads/alien-thunder-kde-store/"
  cp "$work/alien-thunder-network-$version.plasmoid" "$HOME/Downloads/alien-thunder-kde-store/"
  echo "  (a copy is in ~/Downloads/alien-thunder-kde-store)"
fi
