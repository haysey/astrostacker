Haysey's Astrostacker v1.0.0 -- Beta Bronze
============================================

A free, easy-to-use astrophotography image stacking application for
macOS, Windows, Linux, and Raspberry Pi. Built for members of the
Astronomical Society of Victoria (ASV) and the wider amateur astronomy
community.

No coding or command-line experience required -- just download, unzip,
and run.


------------------------------------------------------------------------
WHAT'S NEW IN v1.0.0 -- BETA BRONZE
------------------------------------------------------------------------

The first full release of Haysey's Astrostacker. Everything in one place.

Stacking & processing:
  - 9 stacking methods: Mean, Median, Sigma Clip, Winsorized Sigma,
    Percentile Clip, Weighted Mean, Noise-Weighted Mean, Min, Max
  - Drizzle stacking -- 2x resolution upscale for well-dithered subs
  - PSF fitting -- proper 2D Gaussian star profile measurement per frame.
    Catches blurry AND trailed frames during auto-rejection.
  - PSF-informed sharpening -- positive-only unsharp masking keyed to
    your measured star FWHM. Brightens fine detail without creating dark
    halos. Light / Medium / Strong presets.
  - Non-Local Means denoising -- post-stack noise reduction. Preserves
    star profiles and nebula structure. Light / Medium / Strong presets.
    No GPU required.
  - Weighted Mean stacking -- automatically weights sharper, rounder
    frames higher using PSF quality scores.
  - Local normalisation -- per-frame gradient removal before stacking
  - Gradient removal -- post-stack light pollution subtraction
  - Auto frame rejection -- discards blurry and trailed frames
  - Auto-crop -- trims alignment edge artifacts from the final stack

Calibration:
  - Dark subtraction, flat correction, dark flat support
  - Automatic master dark and master flat building
  - Load pre-built master frames to skip rebuilding each session
  - Auto-resize mismatched calibration frames

Colour cameras:
  - Automatic Bayer demosaicing (RGGB, GRBG, GBRG, BGGR)
  - Full colour pipeline through calibration, alignment, stacking,
    and post-processing

UX:
  - Drag and drop files or folders directly onto the file panels
  - Folder import -- scans an entire directory for supported files
  - Smart settings -- only relevant controls are shown
  - Session save/restore -- reload your file lists and settings later
  - Preview panel, histogram panel, plate solve, mosaic stitching
  - FITS header viewer, blink comparator
  - Export as FITS, TIFF, or PNG

Visual:
  - Dark theme UI, orange accents, card-style panels


------------------------------------------------------------------------
WHAT DOES IT DO?
------------------------------------------------------------------------

Astrophotography images straight from the camera are noisy and faint.
Stacking combines many exposures of the same target to dramatically
reduce noise and reveal detail that no single frame can show.

Haysey's Astrostacker handles the entire workflow:

   1.  Load       -- your light frames (and optional darks, flats,
                     dark flats)
   2.  Calibrate  -- subtract dark current and correct for vignetting
   3.  Reject     -- PSF-based scoring discards blurry/trailed frames
   4.  Debayer    -- convert raw Bayer data to full colour
   5.  Align      -- automatically register all frames to a reference
   6.  Stack      -- combine aligned frames using your choice of method
   7.  Crop       -- auto-trim alignment edge artifacts
   8.  Gradient   -- subtract light pollution gradients
   9.  Sharpen    -- PSF-informed sharpening (Light/Medium/Strong)
  10.  Denoise    -- Non-Local Means noise reduction (Light/Medium/Strong)
  11.  Plate Solve -- identify exactly where in the sky your image points
  12.  Mosaic     -- stitch multiple plate-solved panels into a wide field
  13.  Export     -- save as FITS, TIFF, or PNG


------------------------------------------------------------------------
FEATURES
------------------------------------------------------------------------

