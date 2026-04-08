# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Hayseys Astrostacker.

Works on macOS, Linux, and Windows.
Run with: pyinstaller astrostacker.spec
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None

# Only the specific hidden imports we actually need
hidden_imports = [
    # Astropy - only io.fits and stats
    'astropy',
    'astropy.io',
    'astropy.io.fits',
    'astropy.io.fits.hdu',
    'astropy.io.fits.column',
    'astropy.io.fits.card',
    'astropy.io.fits.header',
    'astropy.io.fits.convenience',
    'astropy.stats',
    'astropy.stats.sigma_clipping',
    'astropy.units',
    'astropy.utils',
    'astropy.utils.data',
    'astropy.config',
    # XISF
    'xisf',
    # Astroalign
    'astroalign',
    # Scipy (ndimage.zoom)
    'scipy',
    'scipy.ndimage',
    'scipy.ndimage._interpolation',
    'scipy.optimize',
    'scipy.spatial',
    # Scikit-image (used by astroalign)
    'skimage',
    'skimage.transform',
    'skimage.feature',
    'skimage.measure',
    # PyQt6
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    # Core
    'numpy',
    'requests',
    'certifi',
]

# Collect data files and package metadata needed at runtime
datas = (
    collect_data_files('astropy') +
    collect_data_files('certifi') +
    copy_metadata('astropy') +
    copy_metadata('numpy') +
    copy_metadata('xisf')
)

a = Analysis(
    ['src/astrostacker/main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'pytest',
        'astropy.visualization.wcsaxes',
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Platform-specific settings
if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Hayseys Astrostacker',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon='icon.icns',
        target_arch=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name='Hayseys Astrostacker',
    )
    app = BUNDLE(
        coll,
        name='Hayseys Astrostacker.app',
        icon='icon.icns',
        bundle_identifier='com.astrostacker.app',
        info_plist={
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleName': "Haysey's Astrostacker",
            'NSHighResolutionCapable': True,
        },
    )
elif sys.platform == 'win32':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Hayseys Astrostacker',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon='icon.ico',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name='Hayseys Astrostacker',
    )
else:
    # Linux
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Hayseys Astrostacker',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name='Hayseys Astrostacker',
    )
