# software/: preliminary live display

**Simulated data only.** No hardware is needed or used. The app has no transmitter control, and neither sweep is cleared to transmit ([decision 001](../docs/decisions/001-sweep.md)). It was asked for early, while Gate 0 is not approved. It passes no gate and demonstrates no performance target.

## Run (PowerShell, from the repository root)

```powershell
.venv\Scripts\python.exe software/run_display.py
```

Your browser opens `http://127.0.0.1:8765/`. Press Ctrl+C in the terminal to stop. Options: `--port 8766`, `--no-browser`.

The project convention is Python 3.11+. This was tested **only on Python 3.13.13**, and the pinned `numpy` 2.5.5 needs Python 3.12 or newer (PyPI metadata), so running on 3.11 would need an older `numpy` and has not been tried. The only runtime dependency is `numpy`. If `.venv` does not exist yet, create it first:

```powershell
uv venv --python 3.13 .venv
```

```powershell
uv pip install --python .venv -r software/requirements.txt
```

(If `uv` reports `invalid peer certificate: UnknownIssuer`, add `--system-certs`.)

## Build a Windows .exe (optional)

This makes one file, `software/dist/specula-display.exe`, which carries Python and `numpy` inside it. It still shows simulated data only. Install the build tools once, then build:

```powershell
uv pip install --python .venv -r software/requirements-build.txt
```

```powershell
.venv\Scripts\python.exe software/build_exe.py
```

Double-clicking the `.exe` should open a console window and show the display in your browser. Press Ctrl+C in that window to stop it (tested from a terminal). Double-clicking, the automatic browser opening and stopping by closing the window have not been tested with the `.exe`. Only one copy can use port 8765, so stop any other running display first, or start with `--port 8766`.

- The `.exe` is a snapshot. Rebuild it after changing the code.
- Git ignores `software/dist/`, so a build is not committed.
- It was tested only on the PC that built it, run from an empty folder with Python removed from the search path. It has **not** been tried on a PC without Python.
- It is not code-signed, so Windows or antivirus software on another PC may warn about it or block it.

## Test and format

```powershell
.venv\Scripts\python.exe -m pytest software sim -q
```

```powershell
.venv\Scripts\python.exe -m ruff check software
```

```powershell
.venv\Scripts\python.exe -m ruff format software
```

`pytest` covers the Python code. The drawing code in `radar_display/web/` has **no automated tests**.

## What is on screen

On a window at least 1200 x 680 pixels, everything fits on one screen: the warning banner, the settings in use, the live readings, three graphs, and a side column with the controls and four tabs (Targets, Settings, Goals, Glossary). Smaller windows scroll. The page uses fonts already on the PC and loads nothing from the internet.

| Item | Meaning |
|---|---|
| Strongest target, SNR | Distance and estimated signal-to-noise ratio of the loudest detection. The table lists all of them |
| Update rate | Frames processed per second, measured on this PC |
| Latency | Recording time (16 ms, calculated) plus the measured delay from the end of the frame to the browser's next drawing slot after the graphs are drawn. It does not include the monitor's own delay or any USB transfer |
| Dropped frames | Gaps in the source's frame numbers. Frames the screen skips while processing keeps up are not counted |
| Range spectrum | Echo strength against distance, with one threshold step and one dot per tested range cell. White ticks show the simulation's true positions |
| Waterfall | The spectrum over the last 12 s, in dB above the noise floor. A dark gap means no row was drawn: lost frames, or the screen was frozen |
| Raw beat signal | One chirp as sampled, and the 16-chirp average |
| Settings in use | Sweep, chirp time, sample rate, chirps per frame and window in the top bar; the full list in the Settings tab |
| Goals tab | The [decision 002](../docs/decisions/002-performance-targets.md) targets |

The controls change the simulated scene and the processing window. Detection and display use Hann. The rectangular window is for looking at the two-target resolution case. The app does not give a pass or fail for that test: use the criterion in decision 002.

## Layout