Stacking & Calibration
  - One-click stacking -- load your files, click Start, and you're done
  - 9 stacking methods (see above)
  - Drizzle stacking -- 2x resolution enhancement for dithered subs
  - Calibration frames -- supports darks, flats, and dark flats
  - Load pre-built masters -- skip rebuilding them each session
  - Master frames saved automatically alongside your output for reuse
  - Colour camera support -- automatic Bayer demosaicing
  - Mono camera support -- works with dedicated astronomy cameras
  - Automatic frame alignment using astroalign (star-based registration)

Processing
  - PSF-based frame rejection -- fits 2D Gaussian profiles to stars,
    measuring FWHM (sharpness) and eccentricity (elongation). Rejects
    both blurry AND trailed frames automatically.
  - PSF-informed sharpening -- tightens star profiles and enhances
    nebula detail. Positive-only: nothing is ever darkened, no dark halos.
  - Light pollution gradient removal -- fits and subtracts a smooth
    background surface to remove sky gradients
  - Local normalisation -- per-frame gradient removal before stacking
  - Non-Local Means denoising -- classical NLM noise reduction with
    automatic noise estimation. Preserves star profiles and nebula structure.
  - Auto-crop -- trims black/NaN borders left by frame alignment

Plate Solving
  - Integrated plate solver using Astrometry.net
  - WCS astrometry embedded for PixInsight SPCC and other tools
  - Auto plate solve -- optionally runs automatically after stacking
  - Annotated results -- view solved images with labelled deep-sky objects

Mosaic Building
  - WCS-based panel stitching -- uses astrometric coordinates, not
    star matching, so it works even on sparse or dissimilar fields
  - Feathered blending -- smooth seamless transitions across panels
  - Dedicated Mosaic tab -- runs on a background thread with live log

Tools & Export
  - Live histogram -- real-time pixel distribution with stats
  - Blink comparator -- cycle through frames to spot satellite trails,
    clouds, or bad subs before stacking
  - FITS header viewer -- inspect all metadata keywords in any FITS file
  - Export to TIFF/PNG -- one-click export with auto-stretch applied
  - Session save/load -- save all file lists and settings to a file
  - Live preview with auto-stretch or linear stretch, multiple zoom levels

General
  - Frame status bar -- shows accepted/rejected counts after stacking
  - Audio notifications -- chime on completion, alert on errors
  - Opens maximized -- automatically fills your screen at launch
  - Apple Silicon optimised -- multi-core parallel processing
  - FITS and XISF support -- reads and writes standard astro image formats
  - Beautiful dark UI with procedural starfield background


------------------------------------------------------------------------
DOWNLOADS
------------------------------------------------------------------------

Download the latest version from the Releases page on GitHub:
  https://github.com/haysey/astrostacker/releases

Files available:
  - Hayseys-Astrostacker-macOS-AppleSilicon.zip  (Mac made 2021 or later)
  - Hayseys-Astrostacker-macOS-Intel.zip         (Mac made before 2021)
  - Hayseys-Astrostacker-Windows-x64.zip         (Windows 10/11, 64-bit)
  - Hayseys-Astrostacker-Linux-x64.tar.gz        (Ubuntu/Debian/Mint)
  - Raspberry Pi: run install_rpi.sh (see install instructions below)

No Python installation required. Everything is bundled -- just download,
unzip, and run.

Not sure which Mac version you need?
Click the Apple menu > About This Mac
  - "Chip: Apple M..." means Apple Silicon -- use the AppleSilicon build
  - "Processor: Intel..." means Intel -- use the Intel build


------------------------------------------------------------------------
INSTALLATION
------------------------------------------------------------------------

macOS (Apple Silicon or Intel)
  1. Download and unzip the correct version for your Mac
  2. Drag "Hayseys Astrostacker.app" to your Applications folder
  3. First launch only -- macOS will block the app because it is not
     signed by Apple:
       - Right-click the app > click Open > click Open again on the dialog
       - You only need to do this once. After that it opens normally.
  4. If you get a "damaged" error, open Terminal and run:
       xattr -cr "/Applications/Hayseys Astrostacker.app"
     Then open the app normally.


