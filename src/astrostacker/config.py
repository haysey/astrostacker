"""Application-wide constants and defaults."""

SUPPORTED_EXTENSIONS = (".fits", ".fit", ".fts", ".xisf")
FILE_FILTER = "Astro Images (*.fits *.fit *.fts *.xisf);;FITS Files (*.fits *.fit *.fts);;XISF Files (*.xisf);;All Files (*)"

STACKING_METHODS = ("mean", "median", "sigma_clip", "min", "max")
DEFAULT_STACKING_METHOD = "sigma_clip"
DEFAULT_SIGMA_LOW = 2.5
DEFAULT_SIGMA_HIGH = 2.5
DEFAULT_SIGMA_ITERS = 5

APP_NAME = "Haysey's Astrostacker"
APP_VERSION = "0.1.0"
