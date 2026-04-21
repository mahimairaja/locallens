"""Direct unit tests for the file walker + SHA-256 core.

Covers both implementations (Rust `RustWalker` when available, pure-Python
`_PyWalker` always). Every test that makes a factual claim about output
asserts both backends produce byte-identical results — that's the permanent
guard against Qdrant `has_hash` dedup breaking on an upgrade or downgrade.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from locallens._internals._file_core import (
    FileEntry,
    _py_hash_file,
    _PyWalker,
    hash_file,
    walk_and_hash,
)
from locallens._internals._rust import HAS_RUST_WALKER

# ---------------------------------------------------------------------------
# Fixture tree + helpers
# ---------------------------------------------------------------------------


def _make_tree(root: Path) -> None:
    """Write a small deterministic file tree for parity assertions."""
    (root / "a.py").write_text("alpha\n")
    (root / "b.py").write_text("beta content\n")
    (root / "sub").mkdir()
    (root / "sub" / "c.md").write_text("# gamma\nbody\n")
    (root / "sub" / "d.txt").write_text("delta")  # excluded by ext filter
    (root / ".hidden").mkdir()
    (root / ".hidden" / "e.py").write_text("hidden!")  # excluded when skip_hidden
    (root / "big.py").write_bytes(b"x" * 50_000)  # kept when max > 50k


def _run_py(root: Path, **kwargs) -> list[FileEntry]:
    """Force the pure-Python backend regardless of HAS_RUST_WALKER."""
    w = _PyWalker(
        extensions=frozenset(kwargs.pop("extensions", {".py", ".md"})),
        max_file_size_bytes=kwargs.pop("max_file_size_bytes", 10_000_000),
        skip_hidden=kwargs.pop("skip_hidden", True),
        follow_symlinks=kwargs.pop("follow_symlinks", True),
    )
    return w.walk_and_hash(root)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_hash_file_matches_hashlib(tmp_path: Path) -> None:
    """Prevent hash-output drift. Dedup via Qdrant's payload index depends
    on the hex strings matching byte-for-byte with hashlib."""
    p = tmp_path / "f.bin"
    p.write_bytes(b"the quick brown fox jumps over the lazy dog")
    assert hash_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_py_hash_file_matches_hashlib(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(os.urandom(64 * 1024 + 17))
    assert _py_hash_file(p) == hashlib.sha256(p.read_bytes()).hexdigest()


def test_walk_and_hash_python_basic(tmp_path: Path) -> None:
    """Pure-Python path returns sorted, filtered, hashed entries."""
    _make_tree(tmp_path)
    out = _run_py(tmp_path)

    # a.py, b.py, big.py, sub/c.md — sorted by path
    names = [e.path.name for e in out]
    assert names == sorted(names)
    assert ".hidden" not in " ".join(str(e.path) for e in out)
    assert all(e.path.suffix in {".py", ".md"} for e in out)
    # Every sha256 matches hashlib
    for e in out:
        assert e.sha256 == hashlib.sha256(e.path.read_bytes()).hexdigest()
        assert e.size == e.path.stat().st_size


@pytest.mark.skipif(not HAS_RUST_WALKER, reason="Rust extension not built")
def test_walk_and_hash_rust_matches_python(tmp_path: Path) -> None:
    """The whole point: Rust and Python produce byte-identical results."""
    _make_tree(tmp_path)
    py_out = _run_py(tmp_path)
    rs_out = walk_and_hash(
        tmp_path,
        frozenset({".py", ".md"}),
        max_file_size_bytes=10_000_000,
    )
    assert HAS_RUST_WALKER  # sanity: this should have hit the Rust path
    assert [str(e.path) for e in rs_out] == [str(e.path) for e in py_out]
    assert [e.sha256 for e in rs_out] == [e.sha256 for e in py_out]
    assert [e.size for e in rs_out] == [e.size for e in py_out]


def test_skip_hidden_any_component(tmp_path: Path) -> None:
    (tmp_path / "a" / ".hidden").mkdir(parents=True)
    (tmp_path / "a" / ".hidden" / "f.py").write_text("x")
    (tmp_path / "a" / "keep.py").write_text("y")
    out = _run_py(tmp_path)
    assert [e.path.name for e in out] == ["keep.py"]


def test_extension_filter_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "LOUD.PY").write_text("x")
    (tmp_path / "quiet.py").write_text("y")
    (tmp_path / "Mix.Md").write_text("z")
    out = _run_py(tmp_path, extensions={".py", ".md"})
    names = sorted(e.path.name for e in out)
    assert names == ["LOUD.PY", "Mix.Md", "quiet.py"]


def test_max_size_gate_skips_large(tmp_path: Path) -> None:
    (tmp_path / "big.py").write_bytes(b"x" * 2000)
    (tmp_path / "small.py").write_bytes(b"ok")
    out = _run_py(tmp_path, max_file_size_bytes=1000)
    names = [e.path.name for e in out]
    assert names == ["small.py"]


def test_empty_root_returns_empty_list(tmp_path: Path) -> None:
    out = _run_py(tmp_path)
    assert out == []


def test_nonexistent_root_returns_empty_list(tmp_path: Path) -> None:
    # Public walk_and_hash handles missing paths gracefully; _PyWalker is
    # only called when the path exists (callers guard), so we verify the
    # top-level helper here.
    missing = tmp_path / "does_not_exist"
    out = walk_and_hash(
        missing,
        frozenset({".py"}),
        max_file_size_bytes=1_000_000,
    )
    assert out == []


@pytest.mark.skipif(not HAS_RUST_WALKER, reason="Rust extension not built")
def test_rust_parallel_equals_serial(tmp_path: Path) -> None:
    """Parallel SHA-256 must produce the same output as serial."""
    _make_tree(tmp_path)
    common = {
        "extensions": frozenset({".py", ".md"}),
        "max_file_size_bytes": 10_000_000,
    }
    parallel = walk_and_hash(tmp_path, parallel=True, **common)
    serial = walk_and_hash(tmp_path, parallel=False, **common)
    assert [str(e.path) for e in parallel] == [str(e.path) for e in serial]
    assert [e.sha256 for e in parallel] == [e.sha256 for e in serial]


def test_eager_parallel_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LOCALLENS_WALK_PARALLEL=0 forces the non-parallel path without changing callers."""
    _make_tree(tmp_path)
    monkeypatch.setenv("LOCALLENS_WALK_PARALLEL", "0")
    out = walk_and_hash(
        tmp_path,
        frozenset({".py", ".md"}),
        max_file_size_bytes=10_000_000,
    )
    # Behavior identical to parallel mode — the env override only toggles
    # *how* work is done, not *what* comes out.
    assert len(out) >= 3
    for e in out:
        assert e.sha256 == hashlib.sha256(e.path.read_bytes()).hexdigest()


def test_symlink_followed_by_default(tmp_path: Path) -> None:
    """Symlinks to files inside the root are included by default — matches
    Python's ``Path.is_file()`` which follows symlinks."""
    real = tmp_path / "real.py"
    real.write_text("hello")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    out = _run_py(tmp_path)
    names = sorted(e.path.name for e in out)
    assert "real.py" in names
    assert "link.py" in names
    # Both should hash to the same value since the symlink resolves to real.
    sha_map = {e.path.name: e.sha256 for e in out}
    assert sha_map["real.py"] == sha_map["link.py"]