Windows
  1. Download and unzip Hayseys-Astrostacker-Windows-x64.zip
  2. Open the folder and double-click "Hayseys Astrostacker.exe"
  3. Windows Defender may block extraction or launch -- this is a false
     positive caused by the way the app is packaged. The app is safe.
     To fix:
       - Open Settings > Privacy & Security > Windows Security
       - Click Virus & threat protection > Manage settings
       - Scroll to Exclusions > Add or remove exclusions
       - Click Add an exclusion > Folder > select the extracted folder
       - Re-extract the zip and it should work fine
  4. If Windows SmartScreen appears:
       - Click "More info"
       - Click "Run anyway"
       - You only need to do this once.


Linux (Ubuntu, Debian, Mint)
  Tested on: Ubuntu 22.04, Ubuntu 24.04, Debian 12, Linux Mint 21+

  Step 1 -- Open a Terminal
    - Ubuntu: Press Ctrl + Alt + T, or right-click the desktop and
      choose "Open Terminal"
    - Linux Mint: Click the Terminal icon in the taskbar, or go to
      Menu > Terminal
    - Debian: Press Ctrl + Alt + T, or find Terminal in your apps menu

  Step 2 -- Run the installer
    Copy and paste each line into the terminal, pressing Enter after each:

      wget https://raw.githubusercontent.com/haysey/astrostacker/main/install_linux.sh
      chmod +x install_linux.sh
      ./install_linux.sh

    The installer will ask for your password once to install system
    libraries. Type your login password and press Enter. You won't see
    the characters as you type -- that is normal.

  Step 3 -- Wait for it to finish (5-10 minutes)
    You will see:
      [1/5] Installing system packages...
      [2/5] Getting source code...
      [3/5] Setting up Python environment...
      [4/5] Creating launcher...
      [5/5] Creating desktop shortcut...
      Installation complete!

  Step 4 -- Launch the app
    - Find "Haysey's AstroStacker" in your applications menu
    - Or type in the terminal:  ~/astrostacker/run.sh

  Updating to a newer version:
    Open a terminal and run:  cd ~/astrostacker && git pull

  Troubleshooting:
    If the app doesn't launch, run it from the terminal to see errors:
      ~/astrostacker/run.sh
    If you see errors about missing libraries, run the installer again:
      ./install_linux.sh
    If you see "permission denied" on the desktop shortcut:
      Right-click > Properties (or Allow Launching) > tick "Allow
      executing file as program"


Raspberry Pi (Pi 4 or Pi 5 -- 64-bit Raspberry Pi OS)
  Requirements: Raspberry Pi 4 (4 GB RAM minimum) or Pi 5, running
  64-bit Raspberry Pi OS (Bookworm recommended). Will NOT work on
  32-bit Raspberry Pi OS.

  How do I know if I have 64-bit?
    Open a terminal and type:  uname -m
    If it says "aarch64" you have 64-bit. If it says "armv7l" you have
    32-bit and will need to reinstall the OS first.

  Step 1 -- Open a Terminal
    Click the Terminal icon in the taskbar, or go to
    Raspberry Pi menu > Accessories > Terminal.

  Step 2 -- Run the installer
    Copy and paste each line into the terminal, pressing Enter after each:

      wget https://raw.githubusercontent.com/haysey/astrostacker/main/install_rpi.sh
      chmod +x install_rpi.sh
      ./install_rpi.sh

    The installer will ask for your password once. Type it (you won't
    see it as you type) and press Enter.

  Step 3 -- Wait for it to finish (10-20 minutes is normal on a Pi)
    The Pi compiles some packages for the ARM processor, so it takes
    longer than a desktop PC. Let it run until you see:
      Installation complete!
    Do not close the terminal window while it is running.

  Step 4 -- Launch the app
    Double-click the "Haysey's AstroStacker" icon on your desktop.
    Or type in the terminal:  ~/astrostacker/run.sh

  Updating to a newer version:
    Open a terminal and run:  cd ~/astrostacker && git pull

  Troubleshooting:
    If the desktop icon doesn't open the app:
      Right-click the icon and choose Execute or Run
      Or open a terminal and type ~/astrostacker/run.sh to see errors
    If you see errors about missing packages:
      Run the installer again:  ./install_rpi.sh

  Performance note: A Raspberry Pi 4 (4 GB+) or Pi 5 will happily
  stack 20-30 light frames. Stacking is CPU-bound so it takes longer
  than a desktop PC -- that is expected. For best performance, disable
  Drizzle and keep frame counts moderate.


