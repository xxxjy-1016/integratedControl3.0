class IntegratedControlError(Exception):
    """Base exception for the PC control application."""


class ConfigurationError(IntegratedControlError):
    """Raised when startup configuration is missing or invalid."""


class DeviceNotReadyError(IntegratedControlError):
    """Raised when a device command is sent before initialization."""


class DeviceLimitError(IntegratedControlError):
    """Raised when a requested target exceeds a configured limit."""


class TransportError(IntegratedControlError):
    """Raised when bytes cannot be exchanged with a device."""


class CommunicationTimeoutError(TransportError):
    """Raised when a transport or device operation times out."""


class ProtocolError(IntegratedControlError):
    """Raised when a device response violates its protocol."""


class DeviceError(IntegratedControlError):
    """Raised when a device reports a non-recoverable fault."""


class PersistenceError(IntegratedControlError):
    """Raised when durable runtime state cannot be read or written."""
