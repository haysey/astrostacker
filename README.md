# Haysey's Astrostacker v1.0.0 — Beta Bronze

A free, easy-to-use astrophotography image stacking application for macOS, Windows, Linux, and Raspberry Pi. Built for members of the Astronomical Society of Victoria (ASV) and the wider amateur astronomy community.

No coding or command-line experience required — just download, unzip, and run.

---

## What's New in v1.0.0 — Beta Bronze

The first full release of Haysey's Astrostacker. Everything in one place.

**Stacking & processing:**
- **9 stacking methods** — Mean, Median, Sigma Clip, Winsorized Sigma, Percentile Clip, Weighted Mean, Noise-Weighted Mean, Min, Max
- **Drizzle stacking** — 2× resolution upscale for well-dithered sub-exposures
- **PSF fitting** — proper 2D Gaussian star profile measurement per frame. Catches blurry AND trailed frames during auto-rejection.
- **PSF-informed sharpening** — positive-only unsharp masking keyed to your measured star FWHM. Brightens fine detail without ever creating dark halos. Light / Medium / Strong presets.
- **Non-Local Means denoising** — post-stack noise reduction. Preserves star profiles and nebula structure. Light / Medium / Strong presets. No GPU required.
- **Weighted Mean stacking** — automatically weights sharper, rounder frames higher using PSF quality scores.
- **Local normalisation** — per-frame gradient removal before stacking, so changing sky glow between frames doesn't contaminate the stack
- **Gradient removal** — post-stack light pollution subtraction
- **Auto frame rejection** — PSF-based scoring discards blurry and trailed frames before stacking
- **Auto-crop** — trims alignment edge artifacts from the final stack

**Calibration:**
- Dark subtraction, flat correction, dark flat support
- Automatic master dark and master flat building (saved alongside your output for reuse)
- Load pre-built master frames to skip rebuilding each session
- Auto-resize mismatched calibration frames — use masters from a different session or binning without errors

**Colour cameras:**
- Automatic Bayer demosaicing (RGGB, GRBG, GBRG, BGGR)
- Full colour pipeline through calibration, alignment, stacking, and post-processing

**UX:**
- Drag and drop files or folders directly onto the file panels
- Folder import — scans an entire directory for supported files
- Smart settings — only relevant controls are shown for your current configuration
- Session save/restore — save your file lists and settings, reload them next time
- Preview panel — view your stacked result before exporting
- Histogram panel — inspect pixel distribution of the result
- Plate solve — identify exactly where in the sky your image points (astrometry.net)
- Mosaic stitching — combine plate-solved panels into a wide-field image
- FITS header viewer — inspect raw FITS header data
- Blink comparator — flip between frames to spot trailing, gradients, or artefacts
- Export as FITS, TIFF, or PNG

**Visual:**
- Dark theme UI, orange accents, card-style panels, animated progress bar

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

> **Tested on:** Ubuntu 22.04, Ubuntu 24.04, Debian 12, Linux Mint 21+

The easiest way to install on Linux is the one-command installer. It handles everything automatically — system libraries, Python environment, desktop shortcut, and launcher.

**Step 1 — Open a Terminal**

- On **Ubuntu**: Press `Ctrl + Alt + T` on your keyboard, or right-click the desktop and choose **Open Terminal**
- On **Linux Mint**: Click the **Terminal** icon in the taskbar, or go to Menu > Terminal
- On **Debian**: Press `Ctrl + Alt + T`, or find Terminal in your applications menu

You should see a black window with a blinking cursor. This is where you type the commands below.

**Step 2 — Run the installer**

Copy and paste each line below into the terminal, pressing **Enter** after each one:

```bash
wget https://raw.githubusercontent.com/haysey/astrostacker/main/install_linux.sh
```
```bash
chmod +x install_linux.sh
```
```bash
./install_linux.sh
```

> **What is this doing?**
> - `wget` downloads the installer script
> - `chmod +x` makes it executable (permission to run)
> - `./install_linux.sh` runs it
>
> The installer will ask for your password once (to install system libraries). This is normal — type your login password and press Enter. You won't see the characters as you type, that's also normal.

**Step 3 — Wait for it to finish**

The installer will show progress as it works through 5 steps. The first run downloads and installs packages, so it may take 5–10 minutes depending on your internet speed. You'll see:

```
[1/5] Installing system packages...
[2/5] Getting source code...
[3/5] Setting up Python environment...
[4/5] Creating launcher...
[5/5] Creating desktop shortcut...
Installation complete!
```

**Step 4 — Launch the app**

Once complete, you can launch it two ways:
- Find **Haysey's AstroStacker** in your applications menu (under Science or Graphics)
- Or type this in the terminal: `~/astrostacker/run.sh`

**Updating to a newer version**

Open a terminal and run:
```bash
cd ~/astrostacker && git pull
```

**Troubleshooting**

If the app doesn't launch, try running it from the terminal so you can see any error messages:
```bash
~/astrostacker/run.sh
```

If you see an error about missing libraries, run the installer again — it will fix them:
```bash
./install_linux.sh
```

If you see a "permission denied" error on the desktop shortcut:
- Right-click the shortcut on your desktop
- Click **Properties** (or **Allow Launching**)
- Tick **Allow executing file as program**

---

#### Raspberry Pi (Pi 4 or Pi 5 — 64-bit Raspberry Pi OS)

> **Requirements:** Raspberry Pi 4 (4GB RAM minimum) or Pi 5, running **64-bit Raspberry Pi OS** (Bookworm recommended). This will **not** work on 32-bit Raspberry Pi OS.

