"""Unit tests for the download file store (tokens, expiry, safety)."""

import os
import time
from pathlib import Path

from mcp_server.files import FileStore


def _store(tmp_path: Path, ttl: int = 3600) -> FileStore:
    return FileStore(tmp_path / "root", "secret-key", ttl)


def test_create_batch_makes_uuid_hex_dir(tmp_path):
    store = _store(tmp_path)
    batch_id, batch_dir = store.create_batch()
    assert len(batch_id) == 32
    assert all(c in "0123456789abcdef" for c in batch_id)
    assert batch_dir.is_dir()
    assert batch_dir.parent == store.root


def test_build_url_is_relative_without_public_url(tmp_path):
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    url = store.build_url("", batch_id, "报表.png")
    assert url.startswith(f"/mcp/files/{batch_id}/报表.png?")
    assert "ts=" in url and "token=" in url


def test_build_url_is_absolute_with_public_url(tmp_path):
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    url = store.build_url("http://cloud/mcp", batch_id, "报表.png")
    assert url.startswith(f"http://cloud/mcp/files/{batch_id}/报表.png?")


def test_verify_accepts_its_own_token(tmp_path):
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    url = store.build_url("", batch_id, "a.png")
    query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
    assert store.verify(batch_id, "a.png", query["ts"], query["token"])


def test_verify_rejects_wrong_token(tmp_path):
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    assert not store.verify(batch_id, "a.png", str(int(time.time())), "bad" * 8)


def test_verify_rejects_expired_timestamp(tmp_path):
    store = _store(tmp_path, ttl=60)
    batch_id, _ = store.create_batch()
    old_ts = int(time.time()) - 3600
    token = store._sign(old_ts, batch_id, "a.png")
    assert not store.verify(batch_id, "a.png", str(old_ts), token)


def test_verify_rejects_non_numeric_timestamp(tmp_path):
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    assert not store.verify(batch_id, "a.png", "yesterday", "x")


def test_token_binds_batch_and_filename(tmp_path):
    """A token for one file must not validate for another."""
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    url = store.build_url("", batch_id, "a.png")
    query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
    assert not store.verify(batch_id, "b.png", query["ts"], query["token"])


def test_file_path_rejects_path_traversal(tmp_path):
    store = _store(tmp_path)
    batch_id, batch_dir = store.create_batch()
    (batch_dir / "ok.png").write_bytes(b"x")
    assert store.file_path(batch_id, "ok.png") is not None
    assert store.file_path(batch_id, "..") is None
    assert store.file_path(batch_id, "../secret") is None
    assert store.file_path(batch_id, "a/b.png") is None
    assert store.file_path(batch_id, "a\\b.png") is None
    assert store.file_path("../../etc/passwd", "a.png") is None


def test_file_path_rejects_missing_files(tmp_path):
    store = _store(tmp_path)
    batch_id, _ = store.create_batch()
    assert store.file_path(batch_id, "never-written.png") is None


def test_cleanup_removes_expired_batches(tmp_path):
    store = _store(tmp_path, ttl=60)
    old_id, old_dir = store.create_batch()
    (old_dir / "f.png").write_bytes(b"x")
    fresh_id, _ = store.create_batch()
    # Backdate the old batch beyond the TTL
    past = time.time() - 3600
    os.utime(old_dir, (past, past))

    store.cleanup()

    assert not old_dir.exists()
    assert (store.root / fresh_id).is_dir()


def test_cleanup_ignores_missing_root(tmp_path):
    _store(tmp_path).cleanup()  # must not raise when nothing was ever written
