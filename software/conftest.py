# Its presence puts software/ on pytest's import path, so tests can import
# radar_display. Importing the package then makes sim/fmcw.py importable.
import radar_display  # noqa: F401
