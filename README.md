# paru-wrapper

A wrapper around `paru` that automates dependency-aware orphaned package cleaning and registers newly built packages directly into a local repository database (like `MKVPKG`).

## Features

- **Automatic Repository DB Registration:** Detects packages compiled during `paru` upgrades and registers them directly in the custom repository database `/mnt/v/Data/makepkg/packages/MKVPKG.db.tar.gz` using `repo-add`.
- **Orphan Preservation & Cleaning:** Before upgrades, automatically checks for orphaned packages. It preserves orphans that will be needed as dependencies of packages being upgraded, and cleans the rest safely via `pacman -Rns --noconfirm`.
- **System Integration:** Installs a wrapper binary to `/usr/bin/paru-wrapper` and overrides normal `paru` invocations for the local user by placing a symlink at `~/.local/bin/paru`.

## Installation

Install using standard Arch packaging:

```bash
makepkg -si
```

## Manual Installation

You can also run the automated installation script:

```bash
./install.sh
```

