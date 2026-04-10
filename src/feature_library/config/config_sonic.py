# Copyright 2026 Amans
"""
This library contains the configuration helper methods for the network device running Sonic.
"""
from .config_base import ConfigBase


class SonicConfig(ConfigBase):
    """
    This class contains the configuration helper methods for the network device running Sonic.
    """

    @staticmethod
    def get_interface_config(interface_name: str) -> dict:
        """
        This method returns the configuration of the specified interface.

        Args:
            interface_name (str): The name of the interface.

        Returns:
            dict: The configuration of the specified interface.
        """
        # Placeholder for actual implementation to retrieve interface configuration
        return {
            "interface_name": interface_name,
            "ip_address": "192.168.1.1",  # Placeholder for actual IP address
        }

    def config_reload(self) -> None:
        """
        This method reloads the configuration of the network device.

        Returns:
            None
        """
        # Placeholder for actual implementation to reload configuration
        print("Configuration reloaded successfully.")

    def config_save(self) -> None:
        """
        This method saves the current configuration of the network device.

        Returns:
            None
        """
        # Placeholder for actual implementation to save configuration
        print("Configuration saved successfully.")
