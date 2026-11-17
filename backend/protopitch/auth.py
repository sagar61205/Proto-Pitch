"""Authentication hook. Every API route depends on it, so real authentication can be added
later without touching the routes (ARCHITECTURE §13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from protopitch.settings import Settings


@dataclass(frozen=True)
class Principal:
    id: str
    display_name: str


class AuthProvider(Protocol):
    def authenticate(self, request: Request) -> Principal: ...


class LocalNoAuth:
    """v1: one owner, no login. Safe only because the server is bound to localhost and the
    API refuses unknown Host headers and cross-site state-changing requests."""

    def authenticate(self, request: Request) -> Principal:
        return Principal(id="owner", display_name="Owner")


def build_auth_provider(settings: Settings) -> AuthProvider:
    if settings.auth.provider == "local_no_auth":
        return LocalNoAuth()
    raise ValueError(f"unknown auth provider: {settings.auth.provider}")


def require_principal(request: Request) -> Principal:
    provider: AuthProvider = request.app.state.auth
    principal = provider.authenticate(request)
    request.state.principal = principal
    return principal
