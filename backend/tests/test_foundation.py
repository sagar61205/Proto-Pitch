"""Configuration, redaction, artifact store, workspaces and migrations."""

from __future__ import annotations

import io
import json
import logging
import tarfile
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from protopitch.context import AppContext
from protopitch.db.models import Base
from protopitch.logging_setup import JsonFormatter
from protopitch.security.redaction import REDACTED, Redactor
from protopitch.settings import load_settings
from protopitch.storage.artifacts import ArtifactNotFoundError, LocalArtifactStore
from protopitch.storage.workspace import WorkspaceManager, confined, pack_tree, unpack_tree

from .conftest import REPO_ROOT


def test_settings_come_from_yaml_and_environment(tmp_path: Path) -> None:
    defaults = load_settings(REPO_ROOT, {})
    assert defaults.server.host == "127.0.0.1"
    assert defaults.jobs.max_step_attempts == 3
    assert defaults.data_dir == REPO_ROOT / "data"
    overridden = load_settings(
        REPO_ROOT,
        {"PROTOPITCH_SERVER__PORT": "9001", "PROTOPITCH_STORAGE__DATA_DIR": str(tmp_path)},
    )
    assert overridden.server.port == 9001
    assert overridden.data_dir == tmp_path


def test_unknown_settings_are_rejected() -> None:
    with pytest.raises(ValueError):
        load_settings(REPO_ROOT, {"PROTOPITCH_SERVER__NO_SUCH_OPTION": "1"})


def test_start_up_needs_no_keys_and_configuration_names_no_provider() -> None:
    """Zero-API invariant: nothing in the platform configuration asks for a model or key."""
    text = "".join(p.read_text() for p in (REPO_ROOT / "config").glob("*.yaml")).lower()
    for word in ("api_key", "anthropic", "openai", "gemini", "ollama"):
        assert word not in text


def test_redactor_hides_known_values_and_credential_shapes() -> None:
    redactor = Redactor.from_environment({"MY_API_KEY": "abcd1234efgh5678", "HOME": "/home/x"})
    text = redactor.redact(
        "key abcd1234efgh5678 and Authorization: Bearer zzzzzzzzzzzz and password=hunter2hunter2 "
        "and sk-ABCDEFGHIJKLMNOPQRSTUV but /home/x stays"
    )
    assert "abcd1234efgh5678" not in text
    assert "zzzzzzzzzzzz" not in text
    assert "hunter2hunter2" not in text
    assert "sk-ABCDEFGHIJKLMNOPQRSTUV" not in text
    assert "/home/x stays" in text
    assert REDACTED in text


def test_log_records_are_json_and_redacted() -> None:
    formatter = JsonFormatter(Redactor(["s3cr3t-value-123"]))
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "token is %s", ("s3cr3t-value-123",), None
    )
    record.job_id = "j1"
    payload = json.loads(formatter.format(record))
    assert payload["message"] == f"token is {REDACTED}"
    assert payload["job_id"] == "j1"


def test_artifact_store_is_content_addressed(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "a")
    ref = store.put_bytes(b"hello")
    assert store.put_bytes(b"hello") == ref
    assert store.get_bytes(ref.sha256) == b"hello"
    assert store.exists(ref.sha256)
    with pytest.raises(ArtifactNotFoundError):
        store.get_bytes("0" * 64)
    with pytest.raises(ValueError):
        store.get_bytes("../../etc/passwd")


def test_artifact_store_detects_corruption(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "a")
    ref = store.put_bytes(b"hello")
    blob = next((tmp_path / "a").rglob(ref.sha256))
    blob.write_bytes(b"tampered")
    with pytest.raises(ArtifactNotFoundError):
        store.get_bytes(ref.sha256)


def test_workspace_snapshots_are_deterministic_and_restorable(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path / "ws", LocalArtifactStore(tmp_path / "a"))
    first = manager.path_for("p1", 1)
    manager.materialise(first, None)
    (first / "sub").mkdir()
    (first / "sub" / "b.txt").write_text("b")
    (first / "a.txt").write_text("a")
    snapshot = manager.save(first)

    other = manager.path_for("p2", 1)
    manager.materialise(other, snapshot)
    assert (other / "sub" / "b.txt").read_text() == "b"
    assert manager.save(other) == snapshot  # same content, same hash, wherever it lives

    # A dirty directory is replaced, not merged.
    manager.begin_changes(other)
    (other / "junk.txt").write_text("junk")
    manager.materialise(other, snapshot)
    assert not (other / "junk.txt").exists()


def test_paths_cannot_escape_their_root(tmp_path: Path) -> None:
    assert confined(tmp_path, "a", "b") == tmp_path.resolve() / "a" / "b"
    with pytest.raises(ValueError):
        confined(tmp_path, "..", "elsewhere")
    with pytest.raises(ValueError):
        confined(tmp_path, "/etc/passwd")


def test_unpacking_refuses_archives_that_escape(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo("../outside.txt")
        info.size = 3
        tar.addfile(info, io.BytesIO(b"bad"))
    with pytest.raises(tarfile.TarError):
        unpack_tree(buffer.getvalue(), tmp_path / "dest")
    assert not (tmp_path / "outside.txt").exists()


def test_symlinks_are_stored_as_links_not_followed(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("host secret")
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "link").symlink_to(secret)
    assert b"host secret" not in pack_tree(tree)


def test_migrations_create_exactly_the_model_schema(ctx: AppContext) -> None:
    tables = set(inspect(ctx.engine).get_table_names())
    assert {
        "projects", "project_versions", "jd_documents", "artifacts", "jobs", "steps",
        "job_events", "approvals", "audit_events",
    } <= tables  # fmt: skip
    with ctx.engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migrations have drifted: {diff}"
    with ctx.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
