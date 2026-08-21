# paru-wrapper

A wrapper around `paru` that automates dependency-aware orphaned package cleaning and registers newly built packages directly into a local repository database (like `MKVPKG`).

## Features

- **Automatic Repository DB Registration:** Detects packages compiled during `paru` upgrades and registers them directly in the custom repository database.
- **Orphan Preservation & Cleaning:** Before upgrades, automatically checks for orphaned packages. It preserves orphans that will be needed as dependencies of packages being upgraded, and cleans the remainder.
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

## Configuration

The wrapper makes several path assumptions by default. These can be configured with environment variables:

- PARU_WRAPPER_REPO — directory where built packages are stored (default: /mnt/v/Data/makepkg/packages)
- PARU_WRAPPER_REPO_DB — repository database path (default: $PARU_WRAPPER_REPO/MKVPKG.db.tar.gz)
- PARU_WRAPPER_PROJECTS_DIR — directory with local package sources (default: $HOME/Projects)
- PARU_WRAPPER_DRY_RUN — if "true", the wrapper will not perform destructive changes

Example:
```bash
export PARU_WRAPPER_REPO=/var/cache/makepkg/packages
export PARU_WRAPPER_PROJECTS_DIR="$HOME/Projects"
/usr/bin/paru-wrapper --dry-run -Syu
```

## Usage & Examples

Build and install via makepkg:
```bash
makepkg -si
```

Or use the bundled installer:
```bash
./install.sh
```

Run a normal upgrade (wrapper will run automatically if you installed the symlink):
```bash
paru -Syu
# or directly
/usr/bin/paru-wrapper -Syu
```

Dry-run example (shows what would be removed/updated without performing actions):
```bash
PARU_WRAPPER_DRY_RUN=true /usr/bin/paru-wrapper --dry-run -Syu
```

## Safety & Permissions

This wrapper calls the following commands which may modify your system:
- sudo pacman -Rns --noconfirm (removes orphaned packages)
- repo-add -R -w (updates repository DB and may remove old package files)
- makepkg -sfi (builds and may install local packages)

Be careful: automatic removals are performed without interactive confirmation when not in dry-run mode. Use --dry-run or set PARU_WRAPPER_DRY_RUN=true to preview actions.

## Troubleshooting

- If repo-add fails due to locks, wait for other package tools to finish or retry.
- If local package rebuilds are not found, ensure PARU_WRAPPER_PROJECTS_DIR contains the package directory with a PKGBUILD.
- If AUR RPC checks fail (network issues), the wrapper will warn; rerun with network access.

## Contributing

Please open issues/PRs to report bugs or improve configurability. The project prefers changes that avoid hard-coded user or path names; use environment variables instead.
