import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

import patcher


def make_test_afw(path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("mimas/afw_notes.txt", "Tx: v40372.43\nRx: v39964.43\n")
        for name, size in patcher.EXPECTED_AFW_FILES.items():
            z.writestr(name, b"\0" * size)
    raw = buf.getvalue()
    path.write_bytes(b"AG" + raw[2:])


class PatcherTests(unittest.TestCase):
    def test_validate_structurally_matching_afw(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.afw"
            make_test_afw(p)
            info = patcher.validate_afw(p)
            self.assertGreater(info["size"], 0)
            self.assertFalse(info["exact_known_target"])
            self.assertEqual(info["images"]["mimas/mimasrx_v39964_6dec2021.bin"], 49424)

    def test_sha256_helper(self):
        self.assertEqual(patcher.sha256(b"abc"), hashlib.sha256(b"abc").hexdigest())

    def test_forced_firmware_names_are_same_length(self):
        self.assertEqual(len(patcher.OLD_FORCED_FW), len(patcher.TARGET_FORCED_FW))


if __name__ == "__main__":
    unittest.main()
