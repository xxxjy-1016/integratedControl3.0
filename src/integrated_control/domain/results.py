from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionResult:
    """Report operation success, status, error code, message, and available measurements."""
    success: bool
    status: str
    error_code: str | None = None
    message: str = ""
    measurements: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def done(
        cls,
        message: str = "",
        measurements: dict[str, Any] | None = None,
    ) -> "ActionResult":
        """Construct an ActionResult indicating successful completion."""
        return cls(True, "DONE", message=message, measurements=measurements or {})

    @classmethod
    def failed(cls, error_code: str, message: str) -> "ActionResult":
        """Construct an ActionResult indicating failure."""
        return cls(False, "FAULT", error_code=error_code, message=message)
