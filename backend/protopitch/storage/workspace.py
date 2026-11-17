"""Workspaces: local directories that are only a cache of a snapshot in the artifact store.

A step starts by materialising the workspace from its snapshot and ends by saving a new
snapshot. A worker on another machine, or the same worker after its directory was deleted,
therefore continues correctly (ARCHITECTURE §13).
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path

from protopitch.storage.artifacts import ArtifactStore


def confined(root: Path, *parts: str) -> Path:
    """Join ``parts`` under ``root`` and refuse anything that escapes it."""
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*parts).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"path escapes its root: {candidate}")
    return candidate


def _normalised(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    if info.isdir():
        info.mode = 0o755
    elif info.isfile():
        info.mode = 0o755 if info.mode & stat.S_IXUSR else 0o644
    return info


def pack_tree(directory: Path) -> bytes:
    """Deterministic tar of ``directory``: same content always yields the same bytes."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        entries = sorted(directory.rglob("*"), key=lambda p: p.relative_to(directory).as_posix())
        for path in entries:
            if not (path.is_symlink() or path.is_file() or path.is_dir()):
                continue  # sockets, devices and fifos are never part of a workspace
            arcname = path.relative_to(directory).as_posix()
            info = tar.gettarinfo(str(path), arcname=arcname)
            info = _normalised(info)
            if info.isfile():
                with path.open("rb") as handle:
                    tar.addfile(info, handle)
            else:
                tar.addfile(info)
    return buffer.getvalue()


def unpack_tree(data: bytes, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
        # The "data" filter rejects absolute paths, traversal and links leaving the tree.
        tar.extractall(dest, filter="data")  # noqa: S202


def make_tree_writable_for_sandbox(directory: Path) -> None:
    """The sandbox runs as a different, unprivileged user and must be able to write here."""
    for current, dirs, files in os.walk(directory):
        for name in dirs + files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            mode = path.stat().st_mode
            wanted = mode | 0o666 | (0o111 if path.is_dir() or mode & stat.S_IXUSR else 0)
            if wanted != mode:
                try:
                    path.chmod(wanted)
                except PermissionError:
                    pass  # created by the sandbox user with an open umask already
    directory.chmod(directory.stat().st_mode | 0o777)


class WorkspaceManager:
    def __init__(self, root: Path, artifacts: ArtifactStore) -> None:
        self._root = root
        self._artifacts = artifacts

    def path_for(self, project_id: str, version: int) -> Path:
        return confined(self._root, project_id, f"v{version}")

    def scratch_path(self, job_id: str) -> Path:
        return confined(self._root, "_jobs", job_id)

    def _marker(self, directory: Path) -> Path:
        return directory.with_name(directory.name + ".snapshot")

    def materialise(self, directory: Path, snapshot: str | None) -> None:
        """Make ``directory`` exactly equal to ``snapshot`` (empty when there is none)."""
        marker = self._marker(directory)
        if (
            snapshot is not None
            and directory.is_dir()
            and marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == snapshot
        ):
            return
        marker.unlink(missing_ok=True)
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        if snapshot is not None:
            unpack_tree(self._artifacts.get_bytes(snapshot), directory)
            self._write_marker(directory, snapshot)

    def begin_changes(self, directory: Path) -> None:
        """Call before a step touches the directory: it no longer matches any snapshot."""
        self._marker(directory).unlink(missing_ok=True)

    def save(self, directory: Path) -> str:
        ref = self._artifacts.put_bytes(pack_tree(directory))
        self._write_marker(directory, ref.sha256)
        return ref.sha256

    def _write_marker(self, directory: Path, snapshot: str) -> None:
        marker = self._marker(directory)
        fd, tmp = tempfile.mkstemp(dir=marker.parent, prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(snapshot)
        os.replace(tmp, marker)

    def remove_project(self, project_id: str) -> None:
        target = confined(self._root, project_id)
        if target.exists():
            shutil.rmtree(target)