------------------------------------------------------------------------
QUICK START GUIDE
------------------------------------------------------------------------

1. Load Your Images
   - Click Add under Light Frames and select your light frames (FITS or
     XISF), or use Add Folder to import an entire directory
   - You can also drag and drop files or folders onto any frame list
   - Optionally add Darks, Flats, and Dark Flats for calibration
   - OR click Master Dark / Master Flat to load pre-built master frames
   - The more light frames you add, the better your result will be

2. Configure Settings
   - Camera Type: select Mono or Colour (Bayer)
   - Bayer Pattern: if using a colour camera, select your sensor's
     pattern (usually RGGB)
   - Stacking Method: Median is the default and safe for beginners.
     Sigma Clip is recommended for 15+ frames.
   - Output Path: where to save the stacked result

3. Processing Options (Optional)
   - Auto-reject blurry frames: automatically score and reject poor
     quality frames
   - Remove light pollution gradient: great for suburban observing sites
   - Local normalisation: remove gradients from each frame individually
   - Sharpen: tightens star profiles and reveals fine detail.
     Choose Light, Medium, or Strong.
   - Denoise: smooth noisy backgrounds while preserving detail.
     Choose Light, Medium, or Strong.
   - Auto-crop stacking edges: cleans up black borders from alignment
   - Drizzle (2x resolution): higher-resolution output (best with
     dithered subs)

4. Stack!
   - Click Start Processing
   - Watch the progress log as your frames are calibrated, scored,
     aligned, and stacked
   - A chime will sound when processing is complete
   - Your stacked image appears in the Preview panel

5. Plate Solve (Optional)
   - Go to the Plate Solve tab
   - Enter your Astrometry.net API key (see section below)
   - Enter your telescope focal length and camera pixel size in the
     FOV Calculator, then click "Calculate and Apply" -- this is strongly
     recommended. Without it, solving can take 10+ minutes or fail.
     See "Finding Your Telescope Focal Length and Camera Pixel Size" below.
   - Click Solve and wait for results
   - This embeds WCS data into your FITS file for tools like PixInsight

   Note: if you tick "Auto plate solve after stacking" in Settings,
   the scale hints you set in the Plate Solve tab are used automatically.
   Set them up once in the Plate Solve tab before using auto plate solve.

6. Export Your Result
   - Use File > Export as TIFF or File > Export as PNG for a stretched
     image ready to share
   - Use Save As in the preview toolbar for raw FITS or XISF data
   - Your stacked FITS file is also saved automatically to the output path


------------------------------------------------------------------------
BUILDING A MOSAIC
------------------------------------------------------------------------

A mosaic combines several overlapping panels into one wide-field image.

How to build one:
  1. Stack each panel separately first (point scope at panel 1, capture
     lights, stack as usual)
  2. Plate solve each stacked panel (embeds the WCS astrometry)
  3. Repeat for panels 2, 3, 4 etc. with 20-30% overlap between panels
  4. Click the Mosaic tab in the sidebar
  5. Click Add Panels and select all your plate-solved stacked FITS files
  6. Set the Output Path and click Build Mosaic
  7. The finished mosaic opens in the preview panel when complete

Tips:
  - Plate solving is required. Panels without astrometry can't be placed.
  - Aim for 20-30% overlap between adjacent panels.
  - Use the same exposure time, gain, and processing for each panel.
  - Stack and calibrate each panel first -- don't mosaic raw subs.


