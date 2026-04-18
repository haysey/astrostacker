# Haysey's Astrostacker v0.3.0

A free, easy-to-use astrophotography image stacking application for macOS, Windows, Linux, and Raspberry Pi. Built for members of the Astronomical Society of Victoria (ASV) and the wider amateur astronomy community.

No coding or command-line experience required — just download, unzip, and run.

---

## What's New in v0.3.0

New stacking methods, denoising, and a full visual polish pass:

**New stacking & processing:**
- **PSF fitting** — proper 2D Gaussian star profile fitting replaces the old HFR measurement. Gives accurate FWHM, eccentricity, and roundness per frame. Frame rejection now catches both blurry AND trailed frames.
- **PSF-informed sharpening** — tightens star profiles and enhances fine detail using the measured star FWHM. Positive-only unsharp masking ensures nothing is ever darkened. Light/Medium/Strong presets.
- **5 new stacking methods** — Winsorized Sigma, Percentile Clipping, Weighted Mean (quality-based), Noise-Weighted Mean, plus the existing Mean, Median, Sigma Clip, Min, Max
- **Non-Local Means denoising** — post-stack noise reduction with Light/Medium/Strong presets. Preserves star profiles and nebula structure while smoothing noisy backgrounds. No model files, no GPU required.
- **Local normalisation** — per-frame gradient removal before stacking, so gradient differences between frames (moonrise, changing sky glow) don't contaminate the stack
- **Percentile Clipping controls** — configurable low/high reject percentages when using Percentile Clipping
- **Weighted Mean** — automatically scores each frame by PSF quality (FWHM + roundness) and weights sharper, rounder frames higher

**UX improvements:**
- **Drag and drop** — drag files or folders directly onto the Light, Dark, Flat, and Dark Flat panels
- **Folder import** — "Add Folder" option scans an entire directory for supported image files
- **Smart settings** — Sigma parameters only appear when using Sigma Clipping/Winsorized Sigma; Bayer pattern only appears for Colour cameras
- **Default stacking method** changed to Median — safest for beginners, advanced users can change as needed
- **Improved startup layout** — all settings visible without scrolling on launch
- **FITS compatibility fix** — handles BZERO/BSCALE scaled files that previously caused a crash
- **Windows performance** — disabled UPX compression to avoid startup slowdown and antivirus false positives

**Visual polish:**
- Orange focus rings, card-style panels, animated status bar, button press animations
- Icons on all secondary buttons, orange progress bar and selection highlights
- Thicker tab indicator with hover highlight

---

## What Does It Do?

Astrophotography images straight from the camera are noisy and faint. **Stacking** combines many exposures of the same target to dramatically reduce noise and reveal detail that no single frame can show.

Haysey's Astrostacker handles the entire workflow:

1. **Load** your light frames (and optional darks, flats, dark flats)
2. **Calibrate** — subtract dark current and correct for vignetting/dust
3. **Reject** — PSF-based scoring discards blurry and trailed frames
4. **Debayer** — convert raw Bayer data to full colour (for colour cameras)
5. **Align** — automatically register all frames to a reference star field
6. **Stack** — combine aligned frames using your choice of 9 methods
7. **Crop** — auto-trim alignment edge artifacts
8. **Gradient removal** — subtract light pollution gradients
9. **Sharpen** — PSF-informed sharpening (Light/Medium/Strong)
10. **Denoise** — Non-Local Means noise reduction (Light/Medium/Strong)
11. **Plate Solve** — identify exactly where in the sky your image points
12. **Mosaic** — stitch multiple plate-solved panels into a wide-field image
13. **Export** — save as FITS, TIFF, or PNG

---

## Features

### Stacking & Calibration
- **One-click stacking** — load your files, click Start, and you're done
- **9 stacking methods** — Mean, Median, Sigma Clip, Winsorized Sigma, Percentile Clip, Weighted Mean, Noise-Weighted Mean, Min, Max
- **Drizzle stacking** — 2x resolution enhancement for well-dithered sub-exposures
- **Calibration frames** — supports darks, flats, and dark flats
- **Load pre-built masters** — load existing master dark and master flat FITS files to skip rebuilding them each session
- **Master frames saved** — master darks and flats are automatically saved alongside your output for reuse
- **Colour camera support** — automatic Bayer demosaicing (RGGB, GRBG, GBRG, BGGR)
- **Mono camera support** — works with dedicated astronomy cameras too
- **Automatic frame alignment** — star-based registration using astroalign

