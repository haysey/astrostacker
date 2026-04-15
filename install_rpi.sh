#!/usr/bin/env bash
# ============================================================
#  Haysey's AstroStacker — Raspberry Pi Installer
# ============================================================
#  Tested on: Raspberry Pi 4/5, Raspberry Pi OS (64-bit Bookworm)
#
#  Usage:
#    chmod +x install_rpi.sh
#    ./install_rpi.sh
#
#  What it does:
#    1. Installs system Qt6 & science libraries via apt
#    2. Creates a Python virtual environment
#    3. Installs pip dependencies
#    4. Creates a desktop shortcut & launcher script
#
#  To run after install:
#    ~/astrostacker/run.sh
#  Or double-click "Haysey's AstroStacker" on your desktop.
# ============================================================

set -e

APP_DIR="$HOME/astrostacker"
VENV_DIR="$APP_DIR/venv"
REPO_URL="https://github.com/haysey/astrostacker.git"

echo ""
echo "============================================"
echo "  Haysey's AstroStacker — Raspberry Pi"
echo "============================================"
echo ""

# ── 1. Check architecture ─────────────────────────────────
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "armv7l" ]]; then
    echo "WARNING: This script is designed for Raspberry Pi (ARM)."
    echo "Detected architecture: $ARCH"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# ── 2. Install system dependencies ────────────────────────
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-venv \
    python3-dev \
    python3-pyqt6 \
    qt6-base-dev \
    libgl1 \
    libglx-mesa0 \
    libegl1 \
    libxkbcommon0 \
    libxcb-cursor0 \
    libxcb-xinerama0 \
    zlib1g \
    git \
    gfortran \
    libopenblas-dev \
    libffi-dev \
    libhdf5-dev \
    pkg-config

# ── 3. Clone or update the repo ───────────────────────────
echo ""
echo "[2/5] Getting source code..."
if [ -d "$APP_DIR/.git" ]; then
    echo "  Updating existing install..."
    cd "$APP_DIR"
    git pull --ff-only origin main
else
    if [ -d "$APP_DIR" ]; then
        echo "  Backing up existing $APP_DIR..."
        mv "$APP_DIR" "${APP_DIR}_backup_$(date +%Y%m%d%H%M%S)"
    fi
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# ── 4. Create virtual environment ─────────────────────────
echo ""
echo "[3/5] Setting up Python environment..."

# IMPORTANT: We MUST use system Python on Pi, because:
#  1. python3-pyqt6 from apt is built for the system Python version
#  2. PyQt6 has no PyPI wheels for ARM Linux, so pip-installing it
#     would try to build from source (slow + often fails)
# If user is in pyenv/conda, /usr/bin/python3 bypasses that.
SYS_PY="/usr/bin/python3"
if [ ! -x "$SYS_PY" ]; then
    echo "ERROR: System Python not found at /usr/bin/python3"
    echo "Install it with: sudo apt install python3"
    exit 1
fi

# Verify system Python can import PyQt6 (sanity check apt install worked)
if ! "$SYS_PY" -c "from PyQt6 import QtCore" 2>/dev/null; then
    echo "ERROR: System Python can't import PyQt6."
    echo "Re-run: sudo apt install python3-pyqt6"
    exit 1
fi

echo "  Using system Python: $($SYS_PY --version)"

# --system-site-packages lets us use the apt-installed PyQt6
"$SYS_PY" -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip -q

# Install dependencies (skip PyQt6 — using system version)
echo "  Installing Python packages (this may take a few minutes on Pi)..."
pip install \
    "numpy>=1.24" \
    "scipy>=1.10" \
    "astropy>=5.3" \
    "xisf>=0.9.5" \
    "astroalign>=2.5" \
    "scikit-image>=0.21" \
    "requests>=2.28" \
    -q

# Install the app itself with --no-deps so pip doesn't try to
# reinstall PyQt6 from PyPI (which would fail on ARM)
pip install --no-deps -e "$APP_DIR" -q

deactivate

# ── 5. Create launcher script ─────────────────────────────
echo ""
echo "[4/5] Creating launcher..."

cat > "$APP_DIR/run.sh" << 'LAUNCHER'
#!/usr/bin/env bash
# Launch Haysey's AstroStacker
cd "$(dirname "$0")"
source venv/bin/activate
python -m astrostacker.main
LAUNCHER
chmod +x "$APP_DIR/run.sh"

# ── 6. Create desktop shortcut ────────────────────────────
echo ""
echo "[5/5] Creating desktop shortcut..."

DESKTOP_DIR="$HOME/Desktop"
mkdir -p "$DESKTOP_DIR"

ICON_PATH="$APP_DIR/icon.png"

cat > "$DESKTOP_DIR/astrostacker.desktop" << DESKTOP
[Desktop Entry]
Name=Haysey's AstroStacker
Comment=Astrophotography image stacking
Exec=$APP_DIR/run.sh
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Science;Graphics;
DESKTOP
chmod +x "$DESKTOP_DIR/astrostacker.desktop"

# Also install in the applications menu
mkdir -p "$HOME/.local/share/applications"
cp "$DESKTOP_DIR/astrostacker.desktop" "$HOME/.local/share/applications/"

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "  To run:   ~/astrostacker/run.sh"
echo "  Or double-click 'Haysey's AstroStacker'"
echo "  on your desktop."
echo ""
echo "  To update later:  cd ~/astrostacker && git pull"
echo "============================================"
echo ""
