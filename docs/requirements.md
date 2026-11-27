# SPECULA-1 requirements

Status: **Gate 0 draft, not approved** (2026-11-27). Source: [charter.md](charter.md).

## Labels

- **assumption**: a design choice, target or outside value not yet proven for this design. Locked charter decisions carry this label too: deciding a value does not verify it.
- **calculated**: follows from a formula or simulation, and is only as good as its inputs. "Sim" means [sim/](../sim/) with an ideal chirp.

No value here is **measured**, and no **datasheet** has been checked. c = 299 792 458 m/s.

## 1. Regulatory finding and sweep choice

The IFT inventory of free-spectrum bands (May 2025 edition, [PDF](https://www.ift.org.mx/sites/default/files/contenidogeneral/espectro-radioelectrico/inventariodebandasdefrecuenciasclasificadascomoespectrolibre-mayo2025.pdf), page 27 of 36) has an entry for **5725-5850 MHz**. I found no entry for 5850-5875 MHz in its segment headings. The charter's 5.725-5.875 GHz sweep therefore goes **25 MHz above the listed band**. The charter's "ISM band" label alone does not show that Mexico permits transmission there.

Values quoted from that entry. Label: **assumption** until you read the page and confirm they apply to an FMCW radar.

| Limit | Value |
|---|---|
| Power delivered to the antenna, max | 1 W |
| Directional antenna gain, max before power must be reduced | 6 dBi |
| EIRP, max | 4 W |
| EIRP density, max in any 1 MHz | 200 mW/MHz |
| Out of band, within 10 MHz of either edge | EIRP density at most -17 dBm/MHz |
| Out of band, 10 MHz or more from the edges | EIRP density at most -27 dBm/MHz |

Cited instruments: Acuerdo SCT, DOF 13/03/2006, and Resolución P/EXT/150306/8, DOF 14/04/2006.

Limits of this check:
- I extracted the text with a temporary script, so accents and layout were garbled. Compare with the original page.
- I did not read the cited instruments or the related technical standard. A search result said IFT-008-2015 covers spread-spectrum and digital-modulation equipment in 5725-5850 MHz. **Whether an FMCW radar qualifies is unknown.**
- The 2025 telecom law moved these functions from the IFT to the CRT and keeps earlier IFT acts in effect (transitory 18). I did not check for CRT rules or inventories issued after May 2025.

Academic use is not an exemption: outside free-use bands, experimentation needs CRT authorization (Art. 159-VII), free of charge for non-profit academic projects (Art. 161). The articles and the limits of that reading are in [decision 001](decisions/001-sweep.md).

Bandwidth options (resolution column is calculated):

| Option | Sweep (GHz) | B (MHz) | c/(2B) (m) | Use |
|---|---|---|---|---|
| A, original charter | 5.725-5.875 | 150 | 0.999 | Simulation and conducted tests only |
| B, full listed band | 5.725-5.850 | 125 | 1.199 | Rejected: no guard for edge tolerance and spectral skirts |
| **C, chosen** | 5.730-5.845 | 115 | 1.303 | Radiated design case. 5 MHz guards are an assumption, to be checked at Gate 1 and Gate 5 |

Choosing C does not by itself permit transmission (M-01).

## 2. What "resolution" means

c/(2B) is the FFT bin spacing for a full-chirp record. It does not guarantee that two targets that far apart show as two peaks.

Sim result. Criterion (**assumption**): two equal echoes near 20 m, noiseless; two peaks, each within c/(8B) of its true range, with a dip of at least 3 dB. The value is the smallest tested separation (0.1 m steps) from which all 72 tested relative phases pass. All values are **calculated**.

| B (MHz) | c/(2B) (m) | Rectangular window (m) | Hann window (m) |
|---|---|---|---|
| 150 | 0.999 | 1.6 | 2.5 |
| 125 | 1.199 | 1.9 | 3.0 |
| 115 | 1.303 | 2.0 | 3.2 |

The open Gate 0 decision is which definition the resolution requirement uses. Rectangular windowing separates closer targets but has higher sidelobes, which can hide a weak target next to a strong one.

## 3. Proposed requirements

| ID | Requirement | Value | Label | Basis or note |
|---|---|---|---|---|
| R-01 | Radiated sweep | 5.730-5.845 GHz | assumption | Decision 001; permission to transmit still open (M-01) |
| R-02 | Sweep bandwidth, radiated / conducted only | 115 MHz / 150 MHz | assumption | 150 MHz only through cables and dummy load unless authorized |
| R-03 | Range bin c/(2B), 115 MHz | 1.303 m | calculated | 150 MHz: 0.999 m. Replaces "~1 m" for radiated tests |
| R-04 | Maximum demo range, indoor | about 30 m | assumption | Target type and size undefined (M-03) |
| R-05 | Chirp (ramp) time T | 1 ms | assumption | Sawtooth assumed; shape and repetition period not decided |
| R-06 | Slope S = B/T, 115 MHz | 1.15e11 Hz/s | calculated | 150 MHz: 1.5e11 Hz/s |
| R-07 | Beat frequency at 30 m, 115 MHz | 23 016 Hz | calculated | f_b = 2RS/c; 150 MHz: 30 021 Hz |
| R-08 | Beat frequency at 3 m and 45 m, 115 MHz | 2 302 Hz and 34 524 Hz | calculated | 150 MHz: 3 002 Hz and 45 031 Hz |
| R-09 | ADC sample rate, real sampling | 100 kSPS or more | assumption | Nyquist 50 kHz |
| R-10 | Range at fs/2 (100 kSPS), 115 MHz | 65.17 m | calculated | 150 MHz: 49.97 m. Usable range is lower because of the anti-alias filter |
| R-11 | Samples per chirp | 100 | calculated | R-05 and R-09, full ramp used |
| R-12 | Round-trip delay at 30 m | 200 ns (0.02 % of T) | calculated | |
| R-13 | ADC resolution used in the sim | 12 bit, ±1 V | assumption | Placeholder. The BOM lists a 16-bit part |
| R-14 | Raw data rate, 100 kSPS in 16-bit words, continuous | 1.6 Mbit/s | calculated | Without protocol overhead. ESP32-S3 USB throughput not checked (Gate 2) |
| R-15 | Range accuracy, one strong target | not set | n/a | See M-04. Ideal sim below is not an accuracy requirement |
| R-16 | Power amplifier in v1 | none | assumption | Locked decision |
| R-17 | Chirp source | ADF4159 plus VCO, linear sweep | assumption | Locked decision; VCO is a candidate only |
| R-18 | First tests | cables and dummy load only | assumption | Project rule |

### Sim results behind the requirements (all calculated, ideal conditions)

| Quantity | Result |
|---|---|
| Worst range error, one target, 3-45 m, 115 MHz, Hann, 16x padding, 12 bit, 0.8 V peak, no noise | 8.3 mm (150 MHz: 3.1 mm) |
| FFT gain over per-sample SNR, 100 samples, real signal, tone on a bin | 17.0 dB rectangular, 15.2 dB Hann |
| Echo at 60 m with no anti-alias filter, 150 MHz | appears at about 40 m |

The millimetre errors describe the peak estimator only. Hardware error also includes sweep nonlinearity, cable and internal delay, noise, leakage and multipath, none of which is modelled.

### Consequences to carry into Gate 1

- **Discarded ramp time costs bandwidth** (calculated). If settling forces 5 % of a 115 MHz ramp to be dropped, the used bandwidth is 109.25 MHz and the bin is 1.372 m. Sweeping extra to compensate needs spectrum inside the permitted band.
- **Anti-alias filter** (calculated). At 100 kSPS, 70 kHz folds onto 30 kHz. To protect 0-30 kHz (covers both sweep cases), attenuation must be in place by 70 kHz; the amount is not set (M-09).
- **Echo spread** (calculated, point target of constant radar cross-section, free space). Received power from 3 m to 30 m falls by 40 dB. Leakage and indoor clutter will add to the dynamic range needed.

### Velocity (later, not a v1 requirement; at 5.8 GHz; calculated)

| Quantity | Value | Condition |
|---|---|---|
| Wavelength | 51.7 mm | |
| Doppler shift | 38.7 Hz per m/s | |
| Range shift from Doppler coupling | 50.4 mm per m/s | S = 1.15e11 Hz/s |
| Unambiguous speed | ±12.9 m/s | 1 ms chirp repetition, no gap (assumption) |
| Velocity bin | 0.40 m/s | 64 chirps (assumption) |

## 4. Missing items

| ID | Missing | Why it matters | Needed by |
|---|---|---|---|
| M-01 | Legal basis for radiating: band, device class, FMCW eligibility, limits, certification, current authority | Needed before any radiation; may change the sweep or require CRT authorization | before radiating |
| M-02 | Resolution definition (bin, or two-target criterion and window) | Pass/fail for the demo | G0 |
| M-03 | Reference targets (type, radar cross-section), minimum range, scene | "30 m" cannot be tested without them | G0 |
| M-04 | Pass/fail limits: range accuracy, detection probability, false-alarm rate, minimum SNR | Gate 6 acceptance | G0 |
| M-05 | Update rate and latency; live display or logged data | Chirp repetition, USB, software | G0 |
| M-06 | Link budget inputs: TX power, antenna gain, losses, noise figure, cross-section, SNR needed | The sim's amplitudes and noise are placeholders. No link budget exists yet | G1/G2 |
| M-07 | TX-RX antenna isolation and leakage tolerance | Can saturate the LNA, mixer or ADC | G1/G2 |
| M-08 | Chirp quality: shape, settling, idle time, linearity, phase noise; PLL reference and loop bandwidth | Resolution and noise floor | G1 |
| M-09 | Baseband: gain, high-pass (leakage and near range), anti-alias attenuation, ADC input range | Dynamic range | G1/G2 |
| M-10 | ADC choice and trigger synchronization between ramp and samples | Phase coherence, velocity | G2 |
| M-11 | Datasheet checks: VCO tuning range, voltage and output power; PLL charge-pump range and ramp limits; mixer LO drive; LNA; splitter levels | None verified | G2 |
| M-12 | Power: supply source, rails, current budget, noise limits | LDO choice | G2 |
| M-13 | Antennas: band, gain, beamwidth, S11 limit, spacing | Link budget, leakage, legal EIRP | G2 |
| M-14 | Test equipment: spectrum analyzer (unconfirmed in charter), 6 GHz VNA loan, signal generator, scope | Gate 5 and out-of-band verification | G2 |
| M-15 | Mechanical and environment limits | Layout, enclosure | G2 |
| M-16 | License: chosen (MIT; CERN-OHL-P-2.0 for `hardware/`). Open: confirm university ownership rules and any co-authors | Right to publish under these licenses | before publishing |

## 5. BOM and charter inconsistencies

Read from [bom/FMCW_6GHz_BOM.xlsx](../bom/FMCW_6GHz_BOM.xlsx). The workbook was not changed. Totals were re-added by hand from the unit prices for Option B: parts per board USD 134.34, one-time USD 49.00, two boards USD 317.68 (**calculated**; they match the charter's rounded figures). The unit prices are **assumptions**: mostly estimates, and the "Verified" ones are 2026-11-26 listing snapshots that I did not recheck. Totals exclude shipping, import duty and IVA; the charter says the same.

1. The workbook title says **5.8-6.0 GHz** and **v1 = open-loop VCO (Option A), v2 = PLL**. The charter locks the PLL for v1 and excludes 5.875-6.0 GHz.
2. The charter lists five verified prices and calls everything else an estimate. The workbook also marks the LTC6241 op-amp (USD 5.84, quantity 2) as verified.
3. Option B has no row for an active loop filter amplifier; the tuning amplifier row is Option A only. Whether one is needed depends on the VCO tuning voltage versus the PLL charge-pump range (**not checked**, M-11). This may change the BOM.
4. The power amplifier row is excluded, which agrees with the charter.
