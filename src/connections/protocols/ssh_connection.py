"""SSH connection implementation using Netmiko and Paramiko."""

from typing import Optional, List, Dict, Any, Union
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from connections.base_connection import BaseConnection
from core.exceptions import ConnectionError, AuthenticationError, TimeoutError
from core.logger import get_logger


logger = get_logger(__name__)


class SSHConnection(BaseConnection):
    """SSH connection implementation using Netmiko."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        device_type: str = "linux",
        port: int = 22,
        timeout: int = 30,
        session_timeout: int = 60,
        auth_timeout: int = 30,
        banner_timeout: int = 15,
        read_timeout_override: Optional[float] = None,
        keepalive: int = 0,
        global_delay_factor: float = 1.0,
        secret: str = "",
        verbose: bool = False,
        **kwargs
    ):
        """
        Initialize SSH connection.

        Args:
            host: Device hostname or IP
            username: SSH username
            password: SSH password
            device_type: Netmiko device type (default: linux)
            port: SSH port (default: 22)
            timeout: Connection timeout
            session_timeout: Session timeout
            auth_timeout: Authentication timeout
            banner_timeout: Banner timeout
            read_timeout_override: Override read timeout
            keepalive: Keepalive interval
            global_delay_factor: Global delay factor
            secret: Enable secret password
            verbose: Enable verbose logging
        """
        super().__init__(host, username, password, port, timeout)

        self.device_type = device_type
        self.session_timeout = session_timeout
        self.auth_timeout = auth_timeout
        self.banner_timeout = banner_timeout
        self.read_timeout_override = read_timeout_override
        self.keepalive = keepalive
        self.global_delay_factor = global_delay_factor
        self.secret = secret
        self.verbose = verbose
        self.session = None
        self._connection_params = kwargs

        logger.info(f"Initialized SSH connection to {host}:{port}")

    def connect(self) -> bool:
        """
        Establish SSH connection to device.

        Returns:
            bool: True if connection successful

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
            TimeoutError: If connection times out
        """
        try:
            logger.info(f"Connecting to {self.host}:{self.port} via SSH")

            connection_params = {
                'device_type': self.device_type,
                'host': self.host,
                'username': self.username,
                'password': self.password,
                'port': self.port,
                'timeout': self.timeout,
                'session_timeout': self.session_timeout,
                'auth_timeout': self.auth_timeout,
                'banner_timeout': self.banner_timeout,
                'global_delay_factor': self.global_delay_factor,
                'keepalive': self.keepalive,
                'verbose': self.verbose,
            }

            if self.secret:
                connection_params['secret'] = self.secret

            if self.read_timeout_override:
                connection_params['read_timeout_override'] = self.read_timeout_override

            # Add any additional parameters
            connection_params.update(self._connection_params)

            self.session = ConnectHandler(**connection_params)

            logger.info(f"Successfully connected to {self.host}")
            return True

        except NetmikoAuthenticationException as e:
            logger.error(f"Authentication failed for {self.host}: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")

        except NetmikoTimeoutException as e:
            logger.error(f"Connection timeout for {self.host}: {e}")
            raise TimeoutError(f"Connection timeout: {e}")

        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.host}: {e}")
            raise ConnectionError(f"Connection failed: {e}")

    def disconnect(self) -> bool:
        """
        Close SSH connection.

        Returns:
            bool: True if disconnection successful
        """
        try:
            if self.session:
                logger.info(f"Disconnecting from {self.host}")
                self.session.disconnect()
                self.session = None
                logger.info(f"Disconnected from {self.host}")
            return True

        except Exception as e:
            logger.error(f"Error disconnecting from {self.host}: {e}")
            return False

    def send_command(
        self,
        command: str,
        expect_string: Optional[str] = None,
        delay_factor: float = 1.0,
        max_loops: int = 500,
        strip_prompt: bool = True,
        strip_command: bool = True,
        normalize: bool = True,
        use_textfsm: bool = False,
        textfsm_template: Optional[str] = None,
        use_ttp: bool = False,
        ttp_template: Optional[str] = None,
        use_genie: bool = False,
        cmd_verify: bool = True,
        **kwargs
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Send command to device and return output.

        Args:
            command: Command to send
            expect_string: Expected string in output
            delay_factor: Delay factor for output
            max_loops: Maximum loops to wait for output
            strip_prompt: Strip prompt from output
            strip_command: Strip command from output
            normalize: Normalize linefeeds
            use_textfsm: Use TextFSM parsing
            textfsm_template: TextFSM template to use
            use_ttp: Use TTP parsing
            ttp_template: TTP template to use
            use_genie: Use Genie parsing
            cmd_verify: Verify command echo

        Returns:
            Command output (string or parsed data)

        Raises:
            ConnectionError: If not connected
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        try:
            logger.debug(f"Sending command to {self.host}: {command}")

            output = self.session.send_command(
                command,
                expect_string=expect_string,
                delay_factor=delay_factor,
                max_loops=max_loops,
                strip_prompt=strip_prompt,
                strip_command=strip_command,
                normalize=normalize,
                use_textfsm=use_textfsm,
                textfsm_template=textfsm_template,
                use_ttp=use_ttp,
                ttp_template=ttp_template,
                use_genie=use_genie,
                cmd_verify=cmd_verify,
                **kwargs
            )

            logger.debug(f"Command executed successfully on {self.host}")
            return output

        except Exception as e:
            logger.error(f"Error executing command on {self.host}: {e}")
            raise ConnectionError(f"Command execution failed: {e}")

    def send_config(
        self,
        config_commands: Union[str, List[str]],
        enter_config_mode: bool = True,
        exit_config_mode: bool = True,
        delay_factor: float = 1.0,
        max_loops: int = 150,
        strip_prompt: bool = False,
        strip_command: bool = False,
        config_mode_command: Optional[str] = None,
        cmd_verify: bool = True,
        **kwargs
    ) -> str:
        """
        Send configuration commands to device.

        Args:
            config_commands: Configuration command(s)
            enter_config_mode: Enter config mode before sending
            exit_config_mode: Exit config mode after sending
            delay_factor: Delay factor
            max_loops: Maximum loops
            strip_prompt: Strip prompt from output
            strip_command: Strip command from output
            config_mode_command: Custom config mode command
            cmd_verify: Verify command echo

        Returns:
            Configuration output

        Raises:
            ConnectionError: If not connected
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        try:
            logger.debug(f"Sending config to {self.host}")

            # Convert single command to list
            if isinstance(config_commands, str):
                config_commands = [config_commands]

            output = self.session.send_config_set(
                config_commands,
                enter_config_mode=enter_config_mode,
                exit_config_mode=exit_config_mode,
                delay_factor=delay_factor,
                max_loops=max_loops,
                strip_prompt=strip_prompt,
                strip_command=strip_command,
                config_mode_command=config_mode_command,
                cmd_verify=cmd_verify,
                **kwargs
            )

            logger.info(f"Configuration applied successfully on {self.host}")
            return output

        except Exception as e:
            logger.error(f"Error applying configuration on {self.host}: {e}")
            raise ConnectionError(f"Configuration failed: {e}")

    def send_config_from_file(
        self,
        config_file: str,
        **kwargs
    ) -> str:
        """
        Send configuration from file.

        Args:
            config_file: Path to configuration file
            **kwargs: Additional arguments for send_config_set

        Returns:
            Configuration output
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        try:
            logger.info(f"Sending config from file {config_file} to {self.host}")
            output = self.session.send_config_from_file(config_file, **kwargs)
            logger.info(f"Configuration from file applied successfully on {self.host}")
            return output

        except Exception as e:
            logger.error(f"Error sending config from file on {self.host}: {e}")
            raise ConnectionError(f"Config file send failed: {e}")

    def is_alive(self) -> bool:
        """
        Check if SSH connection is alive.

        Returns:
            bool: True if connection is alive
        """
        try:
            return self.session is not None and self.session.is_alive()
        except Exception:
            return False

    def enable(self) -> str:
        """
        Enter enable mode (privileged mode).

        Returns:
            Output from enable command
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        try:
            return self.session.enable()
        except Exception as e:
            logger.error(f"Error entering enable mode on {self.host}: {e}")
            raise ConnectionError(f"Enable mode failed: {e}")

    def exit_enable_mode(self) -> str:
        """
        Exit enable mode.

        Returns:
            Output from exit command
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        try:
            return self.session.exit_enable_mode()
        except Exception as e:
            logger.error(f"Error exiting enable mode on {self.host}: {e}")
            raise ConnectionError(f"Exit enable mode failed: {e}")

    def find_prompt(self) -> str:
        """
        Find and return current prompt.

        Returns:
            Current device prompt
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        return self.session.find_prompt()

    def save_config(self, cmd: str = "", confirm: bool = False) -> str:
        """
        Save running configuration.

        Args:
            cmd: Save command (optional)
            confirm: Confirm save (optional)

        Returns:
            Output from save command
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to {self.host}")

        try:
            logger.info(f"Saving configuration on {self.host}")
            output = self.session.save_config(cmd=cmd, confirm=confirm)
            logger.info(f"Configuration saved on {self.host}")
            return output
        except Exception as e:
            logger.error(f"Error saving configuration on {self.host}: {e}")
            raise ConnectionError(f"Save config failed: {e}")

    def __repr__(self) -> str:
        """String representation of connection."""
        return f"SSHConnection(host={self.host}, port={self.port}, device_type={self.device_type})"
