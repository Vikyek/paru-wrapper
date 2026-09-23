#!/usr/bin/env bash
# Automated installation script for paru-wrapper

set -e

echo "Installing paru-wrapper via makepkg..."
makepkg -Ccfsi --noconfirm

echo "Successfully installed paru-wrapper!"

