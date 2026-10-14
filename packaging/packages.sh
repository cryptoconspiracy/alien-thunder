#!/bin/bash
# Waits for the OBS builds of VERSION, copies them into packages/VERSION/, one file per
# distribution with the distribution in its name, and writes the install page.
#
#   packaging/packages.sh 0.4.0            fills packages/0.4.0
#   packaging/packages.sh --commit 0.4.0   and commits and pushes it (make packages VERSION=0.4.0)
#
# release.sh runs it after uploading to OBS; run it by hand to resume a release that
# stopped before this step. OBS keeps only the latest build, so an older version can't be
# filled in. The files are the same ones the OBS repositories serve, signed by OBS.

set -euo pipefail

commit=0
[[ ${1:-} == --commit ]] && { commit=1; shift; }
version=${1:?usage: packaging/packages.sh [--commit] VERSION}
pkg=alien-thunder
name="Alien Thunder"
gh_repo=cryptoconspiracy/alien-thunder
obs_prj=home:cryptoconspiracy
osc=(osc -A https://api.opensuse.org)
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
out=$repo/packages/$version
raw=https://github.com/$gh_repo/raw/main/packages/$version

# What to do after installing, shown at the end of the page
then="Run \`alien-thunder setup\` once, as your own user (not root): it turns the service on, puts the widget on the panel and tells you if anything is missing. Fn+F1 needs your user in the \`input\` group: \`sudo usermod -aG input \$USER\`, then log out and back in."

# OBS repository, the label in file names, the name people know, the package format
distros=(
  "Fedora_44|fedora44|Fedora 44|rpm"
  "Fedora_43|fedora43|Fedora 43|rpm"
  "openSUSE_Tumbleweed|opensuse-tumbleweed|openSUSE Tumbleweed and Slowroll|rpm"
  "openSUSE_Leap_16.0|opensuse-leap16.0|openSUSE Leap 16.0|rpm"
  "Debian_13|debian13|Debian 13 (trixie)|deb"
  "Debian_12|debian12|Debian 12 (bookworm)|deb"
  "xUbuntu_26.04|ubuntu26.04|Ubuntu 26.04, Kubuntu 26.04 and their flavours|deb"
  "xUbuntu_25.10|ubuntu25.10|Ubuntu 25.10, Kubuntu 25.10 and their flavours|deb"
  "xUbuntu_24.04|ubuntu24.04|Ubuntu 24.04 LTS, Linux Mint 22, Pop!_OS 24.04, Zorin OS 18 and other flavours|deb"
  "xUbuntu_22.04|ubuntu22.04|Ubuntu 22.04 LTS, Linux Mint 21, Pop!_OS 22.04, Zorin OS 17 and other flavours|deb"
  "Arch|arch|Arch Linux, Garuda, Manjaro, EndeavourOS, CachyOS|pkg.tar.zst"
)

fail() { echo "packages: $*" >&2; exit 1; }
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "VERSION must look like 1.2.3"

# One line per repository: name and state. "finished" with "succeeded" in its details
# counts as built: the files can be downloaded already, and OBS can sit on "finished" for
# hours before it says "succeeded". A repository whose last build is still an older
# version is waiting too, since right after an upload OBS shows the previous result.
obs_states() {
  "${osc[@]}" api "/build/$obs_prj/_result?package=$pkg" | python3 -I -c '
import sys, xml.etree.ElementTree as ET
for r in ET.parse(sys.stdin).getroot():
    s = r.find("status")
    code = s.get("code") if s is not None else "unknown"
    details = (s.findtext("details") or "") if s is not None else ""
    if code == "finished":
        code = details.split()[0] if details else "finished"
    print(r.get("repository"), code)'
}
# The repositories whose binaries are already VERSION, from one listing of all of them.
with_version() {
  "${osc[@]}" ls -b "$obs_prj" "$pkg" 2>/dev/null \
    | awk -v re="^ ${pkg}[-_]${version//./[.]}-" '/^[^ ]/ { r = $0; sub("/.*", "", r) } $0 ~ re { print r }' | sort -u
}

echo "packages: waiting for the OBS builds of $version"
for ((i = 0; ; i++)); do
  ((i < 180)) || fail "OBS still building after an hour: ${osc[*]} results $obs_prj $pkg"
  pending=()
  enabled=()
  ready=" $(with_version | tr '\n' ' ') "
  while read -r obs code; do
    case $code in
      disabled|excluded) ;;
      failed|unresolvable|broken) fail "the $obs build $code: ${osc[*]} buildlog $obs_prj $pkg $obs x86_64" ;;
      succeeded) enabled+=("$obs"); [[ $ready == *" $obs "* ]] || pending+=("$obs") ;;
      *) enabled+=("$obs"); pending+=("$obs") ;;
    esac
  done < <(obs_states)
  ((${#pending[@]})) || break
  ((i % 6)) || echo "  still waiting for: ${pending[*]}"
  sleep 20
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
rm -rf "$out"
mkdir -p "$out"

built=()
for d in "${distros[@]}"; do
  IFS='|' read -r obs label _ fmt <<<"$d"
  # A distribution the package doesn't build for (too old, a library it lacks) is disabled
  # in OBS and left out; one that builds and still has no file here stops the release.
  [[ " ${enabled[*]} " == *" $obs "* ]] || continue
  "${osc[@]}" getbinaries -q -d "$work/$obs" "$obs_prj" "$pkg" "$obs" x86_64 >/dev/null
  case $fmt in
    rpm) src=$(ls "$work/$obs"/$pkg-"$version"-*.rpm 2>/dev/null | grep -v '\.src\.rpm$' || true) ;;
    deb) src=$(ls "$work/$obs"/${pkg}_"$version"-*_*.deb 2>/dev/null || true) ;;
    *) src=$(ls "$work/$obs"/$pkg-"$version"-*.pkg.tar.zst 2>/dev/null || true) ;;
  esac
  [[ -n $src ]] || fail "OBS built $obs but no $version file came down"
  [[ $(wc -l <<<"$src") == 1 && -f $src ]] || fail "more than one $version build for $obs"
  built+=("$d")
  arch=$(basename "$src" | grep -oE '(noarch|all|any|x86_64|amd64)' | tail -1)
  cp "$src" "$out/$pkg-$version-$label.$arch.$fmt"
