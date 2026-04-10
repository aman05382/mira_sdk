"""
Network Topology Manager

Central manager for network topology operations:
- Device management
- Link management
- Connection management
- Topology queries
- Path finding
"""

import threading
from typing import (
    Optional, Dict, Any, List, Set, Union,
    Callable, Iterator, Tuple
)
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import yaml
from datetime import datetime

from .models import (
    Device, Interface, Link, PortChannel, TrafficGenerator,
    Credentials, DeviceType, DeviceRole, DeviceVendor, DevicePlatform,
    InterfaceType, InterfaceSpeed, LinkType, DeviceState, InterfaceState
)
from core.exceptions import (
    TopologyError, DeviceNotFoundError, DeviceExistsError,
    LinkNotFoundError, LinkExistsError, InterfaceNotFoundError,
    PathNotFoundError, TopologyLoadError, TopologyValidationError
)
from core.logger import get_logger, Timer
from connections.connection_factory import ConnectionFactory
from connections.connection_manager import ConnectionManager

logger = get_logger(__name__)


class TopologyManager:
    """
    Central topology management class.

    Manages all network devices, links, traffic generators and provides
    methods for topology operations, queries, and path finding.

    Usage:
        topology = TopologyManager()
        topology.load_from_file("topology.yaml")

        # Get devices
        device = topology.get_device("leaf1")
        all_spines = topology.get_devices_by_role(DeviceRole.SPINE)

        # Get links
        links = topology.get_links_for_device("leaf1")

        # Connect to devices
        topology.connect_device("leaf1")
        topology.connect_all()
    """

    def __init__(
        self,
        name: str = "default",
        default_credentials: Optional[Credentials] = None,
        max_workers: int = 10
    ):
        """
        Initialize Topology Manager.

        Args:
            name: Topology name
            default_credentials: Default credentials for devices
            max_workers: Max parallel workers for connections
        """
        self.name = name
        self.default_credentials = default_credentials
        self.max_workers = max_workers

        # Storage
        self._devices: Dict[str, Device] = {}
        self._links: Dict[str, Link] = {}  # key: link.id
        self._traffic_generators: Dict[str, TrafficGenerator] = {}
        self._port_channels: Dict[str, PortChannel] = {}  # key: "device:portchannel"

        # Groups and labels
        self._groups: Dict[str, Set[str]] = {}  # group_name -> set of device names
        self._labels: Dict[str, Set[str]] = {}  # label -> set of device names

        # Connection manager
        self._connection_manager = ConnectionManager(max_workers=max_workers)

        # Thread safety
        self._lock = threading.RLock()

        # Metadata
        self._metadata: Dict[str, Any] = {}
        self._created_at = datetime.now()
        self._updated_at = datetime.now()

        logger.info(f"Initialized TopologyManager: {name}")

    # ==================== Device Management ====================

    def add_device(
        self,
        name: str,
        host: str,
        device_type: Union[DeviceType, str] = DeviceType.SWITCH,
        role: Union[DeviceRole, str] = DeviceRole.UNKNOWN,
        vendor: Union[DeviceVendor, str] = DeviceVendor.UNKNOWN,
        platform: Union[DevicePlatform, str] = DevicePlatform.UNKNOWN,
        credentials: Optional[Credentials] = None,
        **kwargs
    ) -> Device:
        """
        Add a device to the topology.

        Args:
            name: Unique device name
            host: Management IP/hostname
            device_type: Type of device
            role: Role in topology
            vendor: Device vendor
            platform: Device platform/OS
            credentials: Device credentials
            **kwargs: Additional device attributes

        Returns:
            Created Device object

        Raises:
            DeviceExistsError: If device already exists
        """
        with self._lock:
            if name in self._devices:
                raise DeviceExistsError(name)

            device = Device(
                name=name,
                host=host,
                device_type=device_type if isinstance(device_type, DeviceType) else DeviceType[device_type.upper()],
                role=role if isinstance(role, DeviceRole) else DeviceRole[role.upper()],
                vendor=vendor if isinstance(vendor, DeviceVendor) else DeviceVendor[vendor.upper()],
                platform=platform if isinstance(platform, DevicePlatform) else DevicePlatform[platform.upper()],
                credentials=credentials or self.default_credentials,
                **kwargs
            )

            self._devices[name] = device
            self._update_timestamp()

            logger.info(f"Added device: {name} ({host})")
            return device

    def remove_device(self, name: str) -> Device:
        """
        Remove a device from the topology.

        Also removes associated links and disconnects if connected.

        Args:
            name: Device name

        Returns:
            Removed Device object

        Raises:
            DeviceNotFoundError: If device not found
        """
        with self._lock:
            if name not in self._devices:
                raise DeviceNotFoundError(name)

            device = self._devices[name]

            # Disconnect if connected
            if device.is_connected:
                try:
                    device.connection.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting {name}: {e}")

            # Remove associated links
            links_to_remove = [
                link_id for link_id, link in self._links.items()
                if link.connects(name)
            ]
            for link_id in links_to_remove:
                del self._links[link_id]

            # Remove from groups and labels
            for group_devices in self._groups.values():
                group_devices.discard(name)
            for label_devices in self._labels.values():
                label_devices.discard(name)

            del self._devices[name]
            self._update_timestamp()

            logger.info(f"Removed device: {name}")
            return device

    def get_device(self, name: str) -> Device:
        """
        Get a device by name.

        Args:
            name: Device name

        Returns:
            Device object

        Raises:
            DeviceNotFoundError: If device not found
        """
        with self._lock:
            if name not in self._devices:
                raise DeviceNotFoundError(name)
            return self._devices[name]

    def get_device_or_none(self, name: str) -> Optional[Device]:
        """Get a device by name, return None if not found."""
        with self._lock:
            return self._devices.get(name)

    def has_device(self, name: str) -> bool:
        """Check if device exists in topology."""
        with self._lock:
            return name in self._devices

    def get_all_devices(self) -> List[Device]:
        """Get all devices in topology."""
        with self._lock:
            return list(self._devices.values())

    def get_device_names(self) -> List[str]:
        """Get all device names."""
        with self._lock:
            return list(self._devices.keys())

    def get_devices_by_role(self, role: Union[DeviceRole, str]) -> List[Device]:
        """Get all devices with specific role."""
        if isinstance(role, str):
            role = DeviceRole[role.upper()]
        with self._lock:
            return [d for d in self._devices.values() if d.role == role]

    def get_devices_by_type(self, device_type: Union[DeviceType, str]) -> List[Device]:
        """Get all devices of specific type."""
        if isinstance(device_type, str):
            device_type = DeviceType[device_type.upper()]
        with self._lock:
            return [d for d in self._devices.values() if d.device_type == device_type]

    def get_devices_by_vendor(self, vendor: Union[DeviceVendor, str]) -> List[Device]:
        """Get all devices from specific vendor."""
        if isinstance(vendor, str):
            vendor = DeviceVendor[vendor.upper()]
        with self._lock:
            return [d for d in self._devices.values() if d.vendor == vendor]

    def get_devices_by_platform(self, platform: Union[DevicePlatform, str]) -> List[Device]:
        """Get all devices with specific platform."""
        if isinstance(platform, str):
            platform = DevicePlatform[platform.upper()]
        with self._lock:
            return [d for d in self._devices.values() if d.platform == platform]

    def get_devices_by_label(self, label: str) -> List[Device]:
        """Get all devices with specific label."""
        with self._lock:
            device_names = self._labels.get(label, set())
            return [self._devices[name] for name in device_names if name in self._devices]

    def get_devices_by_group(self, group: str) -> List[Device]:
        """Get all devices in specific group."""
        with self._lock:
            device_names = self._groups.get(group, set())
            return [self._devices[name] for name in device_names if name in self._devices]

    def get_devices_by_state(self, state: Union[DeviceState, str]) -> List[Device]:
        """Get all devices in specific state."""
        if isinstance(state, str):
            state = DeviceState[state.upper()]
        with self._lock:
            return [d for d in self._devices.values() if d.state == state]

    def filter_devices(self, predicate: Callable[[Device], bool]) -> List[Device]:
        """
        Filter devices using custom predicate function.

        Args:
            predicate: Function that takes Device and returns bool

        Returns:
            List of devices matching predicate

        Example:
            >>> sonic_devices = topology.filter_devices(
            ...     lambda d: d.platform == DevicePlatform.SONIC and d.is_connected
            ... )
        """
        with self._lock:
            return [d for d in self._devices.values() if predicate(d)]

    def iter_devices(self) -> Iterator[Device]:
        """Iterate over all devices."""
        with self._lock:
            for device in self._devices.values():
                yield device

    # ==================== Interface Management ====================

    def add_interface(
        self,
        device_name: str,
        interface_name: str,
        interface_type: Union[InterfaceType, str] = InterfaceType.ETHERNET,
        **kwargs
    ) -> Interface:
        """
        Add an interface to a device.

        Args:
            device_name: Device name
            interface_name: Interface name
            interface_type: Type of interface
            **kwargs: Additional interface attributes

        Returns:
            Created Interface object
        """
        device = self.get_device(device_name)

        interface = Interface(
            name=interface_name,
            device_name=device_name,
            interface_type=interface_type if isinstance(interface_type, InterfaceType) else InterfaceType[interface_type.upper()],
            **kwargs
        )

        device.add_interface(interface)
        self._update_timestamp()

        logger.debug(f"Added interface: {device_name}:{interface_name}")
        return interface

    def remove_interface(self, device_name: str, interface_name: str) -> Interface:
        """Remove an interface from a device."""
        device = self.get_device(device_name)
        interface = device.remove_interface(interface_name)
        if not interface:
            raise InterfaceNotFoundError(device_name, interface_name)

        # Remove any links using this interface
        links_to_remove = [
            link_id for link_id, link in self._links.items()
            if (link.source_device == device_name and link.source_interface == interface_name) or
               (link.dest_device == device_name and link.dest_interface == interface_name)
        ]
        for link_id in links_to_remove:
            del self._links[link_id]

        self._update_timestamp()
        return interface

    def get_interface(self, device_name: str, interface_name: str) -> Interface:
        """
        Get an interface from a device.

        Args:
            device_name: Device name
            interface_name: Interface name

        Returns:
            Interface object
        """
        device = self.get_device(device_name)
        interface = device.get_interface(interface_name)
        if not interface:
            raise InterfaceNotFoundError(device_name, interface_name)
        return interface

    def get_all_interfaces(self, device_name: str) -> List[Interface]:
        """Get all interfaces for a device."""
        device = self.get_device(device_name)
        return list(device.interfaces.values())

    # ==================== Link Management ====================

    def add_link(
        self,
        source_device: str,
        source_interface: str,
        dest_device: str,
        dest_interface: str,
        link_type: Union[LinkType, str] = LinkType.PHYSICAL,
        speed: Union[InterfaceSpeed, str] = InterfaceSpeed.UNKNOWN,
        bidirectional: bool = True,
        **kwargs
    ) -> Link:
        """
        Add a link between two interfaces.

        Args:
            source_device: Source device name
            source_interface: Source interface name
            dest_device: Destination device name
            dest_interface: Destination interface name
            link_type: Type of link
            speed: Link speed
            bidirectional: If True, link works both ways (default)
            **kwargs: Additional link attributes

        Returns:
            Created Link object

        Raises:
            DeviceNotFoundError: If device not found
            LinkExistsError: If link already exists
        """
        with self._lock:
            # Validate devices exist
            if source_device not in self._devices:
                raise DeviceNotFoundError(source_device)
            if dest_device not in self._devices:
                raise DeviceNotFoundError(dest_device)

            # Check if link already exists
            for link in self._links.values():
                if link.source_device == source_device and link.source_interface == source_interface:
                    if link.dest_device == dest_device and link.dest_interface == dest_interface:
                        raise LinkExistsError(
                            f"{source_device}:{source_interface}",
                            f"{dest_device}:{dest_interface}"
                        )
                # Check reverse direction too
                if bidirectional:
                    if link.source_device == dest_device and link.source_interface == dest_interface:
                        if link.dest_device == source_device and link.dest_interface == source_interface:
                            raise LinkExistsError(
                                f"{source_device}:{source_interface}",
                                f"{dest_device}:{dest_interface}"
                            )

            link = Link(
                source_device=source_device,
                source_interface=source_interface,
                dest_device=dest_device,
                dest_interface=dest_interface,
                link_type=link_type if isinstance(link_type, LinkType) else LinkType[link_type.upper()],
                speed=speed if isinstance(speed, InterfaceSpeed) else InterfaceSpeed(speed),
                **kwargs
            )

            self._links[link.id] = link

            # Update interface connected_to
            src_device = self._devices[source_device]
            dst_device = self._devices[dest_device]

            if source_interface in src_device.interfaces:
                src_device.interfaces[source_interface].connected_to = f"{dest_device}:{dest_interface}"

            if dest_interface in dst_device.interfaces:
                dst_device.interfaces[dest_interface].connected_to = f"{source_device}:{source_interface}"

            self._update_timestamp()

            logger.debug(f"Added link: {source_device}:{source_interface} <-> {dest_device}:{dest_interface}")
            return link

    def remove_link(
        self,
        source_device: str,
        source_interface: str,
        dest_device: Optional[str] = None,
        dest_interface: Optional[str] = None
    ) -> Optional[Link]:
        """
        Remove a link from topology.

        If dest is not specified, removes any link from the source interface.
        """
        with self._lock:
            link_to_remove = None

            for link_id, link in self._links.items():
                if link.source_device == source_device and link.source_interface == source_interface:
                    if dest_device is None or (link.dest_device == dest_device and link.dest_interface == dest_interface):
                        link_to_remove = (link_id, link)
                        break
                # Check reverse
                if link.dest_device == source_device and link.dest_interface == source_interface:
                    if dest_device is None or (link.source_device == dest_device and link.source_interface == dest_interface):
                        link_to_remove = (link_id, link)
                        break

            if link_to_remove:
                link_id, link = link_to_remove
                del self._links[link_id]

                # Update interface connected_to
                if link.source_device in self._devices:
                    src_device = self._devices[link.source_device]
                    if link.source_interface in src_device.interfaces:
                        src_device.interfaces[link.source_interface].connected_to = None

                if link.dest_device in self._devices:
                    dst_device = self._devices[link.dest_device]
                    if link.dest_interface in dst_device.interfaces:
                        dst_device.interfaces[link.dest_interface].connected_to = None

                self._update_timestamp()
                logger.debug(f"Removed link: {link.source} <-> {link.dest}")
                return link

            return None

    def get_link(
        self,
        source_device: str,
        source_interface: str,
        dest_device: Optional[str] = None,
        dest_interface: Optional[str] = None
    ) -> Optional[Link]:
        """
        Get a specific link.

        Args:
            source_device: Source device name
            source_interface: Source interface name
            dest_device: Optional destination device
            dest_interface: Optional destination interface

        Returns:
            Link object or None
        """
        with self._lock:
            for link in self._links.values():
                # Check forward direction
                if link.source_device == source_device and link.source_interface == source_interface:
                    if dest_device is None or (link.dest_device == dest_device and link.dest_interface == dest_interface):
                        return link
                # Check reverse direction
                if link.dest_device == source_device and link.dest_interface == source_interface:
                    if dest_device is None or (link.source_device == dest_device and link.source_interface == dest_interface):
                        return link
            return None

    def get_all_links(self) -> List[Link]:
        """Get all links in topology."""
        with self._lock:
            return list(self._links.values())

    def get_links_for_device(self, device_name: str) -> List[Link]:
        """Get all links connected to a device."""
        with self._lock:
            return [link for link in self._links.values() if link.connects(device_name)]

    def get_links_between_devices(self, device1: str, device2: str) -> List[Link]:
        """Get all links between two devices."""
        with self._lock:
            return [
                link for link in self._links.values()
                if link.connects(device1) and link.connects(device2)
            ]

    def get_neighbors(self, device_name: str) -> List[Device]:
        """
        Get all neighbor devices (directly connected).

        Args:
            device_name: Device name

        Returns:
            List of neighbor Device objects
        """
        with self._lock:
            neighbor_names = set()
            for link in self._links.values():
                if link.source_device == device_name:
                    neighbor_names.add(link.dest_device)
                elif link.dest_device == device_name:
                    neighbor_names.add(link.source_device)

            return [self._devices[n] for n in neighbor_names if n in self._devices]

    def get_peer(
        self,
        device_name: str,
        interface_name: str
    ) -> Optional[Tuple[Device, Interface]]:
        """
        Get the peer device and interface for a given interface.

        Args:
            device_name: Device name
            interface_name: Interface name

        Returns:
            Tuple of (peer_device, peer_interface) or None
        """
        link = self.get_link(device_name, interface_name)
        if not link:
            return None

        peer_info = link.get_peer_interface(device_name, interface_name)
        if not peer_info:
            return None

        peer_device_name, peer_interface_name = peer_info
        peer_device = self.get_device_or_none(peer_device_name)
        if not peer_device:
            return None

        peer_interface = peer_device.get_interface(peer_interface_name)
        return (peer_device, peer_interface) if peer_interface else None

    # ==================== Traffic Generator Management ====================

    def add_traffic_generator(
        self,
        name: str,
        host: str,
        vendor: Union[DeviceVendor, str] = DeviceVendor.IXIA,
        **kwargs
    ) -> TrafficGenerator:
        """Add a traffic generator to the topology."""
        with self._lock:
            tgen = TrafficGenerator(
                name=name,
                host=host,
                vendor=vendor if isinstance(vendor, DeviceVendor) else DeviceVendor[vendor.upper()],
                **kwargs
            )
            self._traffic_generators[name] = tgen
            self._update_timestamp()

            logger.info(f"Added traffic generator: {name} ({host})")
            return tgen

    def remove_traffic_generator(self, name: str) -> Optional[TrafficGenerator]:
        """Remove a traffic generator from topology."""
        with self._lock:
            tgen = self._traffic_generators.pop(name, None)
            if tgen:
                self._update_timestamp()
                logger.info(f"Removed traffic generator: {name}")
            return tgen

    def get_traffic_generator(self, name: str) -> Optional[TrafficGenerator]:
        """Get a traffic generator by name."""
        return self._traffic_generators.get(name)

    def get_all_traffic_generators(self) -> List[TrafficGenerator]:
        """Get all traffic generators."""
        return list(self._traffic_generators.values())

    def add_traffic_generator_port(
        self,
        tgen_name: str,
        port_id: str,
        location: str,
        speed: str,
        connected_device: str,
        connected_interface: str
    ):
        """
        Add a traffic generator port and create link to DUT.

        Args:
            tgen_name: Traffic generator name
            port_id: Port identifier
            location: Port location (e.g., "1/1/1")
            speed: Port speed
            connected_device: DUT device name
            connected_interface: DUT interface name
        """
        tgen = self.get_traffic_generator(tgen_name)
        if not tgen:
            raise TopologyError(f"Traffic generator not found: {tgen_name}")

        connected_to = f"{connected_device}:{connected_interface}"
        tgen.add_port(port_id, location, speed, connected_to)

        # Create link
        self.add_link(
            source_device=tgen_name,
            source_interface=port_id,
            dest_device=connected_device,
            dest_interface=connected_interface,
            link_type=LinkType.PHYSICAL,
            speed=InterfaceSpeed(speed) if speed in [s.value for s in InterfaceSpeed] else InterfaceSpeed.UNKNOWN
        )

        logger.debug(f"Added traffic generator port: {tgen_name}:{port_id} -> {connected_to}")

    # ==================== Group & Label Management ====================

    def create_group(self, group_name: str, device_names: Optional[List[str]] = None):
        """Create a device group."""
        with self._lock:
            if group_name not in self._groups:
                self._groups[group_name] = set()

            if device_names:
                for name in device_names:
                    if name in self._devices:
                        self._groups[group_name].add(name)
                        self._devices[name].add_to_group(group_name)

    def add_device_to_group(self, device_name: str, group_name: str):
        """Add a device to a group."""
        with self._lock:
            if device_name not in self._devices:
                raise DeviceNotFoundError(device_name)

            if group_name not in self._groups:
                self._groups[group_name] = set()

            self._groups[group_name].add(device_name)
            self._devices[device_name].add_to_group(group_name)

    def remove_device_from_group(self, device_name: str, group_name: str):
        """Remove a device from a group."""
        with self._lock:
            if group_name in self._groups:
                self._groups[group_name].discard(device_name)
            if device_name in self._devices:
                self._devices[device_name].remove_from_group(group_name)

    def get_groups(self) -> List[str]:
        """Get all group names."""
        return list(self._groups.keys())

    def add_label_to_device(self, device_name: str, label: str):
        """Add a label to a device."""
        with self._lock:
            if device_name not in self._devices:
                raise DeviceNotFoundError(device_name)

            if label not in self._labels:
                self._labels[label] = set()

            self._labels[label].add(device_name)
            self._devices[device_name].add_label(label)

    def remove_label_from_device(self, device_name: str, label: str):
        """Remove a label from a device."""
        with self._lock:
            if label in self._labels:
                self._labels[label].discard(device_name)
            if device_name in self._devices:
                self._devices[device_name].remove_label(label)

    def get_labels(self) -> List[str]:
        """Get all labels."""
        return list(self._labels.keys())

    # ==================== Connection Management ====================

    def connect_device(
        self,
        device_name: str,
        protocol: str = "ssh",
        **kwargs
    ) -> bool:
        """
        Connect to a single device.

        Args:
            device_name: Device name
            protocol: Connection protocol (ssh, netconf, etc.)
            **kwargs: Additional connection parameters

        Returns:
            True if connection successful
        """
        device = self.get_device(device_name)

        if device.is_connected:
            logger.debug(f"Device {device_name} already connected")
            return True

        if not device.credentials:
            raise TopologyError(f"No credentials for device: {device_name}")

        try:
            # Determine connection type
            if device.platform == DevicePlatform.SONIC:
                device_type = "sonic"
            else:
                device_type = device.platform.name.lower()

            connection = ConnectionFactory.create_connection(
                device_type=device_type,
                host=device.host,
                username=device.credentials.username,
                password=device.credentials.password,
                port=device.mgmt_port,
                **device.connection_params,
                **kwargs
            )

            connection.connect()
            device._connection = connection
            device.state = DeviceState.CONNECTED

            logger.info(f"Connected to device: {device_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {device_name}: {e}")
            device.state = DeviceState.UNREACHABLE
            raise

    def disconnect_device(self, device_name: str) -> bool:
        """Disconnect from a device."""
        device = self.get_device(device_name)

        if device._connection:
            try:
                device._connection.disconnect()
                logger.info(f"Disconnected from device: {device_name}")
            except Exception as e:
                logger.warning(f"Error disconnecting from {device_name}: {e}")
            finally:
                device._connection = None
                device.state = DeviceState.REACHABLE

        return True

    def connect_all(
        self,
        parallel: bool = True,
        filter_func: Optional[Callable[[Device], bool]] = None
    ) -> Dict[str, bool]:
        """
        Connect to all devices (or filtered subset).

        Args:
            parallel: Connect in parallel
            filter_func: Optional filter function

        Returns:
            Dict of {device_name: success}
        """
        devices = self.get_all_devices()
        if filter_func:
            devices = [d for d in devices if filter_func(d)]

        results = {}

        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._connect_single, d.name): d.name
                    for d in devices
                }

                for future in as_completed(futures):
                    device_name = futures[future]
                    try:
                        results[device_name] = future.result()
                    except Exception as e:
                        logger.error(f"Connection failed for {device_name}: {e}")
                        results[device_name] = False
        else:
            for device in devices:
                try:
                    results[device.name] = self._connect_single(device.name)
                except Exception as e:
                    logger.error(f"Connection failed for {device.name}: {e}")
                    results[device.name] = False

        return results

    def disconnect_all(self) -> Dict[str, bool]:
        """Disconnect from all devices."""
        results = {}
        for device in self._devices.values():
            results[device.name] = self.disconnect_device(device.name)
        return results

    def _connect_single(self, device_name: str) -> bool:
        """Internal method to connect to single device."""
        try:
            return self.connect_device(device_name)
        except Exception:
            return False

    # ==================== Execute Commands ====================

    def execute_on_device(
        self,
        device_name: str,
        command: str,
        **kwargs
    ) -> str:
        """
        Execute command on a single device.

        Args:
            device_name: Device name
            command: Command to execute

        Returns:
            Command output
        """
        device = self.get_device(device_name)

        if not device.is_connected:
            self.connect_device(device_name)

        return device.connection.send_command(command, **kwargs)

    def execute_on_devices(
        self,
        command: str,
        device_names: Optional[List[str]] = None,
        parallel: bool = True,
        filter_func: Optional[Callable[[Device], bool]] = None
    ) -> Dict[str, str]:
        """
        Execute command on multiple devices.

        Args:
            command: Command to execute
            device_names: List of device names (None = all)
            parallel: Execute in parallel
            filter_func: Optional filter function

        Returns:
            Dict of {device_name: output}
        """
        if device_names:
            devices = [self.get_device(n) for n in device_names]
        else:
            devices = self.get_all_devices()

        if filter_func:
            devices = [d for d in devices if filter_func(d)]

        results = {}

        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.execute_on_device, d.name, command): d.name
                    for d in devices
                }

                for future in as_completed(futures):
                    device_name = futures[future]
                    try:
                        results[device_name] = future.result()
                    except Exception as e:
                        results[device_name] = f"ERROR: {str(e)}"
        else:
            for device in devices:
                try:
                    results[device.name] = self.execute_on_device(device.name, command)
                except Exception as e:
                    results[device.name] = f"ERROR: {str(e)}"

        return results

    # ==================== Path Finding ====================

    def find_path(
        self,
        source: str,
        destination: str,
        algorithm: str = "dijkstra"
    ) -> List[str]:
        """
        Find path between two devices.

        Args:
            source: Source device name
            destination: Destination device name
            algorithm: Path finding algorithm ('dijkstra', 'bfs')

        Returns:
            List of device names in path

        Raises:
            PathNotFoundError: If no path exists
        """
        if source not in self._devices:
            raise DeviceNotFoundError(source)
        if destination not in self._devices:
            raise DeviceNotFoundError(destination)

        if source == destination:
            return [source]

        # Build adjacency graph
        graph = self._build_adjacency_graph()

        if algorithm == "dijkstra":
            path = self._dijkstra(graph, source, destination)
        else:  # BFS
            path = self._bfs(graph, source, destination)

        if not path:
            raise PathNotFoundError(source, destination)

        return path

    def find_all_paths(
        self,
        source: str,
        destination: str,
        max_paths: int = 10
    ) -> List[List[str]]:
        """Find all paths between two devices."""
        if source not in self._devices:
            raise DeviceNotFoundError(source)
        if destination not in self._devices:
            raise DeviceNotFoundError(destination)

        graph = self._build_adjacency_graph()
        paths = []

        def dfs(current: str, target: str, visited: Set[str], path: List[str]):
            if len(paths) >= max_paths:
                return

            if current == target:
                paths.append(path.copy())
                return

            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, target, visited, path)
                    path.pop()
                    visited.remove(neighbor)

        dfs(source, destination, {source}, [source])
        return paths

    def _build_adjacency_graph(self) -> Dict[str, List[str]]:
        """Build adjacency graph from links."""
        graph: Dict[str, List[str]] = {name: [] for name in self._devices}

        for link in self._links.values():
            if link.source_device in graph:
                graph[link.source_device].append(link.dest_device)
            if link.dest_device in graph:
                graph[link.dest_device].append(link.source_device)

        return graph

    def _dijkstra(
        self,
        graph: Dict[str, List[str]],
        source: str,
        destination: str
    ) -> List[str]:
        """Dijkstra's shortest path algorithm."""
        import heapq

        distances = {node: float('infinity') for node in graph}
        distances[source] = 0
        previous = {node: None for node in graph}
        pq = [(0, source)]
        visited = set()

        while pq:
            current_distance, current = heapq.heappop(pq)

            if current in visited:
                continue

            visited.add(current)

            if current == destination:
                break

            for neighbor in graph.get(current, []):
                if neighbor in visited:
                    continue

                # Get link cost
                link = self.get_link(current, None, neighbor, None)
                cost = link.cost if link else 1

                distance = current_distance + cost

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    heapq.heappush(pq, (distance, neighbor))

        # Reconstruct path
        path = []
        current = destination
        while current:
            path.append(current)
            current = previous[current]

        return path[::-1] if path and path[-1] == source else []

    def _bfs(
        self,
        graph: Dict[str, List[str]],
        source: str,
        destination: str
    ) -> List[str]:
        """BFS shortest path."""
        from collections import deque

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            current, path = queue.popleft()

            if current == destination:
                return path

            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    # ==================== Topology I/O ====================

    def load_from_file(self, filepath: Union[str, Path]):
        """
        Load topology from YAML or JSON file.

        Args:
            filepath: Path to topology file
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise TopologyLoadError(str(filepath), "File not found")

        try:
            with open(filepath, 'r') as f:
                if filepath.suffix in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif filepath.suffix == '.json':
                    data = json.load(f)
                else:
                    raise TopologyLoadError(str(filepath), "Unsupported file format")

            self._load_from_dict(data)
            logger.info(f"Loaded topology from {filepath}")

        except Exception as e:
            raise TopologyLoadError(str(filepath), str(e))

    def save_to_file(
        self,
        filepath: Union[str, Path],
        include_credentials: bool = False
    ):
        """
        Save topology to YAML or JSON file.

        Args:
            filepath: Path to save topology
            include_credentials: Include credentials in output
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        data = self.to_dict(include_credentials=include_credentials)

        with open(filepath, 'w') as f:
            if filepath.suffix in ['.yaml', '.yml']:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved topology to {filepath}")

    def _load_from_dict(self, data: Dict[str, Any]):
        """Load topology from dictionary."""
        # Clear existing
        self._devices.clear()
        self._links.clear()
        self._traffic_generators.clear()
        self._groups.clear()
        self._labels.clear()

        # Load metadata
        self.name = data.get('name', self.name)
        self._metadata = data.get('metadata', {})

        # Load default credentials
        if 'default_credentials' in data:
            creds = data['default_credentials']
            self.default_credentials = Credentials(
                username=creds.get('username', 'admin'),
                password=creds.get('password', ''),
                enable_password=creds.get('enable_password')
            )

        # Load devices
        for device_data in data.get('devices', []):
            name = device_data.pop('name')
            host = device_data.pop('host')

            # Handle credentials
            creds = None
            if 'credentials' in device_data:
                creds_data = device_data.pop('credentials')
                creds = Credentials(**creds_data)

            # Handle interfaces
            interfaces_data = device_data.pop('interfaces', [])

            # Handle labels and groups
            labels = set(device_data.pop('labels', []))
            groups = set(device_data.pop('groups', []))

            device = self.add_device(
                name=name,
                host=host,
                credentials=creds,
                labels=labels,
                groups=groups,
                **device_data
            )

            # Add interfaces
            for intf_data in interfaces_data:
                intf_name = intf_data.pop('name')
                self.add_interface(name, intf_name, **intf_data)

            # Update groups index
            for group in groups:
                self.add_device_to_group(name, group)

            # Update labels index
            for label in labels:
                self.add_label_to_device(name, label)

        # Load traffic generators
        for tgen_data in data.get('traffic_generators', []):
            name = tgen_data.pop('name')
            host = tgen_data.pop('host')
            ports = tgen_data.pop('ports', {})

            tgen = self.add_traffic_generator(name, host, **tgen_data)

            for port_id, port_info in ports.items():
                tgen.add_port(
                    port_id,
                    port_info.get('location', ''),
                    port_info.get('speed', 'unknown'),
                    port_info.get('connected_to')
                )

        # Load links
        for link_data in data.get('links', []):
            self.add_link(**link_data)

    def to_dict(self, include_credentials: bool = False) -> Dict[str, Any]:
        """Convert topology to dictionary."""
        return {
            'name': self.name,
            'metadata': self._metadata,
            'devices': [d.to_dict(include_credentials) for d in self._devices.values()],
            'links': [l.to_dict() for l in self._links.values()],
            'traffic_generators': [t.to_dict() for t in self._traffic_generators.values()],
            'groups': {k: list(v) for k, v in self._groups.items()},
            'labels': {k: list(v) for k, v in self._labels.items()},
        }

    # ==================== Validation ====================

    def validate(self) -> List[str]:
        """
        Validate topology consistency.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check all link endpoints exist
        for link in self._links.values():
            if link.source_device not in self._devices:
                errors.append(f"Link references non-existent device: {link.source_device}")
            if link.dest_device not in self._devices:
                errors.append(f"Link references non-existent device: {link.dest_device}")

        # Check for duplicate links
        seen_links = set()
        for link in self._links.values():
            key = tuple(sorted([link.source, link.dest]))
            if key in seen_links:
                errors.append(f"Duplicate link: {link.source} <-> {link.dest}")
            seen_links.add(key)

        # Check all devices have credentials
        for device in self._devices.values():
            if not device.credentials and not self.default_credentials:
                errors.append(f"Device {device.name} has no credentials")

        return errors

    # ==================== Statistics ====================

    def get_statistics(self) -> Dict[str, Any]:
        """Get topology statistics."""
        return {
            'device_count': len(self._devices),
            'link_count': len(self._links),
            'traffic_generator_count': len(self._traffic_generators),
            'group_count': len(self._groups),
            'label_count': len(self._labels),
            'connected_devices': sum(1 for d in self._devices.values() if d.is_connected),
            'devices_by_role': {
                role.name: len(self.get_devices_by_role(role))
                for role in DeviceRole
                if self.get_devices_by_role(role)
            },
            'devices_by_vendor': {
                vendor.name: len(self.get_devices_by_vendor(vendor))
                for vendor in DeviceVendor
                if self.get_devices_by_vendor(vendor)
            },
        }

    # ==================== Utility Methods ====================

    def _update_timestamp(self):
        """Update the last modified timestamp."""
        self._updated_at = datetime.now()

    def __len__(self) -> int:
        """Return number of devices."""
        return len(self._devices)

    def __contains__(self, device_name: str) -> bool:
        """Check if device exists."""
        return device_name in self._devices

    def __getitem__(self, device_name: str) -> Device:
        """Get device by name using indexing."""
        return self.get_device(device_name)

    def __iter__(self) -> Iterator[Device]:
        """Iterate over devices."""
        return iter(self._devices.values())

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect all."""
        self.disconnect_all()

    def __repr__(self) -> str:
        return f"TopologyManager(name={self.name}, devices={len(self._devices)}, links={len(self._links)})"


# Convenience function
def load_topology(filepath: Union[str, Path], **kwargs) -> TopologyManager:
    """
    Load topology from file.

    Args:
        filepath: Path to topology file
        **kwargs: Additional TopologyManager parameters

    Returns:
        TopologyManager instance
    """
    manager = TopologyManager(**kwargs)
    manager.load_from_file(filepath)
    return manager
