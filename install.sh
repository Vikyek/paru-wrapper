#!/usr/bin/env bash
# Build and install paru-wrapper from a freshly validated release archive.

set -euo pipefail

cd -- "$(dirname -- "$(readlink -f -- "$0")")"

# Load makepkg configuration to find the actual source cache.
if [[ -r /etc/makepkg.conf ]]; then
    # shellcheck disable=SC1091
    source /etc/makepkg.conf
fi

if [[ -r "${HOME}/.makepkg.conf" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/.makepkg.conf"
fi

# Read release metadata from the trusted local PKGBUILD.
# shellcheck disable=SC1091
source ./PKGBUILD

if [[ -z "${pkgname:-}" || -z "${pkgver:-}" || -z "${url:-}" ]]; then
    printf '%s\n' \
        "ERROR: PKGBUILD does not define pkgname, pkgver, and url." >&2
    exit 1
fi

archive_name="${pkgname}-${pkgver}.tar.gz"
archive_url="${url}/archive/refs/tags/v${pkgver}.tar.gz"
source_cache="${SRCDEST:-$PWD}"
cached_archive="${source_cache}/${archive_name}"

temporary_directory=$(mktemp -d)
downloaded_archive="${temporary_directory}/${archive_name}"

cleanup() {
    rm -rf -- "$temporary_directory"
}

trap cleanup EXIT INT TERM

mkdir -p -- "$source_cache"

printf 'Installing %s %s via makepkg...\n' "$pkgname" "$pkgver"
printf 'Validating release archive from GitHub...\n'

curl \
    --fail \
    --location \
    --silent \
    --show-error \
    --retry 3 \
    --retry-delay 2 \
    --output "$downloaded_archive" \
    "$archive_url"

# Verify that the downloaded object is a readable gzip-compressed tar archive.
if ! tar -tzf "$downloaded_archive" >/dev/null; then
    printf 'ERROR: Downloaded release archive is invalid: %s\n' \
        "$archive_url" >&2
    exit 1
fi

expected_root="${pkgname}-${pkgver}/"

archive_contents="${temporary_directory}/archive-contents.txt"

if ! tar -tzf "$downloaded_archive" > "$archive_contents"; then
    printf 'ERROR: Could not read release archive: %s\n' \
        "$archive_url" >&2
    exit 1
fi

required_archive_files=(
    "${expected_root}paru-wrapper"
    "${expected_root}pacman-wrapper"
    "${expected_root}update_mkvpkg_aur.py"
    "${expected_root}PKGBUILD"
    "${expected_root}LICENSE"
)

if [[ -f paru-wrapper-gittinator ]]; then
    required_archive_files+=(
        "${expected_root}paru-wrapper-gittinator"
        "${expected_root}paru-wrapper-gittinator-impl"
    )
fi

for required_archive_file in "${required_archive_files[@]}"; do
    if ! grep -Fx \
        -- "$required_archive_file" \
        "$archive_contents" \
        >/dev/null
    then
        printf 'ERROR: Release archive does not contain %s\n' \
            "$required_archive_file" >&2
        exit 1
    fi
done

downloaded_checksum=$(
    sha256sum "$downloaded_archive" |
        awk '{print $1}'
)

if [[ -f "$cached_archive" ]]; then
    cached_checksum=$(
        sha256sum "$cached_archive" |
            awk '{print $1}'
    )

    if [[ "$cached_checksum" == "$downloaded_checksum" ]]; then
        printf 'Cached source archive is current: %s\n' \
            "$cached_archive"
    else
        printf 'Replacing stale cached source archive:\n'
        printf '  cached: %s\n' "$cached_checksum"
        printf '  remote: %s\n' "$downloaded_checksum"

        install \
            -Dm644 \
            "$downloaded_archive" \
            "${cached_archive}.new"

        mv -f -- "${cached_archive}.new" "$cached_archive"
    fi
else
    printf 'Populating source cache: %s\n' "$cached_archive"

    install \
        -Dm644 \
        "$downloaded_archive" \
        "${cached_archive}.new"

    mv -f -- "${cached_archive}.new" "$cached_archive"
fi

# If SRCDEST differs from the repository directory, remove a second stale
# archive from the working tree so makepkg cannot select the wrong copy.
working_archive="${PWD}/${archive_name}"

if [[ "$working_archive" != "$cached_archive" ]]; then
    rm -f -- "$working_archive"
fi

# Remove extracted build trees and any existing binary package for this release.
rm -rf -- src pkg

find . \
    -maxdepth 1 \
    -type f \
    -name "${pkgname}-${pkgver}-*.pkg.tar.*" \
    -delete

printf 'Validated SHA-256: %s\n' "$downloaded_checksum"
printf 'Building and installing a fresh package...\n'

makepkg -Ccfsi --noconfirm

printf 'Verifying installed files...\n'

required_files=(
    /usr/bin/paru-wrapper
    /usr/bin/pacman-wrapper
    /usr/bin/update_mkvpkg_aur.py
)

for required_file in "${required_files[@]}"; do
    if [[ ! -x "$required_file" ]]; then
        printf 'ERROR: Required installed executable is missing: %s\n' \
            "$required_file" >&2
        exit 1
    fi
done

if [[ -f paru-wrapper-gittinator ]]; then
    required_gittinator_files=(
        /usr/lib/paru-wrapper/paru-wrapper-gittinator
        /usr/lib/paru-wrapper/paru-wrapper-gittinator-impl
    )

    for required_file in "${required_gittinator_files[@]}"; do
        if [[ ! -x "$required_file" ]]; then
            printf 'ERROR: Required Gittinator executable is missing: %s\n' \
                "$required_file" >&2
            exit 1
        fi
    done
fi

bash -n /usr/bin/paru-wrapper
bash -n /usr/bin/pacman-wrapper
python3 -c 'from pathlib import Path; p=Path("/usr/bin/update_mkvpkg_aur.py"); compile(p.read_bytes(), str(p), "exec"); print(f"Python syntax OK: {p}")'

installed_version=$(pacman -Q "$pkgname" 2>/dev/null || true)

printf 'Successfully installed %s\n' \
    "${installed_version:-${pkgname} ${pkgver}}"