------------------------------------------------------------------------
SETTING UP YOUR ASTROMETRY.NET API KEY
------------------------------------------------------------------------

The plate solver uses Astrometry.net (https://nova.astrometry.net),
a free online service. You need a free API key to use it.

How to get your free API key:
  1. Go to https://nova.astrometry.net
  2. Click Sign Up and create a free account
  3. Once logged in, go to My Profile (click your username, top right)
  4. Your API Key is displayed on your profile page -- copy it
  5. Paste it into the API Key field in the Plate Solve tab
  6. The app remembers your key automatically -- you only need to do
     this once

Note: The key is stored locally on your computer and is never shared.


------------------------------------------------------------------------
FINDING YOUR TELESCOPE FOCAL LENGTH AND CAMERA PIXEL SIZE
------------------------------------------------------------------------

The Plate Solve tab has an FOV Calculator that dramatically speeds up
plate solving. It needs just two numbers: your telescope focal length
and your camera pixel size. You only need to enter these once -- the
app remembers them every session.

TELESCOPE FOCAL LENGTH (mm)
  This is usually printed on the telescope tube or in the manual.
  It is the number after "f=" on the tube label.

  Examples:
    - A Celestron 8" SCT at f/10 has a focal length of 2032 mm
    - A common 80mm refractor "f/6" has 480 mm focal length
    - A 200/1000 Newtonian has 1000 mm focal length (the second number)
    - Focal reducers and Barlows change this -- use the effective value

  If in doubt, search your telescope model name + "focal length" online.

CAMERA PIXEL SIZE (micrometres, µm)
  Every camera sensor has a different pixel size. Using the wrong value
  (even another camera in the same brand range) will cause plate solving
  to fail or time out. You must use YOUR camera's exact specification.

  How to find it:
    1. Check the manufacturer's product page or spec sheet for your
       camera model. Search "[your camera model] specifications".

    2. For ZWO ASI cameras: go to https://astronomy-imaging-camera.com,
       find your camera model, and look for "Pixel Size" in the specs.
       Examples: ASI294MC Pro = 4.63 µm, ASI183MC = 2.40 µm,
       ASI1600MC = 3.80 µm, ASI533MC Pro = 3.76 µm.

    3. For Canon or Nikon DSLRs: search "[camera model] pixel size".
       Examples: Canon 600D/T3i = 4.30 µm, Canon 80D = 3.71 µm,
       Nikon D5300 = 3.92 µm, Sony A7III = 5.95 µm.

    4. In capture software (Sharpcap, NINA, KStars/Ekos): the camera
       properties panel often displays the pixel size when your camera
       is connected.

    5. On the IDAS or Cloudy Nights forums, search your camera model --
       pixel sizes are frequently listed in imaging reports.

  Round to 2 decimal places. Common values range from 1.85 µm (small
  sensors) to 9.0 µm (large-format cameras).

Once entered, click "Calculate and Apply" and the app works out your
image scale and sets the plate solver bounds automatically. You should
only need to do this once unless you change cameras or telescopes.


------------------------------------------------------------------------
TOOLS MENU
------------------------------------------------------------------------

Blink Comparator (Tools > Blink Comparator)
  Loads all your light frames and lets you cycle through them one at a
  time. Use it to:
    - Spot satellite trails, aircraft, or clouds before stacking
    - Identify frames with poor tracking or focus
  Controls: Previous/Next buttons, Play/Stop for auto-cycling, speed slider.

FITS Header Viewer (Tools > View FITS Header)
  Inspect the full FITS header of any file. Useful for checking:
    - Camera settings (exposure, temperature, gain)
    - WCS astrometry keywords after plate solving
    - Any metadata embedded by your capture software

Session Save/Load (File > Save Session / Load Session)
  Save your entire session -- all file lists, settings, and options --
  to a file. Load it later to pick up exactly where you left off.


------------------------------------------------------------------------
SUPPORTED FILE FORMATS
------------------------------------------------------------------------

  Format                          Read    Write
  FITS (.fits, .fit, .fts)        Yes     Yes
  XISF (.xisf)                    Yes     Yes
  TIFF (.tiff, .tif)              --      Export only
  PNG (.png)                      --      Export only

Output stacked files are saved as 32-bit floating-point FITS, ready for
further processing in PixInsight, Siril, GIMP, or any FITS-compatible tool.

TIFF and PNG exports have auto-stretch applied and are ready to share.


------------------------------------------------------------------------
TIPS FOR BEST RESULTS
------------------------------------------------------------------------

  - More frames = better results. 20-50 light frames is a good start.
    100+ is even better.
  - Always take darks. Dark frames at the same temperature and exposure
    as your lights dramatically reduce noise.
  - Use flats if possible. They correct for vignetting, dust, and uneven
    illumination.
  - Save and reuse master frames. The app saves them automatically.
    Next session, load them with the Master Dark/Flat buttons.
  - Enable auto-reject if you have more than a handful of subs. PSF
    fitting catches both blurry AND trailed frames automatically.
  - Use gradient removal if you observe from suburban areas.
  - Median stacking is the safe default. For 15+ frames, try Sigma Clip
    or Winsorized Sigma to reject satellite trails and hot pixels.
  - Noise-Weighted stacking is great if your subs have varying sky
    conditions -- cleaner exposures contribute more.
  - Try Sharpen on well-exposed stacks -- start with "Light" and
    increase if your stack has good signal. Tightens star profiles and
    reveals fine detail.
  - Denoise after stacking with Non-Local Means -- start with "Light"
    and increase if needed.
  - Drizzle stacking works best when your mount dithers between
    exposures. If you don't dither, standard stacking is better.
  - Plate solve your results to embed astrometry data. PixInsight's SPCC
    requires this for accurate colour calibration.
  - Save sessions before closing so you can reload file lists and
    settings next time.


------------------------------------------------------------------------
SYSTEM REQUIREMENTS
------------------------------------------------------------------------

  Platform        Minimum                       Recommended
  macOS           macOS 11 Big Sur              macOS 13+ Ventura
  Windows         Windows 10 (64-bit)           Windows 11
  Linux           Ubuntu 22.04 / Debian 12      Ubuntu 24.04+
  Raspberry Pi    Pi 4 (4 GB), 64-bit OS        Pi 5 (8 GB), Bookworm
  RAM             8 GB (4 GB on Pi)             16 GB+
  Storage         500 MB for the app            + space for image files


------------------------------------------------------------------------
REPORTING BUGS
------------------------------------------------------------------------

Found a bug or have a suggestion? Please email:

  haysey@haysey.id.au

When reporting a bug, please include:
  - What you were doing when it happened
  - The error message (if any) from the progress log
  - Your operating system and version
  - The number and type of frames you were stacking


------------------------------------------------------------------------
ACKNOWLEDGEMENTS
------------------------------------------------------------------------

  Astrometry.net  -- plate solving engine (https://nova.astrometry.net)
  Astropy         -- FITS I/O and astronomy utilities
  Astroalign      -- automatic frame alignment
  PyQt6           -- graphical interface
  scikit-image    -- star detection and image processing


------------------------------------------------------------------------
LICENSE
------------------------------------------------------------------------

Copyright 2024 Andrew Hayes. All rights reserved.

Haysey's Astrostacker v1.0.0 and all subsequent versions are copyright
Andrew Hayes.

Free to download and use for personal, non-commercial astrophotography.
Repackaging, redistribution, or commercial use of any kind requires
prior written permission from the copyright holder.

For licensing enquiries: haysey@haysey.id.au

See the LICENSE file for full terms.


------------------------------------------------------------------------
Built with care for the Astronomical Society of Victoria
and the wider astronomy community.
------------------------------------------------------------------------
