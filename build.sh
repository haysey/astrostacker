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

# Copy docs into the dist folder alongside the app
# Generate PDF manual before packaging
echo "Generating PDF user manual..."
python3 make_manual_pdf.py

if [ "$(uname -s)" = "Darwin" ]; then
    cp README_plain.txt "dist/README.txt"
    cp GETTING_STARTED.txt "dist/GETTING_STARTED.txt"
    cp USER_MANUAL.txt "dist/USER_MANUAL.txt"
    cp USER_MANUAL.pdf "dist/USER_MANUAL.pdf"
    echo "Output: dist/Hayseys Astrostacker.app"
    echo "Docs:   dist/README.txt  dist/GETTING_STARTED.txt  dist/USER_MANUAL.txt  dist/USER_MANUAL.pdf"
    echo ""
    echo "To run:  open 'dist/Hayseys Astrostacker.app'"
    echo "To distribute: zip the .app, README.txt, GETTING_STARTED.txt, USER_MANUAL.txt and USER_MANUAL.pdf together"
elif [ "$(uname -s)" = "Linux" ]; then
    cp README_plain.txt "dist/Hayseys Astrostacker/README.txt"
    cp GETTING_STARTED.txt "dist/Hayseys Astrostacker/GETTING_STARTED.txt"
    cp USER_MANUAL.txt "dist/Hayseys Astrostacker/USER_MANUAL.txt"
    cp USER_MANUAL.pdf "dist/Hayseys Astrostacker/USER_MANUAL.pdf"
    echo "Output: dist/Hayseys Astrostacker/Hayseys Astrostacker"
    echo "Docs:   dist/Hayseys Astrostacker/README.txt  GETTING_STARTED.txt  USER_MANUAL.txt  USER_MANUAL.pdf"
    echo ""
    echo "To run:  ./dist/Hayseys\\ Astrostacker/Hayseys\\ Astrostacker"
else
    cp README_plain.txt "dist/Hayseys Astrostacker/README.txt"
    cp GETTING_STARTED.txt "dist/Hayseys Astrostacker/GETTING_STARTED.txt"
    cp USER_MANUAL.txt "dist/Hayseys Astrostacker/USER_MANUAL.txt"
    cp USER_MANUAL.pdf "dist/Hayseys Astrostacker/USER_MANUAL.pdf"
    echo "Output: dist/Hayseys Astrostacker/"
    echo "Docs:   dist/Hayseys Astrostacker/README.txt  GETTING_STARTED.txt  USER_MANUAL.txt  USER_MANUAL.pdf"
fi
