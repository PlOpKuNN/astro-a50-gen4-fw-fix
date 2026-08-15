# ASTRO A50 Gen 4 firmware 75% recovery fix

A small, reproducible patcher for one specific ASTRO A50 Gen 4 firmware-update failure observed with **ASTRO Command Center 1.0.226**.

On the affected unit, Command Center could flash the base station and the headset MCU, but the update repeatedly broke at the transition into the headset radio stage around **75%**. A manual headset reset at the right moment could make the official updater continue.

The successful recovery build avoided that broken transition by using Command Center's **existing native “stage absent” branch** to skip `RX_MCU` after it had already been written successfully, then continued into `RX_RADIO` with the original updater code.

> **Important:** this is a targeted recovery workaround, not a universal firmware updater replacement. It has been verified on one A50 Gen 4 Xbox/PC setup using the exact hashes below. The patcher intentionally refuses unknown ACC builds.

## Tested combination

- ASTRO A50 Gen 4 Xbox/PC
- ASTRO Command Center: **1.0.226**
- Original ACC EXE SHA-256: `991e558129af98765cba4f02b10fa5cc4d537e2b6bb4bd3032ca010832eb2dcf`
- Target base/TX firmware: **40372.43**
- Target headset/RX firmware: **39964.43**
- Known target AFW SHA-256: `376edcad419339586878572d5e1619a693f46b795cf113b35806dc079764cd16`
- Successful v0.4 patched EXE SHA-256: `f10ef048246ef51ccbc8d11854b3a14e48aa920adcaef30feeed6a1eefb71a6f`

## What the patch changes

Only three things are changed in the supported ACC executable:

1. **Skip `RX_MCU` using ACC's own existing skip-stage path.**
   - Original instruction at VA `0x490003`: `JE +0x2C`
   - Patched instruction: `JMP +0x2C`
   - This leaves the updater state machine intact; it simply always takes the branch it already uses when the RX_MCU stage is absent.
2. **Increase stage-start grace from 1,000 ms to 7,000 ms** at VA `0x490A35`.
3. Replace the embedded 2019 forced-firmware filename with the 40372/39964 package filename. The patcher then copies the user-supplied AFW into `assets/forced_fw` under that name.

It does **not** patch failures into successes, bypass firmware validation, or contain Logitech/ASTRO firmware or executables.

## Why this works on the tested failure

The update pipeline observed in ACC is:

```text
TX_MCU -> TX_RADIO -> RX_MCU -> RX_RADIO -> MAC restore/reset
```

The failing unit could fully write `RX_MCU` but then failed during the reboot/transition needed before `RX_RADIO`. Earlier experiments that removed or faked the reset caused Command Center to crash because the updater expected a real state transition.

The successful approach was different: once `RX_MCU` had already been written, let ACC **skip that entire stage natively** on the next recovery attempt. That removes the problematic `RX_MCU -> reboot -> RX_RADIO` boundary while preserving the original `RX_RADIO` and finishing logic.

See [docs/TECHNICAL.md](docs/TECHNICAL.md) for the reverse-engineering notes and [docs/RECOVERY.md](docs/RECOVERY.md) before using it.

## Usage

### 1. Keep your original files

Do not overwrite your original Command Center installation. Copy the ACC folder somewhere safe first.

You need:

- your original `ASTRO Command Center.exe` from ACC 1.0.226;
- the target `mimas` AFW containing base **40372.43** and headset **39964.43**.

This repository intentionally does not redistribute either proprietary file.

### 2. Dry-run first

```powershell
py -3 patcher.py --acc "C:\path\to\ASTRO Command Center.exe" --firmware "C:\path\to\mimas_40372_39964.afw" --dry-run
```

The patcher verifies the exact ACC SHA-256, parses the AFW container, checks its image names/sizes and firmware notes, and refuses unsupported inputs.

### 3. Build the recovery EXE

```powershell
py -3 patcher.py --acc "C:\path\to\ASTRO Command Center.exe" --firmware "C:\path\to\mimas_40372_39964.afw"
```

Or:

```powershell
.\patch.ps1 -Acc "C:\path\to\ASTRO Command Center.exe" -Firmware "C:\path\to\mimas_40372_39964.afw"
```

By default it creates:

```text
ASTRO Command Center - RX Recovery v0.4.exe
```

next to the original EXE, and installs a copy of the validated AFW into `assets\forced_fw` using the filename expected by the patched build.

The original EXE is **not modified**.

### 4. Run the recovery build

Run the generated recovery EXE from the same ACC directory. Do not manually reset the headset during the update unless you are aborting/recovering from a failure.

## Do not use this when

- your ACC executable hash does not match the supported 1.0.226 binary;
- your target firmware is not 40372.43 / 39964.43;
- `RX_MCU` has never been successfully written on your headset;
- your failure occurs in a different stage and you have no log showing the same pattern.

This build **deliberately skips RX_MCU**, so it is the wrong tool if RX_MCU itself needs repair.

## Diagnostics

ACC logs are normally under:

```text
%LOCALAPPDATA%\Astro Gaming\ASTRO Command Center\Logs
```

A matching recovery case should show that a previous attempt reached something like:

```text
Europa : starting for RX_MCU
Europa : updateFW called for 1, fw data size is 49424 bytes
Europa : completing updating
```

before failing at/near the transition to:

```text
Europa : starting for RX_RADIO
```

## Safety / warranty

Firmware flashing can leave a device temporarily unusable if interrupted. Use this only if you understand that risk. Keep the original software and a known recovery path available.

This project is an independent community workaround and is not affiliated with or endorsed by Logitech or ASTRO Gaming.

## License

The patcher and documentation in this repository are MIT licensed. No Logitech/ASTRO executable, DLL, or firmware binary is included under that license.
