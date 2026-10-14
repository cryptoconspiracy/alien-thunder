# Alien Thunder 1.3.1: install

Pick your Linux. Download its package and open it: your software center (GNOME Software,
KDE Discover, the Ubuntu App Center, Mint's Software Manager) installs it with the missing
pieces from your distribution. Or paste the block below it into a terminal, which does the
same.

These packages don't update themselves. To get new versions with your system updates,
add the repository instead: see [Install](../../README.md#install) in the README.

## Fedora 44

[Download alien-thunder-1.3.1-fedora44.noarch.rpm](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-fedora44.noarch.rpm)

```sh
sudo dnf install https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-fedora44.noarch.rpm
```

## Fedora 43

[Download alien-thunder-1.3.1-fedora43.noarch.rpm](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-fedora43.noarch.rpm)

```sh
sudo dnf install https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-fedora43.noarch.rpm
```

## openSUSE Tumbleweed and Slowroll

[Download alien-thunder-1.3.1-opensuse-tumbleweed.noarch.rpm](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-opensuse-tumbleweed.noarch.rpm)

```sh
sudo zypper --no-gpg-checks install https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-opensuse-tumbleweed.noarch.rpm
```

## openSUSE Leap 16.0

[Download alien-thunder-1.3.1-opensuse-leap16.0.noarch.rpm](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-opensuse-leap16.0.noarch.rpm)

```sh
sudo zypper --no-gpg-checks install https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-opensuse-leap16.0.noarch.rpm
```

## Debian 13 (trixie)

[Download alien-thunder-1.3.1-debian13.all.deb](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-debian13.all.deb)

```sh
cd /tmp && curl -fLO https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-debian13.all.deb
sudo apt install ./alien-thunder-1.3.1-debian13.all.deb
```

## Ubuntu 26.04, Kubuntu 26.04 and their flavours

[Download alien-thunder-1.3.1-ubuntu26.04.all.deb](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-ubuntu26.04.all.deb)

```sh
cd /tmp && curl -fLO https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-ubuntu26.04.all.deb
sudo apt install ./alien-thunder-1.3.1-ubuntu26.04.all.deb
```

## Ubuntu 25.10, Kubuntu 25.10 and their flavours

[Download alien-thunder-1.3.1-ubuntu25.10.all.deb](https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-ubuntu25.10.all.deb)

```sh
cd /tmp && curl -fLO https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-ubuntu25.10.all.deb
sudo apt install ./alien-thunder-1.3.1-ubuntu25.10.all.deb
```

## Arch Linux, Garuda, Manjaro, EndeavourOS, CachyOS

```sh
cd /tmp && curl -fLO https://github.com/cryptoconspiracy/alien-thunder/raw/main/packages/1.3.1/alien-thunder-1.3.1-arch.any.pkg.tar.zst
sudo pacman -U ./alien-thunder-1.3.1-arch.any.pkg.tar.zst
```

## Then

Run `alien-thunder setup` once, as your own user (not root): it turns the service on, puts the widget on the panel and tells you if anything is missing. Fn+F1 needs your user in the `input` group: `sudo usermod -aG input $USER`, then log out and back in.

## Checking the files

`SHA256SUMS` lists every file's checksum: `sha256sum -c SHA256SUMS` in this folder.
