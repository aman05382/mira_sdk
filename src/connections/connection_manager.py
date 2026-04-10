"""Connection manager for handling multiple device connections."""

from typing import Dict, Optional, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from .base_connection import BaseConnection
from .connection_factory import ConnectionFactory
from core.exceptions import ConnectionError
from core.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manager for multiple device connections."""

    def __init__(self, max_workers: int = 10):
        """
        Initialize connection manager.

        Args:
            max_workers: Maximum number of parallel connections
        """
        self.connections: Dict[str, BaseConnection] = {}
        self.max_workers = max_workers
        self._lock = threading.Lock()

        logger.info(f"Initialized ConnectionManager with {max_workers} max workers")

    def add_connection(
        self,
        name: str,
        device_type: str,
        host: str,
        username: str,
        password: str,
        **kwargs
    ) -> BaseConnection:
        """
        Add a new connection.

        Args:
            name: Unique name for the connection
            device_type: Type of device
            host: Device hostname/IP
            username: Username
            password: Password
            **kwargs: Additional connection parameters

        Returns:
            Created connection instance
        """
        with self._lock:
            if name in self.connections:
                logger.warning(f"Connection {name} already exists, replacing")

            connection = ConnectionFactory.create_connection(
                device_type=device_type,
                host=host,
                username=username,
                password=password,
                **kwargs
            )

            self.connections[name] = connection
            logger.info(f"Added connection: {name}")

            return connection

    def get_connection(self, name: str) -> Optional[BaseConnection]:
        """
        Get connection by name.

        Args:
            name: Connection name

        Returns:
            Connection instance or None
        """
        return self.connections.get(name)

    def remove_connection(self, name: str) -> bool:
        """
        Remove and disconnect a connection.

        Args:
            name: Connection name

        Returns:
            bool: True if removed successfully
        """
        with self._lock:
            if name in self.connections:
                connection = self.connections[name]
                if connection.is_alive():
                    connection.disconnect()
                del self.connections[name]
                logger.info(f"Removed connection: {name}")
                return True
            return False

    def connect_all(self, parallel: bool = True) -> Dict[str, bool]:
        """
        Connect all managed connections.

        Args:
            parallel: Connect in parallel if True

        Returns:
            Dictionary of connection results {name: success}
        """
        results = {}

        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_name = {
                    executor.submit(self._connect_device, name, conn): name
                    for name, conn in self.connections.items()
                }

                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        results[name] = future.result()
                    except Exception as e:
                        logger.error(f"Error connecting {name}: {e}")
                        results[name] = False
        else:
            for name, conn in self.connections.items():
                results[name] = self._connect_device(name, conn)

        return results

    def disconnect_all(self) -> Dict[str, bool]:
        """
        Disconnect all connections.

        Returns:
            Dictionary of disconnection results {name: success}
        """
        results = {}

        for name, conn in self.connections.items():
            try:
                if conn.is_alive():
                    results[name] = conn.disconnect()
                else:
                    results[name] = True
            except Exception as e:
                logger.error(f"Error disconnecting {name}: {e}")
                results[name] = False

        return results

    def execute_command(
        self,
        command: str,
        devices: Optional[List[str]] = None,
        parallel: bool = True
    ) -> Dict[str, str]:
        """
        Execute command on multiple devices.

        Args:
            command: Command to execute
            devices: List of device names (None = all devices)
            parallel: Execute in parallel if True

        Returns:
            Dictionary of results {device_name: output}
        """
        target_devices = devices or list(self.connections.keys())
        results = {}

        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_name = {
                    executor.submit(
                        self._execute_on_device, name, command
                    ): name
                    for name in target_devices
                    if name in self.connections
                }

                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        results[name] = future.result()
                    except Exception as e:
                        logger.error(f"Error executing on {name}: {e}")
                        results[name] = f"ERROR: {str(e)}"
        else:
            for name in target_devices:
                if name in self.connections:
                    results[name] = self._execute_on_device(name, command)

        return results

    def _connect_device(self, name: str, connection: BaseConnection) -> bool:
        """Connect a single device."""
        try:
            logger.info(f"Connecting to {name}")
            result = connection.connect()
            logger.info(f"Successfully connected to {name}")
            return result
        except Exception as e:
            logger.error(f"Failed to connect to {name}: {e}")
            return False

    def _execute_on_device(self, name: str, command: str) -> str:
        """Execute command on a single device."""
        connection = self.connections.get(name)
        if not connection:
            raise ConnectionError(f"Connection {name} not found")

        if not connection.is_alive():
            connection.connect()

        return connection.send_command(command)

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all connections.

        Returns:
            Dictionary of connection statuses
        """
        status = {}

        for name, conn in self.connections.items():
            status[name] = {
                'connected': conn.is_alive(),
                'host': conn.host,
                'port': conn.port,
                'type': conn.__class__.__name__
            }

        return status

    def __len__(self) -> int:
        """Return number of managed connections."""
        return len(self.connections)

    def __enter__(self):
        """Context manager entry."""
        self.connect_all()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect_all()

    def __repr__(self) -> str:
        """String representation."""
        return f"ConnectionManager(connections={len(self.connections)})"
