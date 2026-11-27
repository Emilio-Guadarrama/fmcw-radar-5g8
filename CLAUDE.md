# SPECULA-1: FMCW radar 5.8 GHz

Read `docs/charter.md` first. It holds the locked decisions, requirements (assumptions until simulated), roles and gates G0-G6.

## Rules
- The owner (Emilio) approves every gate. Do not move to the next gate without his explicit yes.
- Never flash hardware, order PCBs or parts, push code, or spend money without explicit confirmation in chat.
- Never add a Co-Authored-By trailer or any Claude attribution to commits or PRs. Commits are authored by the owner.
- Never invent component specs, prices, calculations or results. Cite the datasheet page or show the calculation. Mark each value as: datasheet, calculated, measured, or assumption.
- Always give units and reference conditions. Keep simulation, bench test and live radiation clearly separate.
- Nothing is radiated before checking Mexico's rules (CRT, formerly IFT). First tests use cables and dummy loads.
- Sweep ([decision 001](docs/decisions/001-sweep.md)): radiated design case is 5.730-5.845 GHz (115 MHz). 150 MHz (5.725-5.875 GHz) is for simulation, and cables / dummy load only, unless an authorization covers it. Neither is cleared to transmit. Current requirements and open items are in `docs/requirements.md`.
- Link to datasheets, do not commit the PDFs (copyright, public repo).
- Altium files are binary: review exports in `hardware/exports/` (netlist, BOM as CSV, DRC report, schematic and layout PDFs or images, Gerbers/ODB++).

## Layout
docs/ sim/ hardware/ firmware/ software/ tests/ bom/ (see README.md)

## Conventions
- Python 3.11+, `pytest` for every simulation and processing module, formatted with `ruff`.
- Decisions go in `docs/decisions/NNN-title.md` (context, options, choice, consequences).
- Gate reviews go in `docs/gates/Gn.md`.
- Small commits, imperative messages, no Claude attribution.

## Agents (`.claude/agents/`)
architect, simulator, hardware, inspector (read-only, independent), firmware, validation.
The inspector never reviews its own work.
