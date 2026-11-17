# syntax=docker/dockerfile:1
# Sandbox profile "core". Built only by `make sandbox-images` from this platform-owned file;
# this is the one step that needs general network access, and it runs no generated code.
ARG BASE_IMAGE=python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
FROM ${BASE_IMAGE}

ARG LOCK_HASH
LABEL protopitch.profile="core" protopitch.lock_hash="${LOCK_HASH}"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.lock /opt/protopitch/requirements.lock

# Wheels only, every file hash-verified. An optional CA bundle supports builds behind a
# TLS-inspecting proxy without baking the certificate into the image.
RUN --mount=type=secret,id=ca_bundle,required=false \
    if [ -s /run/secrets/ca_bundle ]; then export PIP_CERT=/run/secrets/ca_bundle; fi; \
    pip install --no-cache-dir --require-hashes --only-binary=:all: \
        -r /opt/protopitch/requirements.lock

RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin sandbox \
    && mkdir /workspace && chown 10001:10001 /workspace

USER 10001:10001
WORKDIR /workspace
