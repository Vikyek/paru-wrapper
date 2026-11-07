# paru-wrapper (v1.1.0)

A power-user wrapper for `paru` and `pacman` designed to manage local custom AUR
repositories (`myrepo`), automate package database synchronization, and provide
seamless, system-wide migration to development (`-git`) packages.

---

## Features & Capabilities

- **Gittinator Engine (`paru --gittinator`):** Scans all explicitly installed,
  non-VCS packages on your system (`pacman -Qqe`), queries the official Arch
  User Repository (AUR) RPC API in optimal batches of 50 candidates, identifies
  existing `-git` counterparts, prompts to replace them, and triggers a full
  system update with `--devel` enabled.
- **Automated Local AUR Synchronization (`myrepo`):** Intercepts package
  management commands to trigger `update_repo_aur.py`. It checks if newer
  versions of your locally built custom packages exist in the AUR, auto-upgrades
  installed packages when configured, and manages repository cleanup (e.g.,
  removing non-git packages when `-git` variants take priority).
- **Dual Wrapper Suite:** Bundles both `paru-wrapper` and `pacman-wrapper` to
  ensure consistent execution, hook firing, and local database alignment
  regardless of whether you invoke `paru` or `pacman`.
- **Transparent Pass-Through:** Any standard flags or subcommands not explicitly
  intercepted by wrapper hooks are passed directly to `/usr/bin/paru` or
  `/usr/bin/pacman`.

---

## Repository Structure

```
paru-wrapper/
├── paru-wrapper             # Main entry point script for paru operations
├── pacman-wrapper           # Secondary wrapper for direct pacman calls
├── update_mkvpkg_aur.py     # Python engine for local repo sync & version checks
├── test_update_mkvpkg_aur.py# Unit test suite for version comparison & repo logic
├── default-plugins/         # Modular plugin hooks for optional integrations
│   ├── 10-snapper.sh        # Pre/post transaction btrfs snapshots
│   ├── 20-anneal.sh         # Automatic rebuild queue unmarking
│   ├── 25-projects-pull.sh  # Pre-transaction upstream updates for Projects package repos
│   ├── 30-rebuild-check.sh  # Post-upgrade shared library rebuild detector
│   ├── 40-paru-completion.sh# Post-transaction shell completion cache generator
│   └── 50-vault-sync.sh     # Background config sync pass
├── install.sh               # Standalone shell installer
├── Makefile                 # GNU Make build targets
├── PKGBUILD                 # Arch Linux package build recipe
└── .SRCINFO                 # Generated package metadata
```

---

## Modular Plugin System

`paru-wrapper` features a plugin architecture. Optional packages plug in seamlessly without hardcoded dependencies in the core script:

- **Rebuild Check**: Detects installed packages needing rebuilds against updated libraries (`paru -S rebuild-check-hook`).
- **Shell Completions**: Generates and updates cached CLI completions for bash/zsh/fish (`paru -S paru-completion-hook`).
- **Snapper Snapshots**: Automatic btrfs snapshots before and after transactions (`pacman -S snapper`).
- **Anneal Queue**: Automatically marks/unmarks rebuilt packages from the rebuild queue (`paru -S anneal`).
- **Custom Plugins**: Place custom executable hooks in `/etc/paru-wrapper/plugins.d/` or `~/.config/paru-wrapper/plugins.d/`. Hooks receive events: `pre-transaction`, `post-transaction`, `deferred-hooks`, `package-rebuilt`, and `post-transaction-bg`.

---

## Dependencies

### Runtime

- `paru` – Upstream AUR helper
- `pacman` – Arch Linux package manager
- `python` – For running `update_mkvpkg_aur.py`
- `curl` – AUR RPC API queries
- `jq` – JSON parsing for API responses
- `bash` – Shell script execution environment

### Build & Installation

- `base-devel` / `make` – System build tools
- `git` – Source control management

---

## Environment Variables

`paru-wrapper` respects environment variables to customize runtime behavior:

| Variable                             | Default | Purpose                                                                                                                                                  |
| :----------------------------------- | :------ | :------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PARU_WRAPPER_AUTO_UPDATE_INSTALLED` | `1`     | Automatically upgrades local custom repository packages when a newer version is found in the AUR. Set to `0` to disable automatic upgrades and only log warnings. |

---

## Installation Methods

### 1. Repository Shell Script

Direct installation for local development:

```fish
./install.sh
```

### 2. GNU Make Target

Install to system-wide or custom binary paths:

```fish
# Install to /usr/local/bin (default)
sudo make install

# Install to user home directory
make PREFIX=$HOME/.local install
```

### 3. Native Arch Package

Build and install via `makepkg`:

```fish
makepkg -si
```

---

## Usage Examples

### Bulk Convert Installed Packages to `-git` Versions

To migrate stable installed packages to their AUR `-git` counterparts and pull
latest upstream commits:

```fish
paru --gittinator
```

### Standard AUR & System Operations

All standard `paru` subcommands work identically, with local repository hooks
firing transparently:

```fish
# Perform system update with local repo checks
paru -Syu

# Install or build a package
paru -S package-name

# Remove a package
paru -R package-name
```

---

## Testing & Maintenance

Before committing changes or bumping release versions, run the unit test suite
to verify version comparison routines, package priority rules, and local
repository management logic:

```fish
# Run unit tests directly via Python
python3 test_update_mkvpkg_aur.py

# Or via Makefile target
make test
```

To update release manifests after modifying `PKGBUILD`:

```fish
makepkg --printsrcinfo > .SRCINFO
```

