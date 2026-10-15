"""Persistent blob store contract and hostile-manifest cases."""
import tempfile
import unittest

from nexo import CodecError, FileBlobStore, MemoryBlobStore


class TestFileBlobStore(unittest.TestCase):
    def test_cross_process_equivalent_reuse(self):
        with tempfile.TemporaryDirectory() as path:
            first = FileBlobStore(path)
            second = FileBlobStore(path)
            image = b"\x89PNG\r\n\x1a\n" + b"pixels..." * 3
            manifest = first.add(image, mime="image/png")
            self.assertEqual(second.resolve(manifest), image)
            self.assertEqual(first.add(image, "image/png"), manifest)

    def test_detects_corrupted_file(self):
        with tempfile.TemporaryDirectory() as path:
            store = FileBlobStore(path)
            manifest = store.add(b"image", "image/png")
            (store.root / manifest["sha256"]).write_bytes(b"wrong")
            with self.assertRaises(CodecError):
                store.resolve(manifest)

    def test_rejects_manifest_traversal(self):
        with tempfile.TemporaryDirectory() as path:
            store = FileBlobStore(path)
            manifest = store.add(b"hello", "application/octet-stream")
            tampered = dict(manifest, sha256="../private")
            with self.assertRaises(CodecError):
                store.resolve(tampered)
            with self.assertRaises(CodecError):
                MemoryBlobStore().resolve({"sha256": "a" * 64,
                                           "ref": "../private", "size": 0, "mime": "x"})

    def test_size_limits(self):
        with tempfile.TemporaryDirectory() as path:
            store = FileBlobStore(path, max_blob_bytes=4)
            with self.assertRaises(CodecError):
                store.add(b"12345")
            manifest = FileBlobStore(path).add(b"12345")
            with self.assertRaises(CodecError):
                store.resolve(manifest)

    def test_shared_memory_manifest_shape(self):
        store = MemoryBlobStore()
        m = store.add(b"xyz", "image/png")
        self.assertEqual(store.resolve(m), b"xyz")
        with self.assertRaises(CodecError):
            store.resolve(dict(m, size=-1))
