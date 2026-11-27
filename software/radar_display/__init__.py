"""SPECULA-1 preliminary live display. Simulated data only; no transmitter control."""

import sys
from pathlib import Path

# The signal model and range FFT live in sim/fmcw.py and are reused, not copied.
# sim/ is not an installed package, so add it to the import path here, once.
_SIM_DIR = str(Path(__file__).resolve().parents[2] / "sim")
if _SIM_DIR not in sys.path:
    sys.path.append(_SIM_DIR)
