# Haysey's Astrostacker

A free, easy-to-use astrophotography image stacking application for macOS and Windows. Built to help amateur astronomers produce clean, deep-sky images from their raw camera frames — no coding or command-line experience required.

![App Screenshot](screenshots/main-window.png)
*Main window with starfield background and Southern Cross logo*

---

## What Does It Do?

Astrophotography images straight from the camera are noisy and faint. **Stacking** combines many exposures of the same target to dramatically reduce noise and reveal detail that no single frame can show.

Haysey's Astrostacker handles the entire workflow:

1. **Load** your light frames (and optional darks, flats, dark flats)
2. **Calibrate** — subtract dark current and correct for vignetting/dust
3. **Debayer** — convert raw Bayer data to full colour (for colour cameras)
4. **Align** — automatically register all frames to a reference star field
5. **Stack** — combine aligned frames using your choice of method
6. **Plate Solve** — identify exactly where in the sky your image points
7. **Save** — output a calibrated, stacked FITS file ready for processing in PixInsight, Siril, or any astro tool

---

## Features

- **One-click stacking** — load your files, click Start, and you're done
- **Colour camera support** — automatic Bayer demosaicing (RGGB, GRBG, GBRG, BGGR)
- **Mono camera support** — works with dedicated astronomy cameras too
- **Multiple stacking methods** — Mean, Median, Sigma Clip, Min, Max
- **Automatic frame alignment** — star-based registration using astroalign
- **Calibration frames** — supports darks, flats, and dark flats
- **Plate solving** — integrated Astrometry.net solver identifies objects in your image
- **WCS astrometry** — embeds world coordinate system data for PixInsight SPCC and other tools
- **Auto plate solve** — optionally plate solves automatically after stacking
- **Annotated results** — view solved images with labelled deep-sky objects (Messier, NGC, IC, etc.)
- **Live preview** — view your stacked result with auto-stretch, multiple zoom levels
- **Apple Silicon optimised** — multi-core parallel processing on M1/M2/M3/M4 Macs
- **FITS and XISF support** — reads and writes standard astro image formats
- **Audio notifications** — bell chime when processing completes
- **Astronomy news ticker** — scrolling headlines from Space.com, Sky & Telescope, and SpaceNews
- **Beautiful UI** — dark theme with procedural starfield background

---

## Downloads

Download the latest version for your platform:

