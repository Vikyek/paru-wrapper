# paru-wrapper v1.1.1

## Changes

- Corrects the release package metadata for version 1.1.1.
- Packages `paru-wrapper`, `pacman-wrapper`, and `update_mkvpkg_aur.py` from the GitHub tag archive.
- Keeps the existing `paru-wrapper.install` post-install and post-upgrade integration.
- Uses the repository's GPL-3.0-only license metadata.
- Includes the tested local AUR repository update logic.

## Validation

- `python -m py_compile update_mkvpkg_aur.py`
- `pytest -q`: 34 passed
- `make test`: 34 passed

## Release commands

```bash
git add PKGBUILD .SRCINFO update_mkvpkg_aur.py test_update_mkvpkg_aur.py
git commit -m "release: prepare v1.1.1"
git push origin main
git tag -a v1.1.1 -m "paru-wrapper v1.1.1"
git push origin v1.1.1

rm -rf src pkg paru-wrapper-*.tar.gz
makepkg -Cfs
bash ./install.sh
```
