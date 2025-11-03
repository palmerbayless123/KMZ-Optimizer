"""Custom exception hierarchy for the KMZ Optimizer domain."""

from __future__ import annotations


class ProcessingError(RuntimeError):
    """Raised when the processing pipeline fails."""

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}

    def as_dict(self) -> dict:
        """Return a serializable representation."""
        payload = {"message": str(self)}
        if self.details:
            payload["details"] = self.details
        return payload
