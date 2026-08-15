# Recovery and troubleshooting

Read this before flashing.

## Before running the patch

1. Keep a copy of the original ASTRO Command Center folder.
2. Keep the original `ASTRO Command Center.exe` untouched.
3. Verify that `patcher.py --dry-run` succeeds.
4. Make sure the headset has adequate charge and is detected by the base station.
5. Connect the base station directly to the PC rather than through an unreliable hub.

## If Command Center closes or the update fails

Do not repeatedly launch firmware updates back-to-back while the headset/base is in an uncertain boot state.

1. Close Command Center.
2. Restore the headset/base to a state where the normal ACC can detect them.
3. Keep the log from `%LOCALAPPDATA%\Astro Gaming\ASTRO Command Center\Logs`.
4. Check which stage actually completed.

This recovery patch is specifically intended for a case where `RX_MCU` was already fully written and the failure occurs at the transition into `RX_RADIO`.

## Signs this may be the same failure

A previous log contains:

```text
Europa : starting for RX_MCU
Europa : updateFW called for 1, fw data size is 49424 bytes
Europa : completing updating
```

and then fails, crashes, or loses the headset around:

```text
Europa : starting for RX_RADIO
```

Earlier observed failures on the same device also included `HID_ERROR_SLAVE_TIMEOUT` during command `0xF9` and errors around `0xFC` during headset MAC restore.

## If RX_MCU itself fails

Do **not** use the skip-RX-MCU recovery patch as a substitute for successfully writing RX_MCU. The patched build deliberately does not flash that image.

Use the original/manual recovery path appropriate for the device, get RX_MCU written successfully, and only then consider the skip-stage recovery if the next transition reproduces the same problem.
