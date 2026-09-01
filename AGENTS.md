# Agent & Developer Rules for paru-wrapper

- **Pre-flight Check**: Run `bash scripts/agent-preflight-check.sh` before finalizing any PR or commit.
- **Surgical Edits**: Touch only files explicitly requested by the task description.
- **Package Metadata Sync**: If modifying `update_mkvpkg_aur.py` or `paru-wrapper`, update `PKGBUILD` checksums and regenerate `.SRCINFO` using `updpkgsums` / `makepkg --printsrcinfo > .SRCINFO`.
- **Bash Wrapper Rules**: Never insert `--` before forward-passed `$@` arguments in `/usr/bin/paru`.
