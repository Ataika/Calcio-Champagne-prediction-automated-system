"""Source acquisition checks use fake HTTP responses and never download real data."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loader.get_data import ensure_dataset


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.data = self.base / "data"
        self.manifest = self.base / "manifest.json"
        self.payload = b"first,second\n1,2\n"
        self.entry = dict(table="sample", path="sample/sample.csv", bytes=len(self.payload),
                          url="https://example.invalid/sample.csv", header=["first", "second"],
                          sha256=hashlib.sha256(self.payload).hexdigest())
        for context in (patch("loader.get_data.MANIFEST", self.manifest),
                        patch.dict("os.environ", {"DOWNLOAD_DATA": "1"})):
            context.start()
            self.addCleanup(context.stop)
        self.destination = self.data / self.entry["path"]

    def save_manifest(self):
        self.manifest.write_text(json.dumps(dict(revision="test-snapshot", files=[self.entry])))

    def assert_no_partial_files(self):
        self.assertEqual(list(self.data.rglob("*.tmp")), [])

    def test_verified_download_is_reused_without_network(self):
        self.save_manifest()
        with patch("loader.get_data.urllib.request.urlopen", return_value=io.BytesIO(self.payload)) as download:
            ensure_dataset(self.data, verify=True)
            self.assertEqual(self.destination.read_bytes(), self.payload)
            download.reset_mock()
            ensure_dataset(self.data, verify=True)
            download.assert_not_called()
        self.assert_no_partial_files()

    def test_wrong_checksum_is_never_installed(self):
        self.save_manifest()
        with patch("loader.get_data.urllib.request.urlopen", return_value=io.BytesIO(b"corrupt")), \
                self.assertRaisesRegex(ValueError, "checksum"):
            ensure_dataset(self.data)
        self.assertFalse(self.destination.exists())
        self.assert_no_partial_files()

    def test_valid_checksum_with_wrong_header_is_rejected(self):
        payload = b"second,first\n2,1\n"
        self.entry["sha256"] = hashlib.sha256(payload).hexdigest()
        self.save_manifest()
        with patch("loader.get_data.urllib.request.urlopen", return_value=io.BytesIO(payload)), \
                self.assertRaisesRegex(ValueError, "column order"):
            ensure_dataset(self.data)
        self.assertFalse(self.destination.exists())
        self.assert_no_partial_files()

    def test_interrupted_download_leaves_no_partial_source(self):
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise OSError("connection lost")
                return super().read(4)

        self.save_manifest()
        with patch("loader.get_data.urllib.request.urlopen", return_value=Interrupted(self.payload)), \
                self.assertRaisesRegex(OSError, "connection lost"):
            ensure_dataset(self.data)
        self.assertFalse(self.destination.exists())
        self.assert_no_partial_files()

    def test_corrupt_existing_source_is_preserved_and_reported(self):
        self.save_manifest()
        self.destination.parent.mkdir(parents=True)
        corrupt = b"first,second\nchanged,2\n"
        self.destination.write_bytes(corrupt)
        with patch("loader.get_data.urllib.request.urlopen") as download, \
                self.assertRaisesRegex(ValueError, "checksum"):
            ensure_dataset(self.data, verify=True)
        download.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), corrupt)

    def test_metadata_normalization_validates_output_checksum(self):
        payload = b"first,extra\n1,ignored\n"
        normalized = b"first,second\n1,\n"
        self.entry.update(normalize=True, sha256=hashlib.sha256(payload).hexdigest(),
                          output_sha256=hashlib.sha256(normalized).hexdigest())
        self.save_manifest()
        with patch("loader.get_data.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            ensure_dataset(self.data, verify=True)
        self.assertEqual(self.destination.read_bytes(), normalized)
        self.assert_no_partial_files()


if __name__ == "__main__":
    unittest.main()
