#!/usr/bin/env bash
# ============================================================
#  Haysey's AstroStacker — Linux Desktop Installer
# ============================================================
#  Tested on: Ubuntu 22.04+, Debian 12+, Linux Mint 21+
#
#  Usage:
#    chmod +x install_linux.sh
#    ./install_linux.sh
#
#  This is an alternative to the PyInstaller build.
#  It installs from source with a virtual environment.
#
#  To run after install:
#    ~/astrostacker/run.sh
#  Or find "Haysey's AstroStacker" in your applications menu.
# ============================================================

set -e

APP_DIR="$HOME/astrostacker"
VENV_DIR="$APP_DIR/venv"
REPO_URL="https://github.com/haysey/astrostacker.git"

echo ""
echo "============================================"
echo "  Haysey's AstroStacker — Linux Installer"
echo "============================================"
echo ""

# ── 1. Install system dependencies ────────────────────────
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-venv \
    python3-dev \
    python3-pip \
    libgl1 \
    libglx-mesa0 \
    libegl1 \
    libxkbcommon0 \
    libdbus-1-3 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxkbcommon-x11-0 \
    git

# ── 2. Clone or update the repo ───────────────────────────
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

# ── 3. Create virtual environment ─────────────────────────
echo ""
echo "[3/5] Setting up Python environment..."

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip -q

echo "  Installing Python packages..."
pip install -r "$APP_DIR/requirements.txt" -q

# Install the app itself
pip install -e "$APP_DIR" -q

deactivate

# ── 4. Create launcher script ─────────────────────────────
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

# ── 5. Create desktop shortcut ────────────────────────────
echo ""
echo "[5/5] Creating desktop shortcut..."

ICON_PATH="$APP_DIR/icon.png"

# Applications menu entry
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/astrostacker.desktop" << DESKTOP
[Desktop Entry]
Name=Haysey's AstroStacker
Comment=Astrophotography image stacking
Exec=$APP_DIR/run.sh
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Science;Graphics;
DESKTOP

# Desktop shortcut (if ~/Desktop exists)
if [ -d "$HOME/Desktop" ]; then
    cp "$HOME/.local/share/applications/astrostacker.desktop" "$HOME/Desktop/"
    chmod +x "$HOME/Desktop/astrostacker.desktop"
fi

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "  To run:   ~/astrostacker/run.sh"
echo "  Or find 'Haysey's AstroStacker' in your"
echo "  applications menu."
echo ""
echo "  To update later:  cd ~/astrostacker && git pull"
echo "============================================"
echo ""
