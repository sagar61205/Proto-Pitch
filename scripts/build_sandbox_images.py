#!/usr/bin/env python3
"""Build the sandbox profile images, tagged by the hash of their dependency lock.

Usage: build_sandbox_images.py [--lock] [profile ...]

  --lock   regenerate requirements.lock from requirements.in (needs uv and network)

Environment (all optional, for restricted networks):
  PROTOPITCH_BUILD_NETWORK     e.g. "host"
  PROTOPITCH_BUILD_CA_BUNDLE   path to a CA bundle passed to pip as a build secret
  PROTOPITCH_BUILD_BASE_IMAGE  alternative reference for the pinned base image
  PROTOPITCH_DOCKER            docker binary (default "docker")
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "sandbox-images"
IMAGE_NAMES = {"core": "protopitch-sbx-core"}


def compile_lock(profile: str) -> None:
    directory = IMAGES / profile
    subprocess.run(
        [
            "uv", "pip", "compile", "--universal", "--generate-hashes", "--no-header",
            "--python-version", "3.12", "requirements.in", "-o", "requirements.lock",
        ],
        cwd=directory,
        check=True,
    )  # fmt: skip


def build(profile: str) -> str:
    directory = IMAGES / profile
    lock = directory / "requirements.lock"
    if not lock.is_file():
        sys.exit(f"{lock} is missing; run with --lock first")
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest()
    tag = f"{IMAGE_NAMES[profile]}:{lock_hash[:12]}"
    command = [
        os.environ.get("PROTOPITCH_DOCKER", "docker"), "build",
        "--build-arg", f"LOCK_HASH={lock_hash}", "--tag", tag,
    ]  # fmt: skip
    if network := os.environ.get("PROTOPITCH_BUILD_NETWORK"):
        command += ["--network", network]
    if ca_bundle := os.environ.get("PROTOPITCH_BUILD_CA_BUNDLE"):
        command += ["--secret", f"id=ca_bundle,src={ca_bundle}"]
    if base := os.environ.get("PROTOPITCH_BUILD_BASE_IMAGE"):
        command += ["--build-arg", f"BASE_IMAGE={base}"]
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        if value := os.environ.get(proxy) or os.environ.get(proxy.lower()):
            command += ["--build-arg", f"{proxy}={value}"]
    command.append(str(directory))
    env = dict(os.environ, DOCKER_BUILDKIT="1")
    subprocess.run(command, check=True, env=env)
    return tag


def main() -> None:
    args = sys.argv[1:]
    relock = "--lock" in args
    profiles = [a for a in args if not a.startswith("--")] or sorted(IMAGE_NAMES)
    for profile in profiles:
        if profile not in IMAGE_NAMES:
            sys.exit(f"unknown profile: {profile}")
        if relock:
            compile_lock(profile)
        else:
            print(f"built {build(profile)}")  # noqa: T201


if __name__ == "__main__":
    main()
