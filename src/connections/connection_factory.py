"""Factory for creating device connections."""

from typing import Optional, Dict, Any
from .base_connection import BaseConnection
from .vendors.sonic.sonic_connection import SONiCConnection
from core.exceptions import ConnectionError
from core.logger import get_logger

logger = get_logger(__name__)


class ConnectionFactory:
    """Factory class for creating device connections."""

    # Registry of connection classes
    _connection_registry: Dict[str, type] = {
        'sonic': SONiCConnection,
        # Add more vendors here as implemented
        # 'cisco_ios': CiscoIOSConnection,
        # 'cisco_nxos': CiscoNXOSConnection,
        # 'juniper_junos': JuniperJunOSConnection,
        # 'arista_eos': AristaEOSConnection,
    }

    @classmethod
    def create_connection(
        cls,
        device_type: str,
        host: str,
        username: str,
        password: str,
        **kwargs
    ) -> BaseConnection:
        """
        Create a connection instance based on device type.

        Args:
            device_type: Type of device (e.g., 'sonic', 'cisco_ios')
            host: Device hostname/IP
            username: Authentication username
            password: Authentication password
            **kwargs: Additional connection parameters

        Returns:
            Connection instance

        Raises:
            ConnectionError: If device type not supported
        """
        device_type = device_type.lower()

        if device_type not in cls._connection_registry:
            raise ConnectionError(
                f"Unsupported device type: {device_type}. "
                f"Supported types: {list(cls._connection_registry.keys())}"
            )

        connection_class = cls._connection_registry[device_type]

        logger.info(f"Creating {device_type} connection to {host}")

        return connection_class(
            host=host,
            username=username,
            password=password,
            **kwargs
        )

    @classmethod
    def register_connection(cls, device_type: str, connection_class: type):
        """
        Register a new connection class.

        Args:
            device_type: Device type identifier
            connection_class: Connection class to register
        """
        cls._connection_registry[device_type.lower()] = connection_class
        logger.info(f"Registered connection type: {device_type}")

    @classmethod
    def get_supported_types(cls) -> list:
        """Get list of supported device types."""
        return list(cls._connection_registry.keys())
