from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionResult:
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
        return cls(True, "DONE", message=message, measurements=measurements or {})

    @classmethod
    def failed(cls, error_code: str, message: str) -> "ActionResult":
        return cls(False, "FAULT", error_code=error_code, message=message)
