# 002: Gate 0 performance targets

Date: 2026-11-27. Status: chosen by the owner ("Balanced"). **This does not approve Gate 0**, does not start Gate 1, and does not permit transmission.

## Context
Gate 0 still needed a resolution definition, reference target, minimum range, pass/fail limits and update rate (M-02 to M-05 in [requirements](../requirements.md)). The architect agent proposed options.

## Options

| Item | Conservative | Balanced | Ambitious |
|---|---|---|---|
| Two equal targets, 115 MHz | 3.5 m, Hann | 2.5 m, rectangular | 2.2 m, rectangular |
| Trihedral reflector leg edge | 0.20 m | 0.15 m | 0.15 m; person reported only |
| Minimum range | 5 m | 3 m | 2 m |
| Range error, 95 % of trials | 0.50 m at SNR 15 dB or more | 0.20 m at SNR 20 dB or more | 0.10 m at SNR 30 dB or more |
| Pd / Pfa | 0.80 / 1e-3 | 0.90 / 1e-4 | 0.95 / 1e-6 |
| Update rate, chirps per frame | 1 Hz, 16 | 10 Hz, 16 | 20 Hz, 32 |

## Choice: Balanced
Every value is a **target (assumption)**. None has been shown to be achievable on hardware. Gate 1 may propose changes, which need the owner's approval.

| Item | Target | Conditions |
|---|---|---|
| Resolution (M-02) | Two equal targets shown separately at 2.5 m spacing or less at 115 MHz; 2.0 m or less at 150 MHz (simulation and conducted only) | Rectangular window. Peaks within c/(8B) of truth, dip of at least 3 dB. The range bin stays 1.303 m / 0.999 m (calculated) |
| Reference target (M-03) | Triangular trihedral corner reflector, 0.15 m leg edge, static | Peak radar cross-section about 0.79 m² at 5.7875 GHz (calculated, 4πa⁴/(3λ²); textbook formula, source page not checked) |
| Range span (M-03) | 3 m minimum, evaluated to 30 m | |
| Accuracy (M-04) | Error of 0.20 m or less in 95 % of trials | SNR 20 dB or more after Hann FFT and integration. One isolated static reflector, at least the resolution spacing from other strong reflectors, one offset calibration at a distance not used as a test point. To pass at 95 % confidence: at least 59 independent trials with no failure (calculated) |
| Detection (M-04) | Pd 0.90 or more at Pfa 1e-4 | Pfa is per range cell per frame. Steady target (Swerling 0). About 21 cells from 3 to 30 m at 115 MHz |
| Update rate (M-05) | 10 Hz or more, 16 chirps per frame | Chirp 1 ms and 100 kSPS are assumptions (R-05, R-09) |
| Display and latency (M-05) | Live display, latency 200 ms or less | Accepted by the owner |
| Processing window | Rectangular for the resolution test only; Hann otherwise | |

## Basis (calculated, ideal; not feasibility)
- Detection: 11.7 dB SNR needed for a steady target with a known threshold, white Gaussian noise, square-law detector, one integrated look. Adaptive threshold (CFAR) loss for this target model was not calculated.
- Detection test size: 29 detections with no miss, or at least 279 of 300 (passes about 95 % of the time if true Pd is 0.95). Zero false alarms in 30 000 independent noise-only cells bounds Pfa at 1e-4 (95 % confidence).
- Two-target simulation by the architect agent: with the rectangular window, 2.0 m is needed near 10-28 m and 2.1 m at 3 m. Noiseless. The script is not saved in the repo, and the existing tests do not assert the two-target table. Gate 1 must reproduce both with tests.
- The accuracy limit rests on a noise-only Monte Carlo from the same unsaved script, not independently rechecked.
- Not modelled: sweep nonlinearity, leakage, clutter, multipath, phase noise, baseband and ADC noise.

## Owner's answers (2026-11-27)

| Topic | Answer |
|---|---|
| Two-target requirement and rectangular-window test | Accepted after an explanation: 2.5 m at 115 MHz, rectangular window. The explanation said this does not show the same separation with Hann (about 3.2 m ideal, calculated) |
| Static reflector or person / moving targets | Not answered. Balanced assumes a static reflector for pass/fail |
| 3 m minimum range | Accepted |
| Test space | No specific site yet. A field is possible |
| Live display | Wanted, with graphs and all relevant information. A preliminary version was started in a separate session, simulated data only. 200 ms latency accepted |
| Equipment | Coaxial cable to SMA (length, type and connectors not recorded). VNA and spectrum analyzer possibly in university labs (access and 6 GHz coverage unconfirmed). Laser distance meter probably available. Reflectors: owner was not familiar with them. Delay line: none reported |
| Test time | As much as needed |

## Legal basis: M-01 stays open
The owner reports that, from their own research and from a faculty member with experience in radar projects, there should be no legal limitation for a project used only inside the university's installations. No document, article or written statement is on file.

This does not close M-01:
- The articles read in [decision 001](001-sweep.md) showed no exemption for university or on-premises use. That reading was partial and is not legal advice.
- Free-spectrum use (Art. 33-II) may cover the 115 MHz sweep, but whether FMCW radar qualifies under the 5725-5850 MHz entry and meets its limits is still unverified.
- An off-campus field would fall outside the "inside the installations" premise.

To close it: a citable rule or a written answer from the university or the regulator (CRT) that covers FMCW, the frequencies, the power and the test site. Until then, work stays on simulation, cables and dummy loads.

Whether Gate 6 may pass on conducted evidence alone if M-01 is still open is **not decided**.

## Consequences
- M-02 to M-05 have chosen targets.
- The 2.5 m two-target limit is coarser than the charter's original "~1 m".
- Gate 1 needs: saved and tested simulations for two-target separation, accuracy and detection, with noise, leakage and nonlinearity; and a link budget (M-06). No link budget exists yet.
- Possible later needs: two reflectors, splitters, attenuators, delay cable (about 42 m of coax to represent 30 m at an assumed velocity factor of 0.7; loss unknown), isolation hardware, a distance reference. Nothing is to be bought without the owner's confirmation.
- [requirements](../requirements.md) and the [G0 review](../gates/G0.md) include these targets.
