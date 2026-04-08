#!/bin/bash
# Build AstroStacker for the current platform.
# Usage: ./build.sh
#
# Output:
#   macOS:   dist/AstroStacker.app
#   Linux:   dist/AstroStacker/AstroStacker
#   Windows: dist/AstroStacker/AstroStacker.exe

set -e

echo "=== AstroStacker Build ==="
echo "Platform: $(uname -s)"
echo ""

# Ensure we're in the project root
cd "$(dirname "$0")"

# Install build dependencies
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -e .
python3 -m pip install pyinstaller

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Run PyInstaller
echo "Building application..."
python3 -m PyInstaller astrostacker.spec --clean

echo ""
echo "=== Build Complete ==="

if [ "$(uname -s)" = "Darwin" ]; then
    echo "Output: dist/Hayseys Astrostacker.app"
    echo ""
    echo "To run:  open 'dist/Hayseys Astrostacker.app'"
    echo "To distribute: zip the .app or create a DMG"
elif [ "$(uname -s)" = "Linux" ]; then
    echo "Output: dist/Hayseys Astrostacker/Hayseys Astrostacker"
    echo ""
    echo "To run:  ./dist/Hayseys\\ Astrostacker/Hayseys\\ Astrostacker"
else
    echo "Output: dist/Hayseys Astrostacker/"
fi
