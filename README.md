# fmcw-radar-5g8 (SPECULA-1)

Low-cost 5.8 GHz FMCW radar. Chirp from a PLL (ADF4159) plus VCO, ESP32-S3 for capture and USB, Python for range processing.

**Status:** set-up (2026-11). No hardware built yet. All numbers below are design targets, not measurements.

## New here? Start with the learning guide

This is a learning project: we build it to learn how radar works, and we document it so others can learn with us. **[Open the interactive guide online](https://emilio-guadarrama.github.io/fmcw-radar-5g8/)**: the whole project in plain language, with analogies, diagrams you can play with, and a glossary. No download needed. The same content is also in [docs/learn/](docs/learn/README.md).

## Targets (assumptions, to be validated in simulation)

| Parameter | Target |
|---|---|
| Radiated sweep | 115 MHz (5.730-5.845 GHz), see [decision 001](docs/decisions/001-sweep.md) |
| Range bin | c/(2B) = 1.30 m (two equal targets need more separation, see [requirements](docs/requirements.md)) |
| Conducted tests only | 150 MHz (5.725-5.875 GHz), bin 1.00 m |
| Max range (indoor demo) | ~30 m |
| Chirp time | ~1 ms (115 MHz: S = 1.15e11 Hz/s, beat ~23 kHz at 30 m) |
| Budget | ~$134 parts per board (BOM estimate, USD, qty 1) |
| Timeline | ~2-3 months to a measured demo |

## Layout

```
docs/       charter, requirements, decisions, gate reviews, learning guide (docs/learn/)
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

The May 2025 IFT free-spectrum inventory lists 5.725-5.850 GHz; whether it covers an FMCW radar is unconfirmed. University use is not an exemption. Early tests use cables and dummy loads; nothing is radiated before checking Mexico's rules (CRT, formerly IFT).

## License

- Hardware design source in `hardware/`: [CERN-OHL-P-2.0](hardware/LICENSE).
- Everything else in this repository, including code, docs and the BOM: [MIT](LICENSE).

Third-party material keeps its own terms. Neither license gives permission to transmit radio signals.