| File | Role |
|---|---|
| `radar_display/source.py` | `FrameSource` interface and the `Frame` it returns |
| `radar_display/simulated.py` | Simulated source, using `sim/fmcw.py` |
| `radar_display/processing.py` | Integration, noise estimate, threshold, detections, SNR |
| `radar_display/metrics.py` | Update rate, dropped frames, processing time |
| `radar_display/snapshot.py` | The data sent to the page, including the calculated settings and a copy of the decision 002 targets (update it if that decision changes) |
| `radar_display/engine.py`, `server.py` | Processing loop and local web server (`127.0.0.1` only) |
| `radar_display/web/` | The page. It draws and measures screen delay; it does no radar calculations |

`sim/fmcw.py` supplies the signal model, windows and range FFT, and is imported, not copied. The one overlap is the peak refinement: `fmcw.estimate_range_m` only finds the strongest peak, so `processing.py` applies the same method to every peak, and a test checks that the two agree.

## Processing

1. **Integrate:** average the 16 chirps, then range FFT (12.0 dB gain for a still target, calculated).
2. **Noise:** subtract the average from each chirp. Still targets cancel, and what is left estimates the noise in each range cell.
3. **Threshold:** for Gaussian noise that is independent between chirps, `threshold power = a * Pn` with `a = (M-1) * (Pfa^(-1/(M-1)) - 1)`. For M = 16 and Pfa = 1e-4 that is 11.0 dB above the noise (calculated).
4. **Detect:** a range cell above threshold that is a local peak and is at least 6 dB above the window leakage that stronger detections could cause (the 6 dB is an assumption). Cells from 3 to 30 m, within half a cell, are tested: 22 cells at 115 MHz.

Check of step 3 (simulation, one-off run of 60 000 noise-only frames, 1.32 million cells, 10 mV noise, 115 MHz, Hann): set 1e-2, 1e-3, 1e-4; measured 9.99e-3, 1.03e-3, 9.7e-5. The tests repeat a smaller version at 1e-2 and 1e-3. This counts cells above the threshold. It says nothing about real hardware noise.

This method was picked for the preliminary display. It is **not** a project decision; Gate 1 should choose the detector.

## Limits to keep in mind

- **Moving targets:** averaging assumes nothing moves during a frame. At 5.8 GHz, a few millimetres of movement during the 16 ms changes the echo phase a lot, so a real moving target can weaken or vanish, and its motion also raises the noise estimate. The "moving reflector" scene jumps between frames and holds still within each, so it **does not show this**.
- **Anything that holds still is a "target".** On real hardware that includes TX-RX leakage, cables and walls. None of these are modelled, and there is no background subtraction.
- Echo voltage (0.4 V at 3 m, falling as 1/range^2) and noise (10 mV RMS) are **assumptions**, not a link budget. SNR and maximum distance on screen say nothing about the real radar.
- The model limits in [sim/fmcw.py](../sim/fmcw.py) apply: ideal chirp, no phase noise, no analog filters, so echoes past the sampling limit would alias.
- Chirps are assumed to run back to back (repetition is not decided). Simulated frames come at 12.5 per second (assumption).
- A weak target close to a much stronger one can be hidden by the leakage rule.
- **Latency is not verified against the 200 ms target.** In the browser pane used for checking, early samples read 72 to 104 ms. While the pane was hidden, drawing was throttled and samples reached about 1 s, even though the page did not always report itself hidden. Timed separately there: data reached the page a median 9 ms after capture, and one redraw took 0.8 ms. Check the number in your own browser with the window visible. A hidden or minimised window can read high.
- Latency uses this PC's clock in both Python and the browser, so it only works with both on the same PC.

## Still missing

- **ESP32-S3 USB source.** Write a `FrameSource` subclass with `is_simulated = False`, then select it in `run_display.py`. The USB protocol, firmware, sample scaling to volts, chirp-to-sample triggering (M-10), frame numbering and capture timestamps are all undefined. Without a shared clock, latency would start when data reaches the PC. Review the on-screen text and "simulated" labels at the same time: they were written for simulated data.
- How the real sweep settings will be reported with each frame. The sweep selector changes only the simulation.
- Recording and replay of frames.
- Background (static clutter) removal, calibration offset, and a decision on moving targets and Doppler.
- Tests for the decision 002 accuracy, detection and two-target targets. Those belong to Gate 1.
- Automated tests of the web page.