done
(cd "$out" && sha256sum -- * > SHA256SUMS)

file_for() { (cd "$out" && ls -- "$pkg-$version-$1".*); }

{
  cat <<EOF
# $name $version: install

Pick your Linux. Download its package and open it: your software center (GNOME Software,
KDE Discover, the Ubuntu App Center, Mint's Software Manager) installs it with the missing
pieces from your distribution. Or paste the block below it into a terminal, which does the
same.

These packages don't update themselves. To get new versions with your system updates,
add the repository instead: see [Install](../../README.md#install) in the README.

EOF
  for d in "${built[@]}"; do
    IFS='|' read -r _ label title fmt <<<"$d"
    f=$(file_for "$label")
    echo "## $title"
    echo
    [[ $fmt == pkg.tar.zst ]] || { echo "[Download $f]($raw/$f)"; echo; }
    echo '```sh'
    case $fmt in
      rpm) [[ $label == fedora* ]] && echo "sudo dnf install $raw/$f" || echo "sudo zypper --no-gpg-checks install $raw/$f" ;;
      deb) printf 'cd /tmp && curl -fLO %s/%s\nsudo apt install ./%s\n' "$raw" "$f" "$f" ;;
      # From a URL pacman insists on a signature from a trusted key; a local file doesn't.
      *) printf 'cd /tmp && curl -fLO %s/%s\nsudo pacman -U ./%s\n' "$raw" "$f" "$f" ;;
    esac
    echo '```'
    echo
  done
  echo "## Then"
  echo
  echo "$then"
  echo
  echo "## Checking the files"
  echo
  echo "\`SHA256SUMS\` lists every file's checksum: \`sha256sum -c SHA256SUMS\` in this folder."
} > "$out/README.md"

# packages/README.md always shows the newest version
latest=$(ls "$repo/packages" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
sed "s|(../../README.md#install)|(../README.md#install)|; s|^# $name .*: install|# $name $latest: install|" \
  "$repo/packages/$latest/README.md" > "$repo/packages/README.md"
# Every repository OBS builds must be in the folder; the distros list above needs a line
# for a repository added to OBS.
((${#built[@]} == ${#enabled[@]})) || fail "OBS builds ${enabled[*]} but packages/$version has ${#built[@]} files; add the missing ones to distros"
(cd "$out" && sha256sum -c --quiet SHA256SUMS)
echo "packages/$version:"
ls "$out"

if ((commit)); then
  cd "$repo"
  git add packages
  git commit -q -m "Packages: $version"
  git push -q origin main
  echo "packages: committed and pushed"
fi
