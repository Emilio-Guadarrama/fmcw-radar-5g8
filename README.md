# fmcw-radar-5g8 (SPECULA-1)

Low-cost FMCW radar in the 5.725-5.875 GHz ISM band. Chirp from a PLL (ADF4159) plus VCO, ESP32-S3 for capture and USB, Python for range processing.

**Status:** set-up (2026-11). No hardware built yet. All numbers below are design targets, not measurements.

## Targets (assumptions, to be validated in simulation)

| Parameter | Target |
|---|---|
| Sweep bandwidth | 150 MHz (5.725-5.875 GHz) |
| Range resolution | c/(2B) = 1.0 m |
| Max range (indoor demo) | ~30 m |
| Chirp time | ~1 ms (S = 1.5e11 Hz/s, beat ~30 kHz at 30 m) |
| Budget | ~$134 parts per board (BOM estimate, USD, qty 1) |
| Timeline | ~2-3 months to a measured demo |

## Layout

```
docs/       charter, requirements, decisions, gate reviews
sim/        Python signal chain, PLL loop filter, openEMS
hardware/   Altium project + review exports (netlist, BOM, Gerbers)
firmware/   ESP32-S3 firmware
software/   Python processing and plotting
tests/      bring-up procedures and measurement logs
bom/        BOM workbook
```

## Process

Work advances through approval gates G0-G6 (spec, simulation, architecture/BOM, schematic review, layout review, bring-up, demo). See [docs/charter.md](docs/charter.md).

## Regulatory note

5.875-6.0 GHz is outside the ISM band. Early tests use cables and dummy loads; nothing is radiated before checking Mexico's IFT rules.

## License

Not yet chosen.