| Platform | Download |
|----------|----------|
| **Windows (64-bit)** | [Hayseys-Astrostacker-Windows-x64.zip](https://github.com/haysey/astrostacker/actions) |
| **macOS (Apple Silicon)** | [Hayseys-Astrostacker-macOS-AppleSilicon.zip](https://github.com/haysey/astrostacker/actions) |
| **macOS (Intel)** | [Hayseys-Astrostacker-macOS-Intel.zip](https://github.com/haysey/astrostacker/actions) |

To download: go to **Actions** → click the latest successful run (green tick) → scroll to **Artifacts** → download for your platform.

> **No Python installation required.** Everything is bundled — just download, unzip, and run.

---

## Getting Started

### Installation

#### macOS (Apple Silicon or Intel)

1. Download and unzip the correct version for your Mac
2. Drag **Hayseys Astrostacker.app** to your Applications folder (or wherever you like)
3. **First launch only** — macOS will block the app because it's not signed by Apple:
   - Right-click the app → click **Open** → click **Open** again on the dialog
   - You only need to do this once. After that, it opens normally.
4. If you still get a "damaged" error, open **Terminal** and run:
   ```
   xattr -cr "/Applications/Hayseys Astrostacker.app"
   ```
   Then open the app normally.

> **Which version do I need?**
> - If your Mac was made in **2021 or later**, download the **Apple Silicon** version
> - If your Mac was made **before 2021**, download the **Intel** version
> - Not sure? Click the Apple menu → **About This Mac** → look for "Chip: Apple M..." (Apple Silicon) or "Processor: Intel..." (Intel)

#### Windows

1. Download and unzip `Hayseys-Astrostacker-Windows-x64.zip`
2. Open the folder and double-click **Hayseys Astrostacker.exe**
3. If Windows SmartScreen appears:
   - Click **More info**
   - Click **Run anyway**
   - You only need to do this once.

---

### Quick Start Guide

#### 1. Load Your Images

![File Panel](screenshots/file-panel.png)

- Click **Add Lights** and select your light frames (FITS or XISF)
- Optionally add **Darks**, **Flats**, and **Dark Flats** for calibration
- The more light frames you add, the better your result will be

#### 2. Configure Settings

![Settings Panel](screenshots/settings-panel.png)

- **Camera Type** — select Mono or Colour (Bayer)
- **Bayer Pattern** — if using a colour camera, select your sensor's pattern (usually RGGB)
- **Stacking Method** — Sigma Clip is recommended (rejects satellites, planes, hot pixels)
- **Output Path** — where to save the stacked result

#### 3. Stack!

- Click **Start Processing**
- Watch the progress log as your frames are calibrated, debayered, aligned, and stacked
- A bell chime will sound when processing is complete
- Your stacked image appears in the Preview tab

#### 4. Plate Solve (Optional)

![Plate Solve Panel](screenshots/platesolve-panel.png)

Plate solving identifies exactly where your image points in the sky and which objects are in the frame. This also embeds WCS (World Coordinate System) data into your FITS file, which is required by tools like PixInsight's SPCC (SpectrophotometricColorCalibration).

- Go to the **Plate Solve** tab
- Enter your **Astrometry.net API key** (see below)
- Select an image or tick **Auto plate solve after stacking**
- Click **Solve** and wait for results

---

## Setting Up Your Astrometry.net API Key

The plate solver uses [Astrometry.net](https://nova.astrometry.net), a free online service. You'll need an API key to use it.

### How to get your free API key:

1. Go to **https://nova.astrometry.net**
2. Click **Sign Up** and create a free account
3. Once logged in, go to **My Profile** (click your username, top right)
4. Your **API Key** is displayed on your profile page — copy it
5. Paste it into the **API Key** field in the Plate Solve tab
6. The app remembers your key automatically — you only need to do this once

> **Note:** An API key is required for plate solving. The key is stored locally on your computer and is never shared.

---

## Supported File Formats

| Format | Read | Write |
|--------|------|-------|
| FITS (.fits, .fit, .fts) | Yes | Yes |
| XISF (.xisf) | Yes | No |

Output files are saved as 32-bit floating-point FITS — ready for further processing in PixInsight, Siril, GIMP, or any tool that reads FITS.

---

## Tips for Best Results

- **More frames = better results.** 20-50 light frames is a good starting point.
- **Always take darks.** Dark frames at the same temperature and exposure as your lights dramatically reduce noise.
- **Use flats if possible.** Flat frames correct for vignetting, dust spots, and uneven illumination.
- **Sigma Clip stacking** is recommended — it automatically rejects outliers like satellite trails and hot pixels.
- **Plate solve your results** to embed astrometry data. PixInsight's SPCC requires this for accurate colour calibration.

---

## Screenshots

> **Note:** Add your own screenshots to a `screenshots/` folder in the repository. Suggested screenshots:
> - `main-window.png` — full app window showing the starfield background
> - `file-panel.png` — the file loading panel with some frames loaded
> - `settings-panel.png` — the settings panel showing camera and stacking options
> - `platesolve-panel.png` — the plate solve tab
> - `solve-result.png` — an annotated plate solve result
> - `preview.png` — the stacked image preview

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

## System Requirements

| | Minimum | Recommended |
|---|---------|-------------|
| **macOS** | macOS 11 (Big Sur) | macOS 13+ (Ventura or later) |
| **Windows** | Windows 10 (64-bit) | Windows 11 |
| **RAM** | 8 GB | 16 GB+ |
| **Storage** | 500 MB for the app | + space for your image files |

---

## Acknowledgements

- [Astrometry.net](https://nova.astrometry.net) — plate solving engine
- [Astropy](https://www.astropy.org) — FITS I/O and astronomy utilities
- [Astroalign](https://astroalign.readthedocs.io) — automatic frame alignment
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — graphical interface

---

## License

This application is provided free of charge for personal use by members of the astronomical community.

---

*Built with care for the astronomy community.*
