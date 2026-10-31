"""Typed exceptions tools raise; envelope.py maps them to stable error codes.

Every tool function raises one of these instead of returning ad-hoc error
dicts, so the envelope builder is the single place that decides the wire
format. Never let a raw exception/traceback reach the model.
"""


class ToolError(Exception):
    code: str = "INTERNAL_ERROR"
    retryable: bool = False


class ToolInputError(ToolError):
    code = "INVALID_ARGUMENT"


class RecordNotFoundError(ToolError):
    code = "RECORD_NOT_FOUND"


class AmbiguousReferenceError(ToolError):
    code = "AMBIGUOUS_REFERENCE"


class InsufficientEvidenceError(ToolError):
    code = "INSUFFICIENT_EVIDENCE"


class PolicyDeniedError(ToolError):
    code = "POLICY_DENIED"


class ApprovalRequiredError(ToolError):
    code = "APPROVAL_REQUIRED"


class ActionFailedError(ToolError):
    code = "ACTION_FAILED"
    retryable = True


class DependencyUnavailableError(ToolError):
    code = "DEPENDENCY_UNAVAILABLE"
    retryable = True


class VerificationFailedError(ToolError):
    code = "VERIFICATION_FAILED"


class DuplicateOperationError(ToolError):
    code = "DUPLICATE_OPERATION"


class InvalidStateTransitionError(ToolError):
    code = "INVALID_STATE_TRANSITION"
