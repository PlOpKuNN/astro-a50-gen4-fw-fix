#!/usr/bin/env python3
"""ASTRO A50 Gen 4 ACC 1.0.226 RX_MCU skip recovery patcher.

This tool does NOT contain or redistribute Logitech/ASTRO binaries.
It patches a user-supplied ASTRO Command Center 1.0.226 executable and
installs a user-supplied target .afw package into assets/forced_fw.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import zipfile

ORIGINAL_EXE_SHA256 = "991e558129af98765cba4f02b10fa5cc4d537e2b6bb4bd3032ca010832eb2dcf"
KNOWN_PATCHED_EXE_SHA256 = "f10ef048246ef51ccbc8d11854b3a14e48aa920adcaef30feeed6a1eefb71a6f"
TARGET_AFW_SHA256 = "376edcad419339586878572d5e1619a693f46b795cf113b35806dc079764cd16"
OLD_FORCED_FW = b"mimas_190705151435_tm-35155_tr-43_rm-34843_rr-43.afw"
TARGET_FORCED_FW = b"mimas_220420021220_tm-40372_tr-43_rm-39964_rr-43.afw"
EXPECTED_AFW_FILES = {
    "mimas/mimasrx_v39964_6dec2021.bin": 49424,
    "mimas/mimastx_v40372_20apr2022.bin": 344064,
    "mimas/avnerarx_v43_27Jun2019_r21.bin": 65562,
    "mimas/avneratx_v43_27Jun2019_r21.bin": 65554,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_pe(data: bytearray):
    if data[:2] != b"MZ":
        raise ValueError("Not a PE executable (missing MZ header)")
    peoff = struct.unpack_from("<I", data, 0x3C)[0]
    if data[peoff : peoff + 4] != b"PE\0\0":
        raise ValueError("Not a valid PE executable")
    fh = peoff + 4
    nsec = struct.unpack_from("<H", data, fh + 2)[0]
    szopt = struct.unpack_from("<H", data, fh + 16)[0]
    opt = fh + 20
    if struct.unpack_from("<H", data, opt)[0] != 0x10B:
        raise ValueError("Expected a 32-bit PE32 executable")
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    sec0 = opt + szopt
    sections = []
    for i in range(nsec):
        off = sec0 + i * 40
        name = bytes(data[off : off + 8]).rstrip(b"\0").decode(errors="replace")
        virtual_size, virtual_address, raw_size, raw_ptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append((name, virtual_size, virtual_address, raw_size, raw_ptr, off))
    return opt, image_base, sections


def va_to_offset(va: int, image_base: int, sections) -> int:
    rva = va - image_base
    for _name, vsize, sva, rsize, rptr, _hdr in sections:
        if sva <= rva < sva + max(vsize, rsize):
            return rptr + (rva - sva)
    raise ValueError(f"VA {va:#x} is outside mapped sections")


def patch_at_va(data: bytearray, va: int, expected: bytes, replacement: bytes, image_base: int, sections):
    if len(expected) != len(replacement):
        raise ValueError("Patch length mismatch")
    off = va_to_offset(va, image_base, sections)
    actual = bytes(data[off : off + len(expected)])
    if actual != expected:
        raise ValueError(
            f"Unexpected bytes at {va:#x}: got {actual.hex(' ')}, expected {expected.hex(' ')}"
        )
    data[off : off + len(replacement)] = replacement


def validate_afw(path: Path) -> dict:
    raw = path.read_bytes()
    digest = sha256(raw)
    if raw[:2] != b"AG":
        raise ValueError("AFW container does not start with ASTRO 'AG' signature")

    # AFW is a ZIP container whose first two signature bytes are changed from PK to AG.
    with zipfile.ZipFile(io.BytesIO(b"PK" + raw[2:])) as archive:
        names = set(archive.namelist())
        missing = [name for name in EXPECTED_AFW_FILES if name not in names]
        if missing:
            raise ValueError("AFW is not the expected 40372.43/39964.43 package; missing: " + ", ".join(missing))
        sizes = {name: len(archive.read(name)) for name in EXPECTED_AFW_FILES}
        bad_sizes = {
            name: (sizes[name], expected)
            for name, expected in EXPECTED_AFW_FILES.items()
            if sizes[name] != expected
        }
        if bad_sizes:
            raise ValueError(f"AFW contains unexpected image sizes: {bad_sizes}")
        notes = archive.read("mimas/afw_notes.txt").decode(errors="replace") if "mimas/afw_notes.txt" in names else ""
        if "Tx: v40372.43" not in notes or "Rx: v39964.43" not in notes:
            raise ValueError("AFW notes do not identify target Tx 40372.43 / Rx 39964.43")

    return {
        "sha256": digest,
        "exact_known_target": digest == TARGET_AFW_SHA256,
        "size": len(raw),
        "images": sizes,
    }


def build_patch(exe_path: Path, afw_path: Path, output_path: Path, install_firmware: bool, dry_run: bool):
    original = exe_path.read_bytes()
    original_hash = sha256(original)
    if original_hash == KNOWN_PATCHED_EXE_SHA256:
        raise ValueError("This executable already matches the known v0.4 patched build")
    if original_hash != ORIGINAL_EXE_SHA256:
        raise ValueError(
            "Unsupported ASTRO Command Center executable.\n"
            f"SHA-256: {original_hash}\n"
            f"Expected: {ORIGINAL_EXE_SHA256}\n"
            "This patch intentionally refuses unknown builds because the patch uses verified code offsets."
        )

    afw_info = validate_afw(afw_path)
    data = bytearray(original)
    opt, image_base, sections = parse_pe(data)

    # Fix used by the successful v0.4 recovery build:
    # At VA 0x490003 the original updater has JE +0x2c, taking its built-in
    # 'stage absent' path when RX_MCU is not selected. Convert JE -> JMP so
    # RX_MCU is skipped while the updater's own state machine remains intact.
    patch_at_va(data, 0x490003, bytes.fromhex("74 2c"), bytes.fromhex("eb 2c"), image_base, sections)

    # Give stage start / device state a little more time (1000 ms -> 7000 ms).
    patch_at_va(data, 0x490A35, struct.pack("<I", 1000), struct.pack("<I", 7000), image_base, sections)

    # Point the bundled forced-firmware lookup at the target 40372/39964 filename.
    if len(OLD_FORCED_FW) != len(TARGET_FORCED_FW):
        raise AssertionError("Firmware filename patch unexpectedly changed length")
    pos = data.find(OLD_FORCED_FW)
    if pos < 0 or data.find(OLD_FORCED_FW, pos + 1) >= 0:
        raise ValueError("Expected exactly one embedded forced-firmware filename")
    data[pos : pos + len(OLD_FORCED_FW)] = TARGET_FORCED_FW

    # PE checksum is stale after modifications. Windows does not require it for this normal EXE.
    struct.pack_into("<I", data, opt + 64, 0)
    patched_hash = sha256(data)

    result = {
        "input_exe": str(exe_path),
        "input_exe_sha256": original_hash,
        "output_exe": str(output_path),
        "output_exe_sha256": patched_hash,
        "known_v04_sha_match": patched_hash == KNOWN_PATCHED_EXE_SHA256,
        "afw": str(afw_path),
        "afw_info": afw_info,
        "firmware_destination": None,
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)

    if install_firmware:
        forced_dir = exe_path.parent / "assets" / "forced_fw"
        forced_dir.mkdir(parents=True, exist_ok=True)
        dest = forced_dir / TARGET_FORCED_FW.decode("ascii")
        shutil.copy2(afw_path, dest)
        result["firmware_destination"] = str(dest)

    manifest = output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch ASTRO Command Center 1.0.226 for the tested A50 Gen 4 75% recovery path")
    parser.add_argument("--acc", required=True, type=Path, help="Path to the ORIGINAL ASTRO Command Center.exe")
    parser.add_argument("--firmware", required=True, type=Path, help="Path to mimas_220420021220...40372/39964.afw")
    parser.add_argument("--output", type=Path, help="Patched EXE path (default: same directory, RX Recovery name)")
    parser.add_argument("--no-install-firmware", action="store_true", help="Validate the AFW but do not copy it into assets/forced_fw")
    parser.add_argument("--dry-run", action="store_true", help="Validate and calculate the patch without writing files")
    args = parser.parse_args()

    exe = args.acc.expanduser().resolve()
    afw = args.firmware.expanduser().resolve()
    if not exe.is_file():
        parser.error(f"ACC executable not found: {exe}")
    if not afw.is_file():
        parser.error(f"AFW firmware not found: {afw}")
    output = args.output.expanduser().resolve() if args.output else exe.with_name("ASTRO Command Center - RX Recovery v0.4.exe")

    try:
        result = build_patch(exe, afw, output, not args.no_install_firmware, args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    if not args.dry_run:
        print("\nPatch complete. The original EXE was not modified.")
        print("Run the generated RX Recovery EXE from the same ACC directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
