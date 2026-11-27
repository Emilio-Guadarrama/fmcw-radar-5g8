---
name: validation
description: Bring-up plans and measurement procedures for Gate 5 and Gate 6. Use for tests/.

---
Read CLAUDE.md and docs/charter.md first. Follow their rules. Mark every value as datasheet, calculated, measured or assumption, with units. Report open questions instead of guessing.

Write step-by-step procedures in tests/ in this order: power rails, chirp generator on a spectrum analyzer or scope, receive chain with a signal generator, then cables and dummy load, then antennas. Define pass/fail limits and a log template. Include the regulatory check before any radiation.
