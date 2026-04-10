"""Main SONiC connection class combining multiple protocols."""

from typing import Optional, Dict, Any, List, Union
from connections.protocols.ssh_connection import SSHConnection
from connections.protocols.redis_connection import RedisConnection
from core.exceptions import ConnectionError
from core.logger import get_logger

logger = get_logger(__name__)


class SONiCConnection:
    """
    Comprehensive SONiC device connection supporting multiple protocols.

    Provides unified interface for SONiC automation via:
    - SSH/CLI
    - Redis (CONFIG_DB, APPL_DB, etc.)
    - REST API (optional)
    - gNMI (optional)
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        ssh_port: int = 22,
        redis_port: int = 6379,
        timeout: int = 30,
        enable_redis: bool = True,
        enable_rest: bool = False,
        enable_gnmi: bool = False,
        **kwargs
    ):
        """
        Initialize SONiC connection.

        Args:
            host: Device hostname/IP
            username: SSH username
            password: SSH password
            ssh_port: SSH port
            redis_port: Redis port
            timeout: Connection timeout
            enable_redis: Enable Redis connection
            enable_rest: Enable REST API connection
            enable_gnmi: Enable gNMI connection
        """
        self.host = host
        self.username = username
        self.password = password
        self.ssh_port = ssh_port
        self.redis_port = redis_port
        self.timeout = timeout

        # Initialize connections
        self.ssh: Optional[SSHConnection] = None
        self.redis_config: Optional[RedisConnection] = None
        self.redis_appl: Optional[RedisConnection] = None
        self.redis_state: Optional[RedisConnection] = None
        self.redis_counters: Optional[RedisConnection] = None

        self._enable_redis = enable_redis
        self._enable_rest = enable_rest
        self._enable_gnmi = enable_gnmi
        self._kwargs = kwargs

        logger.info(f"Initialized SONiC connection to {host}")

    def connect(self) -> bool:
        """
        Establish all enabled connections.

        Returns:
            bool: True if connections successful
        """
        try:
            # Connect SSH (primary connection)
            logger.info(f"Connecting to SONiC device {self.host} via SSH")
            self.ssh = SSHConnection(
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.ssh_port,
                device_type="sonic",
                timeout=self.timeout,
                **self._kwargs
            )
            self.ssh.connect()

            # Connect to Redis databases if enabled
            if self._enable_redis:
                self._connect_redis_dbs()

            logger.info(f"Successfully connected to SONiC device {self.host}")
            return True

        except Exception as e:
            logger.error(f"Error connecting to SONiC device {self.host}: {e}")
            self.disconnect()
            raise ConnectionError(f"SONiC connection failed: {e}")

    def _connect_redis_dbs(self):
        """Connect to SONiC Redis databases."""
        try:
            # CONFIG_DB
            logger.debug(f"Connecting to CONFIG_DB on {self.host}")
            self.redis_config = RedisConnection(
                host=self.host,
                port=self.redis_port,
                db=RedisConnection.CONFIG_DB,
                socket_timeout=self.timeout
            )
            self.redis_config.connect()

            # APPL_DB
            logger.debug(f"Connecting to APPL_DB on {self.host}")
            self.redis_appl = RedisConnection(
                host=self.host,
                port=self.redis_port,
                db=RedisConnection.APPL_DB,
                socket_timeout=self.timeout
            )
            self.redis_appl.connect()

            # STATE_DB
            logger.debug(f"Connecting to STATE_DB on {self.host}")
            self.redis_state = RedisConnection(
                host=self.host,
                port=self.redis_port,
                db=RedisConnection.STATE_DB,
                socket_timeout=self.timeout
            )
            self.redis_state.connect()

            # COUNTERS_DB
            logger.debug(f"Connecting to COUNTERS_DB on {self.host}")
            self.redis_counters = RedisConnection(
                host=self.host,
                port=self.redis_port,
                db=RedisConnection.COUNTERS_DB,
                socket_timeout=self.timeout
            )
            self.redis_counters.connect()

            logger.info(f"Connected to all Redis databases on {self.host}")

        except Exception as e:
            logger.error(f"Error connecting to Redis databases: {e}")
            raise

    def disconnect(self) -> bool:
        """
        Close all connections.

        Returns:
            bool: True if disconnections successful
        """
        success = True

        try:
            if self.ssh:
                self.ssh.disconnect()
                self.ssh = None

            if self.redis_config:
                self.redis_config.disconnect()
                self.redis_config = None

            if self.redis_appl:
                self.redis_appl.disconnect()
                self.redis_appl = None

            if self.redis_state:
                self.redis_state.disconnect()
                self.redis_state = None

            if self.redis_counters:
                self.redis_counters.disconnect()
                self.redis_counters = None

            logger.info(f"Disconnected from SONiC device {self.host}")

        except Exception as e:
            logger.error(f"Error disconnecting from {self.host}: {e}")
            success = False

        return success

    def is_alive(self) -> bool:
        """
        Check if primary connection (SSH) is alive.

        Returns:
            bool: True if connection is alive
        """
        return self.ssh is not None and self.ssh.is_alive()

    # SSH/CLI Methods

    def cli(self, command: str, **kwargs) -> str:
        """
        Execute CLI command via SSH.

        Args:
            command: Command to execute

        Returns:
            Command output
        """
        if not self.ssh:
            raise ConnectionError("SSH not connected")

        return self.ssh.send_command(command, **kwargs)

    def cli_config(self, commands: Union[str, List[str]], **kwargs) -> str:
        """
        Execute configuration commands via CLI.

        Args:
            commands: Configuration command(s)

        Returns:
            Configuration output
        """
        if not self.ssh:
            raise ConnectionError("SSH not connected")

        # SONiC uses 'sudo config' for configuration
        if isinstance(commands, str):
            commands = [commands]

        results = []
        for cmd in commands:
            if not cmd.startswith('sudo'):
                cmd = f'sudo {cmd}'
            results.append(self.ssh.send_command(cmd, **kwargs))

        return '\n'.join(results)

    # Show Commands

    def show_version(self) -> Dict[str, Any]:
        """Get SONiC version information."""
        output = self.cli("show version")
        return self._parse_show_version(output)

    def show_interfaces_status(self) -> str:
        """Get interface status."""
        return self.cli("show interfaces status")

    def show_interfaces_counters(self) -> str:
        """Get interface counters."""
        return self.cli("show interfaces counters")

    def show_ip_interfaces(self) -> str:
        """Get IP interface information."""
        return self.cli("show ip interfaces")

    def show_ip_route(self) -> str:
        """Get routing table."""
        return self.cli("show ip route")

    def show_ip_bgp_summary(self) -> str:
        """Get BGP summary."""
        return self.cli("show ip bgp summary")

    def show_vlan_brief(self) -> str:
        """Get VLAN brief information."""
        return self.cli("show vlan brief")

    def show_mac_address(self) -> str:
        """Get MAC address table."""
        return self.cli("show mac")

    def show_platform_summary(self) -> str:
        """Get platform summary."""
        return self.cli("show platform summary")

    def show_system_status(self) -> str:
        """Get system status."""
        return self.cli("show system-status")

    # CONFIG_DB Methods

    def config_db_get(self, table: str, key: Optional[str] = None) -> Union[Dict, List]:
        """
        Get configuration from CONFIG_DB.

        Args:
            table: Table name (e.g., 'PORT', 'VLAN', 'BGP_NEIGHBOR')
            key: Specific key (optional)

        Returns:
            Configuration data
        """
        if not self.redis_config:
            raise ConnectionError("Redis CONFIG_DB not connected")

        if key:
            # Get specific entry
            full_key = f"{table}|{key}"
            data = self.redis_config.hgetall(full_key)
            return data if data else {}
        else:
            # Get all entries for table
            pattern = f"{table}|*"
            keys = self.redis_config.keys(pattern)
            result = {}
            for k in keys:
                # Extract key name (after the pipe)
                key_name = k.split('|', 1)[1] if '|' in k else k
                result[key_name] = self.redis_config.hgetall(k)
            return result

    def config_db_set(self, table: str, key: str, field: str, value: str) -> bool:
        """
        Set configuration in CONFIG_DB.

        Args:
            table: Table name
            key: Key name
            field: Field name
            value: Field value

        Returns:
            bool: True if successful
        """
        if not self.redis_config:
            raise ConnectionError("Redis CONFIG_DB not connected")

        full_key = f"{table}|{key}"
        return bool(self.redis_config.hset(full_key, field, value))

    def config_db_delete(self, table: str, key: str) -> bool:
        """
        Delete configuration from CONFIG_DB.

        Args:
            table: Table name
            key: Key name

        Returns:
            bool: True if successful
        """
        if not self.redis_config:
            raise ConnectionError("Redis CONFIG_DB not connected")

        full_key = f"{table}|{key}"
        return bool(self.redis_config.delete(full_key))

    # PORT Configuration

    def get_port_config(self, port: Optional[str] = None) -> Dict:
        """Get port configuration."""
        return self.config_db_get("PORT", port)

    def set_port_admin_status(self, port: str, status: str) -> bool:
        """
        Set port admin status.

        Args:
            port: Port name (e.g., 'Ethernet0')
            status: 'up' or 'down'

        Returns:
            bool: True if successful
        """
        return self.config_db_set("PORT", port, "admin_status", status)

    def set_port_mtu(self, port: str, mtu: int) -> bool:
        """Set port MTU."""
        return self.config_db_set("PORT", port, "mtu", str(mtu))

    def set_port_speed(self, port: str, speed: str) -> bool:
        """
        Set port speed.

        Args:
            port: Port name
            speed: Speed value (e.g., '100000' for 100G)
        """
        return self.config_db_set("PORT", port, "speed", speed)

    # VLAN Configuration

    def get_vlan_config(self, vlan: Optional[str] = None) -> Dict:
        """Get VLAN configuration."""
        return self.config_db_get("VLAN", vlan)

    def create_vlan(self, vlan_id: int) -> bool:
        """
        Create VLAN.

        Args:
            vlan_id: VLAN ID

        Returns:
            bool: True if successful
        """
        vlan_name = f"Vlan{vlan_id}"
        return self.config_db_set("VLAN", vlan_name, "vlanid", str(vlan_id))

    def delete_vlan(self, vlan_id: int) -> bool:
        """Delete VLAN."""
        vlan_name = f"Vlan{vlan_id}"
        return self.config_db_delete("VLAN", vlan_name)

    def add_vlan_member(self, vlan_id: int, port: str, tagging_mode: str = "untagged") -> bool:
        """
        Add port to VLAN.

        Args:
            vlan_id: VLAN ID
            port: Port name
            tagging_mode: 'tagged' or 'untagged'
        """
        vlan_name = f"Vlan{vlan_id}"
        key = f"{vlan_name}|{port}"
        return self.config_db_set("VLAN_MEMBER", key, "tagging_mode", tagging_mode)

    # Interface IP Configuration

    def get_interface_ip(self, interface: Optional[str] = None) -> Dict:
        """Get interface IP configuration."""
        return self.config_db_get("INTERFACE", interface)

    def set_interface_ip(self, interface: str, ip_prefix: str) -> bool:
        """
        Set interface IP address.

        Args:
            interface: Interface name (e.g., 'Ethernet0')
            ip_prefix: IP address with prefix (e.g., '10.0.0.1/24')
        """
        key = f"{interface}|{ip_prefix}"
        return self.config_db_set("INTERFACE", key, "NULL", "NULL")

    def delete_interface_ip(self, interface: str, ip_prefix: str) -> bool:
        """Delete interface IP address."""
        key = f"{interface}|{ip_prefix}"
        return self.config_db_delete("INTERFACE", key)

    # BGP Configuration

    def get_bgp_neighbor(self, neighbor: Optional[str] = None) -> Dict:
        """Get BGP neighbor configuration."""
        return self.config_db_get("BGP_NEIGHBOR", neighbor)

    def add_bgp_neighbor(
        self,
        neighbor_ip: str,
        asn: int,
        name: Optional[str] = None
    ) -> bool:
        """
        Add BGP neighbor.

        Args:
            neighbor_ip: Neighbor IP address
            asn: AS number
            name: Neighbor name (optional)
        """
        success = self.config_db_set("BGP_NEIGHBOR", neighbor_ip, "asn", str(asn))
        if name and success:
            success = self.config_db_set("BGP_NEIGHBOR", neighbor_ip, "name", name)
        return success

    def delete_bgp_neighbor(self, neighbor_ip: str) -> bool:
        """Delete BGP neighbor."""
        return self.config_db_delete("BGP_NEIGHBOR", neighbor_ip)

    # APPL_DB Methods (Runtime State)

    def get_port_table(self, port: Optional[str] = None) -> Dict:
        """Get port information from APPL_DB."""
        if not self.redis_appl:
            raise ConnectionError("Redis APPL_DB not connected")

        if port:
            key = f"PORT_TABLE:{port}"
            return self.redis_appl.hgetall(key)
        else:
            pattern = "PORT_TABLE:*"
            keys = self.redis_appl.keys(pattern)
            result = {}
            for k in keys:
                port_name = k.split(':', 1)[1] if ':' in k else k
                result[port_name] = self.redis_appl.hgetall(k)
            return result

    def get_route_table(self, prefix: Optional[str] = None) -> Dict:
        """Get routing table from APPL_DB."""
        if not self.redis_appl:
            raise ConnectionError("Redis APPL_DB not connected")

        if prefix:
            key = f"ROUTE_TABLE:{prefix}"
            return self.redis_appl.hgetall(key)
        else:
            pattern = "ROUTE_TABLE:*"
            keys = self.redis_appl.keys(pattern)
            result = {}
            for k in keys:
                route = k.split(':', 1)[1] if ':' in k else k
                result[route] = self.redis_appl.hgetall(k)
            return result

    def get_neigh_table(self, ip: Optional[str] = None) -> Dict:
        """Get neighbor (ARP/NDP) table from APPL_DB."""
        if not self.redis_appl:
            raise ConnectionError("Redis APPL_DB not connected")

        if ip:
            # Try different interface patterns
            pattern = f"NEIGH_TABLE:*:{ip}"
            keys = self.redis_appl.keys(pattern)
            if keys:
                return self.redis_appl.hgetall(keys[0])
            return {}
        else:
            pattern = "NEIGH_TABLE:*"
            keys = self.redis_appl.keys(pattern)
            result = {}
            for k in keys:
                result[k] = self.redis_appl.hgetall(k)
            return result

    # STATE_DB Methods

    def get_port_state(self, port: Optional[str] = None) -> Dict:
        """Get port operational state from STATE_DB."""
        if not self.redis_state:
            raise ConnectionError("Redis STATE_DB not connected")

        if port:
            key = f"PORT_TABLE|{port}"
            return self.redis_state.hgetall(key)
        else:
            pattern = "PORT_TABLE|*"
            keys = self.redis_state.keys(pattern)
            result = {}
            for k in keys:
                port_name = k.split('|', 1)[1] if '|' in k else k
                result[port_name] = self.redis_state.hgetall(k)
            return result

    def get_interface_state(self, interface: Optional[str] = None) -> Dict:
        """Get interface state from STATE_DB."""
        if not self.redis_state:
            raise ConnectionError("Redis STATE_DB not connected")

        if interface:
            key = f"INTERFACE_TABLE|{interface}"
            return self.redis_state.hgetall(key)
        else:
            pattern = "INTERFACE_TABLE|*"
            keys = self.redis_state.keys(pattern)
            result = {}
            for k in keys:
                intf_name = k.split('|', 1)[1] if '|' in k else k
                result[intf_name] = self.redis_state.hgetall(k)
            return result

    # COUNTERS_DB Methods

    def get_port_counters(self, port: str) -> Dict:
        """
        Get port counters from COUNTERS_DB.

        Args:
            port: Port name

        Returns:
            Dictionary of counter values
        """
        if not self.redis_counters:
            raise ConnectionError("Redis COUNTERS_DB not connected")

        # Get port OID
        port_oid = self.redis_counters.hget("COUNTERS_PORT_NAME_MAP", port)
        if not port_oid:
            logger.warning(f"Port {port} not found in counter name map")
            return {}

        # Get counters for this port
        key = f"COUNTERS:{port_oid}"
        return self.redis_counters.hgetall(key)

    def get_queue_counters(self, port: str, queue: int) -> Dict:
        """Get queue counters for a specific port and queue."""
        if not self.redis_counters:
            raise ConnectionError("Redis COUNTERS_DB not connected")

        # This is a simplified implementation
        # Actual queue counter retrieval may be more complex
        pattern = f"COUNTERS:*:{port}:{queue}"
        keys = self.redis_counters.keys(pattern)
        if keys:
            return self.redis_counters.hgetall(keys[0])
        return {}

    # Utility Methods

    def _parse_show_version(self, output: str) -> Dict[str, Any]:
        """Parse show version output."""
        version_info = {}
        for line in output.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                version_info[key.strip()] = value.strip()
        return version_info

    def save_config(self) -> str:
        """Save running configuration."""
        return self.cli("sudo config save -y")

    def reload_config(self) -> str:
        """Reload configuration."""
        return self.cli("sudo config reload -y")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def __repr__(self) -> str:
        """String representation."""
        return f"SONiCConnection(host={self.host}, ssh_port={self.ssh_port})"
