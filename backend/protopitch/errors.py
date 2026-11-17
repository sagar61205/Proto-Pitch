"""Errors the owner may see: a stable code, a plain message and suggested next actions."""

from __future__ import annotations


class PlatformError(Exception):
    code = "platform_error"
    status_code = 500

    def __init__(self, message: str, *, next_actions: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.next_actions = next_actions or []

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "next_actions": self.next_actions}


class NotFoundError(PlatformError):
    code = "not_found"
    status_code = 404


class ValidationFailedError(PlatformError):
    code = "validation_failed"
    status_code = 422


class ConflictError(PlatformError):
    code = "conflict"
    status_code = 409


class IllegalTransitionError(PlatformError):
    code = "illegal_transition"
    status_code = 409


class ApprovalRequiredError(PlatformError):
    code = "approval_required"
    status_code = 403


class ForbiddenError(PlatformError):
    code = "forbidden"
    status_code = 403


class SandboxUnavailableError(PlatformError):
    code = "sandbox_unavailable"
    status_code = 503


class LeaseLostError(PlatformError):
    """The worker no longer owns the job; it must stop without writing results."""

    code = "lease_lost"
    status_code = 409
