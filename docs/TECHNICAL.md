# Technical notes

These notes describe the behavior observed while reverse engineering ASTRO Command Center 1.0.226 and one A50 Gen 4 Xbox/PC unit. Treat device-wide conclusions as provisional until reproduced on more hardware.

## Executable

The supported executable is a native 32-bit Qt/C++ Windows program, not .NET.

Supported original SHA-256:

```text
991e558129af98765cba4f02b10fa5cc4d537e2b6bb4bd3032ca010832eb2dcf
```

The binary contains updater-related classes/strings such as `FirmwareUpdater`, `FirmwareUpdaterThread`, `AstroA50Mimas`, and `Europa` logging.

## Four updater stages

Observed stage indexes and firmware-data commands:

| Stage index | Stage | Data command | Observed image size |
|---:|---|---:|---:|
| 0 | TX_MCU | `0x43` | 344,064 bytes |
| 1 | RX_MCU | `0xF3` | 49,424 bytes |
| 2 | TX_RADIO | `0x49` | 65,554 bytes |
| 3 | RX_RADIO | `0xF9` | 65,562 bytes |

`0xFC` is used during the headset MAC-update/restore operation after firmware transfer.

## The observed 75% failure

On the affected unit, the updater could repeatedly complete:

```text
TX_MCU -> TX_RADIO -> RX_MCU
```

but the transition after RX_MCU was unreliable. A manual headset reset at approximately the 75% boundary could make the official flow proceed. Experiments that simply suppressed/faked the reset proved that `RX_RADIO` still depends on a valid device state; Command Center could crash if its state machine and the physical headset state diverged.

The successful recovery strategy was therefore to avoid that transition entirely **after RX_MCU had already been written**.

## Native skip-stage branch

At VA `0x490003`, ACC already has a conditional branch that skips the RX_MCU stage when that stage is absent from the selected update plan:

```text
74 2c    JE +0x2c
```

The v0.4 recovery patch changes only the condition:

```text
eb 2c    JMP +0x2c
```

This is intentionally preferable to jumping over arbitrary updater code: ACC executes its own existing “stage absent” path and keeps the surrounding orchestration intact.

## Stage-start grace

At VA `0x490A35`, the original immediate value is `1000` ms. v0.4 changes it to `7000` ms. This is a tolerance change, not a success-forcing patch.

## Forced firmware filename

ACC 1.0.226 contains an old bundled forced-firmware filename:

```text
mimas_190705151435_tm-35155_tr-43_rm-34843_rr-43.afw
```

The tested target package filename has the same length, allowing a safe in-place string replacement:

```text
mimas_220420021220_tm-40372_tr-43_rm-39964_rr-43.afw
```

The patcher does not ship that firmware. It validates a user-provided AFW and copies it into the ACC `assets/forced_fw` folder.

## AFW format

Observed `.afw` files are ZIP-compatible containers with the first two ZIP magic bytes changed from `PK` to `AG`. For validation, the patcher restores those two bytes **in memory only** and inspects the archive.

Target package expected contents include:

```text
mimas/mimastx_v40372_20apr2022.bin
mimas/mimasrx_v39964_6dec2021.bin
mimas/avneratx_v43_27Jun2019_r21.bin
mimas/avnerarx_v43_27Jun2019_r21.bin
```

## What this project does not do

- It does not implement a standalone firmware flasher.
- It does not disable AFW validation.
- It does not patch updater failures into success codes.
- It does not include proprietary firmware or ACC binaries.
- It does not claim the same failure mechanism applies to every A50 Gen 4.
