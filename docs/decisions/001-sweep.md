# 001: Radar sweep

Date: 2026-11-27. Status: chosen. The owner delegated the choice (use what is most convenient; if there is another reason to stay within the band, say so and apply what is best). This does not approve Gate 0.

## Context
The charter's 5.725-5.875 GHz sweep goes 25 MHz above the 5725-5850 MHz entry in the May 2025 IFT free-spectrum inventory ([requirements](../requirements.md), section 1). The owner asked whether a university project makes this acceptable.

## A university project is not an exemption
Read from the [Ley en Materia de Telecomunicaciones y Radiodifusión](https://www.diputados.gob.mx/LeyesBiblio/pdf/LMTR.pdf) (DOF 16-07-2025). I extracted the text with a temporary script and read only passages found by keyword search. This is not legal advice.

- Art. 33-II: free spectrum may be used without concession or authorization, under the regulator's guidelines.
- Art. 48: private use of bands that are **not** free use requires a concession.
- Art. 159-VII: using bands for experimentation, feasibility tests of technologies in development, or temporary equipment tests requires authorization from the Comisión Reguladora de Telecomunicaciones (CRT).
- Art. 160-III: that authorization lasts up to seven years, renewable, subject to availability.
- Art. 161: it is free for non-profit social, educational, scientific or academic projects. **Free of charge, but still required.**
- Art. 289: those who provide services without concession or authorization, "or by any other means invade or obstruct" general communication routes, lose the equipment used. I do not know how this would apply to a low-power student radar.
- Transitory 18: earlier IFT acts remain in effect.

I did not check CRT rules issued under this law, the application procedure, or any inventory newer than May 2025.

## Other reasons to stay inside
- I have not checked who is assigned or operating at 5850-5875 MHz, so I cannot rule out interference.
- The demo and documentation are public; an in-band design is easier to defend in a university review.
- The cost is moderate, and the sweep is a PLL setting, so it should be reversible in software (limits to be checked at Gate 1 and Gate 5).

## Options
A: 150 MHz, 5.725-5.875. B: 125 MHz, 5.725-5.850, no guards. C: 115 MHz, 5.730-5.845, 5 MHz guards.

## Choice
- **Radiated design case: C.** The guard size is an assumption.
- **150 MHz: simulation, and conducted tests through cables and a dummy load only.**
- Possible route to radiating 150 MHz: an Art. 159-VII authorization that covers it.

## Consequences (calculated, ideal simulation)
| Quantity | 150 MHz | 115 MHz |
|---|---|---|
| c/(2B) | 0.999 m | 1.303 m |
| Two equal targets, rectangular / Hann | 1.6 / 2.5 m | 2.0 / 3.2 m |
| Beat frequency at 30 m | 30 021 Hz | 23 016 Hz |

The charter's "~1 m" becomes a range bin of about 1.3 m for radiated tests.

Choosing C does not clear the radar to transmit. Still open: whether FMCW radar qualifies under the 5725-5850 MHz entry (its cited instruments are unread), whether the power and EIRP limits are met, and whether real emissions meet the out-of-band limits (needs a spectrum analyzer, unconfirmed).
