# paru-wrapper (v1.2.0)

[![AUR Package CI/CD](https://github.com/Vikyek/paru-wrapper/actions/workflows/aur-release.yml/badge.svg)](https://github.com/Vikyek/paru-wrapper/actions/workflows/aur-release.yml)
[![CodeQL](https://github.com/Vikyek/paru-wrapper/actions/workflows/codeql.yml/badge.svg)](https://github.com/Vikyek/paru-wrapper/actions/workflows/codeql.yml)
[![AUR version](https://img.shields.io/aur/version/paru-wrapper?color=blue&logo=arch-linux)](https://aur.archlinux.org/packages/paru-wrapper)
[![GitHub release](https://img.shields.io/github/v/release/Vikyek/paru-wrapper?include_prereleases&label=release)](https://github.com/Vikyek/paru-wrapper/releases)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL_3.0-blue.svg)](LICENSE)
[![Sponsor Vikyek](https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?logo=github-sponsors&logoColor=white)](https://github.com/sponsors/Vikyek)
[![Donate on Liberapay](https://img.shields.io/badge/Donate-Liberapay-f6c915?logo=liberapay&logoColor=black)](https://liberapay.com/Vikyek)
[![Sponsor on Polar](https://img.shields.io/badge/Sponsor-Polar-0062FF?logo=polar&logoColor=white)](https://polar.sh/vikyek)

A high-performance, power-user wrapper for `paru` and `pacman` on Arch Linux. Engineered with an event-driven modular plugin hook architecture, automated local custom repository synchronization (`myrepo`), dependency-aware orphan pruning, and seamless system-wide migration to development (`-git`) packages.

> **Selected for inclusion in the XERJ Corpus Hub** for its decoupled, modular plugin hook architecture.

---

## Quickstart

Install `paru-wrapper` using your preferred method:

```bash
# Option 1: Install from AUR (recommended)
paru -S paru-wrapper

# Option 2: Run standalone installer
./install.sh

# Option 3: System build via GNU Make
sudo make install
```

Verify the installation and review wrapper capabilities:

```bash
paru-wrapper --wrapper-help
paru-wrapper --wrapper-version
```

---

## Core Features & Value Proposition

- **Modular Plugin Hook Architecture (XERJ Corpus Selection):** Extensible, event-driven lifecycle hooks execute custom tasks across transaction stages (`pre-transaction`, `post-transaction`, `package-rebuilt`, `deferred-hooks`, `post-transaction-bg`). Eliminates monolithic scripts with isolated subshell execution and prioritized override tiers.
- **Gittinator Engine (`paru --gittinator`):** Scans all explicitly installed, non-VCS packages (`pacman -Qqe`), queries the AUR RPC API in optimized chunks of 50 packages, interactively matches `-git` development counterparts, and triggers a full upgrade with `--devel`.
- **Automated Local AUR Repository Sync (`myrepo`):** Integrates custom local repository management (`update_mkvpkg_aur.py`). Detects when newer upstream AUR versions exist, triggers automated package rebuilds, and prunes superseded non-git packages when `-git` builds take priority.
- **Dependency-Aware Orphan Pruning:** Automatically tracks dependencies introduced during builds and safely prunes true orphans without removing shared libraries required by freshly compiled packages.
- **Transparent Dual Wrapper:** Wraps both `paru` and `pacman` seamlessly. Non-wrapper arguments and subcommands pass directly to upstream binaries (`/usr/bin/paru`, `/usr/bin/pacman`) with zero overhead or impedance mismatch.

---

## Modular Plugin Hook Architecture

The core of `paru-wrapper` is designed around a decoupled, event-driven plugin hook system. Optional system integrations plug in naturally without adding hardcoded bloat to core package management.

### Hook Priority & Discovery

Hooks are executed in order of precedence. Higher-priority tiers shadow lower-priority scripts with identical filenames:

```
1. User Hooks:    ~/.config/paru-wrapper/plugins.d/    (Overrides system & defaults)
2. Host Hooks:    /etc/paru-wrapper/plugins.d/           (Machine-level overrides)
3. Packaged:      /usr/lib/paru-wrapper/plugins.d/       (Standard distribution defaults)
4. Local Dev:     ./default-plugins/                     (Fallback for source checkouts)
```

### Lifecycle Events

| Event | Execution Point | Primary Use Case |
| :--- | :--- | :--- |
| `pre-transaction` | Before package downloads or compilations begin | Creating Btrfs pre-snapshots (`10-snapper.sh`), fetching git updates for source projects (`25-projects-pull.sh`) |
| `package-rebuilt` | Immediately after an individual package re-indexes | Unmarking completed jobs in package rebuild queues (`20-anneal.sh`) |
| `post-transaction` | Right after package manager transaction finishes | Creating matched Btrfs post-snapshots (`10-snapper.sh`) |
| `deferred-hooks` | Executed after pacman transaction completes | Scanning binaries for broken shared libraries (`30-rebuild-check.sh`) |
| `post-transaction-bg` | Asynchronously spawned in the background | Regenerating shell completion caches (`40-paru-completion.sh`), syncing configuration vaults (`50-vault-sync.sh`) |

### Bundled Plugins Catalog

- **`10-snapper.sh`**: Creates synchronized Btrfs pre/post snapshots via `snapper`.
- **`20-anneal.sh`**: Automatically marks recompiled packages as resolved in the `anneal` rebuild queue.
- **`25-projects-pull.sh`**: Pulls upstream git fast-forwards for local package repos residing in `$PARU_WRAPPER_PROJECTS_DIR` before builds start.
- **`30-rebuild-check.sh`**: Scans installed packages for broken `.so` shared-library references (`rebuild-check-hook`).
- **`40-paru-completion.sh`**: Rebuilds cached command completions for Bash, Zsh, and Fish (`paru-completion-hook`).
- **`50-vault-sync.sh`**: Performs background synchronization for private configuration repositories.

### Authoring Custom Plugins

Create an executable shell script in `~/.config/paru-wrapper/plugins.d/` (e.g. `99-notify.sh`):

```bash
#!/usr/bin/env bash
# ~/.config/paru-wrapper/plugins.d/99-notify.sh

plugin_name="desktop-notifier"

plugin_hook() {
    local event="$1"
    shift

    case "$event" in
        pre-transaction)
            notify-send "paru-wrapper" "Package transaction started..."
            ;;
        post-transaction)
            notify-send "paru-wrapper" "Package transaction completed successfully!"
            ;;
    esac
}
```

Hooks execute inside subshells to prevent polluting parent shell environments.

---

## Repository Structure

```
paru-wrapper/
├── paru-wrapper             # Main entry point script for paru operations
├── pacman-wrapper           # Secondary wrapper for direct pacman calls
├── update_mkvpkg_aur.py     # Local AUR repo synchronization engine
├── test_update_mkvpkg_aur.py# Unit test suite for version comparison & repo sync
├── default-plugins/         # Bundled modular plugin hook scripts
│   ├── 10-snapper.sh        # Pre/post transaction Btrfs snapshots
│   ├── 20-anneal.sh         # Automatic rebuild queue unmarking
│   ├── 25-projects-pull.sh  # Pre-transaction upstream git updates
│   ├── 30-rebuild-check.sh  # Post-upgrade shared library rebuild detector
│   ├── 40-paru-completion.sh# Post-transaction shell completion cache builder
│   └── 50-vault-sync.sh     # Background configuration synchronization
├── man1/                    # Manual page documentation (man 1 paru-wrapper)
│   └── paru-wrapper.1
├── scripts/                 # Maintenance & CI pre-flight verification scripts
│   └── agent-preflight-check.sh
├── install.sh               # Standalone shell installer
├── Makefile                 # GNU Make build & installation targets
├── PKGBUILD                 # Arch Linux package build recipe
└── .SRCINFO                 # Generated package metadata
```

---

## Dependencies

### Runtime Dependencies

- `paru` – Upstream AUR helper
- `pacman` – Arch Linux package manager
- `python` – For running `update_mkvpkg_aur.py`
- `curl` – AUR RPC API queries
- `jq` – JSON parsing for API responses
- `bash` – Shell script execution environment
- `git` – Source control management
- `sudo` – Privilege escalation for package operations
- `coreutils` – Essential system utilities

### Optional Plugin Dependencies

- `snapper` – Automatic Btrfs snapshots (`10-snapper.sh`)
- `anneal` – Automatic rebuild queue unmarking (`20-anneal.sh`)
- `rebuild-check` – Broken shared library detection (`30-rebuild-check.sh`)
- `paru-completion-hook` – Shell tab-completion caching (`40-paru-completion.sh`)

---

## Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PARU_WRAPPER_REPO` | `""` | Name of the custom local pacman repository database. |
| `PARU_WRAPPER_REPO_DIR` | `""` | Directory containing the custom repository `.db` file. |
| `PARU_WRAPPER_PROJECTS_DIR` | `~/Projects` | Root path to local development project source checkouts. |
| `PARU_WRAPPER_AUTO_UPDATE_INSTALLED` | `1` | Automatically upgrades local custom repository packages when a newer AUR version is found. Set to `0` to log warnings only. |
| `PARU_WRAPPER_DRY_RUN` | `false` | Simulates actions without making changes to filesystem or databases. |
| `FORCE_REBUILD` | `0` | When set to `1`, forces recompilation of target packages from source. |

---

## Installation & Setup

### 1. Arch User Repository (AUR)

Install via your preferred AUR helper:

```bash
paru -S paru-wrapper
```

### 2. Standalone Installer Script

The bundled `install.sh` builds and validates release archives with checksums:

```bash
./install.sh
```

### 3. GNU Make Target

Install to `/usr/local` (default) or a custom prefix:

```bash
# System install
sudo make install

# User home directory install
make PREFIX=$HOME/.local install
```

### 4. Manual Package Build

Build directly with `makepkg`:

```bash
makepkg -si
```

---

## Usage Examples

### Migrate Installed Packages to `-git` (Gittinator)

Scan installed packages, match them against AUR `-git` counterparts, and upgrade:

```bash
paru --gittinator
```

### Manage Custom Local Repositories

Initialize or connect a custom local repository:

```bash
# Initialize a new custom repository
paru-wrapper --init-repo myrepo /var/cache/pacman/myrepo ~/Projects

# Connect to an existing custom repository
paru-wrapper --connect-repo myrepo /var/cache/pacman/myrepo ~/Projects
```

### Inspect Wrapper Diagnostics

```bash
# Display extended wrapper help and environment flags
paru-wrapper --wrapper-help

# Display wrapper version
paru-wrapper --wrapper-version
```

### Transparent Daily Operations

Standard `paru` and `pacman` subcommands operate normally, triggering plugin hooks transparently:

```bash
# Full system upgrade with local repository synchronization
paru -Syu

# Install or build packages
paru -S package-name

# Remove packages with dependency-aware orphan pruning
paru -R package-name
```

---

## Support & Sponsorship

`paru-wrapper` is authored and maintained by **[Vikyek](https://github.com/Vikyek)** as an independent open-source project. Everything is 100% open-source, telemetry-free, and public.

<div align="center">

<!-- Official GitHub Sponsors Button & Card (Rendered in web/HTML environments; GitHub markdown sanitizer strips iframes, falling back to native badges) -->
<iframe src="https://github.com/sponsors/Vikyek/button" title="Sponsor Vikyek" height="32" width="114" style="border: 0; border-radius: 6px;"></iframe>
<iframe src="https://github.com/sponsors/Vikyek/card" title="Sponsor Vikyek" height="225" width="600" style="border: 0;"></iframe>

[![Sponsor Vikyek](https://img.shields.io/badge/Sponsor-%E2%9D%A4-ea4aaa?logo=github&style=for-the-badge)](https://github.com/sponsors/Vikyek)
[![Donate on Liberapay](https://img.shields.io/badge/Donate-Liberapay-f6c915?logo=liberapay&logoColor=black)](https://liberapay.com/Vikyek)
[![Sponsor on Polar](https://img.shields.io/badge/Sponsor-Polar-0062FF?logo=polar&logoColor=white)](https://polar.sh/vikyek)

</div>

> ### 🎯 Active Sponsorship Goal: Monthly Living Essentials
> **Target:** **2,710 PLN / ~$675 USD per month** (Rent & Utilities)  
> Covering basic living essentials directly unlocks dedicated, sustainable full-time independent open-source engineering across `paru-wrapper` and related Arch Linux tooling.

If `paru-wrapper` accelerates your workflow, secures your system with automatic snapshots, or simplifies local package builds, consider supporting my work:

- **GitHub Sponsors**: [github.com/sponsors/Vikyek](https://github.com/sponsors/Vikyek)
- **Liberapay (Recurrent Open-Source Patronage)**: [liberapay.com/Vikyek](https://liberapay.com/Vikyek)
- **Polar**: [polar.sh/vikyek](https://polar.sh/vikyek)

Every contribution—monthly or one-time—directly supports active maintenance, hardware testbeds, and new feature development!

---

## Contributing & Testing

Contributions, bug reports, and plugin enhancements are welcome! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

### Running Tests

```bash
# Run unit tests
make test

# Run pre-flight check
bash scripts/agent-preflight-check.sh
```

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
