"""
Base connection class for all network devices.
This module defines the `BaseConnection` class,
which serves as an abstract base class for all types of network device connections (e.g., SSH, Telnet, API).
It provides a common interface for connecting to devices, sending commands and configurations, and checking connection status.
Subclasses must implement the abstract methods defined in this class.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging


class BaseConnection(ABC):
    """Abstract base class for device connections."""

    def __init__(self, host: str, username: str, password: str,
                 port: Optional[int] = None, timeout: int = 30):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.session = None
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to device."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to device."""
        pass

    @abstractmethod
    def send_command(self, command: str, **kwargs) -> str:
        """Send command to device and return output."""
        pass

    @abstractmethod
    def send_config(self, config: str, **kwargs) -> str:
        """Send configuration to device."""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if connection is active."""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
