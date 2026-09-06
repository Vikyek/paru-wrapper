**Before:**
```bash
[paru-wrapper] Temporarily disabling redundant hooks...
[paru-wrapper] Automatically updating MKVPKG repository database at /mnt/v/Data/makepkg/packages/MKVPKG.db.tar.gz...
[paru-wrapper] Warning: Failed to update repository database
[paru-wrapper] DRY RUN: would run: repo-add -R -w "/mnt/v/Data/makepkg/packages/MKVPKG.db.tar.gz" ""
```

**After:**
```bash
# Semantic coloring applies if no NO_COLOR is set and output is a TTY.
[paru-wrapper] Temporarily disabling redundant hooks...
[paru-wrapper] Automatically updating MKVPKG repository database at /mnt/v/Data/makepkg/packages/MKVPKG.db.tar.gz...
[paru-wrapper] Warning: Failed to update repository database
[paru-wrapper] DRY RUN: would run: repo-add -R -w "/mnt/v/Data/makepkg/packages/MKVPKG.db.tar.gz" ""
```