### Processing
- **PSF-based frame rejection** — fits 2D Gaussian profiles to stars in each frame, measuring FWHM (sharpness) and eccentricity (elongation). Automatically rejects both blurry AND trailed frames.
- **PSF-informed sharpening** — tightens star profiles and enhances nebula detail using the measured star FWHM. Positive-only enhancement ensures nothing is ever darkened — no dark halos. Light/Medium/Strong presets.
- **Light pollution gradient removal** — fits and subtracts a smooth background surface to remove sky gradients from light pollution, moonlight, or vignetting
- **Local normalisation** — per-frame gradient removal before stacking to prevent gradient drift between frames from contaminating the stack
- **Non-Local Means denoising** — classical NLM noise reduction (Buades et al. 2005) with automatic noise estimation and Light/Medium/Strong presets. Preserves star profiles and nebula structure.
- **Auto-crop** — trims the black/NaN borders left by frame alignment for a clean rectangular result

### Plate Solving
- **Integrated plate solver** — uses Astrometry.net to identify objects in your image
- **WCS astrometry** — embeds World Coordinate System data for PixInsight SPCC and other tools
- **Auto plate solve** — optionally plate solves automatically after stacking
- **Annotated results** — view solved images with labelled deep-sky objects (Messier, NGC, IC, HD stars, etc.)

### Mosaic Building
- **WCS-based panel stitching** — combine multiple plate-solved FITS panels into a single wide-field image
- **Automatic alignment** — uses astrometric coordinates (not star matching), so it works even on sparse or dissimilar fields
- **Feathered blending** — smooth seamless transitions across overlapping regions
- **Dedicated Mosaic tab** — runs on a background thread with live progress log

### Tools & Export
- **Live histogram** — real-time pixel value distribution with min, max, mean, and median stats
- **Blink comparator** — cycle through your frames with play/pause to spot satellite trails, clouds, or bad subs before stacking
- **FITS header viewer** — inspect all metadata keywords in any FITS file (Tools menu)
- **Export to TIFF/PNG** — one-click export with auto-stretch applied (File menu)
- **Session save/load** — save all your file lists and settings to a JSON file and reload them later (File menu)
- **Live preview** — view images with PixInsight-style auto-stretch or linear stretch, multiple zoom levels
- **Save As** — save the current preview image in FITS, XISF, PNG, or TIFF format

### General
- **Frame status bar** — shows accepted/rejected frame counts after stacking, with option to delete rejected files from disk
- **Audio notifications** — chime when processing completes, alert on errors
- **Opens maximized** — automatically fills your screen at launch for best layout
- **Apple Silicon optimised** — multi-core parallel processing on M1/M2/M3/M4 Macs
- **FITS and XISF support** — reads and writes standard astro image formats
- **Beautiful UI** — dark theme with procedural starfield background and Southern Cross logo

---

## Downloads

Download the latest version for your platform:

