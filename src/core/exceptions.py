"""
Custom exceptions for the network automation framework.
"""

from typing import Optional


class MiraException(Exception):
    """Base exception for all framework errors."""
    pass


class MiraBaseException(MiraException):
    """Base exception for all framework errors with additional context."""

    def __init__(self, message: str, **context):
        super().__init__(message)
        self.context = context
        self.message = message

    def __str__(self):
        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        return f"{self.message} ({context_str})" if context_str else self.message


class ConnectionError(MiraException):
    """Connection-related errors."""

    def __init__(self, message: str, host: Optional[str] = None,
                 port: Optional[int] = None, protocol: Optional[str] = None):
        super().__init__(message)
        self.host = host
        self.port = port
        self.protocol = protocol
        self.message = message

    def __str__(self):
        if self.host:
            return f"[{self.host}:{self.port}] {self.message}"
        return self.message


class AuthenticationError(ConnectionError):
    """Authentication failures."""
    pass


class TimeoutError(ConnectionError):
    """Timeout errors."""
    pass


class CommandError(MiraException):
    """Command execution errors."""

    def __init__(self, message: str, command: Optional[str] = None,
                 output: Optional[str] = None):
        super().__init__(message)
        self.command = command
        self.output = output


class ConfigError(MiraException):
    """Configuration errors."""
    pass


class ParseError(MiraException):
    """Parsing errors."""
    pass


class ValidationError(MiraException):
    """Validation errors."""
    pass


class TopologyError(MiraException):
    """Base topology exception."""
    pass


class DeviceNotFoundError(TopologyError):
    """Device not found in topology."""
    def __init__(self, device_name: str):
        self.device_name = device_name
        super().__init__(f"Device not found: {device_name}")


class DeviceExistsError(TopologyError):
    """Device already exists in topology."""
    def __init__(self, device_name: str):
        self.device_name = device_name
        super().__init__(f"Device already exists: {device_name}")


class LinkNotFoundError(TopologyError):
    """Link not found in topology."""
    def __init__(self, source: str, dest: str):
        self.source = source
        self.dest = dest
        super().__init__(f"Link not found: {source} <-> {dest}")


class LinkExistsError(TopologyError):
    """Link already exists in topology."""
    def __init__(self, source: str, dest: str):
        self.source = source
        self.dest = dest
        super().__init__(f"Link already exists: {source} <-> {dest}")


class InterfaceNotFoundError(TopologyError):
    """Interface not found on device."""
    def __init__(self, device_name: str, interface_name: str):
        self.device_name = device_name
        self.interface_name = interface_name
        super().__init__(f"Interface not found: {device_name}:{interface_name}")


class TopologyValidationError(TopologyError):
    """Topology validation failed."""
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__(f"Topology validation failed: {errors}")


class PathNotFoundError(TopologyError):
    """No path found between devices."""
    def __init__(self, source: str, dest: str):
        self.source = source
        self.dest = dest
        super().__init__(f"No path found: {source} -> {dest}")


class TopologyLoadError(TopologyError):
    """Failed to load topology from file."""
    def __init__(self, filepath: str, reason: str):
        self.filepath = filepath
        self.reason = reason
        super().__init__(f"Failed to load topology from {filepath}: {reason}")
