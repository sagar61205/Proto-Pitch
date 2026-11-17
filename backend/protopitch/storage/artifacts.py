"""Content-addressed artifact storage.

Everything a job needs to continue on another machine goes through this interface; nothing
may assume a shared local path (ARCHITECTURE §13).
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ArtifactRef:
    sha256: str
    size: int


class ArtifactNotFoundError(KeyError):
    pass


class ArtifactStore(Protocol):
    def put_bytes(self, data: bytes) -> ArtifactRef: ...
    def put_file(self, path: Path) -> ArtifactRef: ...
    def get_bytes(self, sha256: str) -> bytes: ...
    def fetch_to(self, sha256: str, dest: Path) -> None: ...
    def exists(self, sha256: str) -> bool: ...


def _check_hash(sha256: str) -> str:
    if not _HASH.match(sha256):
        raise ValueError("artifact reference must be a lowercase SHA-256 hex digest")
    return sha256


def hash_file(path: Path) -> ArtifactRef:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return ArtifactRef(digest.hexdigest(), size)


class LocalArtifactStore:
    """Artifacts as files under ``<root>/sha256/ab/cd/<digest>``; writes are atomic."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, sha256: str) -> Path:
        _check_hash(sha256)
        return self._root / "sha256" / sha256[:2] / sha256[2:4] / sha256

    def put_bytes(self, data: bytes) -> ArtifactRef:
        ref = ArtifactRef(hashlib.sha256(data).hexdigest(), len(data))
        target = self._path(ref.sha256)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                os.replace(tmp, target)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        return ref

    def put_file(self, path: Path) -> ArtifactRef:
        ref = hash_file(path)
        target = self._path(ref.sha256)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            try:
                with os.fdopen(fd, "wb") as out, path.open("rb") as src:
                    for chunk in iter(lambda: src.read(1 << 20), b""):
                        out.write(chunk)
                os.replace(tmp, target)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        return ref

    def get_bytes(self, sha256: str) -> bytes:
        path = self._path(sha256)
        if not path.is_file():
            raise ArtifactNotFoundError(sha256)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ArtifactNotFoundError(f"{sha256} is corrupt in the store")
        return data

    def fetch_to(self, sha256: str, dest: Path) -> None:
        path = self._path(sha256)
        if not path.is_file():
            raise ArtifactNotFoundError(sha256)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with path.open("rb") as src, dest.open("wb") as out:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                out.write(chunk)
        if hash_file(dest).sha256 != sha256:
            dest.unlink(missing_ok=True)
            raise ArtifactNotFoundError(f"{sha256} is corrupt in the store")

    def exists(self, sha256: str) -> bool:
        return self._path(sha256).is_file()
