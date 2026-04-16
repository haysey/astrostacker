"""Application-wide constants and defaults."""

SUPPORTED_EXTENSIONS = (".fits", ".fit", ".fts", ".xisf")
FILE_FILTER = "Astro Images (*.fits *.fit *.fts *.xisf);;FITS Files (*.fits *.fit *.fts);;XISF Files (*.xisf);;All Files (*)"

STACKING_METHODS = (
    "mean", "median", "sigma_clip", "winsorized_sigma",
    "percentile_clip", "weighted_mean", "noise_weighted",
    "min", "max",
)
DEFAULT_STACKING_METHOD = "median"
DEFAULT_SIGMA_LOW = 2.5
DEFAULT_SIGMA_HIGH = 2.5
DEFAULT_SIGMA_ITERS = 5
DEFAULT_PERCENTILE_LOW = 10.0
DEFAULT_PERCENTILE_HIGH = 10.0

# Camera types
CAMERA_MONO = "mono"
CAMERA_COLOUR = "colour"
CAMERA_TYPES = (CAMERA_MONO, CAMERA_COLOUR)
DEFAULT_BAYER_PATTERN = "RGGB"

APP_NAME = "Haysey's Astrostacker"
APP_VERSION = "0.3.0"
