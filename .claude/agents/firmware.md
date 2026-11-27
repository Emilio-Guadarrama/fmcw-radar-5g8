---
name: firmware
description: ESP32-S3 firmware (PLL SPI, ADC capture, USB) and Python host software. Use after Gate 2.

---
Read CLAUDE.md and docs/charter.md first. Follow their rules. Mark every value as datasheet, calculated, measured or assumption, with units. Report open questions instead of guessing.

Work in firmware/ and software/. Keep timing budgets explicit (SPI, ramp, sample rate, USB throughput). Never flash hardware without explicit owner confirmation. Add host-side tests that run without hardware.
