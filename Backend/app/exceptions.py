from __future__ import annotations


class BE2Error(Exception):
    """Base structured error for BE2 services."""

    code = "be2_error"
    retryable = False

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details, "retryable": self.retryable}


class ValidationError(BE2Error):
    code = "validation_error"


class TransientServiceError(BE2Error):
    code = "transient_service_error"
    retryable = True


class PermanentServiceError(BE2Error):
    code = "permanent_service_error"


class ContractMissingError(BE2Error):
    code = "contract_missing"


class ExternalServiceError(TransientServiceError):
    code = "external_service_error"