| Platform | Download |
|----------|----------|
| **Windows (64-bit)** | [Hayseys-Astrostacker-Windows-x64.zip](https://github.com/haysey/astrostacker/actions) |
| **macOS (Apple Silicon)** | [Hayseys-Astrostacker-macOS-AppleSilicon.zip](https://github.com/haysey/astrostacker/actions) |
| **macOS (Intel)** | [Hayseys-Astrostacker-macOS-Intel.zip](https://github.com/haysey/astrostacker/actions) |
| **Linux (64-bit)** | [Hayseys-Astrostacker-Linux-x64.tar.gz](https://github.com/haysey/astrostacker/actions) |
| **Raspberry Pi** | Run `install_rpi.sh` (see below) |

To download: go to **Actions** > click the latest successful run (green tick) > scroll to **Artifacts** > download for your platform.

> **No Python installation required.** Everything is bundled — just download, unzip, and run.

---

## Getting Started

### Installation

#### macOS (Apple Silicon or Intel)

1. Download and unzip the correct version for your Mac
2. Drag **Hayseys Astrostacker.app** to your Applications folder (or wherever you like)
3. **First launch only** — macOS will block the app because it's not signed by Apple:
   - Right-click the app > click **Open** > click **Open** again on the dialog
   - You only need to do this once. After that, it opens normally.
4. If you still get a "damaged" error, open **Terminal** and run:
   ```
   xattr -cr "/Applications/Hayseys Astrostacker.app"
   ```
   Then open the app normally.

> **Which version do I need?**
> - If your Mac was made in **2021 or later**, download the **Apple Silicon** version
> - If your Mac was made **before 2021**, download the **Intel** version
> - Not sure? Click the Apple menu > **About This Mac** > look for "Chip: Apple M..." (Apple Silicon) or "Processor: Intel..." (Intel)

#### Windows

1. Download and unzip `Hayseys-Astrostacker-Windows-x64.zip`
2. Open the folder and double-click **Hayseys Astrostacker.exe**
3. **Windows Defender may block extraction or launch** — this is a false positive caused by the way the app is packaged (PyInstaller). The app is safe. To fix:
   - Open **Settings** > **Privacy & Security** > **Windows Security**
   - Click **Virus & threat protection** > **Manage settings**
   - Scroll down to **Exclusions** > **Add or remove exclusions**
   - Click **Add an exclusion** > **Folder** > select the folder where you extracted the zip
   - Re-extract the zip and it should work fine
4. If Windows SmartScreen appears on first launch:
   - Click **More info**
   - Click **Run anyway**
   - You only need to do this once.

#### Linux (Ubuntu, Debian, Mint)

**Option A — Pre-built binary (easiest):**

1. Download `Hayseys-Astrostacker-Linux-x64.tar.gz`
2. Extract it: `tar -xzf Hayseys-Astrostacker-Linux-x64.tar.gz`
3. Run it: `cd "Hayseys Astrostacker" && ./"Hayseys Astrostacker"`

**Option B — Install from source (recommended for most users):**

1. Open a terminal
2. Download and run the installer:
   ```
   wget https://raw.githubusercontent.com/haysey/astrostacker/main/install_linux.sh
   chmod +x install_linux.sh
   ./install_linux.sh
   ```
3. The installer creates a desktop shortcut and adds the app to your applications menu
4. To update later: `cd ~/astrostacker && git pull`

#### Raspberry Pi (Pi 4, Pi 5 — 64-bit Raspberry Pi OS)

Raspberry Pi uses a dedicated install script that installs Qt6 from the system and the rest via pip. This is faster and more reliable than a pre-built binary on ARM.

1. Open a terminal on your Pi
2. Download and run the installer:
   ```
   wget https://raw.githubusercontent.com/haysey/astrostacker/main/install_rpi.sh
   chmod +x install_rpi.sh
   ./install_rpi.sh
   ```
3. The installer handles everything — system packages, Python environment, desktop shortcut
4. Launch from the desktop icon or run `~/astrostacker/run.sh`

> **Pi performance note:** A Raspberry Pi 4 (4GB+) or Pi 5 will happily stack 20-30 frames at a time. Stacking is CPU-bound, so expect it to take longer than a desktop — but it works well for smaller batches. Drizzle and mosaic building will be slow on a Pi; disable drizzle for faster results.

---

### Quick Start Guide

#### 1. Load Your Images

- Click **Add** under Light Frames and select your light frames (FITS or XISF), or use **Add Folder** to import an entire directory
- You can also **drag and drop** files or folders directly onto any frame list
- Optionally add **Darks**, **Flats**, and **Dark Flats** for calibration
- OR click **Master Dark...** / **Master Flat...** to load pre-built master frames
- The more light frames you add, the better your result will be

#### 2. Configure Settings

- **Camera Type** — select Mono or Colour (Bayer)
- **Bayer Pattern** — if using a colour camera, select your sensor's pattern (usually RGGB)
- **Stacking Method** — Median is the default and safe for beginners. Sigma Clip is recommended for 15+ frames (rejects satellites, planes, hot pixels)
- **Output Path** — where to save the stacked result

#### 3. Processing Options (Optional)

- **Auto-reject blurry frames** — tick this to automatically score and reject poor-quality frames
- **Remove light pollution gradient** — great for suburban observing sites
- **Local normalisation** — remove gradients from each frame individually before stacking (best for multi-hour sessions where sky brightness changes)
- **Sharpen (Deconvolution)** — tightens star profiles and reveals fine detail. Choose Light, Medium, or Strong.
- **Denoise (Non-Local Means)** — smooth noisy backgrounds while preserving detail. Choose Light, Medium, or Strong.
- **Auto-crop stacking edges** — cleans up the black borders from alignment
- **Drizzle (2x resolution)** — produces a higher-resolution output (best with dithered subs)

#### 4. Stack!

- Click **Start Processing**
- Watch the progress log as your frames are calibrated, scored, aligned, and stacked
- A chime will sound when processing is complete
- Your stacked image appears in the Preview panel with a live histogram

#### 5. Plate Solve (Optional)

Plate solving identifies exactly where your image points in the sky and which objects are in the frame. This also embeds WCS (World Coordinate System) data into your FITS file, which is required by tools like PixInsight's SPCC (Spectrophotometric Color Calibration).

- Go to the **Plate Solve** tab
- Enter your **Astrometry.net API key** (see below)
- Select an image or tick **Auto plate solve after stacking** in Settings
- Click **Solve** and wait for results

#### 6. Export Your Result

- Use **File > Export as TIFF** or **File > Export as PNG** for a stretched image ready to share
- Use **Save As** in the preview toolbar for raw FITS or XISF data
- Your stacked FITS file is also saved automatically to the output path

---

## Building a Mosaic

A mosaic combines several overlapping panels (each a separate stack) into one wide-field image — great for large targets like the Milky Way core, the Andromeda galaxy, or the Heart & Soul nebulae that don't fit in a single frame.

### How it works

1. **Stack each panel separately first.** Point your scope at panel 1, capture your lights, stack them in AstroStacker as usual.
2. **Plate solve each stacked panel.** Go to the Plate Solve tab and solve each stacked FITS file. This embeds the WCS astrometry that tells the mosaic engine exactly where each panel sits in the sky.
3. **Repeat** for panels 2, 3, 4, etc. — with some overlap between adjacent panels (20-30% is ideal).

### Building the mosaic

1. Click the **Mosaic** tab in the sidebar
2. Click **Add Panels** and select all your plate-solved stacked FITS files (2 or more)
3. Set the **Output Path** — where to save the finished mosaic
4. Click **Build Mosaic**
5. Watch the log as panels are loaded, reprojected onto a common grid, and blended together
6. The finished mosaic opens in the preview panel when complete

### Tips for best mosaics

- **Plate solving is required.** The mosaic engine uses the embedded WCS — a panel without astrometry can't be placed.
- **Overlap matters.** Aim for 20-30% overlap between adjacent panels so the feathered blending has something to work with.
- **Match exposures.** Try to use the same exposure time, gain, and processing for each panel so brightness matches.
- **Stack and calibrate each panel first.** Don't mosaic raw subs — stack each panel to reduce noise, then mosaic the stacks.

---

## Setting Up Your Astrometry.net API Key

The plate solver uses Astrometry.net (https://nova.astrometry.net), a free online service. You need an API key to use it.

### How to get your free API key:

1. Go to **https://nova.astrometry.net**
2. Click **Sign Up** and create a free account
3. Once logged in, go to **My Profile** (click your username, top right)
4. Your **API Key** is displayed on your profile page — copy it
5. Paste it into the **API Key** field in the Plate Solve tab
6. The app remembers your key automatically — you only need to do this once

> **Note:** An API key is required for plate solving. The key is stored locally on your computer (macOS Preferences / Windows Registry) and is never shared or bundled with the app.

---

## Using the Tools Menu

### Blink Comparator (Tools > Blink Comparator)

The blink comparator loads all your light frames and lets you cycle through them one at a time. Use it to:
- Spot satellite trails, aircraft, or clouds before stacking
- Identify frames with poor tracking or focus
- Check that alignment is working correctly

Controls: Previous/Next buttons, Play/Stop for auto-cycling, and a speed slider.

### FITS Header Viewer (Tools > View FITS Header)

Inspect the full FITS header of any file — useful for checking:
- Camera settings (exposure, temperature, gain)
- WCS astrometry keywords after plate solving
- Any metadata embedded by your capture software

### Session Save/Load (File > Save/Load Session)

Save your entire session — all file lists, settings, and options — to a JSON file. Load it later to pick up exactly where you left off. Great for multi-night imaging projects.

---

## Supported File Formats

| Format | Read | Write |
|--------|------|-------|
| FITS (.fits, .fit, .fts) | Yes | Yes |
| XISF (.xisf) | Yes | Yes |
| TIFF (.tiff, .tif) | — | Export only |
| PNG (.png) | — | Export only |

Output stacked files are saved as 32-bit floating-point FITS — ready for further processing in PixInsight, Siril, GIMP, or any tool that reads FITS.

TIFF and PNG exports have auto-stretch applied (PixInsight-style screen transfer function) and are ready to share directly.

---

## Tips for Best Results

- **More frames = better results.** 20-50 light frames is a good starting point. 100+ is even better.
- **Always take darks.** Dark frames at the same temperature and exposure as your lights dramatically reduce noise.
- **Use flats if possible.** Flat frames correct for vignetting, dust spots, and uneven illumination.
- **Save and reuse master frames.** The app saves master darks and flats automatically. Next session, load them with the Master Dark/Flat buttons instead of re-adding individual frames.
- **Enable auto-reject** if you have more than a handful of subs. PSF fitting catches both blurry AND trailed frames automatically.
- **Use gradient removal** if you observe from suburban areas — it makes a big difference.
- **Median stacking** is the safe default. For 15+ frames, try **Sigma Clip** or **Winsorized Sigma** to reject satellite trails and hot pixels.
- **Noise-Weighted stacking** is great if your subs have varying sky conditions — cleaner exposures contribute more.
- **Try Sharpen (Deconvolution)** on well-exposed stacks — start with "Light" and increase if your stack has good SNR. Tightens star profiles and reveals fine detail.
- **Denoise after stacking** with the Non-Local Means option — start with "Light" and increase if needed. Denoising runs after deconvolution, cleaning up any amplified noise.
- **Drizzle stacking** works best when your mount dithers between exposures. If you don't dither, standard stacking is better.
- **Plate solve your results** to embed astrometry data. PixInsight's SPCC requires this for accurate colour calibration.
- **Save sessions** before closing the app so you can reload your file lists and settings next time.

---

## System Requirements

| | Minimum | Recommended |
|---|---------|-------------|
| **macOS** | macOS 11 (Big Sur) | macOS 13+ (Ventura or later) |
| **Windows** | Windows 10 (64-bit) | Windows 11 |
| **Linux** | Ubuntu 22.04 / Debian 12 / Mint 21 | Ubuntu 24.04+ |
| **Raspberry Pi** | Pi 4 (4GB), 64-bit Raspberry Pi OS | Pi 5 (8GB), 64-bit Bookworm |
| **RAM** | 8 GB (4 GB on Pi) | 16 GB+ |
| **Storage** | 500 MB for the app | + space for your image files |

---

## Reporting Bugs

Found a bug or have a suggestion? Please email:

**compute@asv.org.au**

When reporting a bug, please include:
- What you were doing when it happened
- The error message (if any) from the progress log
- Your operating system (macOS or Windows) and version
- The number and type of frames you were stacking

---

## Acknowledgements

- [Astrometry.net](https://nova.astrometry.net) — plate solving engine
- [Astropy](https://www.astropy.org) — FITS I/O and astronomy utilities
- [Astroalign](https://astroalign.readthedocs.io) — automatic frame alignment
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — graphical interface
- [scikit-image](https://scikit-image.org) — star detection and image processing

---

## License

**© 2024 Andrew Hayes. All rights reserved.**

Haysey's Astrostacker v0.3.0 and all subsequent versions are copyright Andrew Hayes.

Free to download and use for personal, non-commercial astrophotography. Repackaging, redistribution, or commercial use of any kind requires prior written permission from the copyright holder.

For licensing enquiries: **haysey@haysey.id.au**

See the [LICENSE](LICENSE) file for full terms.

---

*Built with care for the Astronomical Society of Victoria and the wider astronomy community.*