> **How do I know if I have 64-bit?** Open a terminal and type `uname -m`. If it says `aarch64` you have 64-bit. If it says `armv7l` you have 32-bit and will need to reinstall the OS.

Raspberry Pi uses a dedicated installer that installs Qt6 from the system package manager — this is more reliable than a pre-built binary on ARM hardware.

**Step 1 — Open a Terminal**

Click the **Terminal** icon in the taskbar at the top of the screen, or go to the Raspberry Pi menu > Accessories > Terminal.

**Step 2 — Run the installer**

Copy and paste each line into the terminal, pressing **Enter** after each one:

```bash
wget https://raw.githubusercontent.com/haysey/astrostacker/main/install_rpi.sh
```
```bash
chmod +x install_rpi.sh
```
```bash
./install_rpi.sh
```

> The installer will ask for your password once to install system packages. Type your password (you won't see it as you type) and press Enter.

**Step 3 — Wait for it to finish**

On a Raspberry Pi, the first install takes longer than on a desktop PC — **10 to 20 minutes** is normal because it's compiling some packages for the ARM processor. You'll see it working through 5 steps. Let it run until you see:

```
Installation complete!
```

Don't close the terminal window while it's running.

**Step 4 — Launch the app**

Once complete, look for the **Haysey's AstroStacker** icon on your desktop. Double-click it to launch.

Alternatively, type this in the terminal:
```bash
~/astrostacker/run.sh
```

**Updating to a newer version**

Open a terminal and run:
```bash
cd ~/astrostacker && git pull
```

**Troubleshooting**

If the app doesn't open when you double-click the desktop icon:
- Right-click the icon and choose **Execute** or **Run**
- Or open a terminal and type `~/astrostacker/run.sh` to see any error messages

If you see errors about missing packages, run the installer again:
```bash
./install_rpi.sh
```

> **Performance note:** A Raspberry Pi 4 (4GB+) or Pi 5 will happily stack 20–30 light frames. Stacking is CPU-bound so it takes longer than a desktop PC — that's expected. For best performance, disable Drizzle and keep frame counts moderate. The Pi 5 is noticeably faster than the Pi 4 for this kind of work.

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
- Enter your **telescope focal length** and **camera pixel size** in the FOV Calculator, then click **Calculate & Apply** — this is strongly recommended. Without scale hints, solving can take 10+ minutes or time out entirely. See [Finding Your Telescope Focal Length and Camera Pixel Size](#finding-your-telescope-focal-length-and-camera-pixel-size) below.
- Click **Solve** and wait for results

> **Auto plate solve:** If you tick **Auto plate solve after stacking** in Settings, the scale hints you set in the Plate Solve tab are used automatically. Set them up once in the Plate Solve tab before using this option.

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

## Finding Your Telescope Focal Length and Camera Pixel Size

The Plate Solve tab has an **FOV Calculator** that dramatically speeds up plate solving. It needs just two numbers: your telescope focal length and your camera pixel size. You only need to enter these once — the app remembers them every session.

### Telescope Focal Length (mm)

This is usually printed on the telescope tube or in the manual. Look for a label like **f=800mm** or **FL=1000mm**.

| Telescope type | Example focal length |
|---|---|
| 80mm refractor f/6 | 480 mm |
| 100mm refractor f/9 | 900 mm |
| 8" SCT at f/10 | 2032 mm |
| 200/1000 Newtonian | 1000 mm (the second number) |
| Reducer/Barlow | Changes the effective value — use the effective FL |

If in doubt, search **"[your telescope model] focal length"** online.

### Camera Pixel Size (µm)

Every camera sensor has a different pixel size. Using the wrong value — even another model from the same brand — will cause plate solving to fail or time out. You must use your camera's exact specification.

**How to find it:**

1. **Manufacturer's product page:** Search **"[your camera model] specifications"** and look for **Pixel Size** or **Pixel Pitch** in the spec table.

2. **ZWO ASI cameras:** Go to [astronomy-imaging-camera.com](https://astronomy-imaging-camera.com), find your model, and check the specs.
   - Common ZWO values: ASI294MC Pro = **4.63 µm**, ASI183MC = **2.40 µm**, ASI1600MC = **3.80 µm**, ASI533MC Pro = **3.76 µm**, ASI2600MC Pro = **3.76 µm**

3. **Canon / Nikon / Sony DSLRs:** Search **"[camera model] pixel size"** — e.g. Canon 600D/T3i = 4.30 µm, Nikon D5300 = 3.92 µm, Sony A7 III = 5.95 µm.

4. **Capture software:** Sharpcap, NINA, and KStars/Ekos often display the pixel size in the camera properties panel when your camera is connected.

5. **Cloudy Nights forum:** Search your camera model — pixel sizes are frequently listed in imaging reports.

Round to 2 decimal places. Common values range from about 1.85 µm (small sensors) to 9.0 µm (large-format cameras).

Once entered, click **Calculate & Apply** and the app works out your image scale and sets the solver bounds automatically. You should only need to do this once unless you change cameras or telescopes.

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

**haysey@haysey.id.au**

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

Haysey's Astrostacker v1.0.0 and all subsequent versions are copyright Andrew Hayes.

Free to download and use for personal, non-commercial astrophotography. Repackaging, redistribution, or commercial use of any kind requires prior written permission from the copyright holder.

For licensing enquiries: **haysey@haysey.id.au**

See the [LICENSE](LICENSE) file for full terms.

---

*Built with care for the Astronomical Society of Victoria and the wider astronomy community.*
