# Contributing to paru-wrapper

Thank you for your interest in contributing to `paru-wrapper`! This project is maintained by an independent solo developer ([Vikyek](https://github.com/Vikyek)). External contributions, bug reports, performance improvements, and plugin ideas are warmly welcome.

---

## Code of Conduct & Philosophy

- **Surgical Edits**: Keep changes focused and minimal. Touch only what is necessary to solve the issue or implement the feature.
- **Decoupled Architecture**: Features requiring external tools or optional system capabilities belong in the **Modular Plugin System** (`default-plugins/` or user plugin hooks) rather than hardcoded core dependencies.
- **Pass-Through Integrity**: Never break or interfere with upstream `paru` and `pacman` flag forwarding.

---

## Development & Local Testing

### Prerequisites

Ensure you have the required runtime and development tools installed:

```bash
sudo pacman -S --needed base-devel git python jq curl
```

### Running Unit Tests

Unit tests validate Arch Linux EVR version comparison, RPC query parsing, and repository synchronization logic:

```bash
# Run unit tests via Makefile
make test

# Or directly with Python
python3 -m unittest discover -b -s . -p "test_*.py"
```

### Pre-Flight Verification

Before opening a pull request, run the automated agent pre-flight check script:

```bash
bash scripts/agent-preflight-check.sh
```

This verifies:
1. Shell syntax validity across all bash entrypoints and default plugins.
2. Wrapper argument forwarding invariants (e.g. ensuring user flags pass cleanly to `/usr/bin/paru`).
3. Parity for `--wrapper-help` and `--wrapper-version` CLI entrypoints.
4. Clean workspace state.

---

## Contributing Plugins

`paru-wrapper` uses an event-driven modular plugin architecture. To propose a new bundled plugin for `default-plugins/`:

1. Ensure the script defines `plugin_hook()` handling relevant lifecycle events:
   - `pre-transaction`
   - `post-transaction`
   - `package-rebuilt`
   - `deferred-hooks`
   - `post-transaction-bg`
2. Implement a `plugin_check()` guard to ensure optional binaries exist before executing.
3. Keep hook operations non-destructive and defensive.
4. Document any new optional dependencies in `PKGBUILD` (`optdepends`), `man1/paru-wrapper.1`, and `README.md`.

---

## Commit Guidelines

Follow standard conventional commit practices:

- Use the imperative mood in the subject line (e.g., `feat: add hook`, `fix: handle edge case`).
- Keep the subject line concise (under 72 characters).
- Explain the **why** behind changes in the commit body, followed by bulleted details.

Example:
```gitcommit
feat(plugins): add custom hook support for pre-transaction checks

Allow third-party hooks to execute prior to pacman transactions, enabling
filesystem snapshotting and custom repository pre-fetching.

* Add dispatch_plugin_hooks invocation in pre-transaction phase
* Support user overrides via ~/.config/paru-wrapper/plugins.d/
```

---

## Submitting Pull Requests

1. Fork the repository and create your feature branch: `git checkout -b feat/my-improvement`.
2. Make your changes and run `make test` and `bash scripts/agent-preflight-check.sh`.
3. Commit with a clear, descriptive commit message.
4. Push to your fork and submit a Pull Request against `main`.
5. Provide a summary of the problem solved, testing performed, and any package metadata touched.
