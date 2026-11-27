# sim/

Baseband FMCW model: chirp, dechirp, noise, ADC quantization, range FFT. **Simulation only.** Model limits are listed at the top of [fmcw.py](fmcw.py).

The default RadarConfig is the 115 MHz radiated design case. CONDUCTED_150MHZ is for simulation and cable tests only ([decision 001](../docs/decisions/001-sweep.md)).

Not covered (Gate 1 or later): PLL loop filter, chirp settling and nonlinearity, phase noise, TX-RX leakage, clutter, analog filtering, link budget, antennas, Doppler.

## Run (PowerShell, from the repository root)

```powershell
uv venv --python 3.13 .venv
```

```powershell
uv pip install --python .venv -r sim/requirements.txt
```

```powershell
.venv\Scripts\python.exe -m pytest sim -q
```

```powershell
.venv\Scripts\python.exe sim/run_sim.py
```

If `uv` reports `invalid peer certificate: UnknownIssuer`, add `--system-certs` so it verifies against the Windows certificate store.

Plots and `summary.md` are written to `sim/out/`.
