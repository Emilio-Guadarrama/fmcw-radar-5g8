# FMCW radar 5.8 GHz: project charter

Status: set-up, draft 1 (2026-11-26). Owner: Emilio. Every contributor reads this file first.

## Goal
Build a small FMCW radar in the 5.725-5.875 GHz ISM band that measures range (and, later, velocity) of indoor targets. Deliverables: a measured range demo, Python processing, a documented design.

## Locked decisions (2026-11-26)
- First demo: indoor, up to ~30 m, ~1 m range resolution.
- Chirp generator: PLL-based (ADF4159 plus VCO), linear sweep.
- Timeline: ~2-3 months to a working demo.
- Approval: the owner approves at every design gate. Nothing is sent to fabrication, flashed, or purchased without explicit confirmation.
- EDA: working default is Altium for the main board. Antenna boards may use KiCad + openEMS. Revisit at Gate 2.
- Power amplifier: none in v1 (low power, indoor, bench first).
- VNA must reach 6 GHz (a NanoVNA V2 stops at 3 GHz).

## Amendment 2026-11-27: sweep ([decision 001](decisions/001-sweep.md))
- Radiated design case: 5.730-5.845 GHz, B = 115 MHz, range bin about 1.30 m. This replaces the ~1 m target for radiated tests.
- 150 MHz (5.725-5.875 GHz): simulation, and cables / dummy load only, unless an authorization covers it.
- A university project is not an exemption. This amendment does not permit transmission.
- The 150 MHz figures below are the original baseline.

## Initial requirements (assumptions to be validated by simulation, not verified)
- Sweep B = 150 MHz. Range resolution c/(2B) = 1.0 m.
- Chirp time ~1 ms. Slope S = B/T = 1.5e11 Hz/s.
- Beat frequency at 30 m: f = 2RS/c = 30 kHz. ADC rate of ~100 kSPS or more is enough for v1.
- ESP32-S3 over USB should carry this data rate (to be confirmed at Gate 2).
- 5.875-6.0 GHz is outside the ISM band and not used in v1. The May 2025 IFT free-spectrum inventory lists only up to 5.850 GHz (see amendment). Check Mexico's IFT rules before radiating anything; first tests use cables / loopback.

## Block diagram (v1)
PLL (ADF4159) + VCO (HMC431LP4E candidate) -> splitter -> TX antenna. RX antenna -> LNA -> mixer (LO from splitter) -> baseband amp -> ADC -> ESP32-S3 -> USB -> Python (range FFT).

## Budget (see bom/FMCW_6GHz_BOM.xlsx; USD; qty 1; excludes shipping, duty, IVA)
- Parts per board ~$134, one-time ~$49, 2 builds ~$318.
- Verified prices: VCO $27.50, LNA $15.44, mixer $18.14, PLL $9-11 (LCSC), ADC $17.99 (LCSC). Everything else is an estimate.

## Roles
1. Manager: owns the charter, task list, gates.
2. Architect: requirements, link budget, block diagram, part selection.
3. Simulator: Python signal chain, PLL loop filter, antenna and line simulation.
4. Hardware developer: schematic, stackup, layout.
5. Schematic inspector: independent review of exports. Never reviews its own work.
6. Firmware / software developer: ESP32-S3 firmware, Python processing.
7. Validation lead: bring-up plan, measurement procedures, safety.

## Gates (owner approves each)
- G0 spec and requirements.
- G1 simulation proves the chirp / processing parameters.
- G2 architecture, BOM, EDA choice.
- G3 schematic reviewed by the inspector.
- G4 layout reviewed; explicit confirmation before ordering PCBs.
- G5 bring-up results (chirp generator, then receive chain, then antennas).
- G6 measured demo.

## Open items
- Spectrum analyzer availability (unconfirmed).
- Cheaper LNA / ADC / op-amp candidates to shortlist.
- Antennas: bench ducks first, printed FR-4 patches later; sweep must match the antenna band.
