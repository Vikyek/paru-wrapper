# Jules Agent Guidelines for paru-wrapper

## Pre-Task Verification
- **Check Exists First**: Verify whether the requested bug or security vulnerability is already fixed on `main` before editing files.
- **Graceful Exit on Pre-Fixed Issues**: If an issue is already resolved, make NO code changes. State that the issue is resolved on `main` and finish the session cleanly without submitting out-of-scope edits.

## Workspace & Scope Management
- **Keep Workspace Clean**: Always run `git status` and `git diff` before committing.
- **Strict Scope Discipline**: Touch ONLY files directly related to the user prompt. Never modify Python scripts, test suites, `PKGBUILD`, or `.SRCINFO` during bash script tasks unless explicitly requested.
- **Never Fix Dirty Checksums with Code**: If `makepkg` fails checksum checks, check for dirty/uncommitted workspace files first (`git checkout -- .`) before assuming `PKGBUILD` checksums are wrong.

## Shell Script Invariants (`paru-wrapper`)
- **Preserve Forwarded Arguments**: NEVER add `--` immediately before `"$@"` in wrapper execution commands like `/usr/bin/paru "$@"`. User flags (e.g. `-Syu`, `-R`) must not be turned into positional package arguments.
