# Changelog

## v0.4-recovery

First public-source version of the recovery method that completed successfully on the tested A50 Gen 4 unit.

- uses ACC's native skip-stage branch to omit RX_MCU;
- preserves the original TX_MCU, TX_RADIO, RX_RADIO, MAC and final reset paths;
- increases stage-start grace from 1 s to 7 s;
- validates ACC 1.0.226 by SHA-256;
- validates the user-provided 40372.43 / 39964.43 AFW before installing it;
- never modifies the original EXE in place.
