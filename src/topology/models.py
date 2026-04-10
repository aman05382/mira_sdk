"""
Network Topology Data Models.

Defines all entities in a network topology:
- Device, Interface, Link, Topology
- Traffic Generators, Connections
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
import uuid


class DeviceType(Enum):
    """Device type enumeration."""
    SWITCH = auto()
    ROUTER = auto()
    FIREWALL = auto()
    LOAD_BALANCER = auto()
    SERVER = auto()
    TRAFFIC_GENERATOR = auto()
    DUT = auto()  # Device Under Test
    UNKNOWN = auto()


class DeviceRole(Enum):
    """Device role in topology."""
    SPINE = auto()
    LEAF = auto()
    BORDER_LEAF = auto()
    SUPERSPINE = auto()
    CORE = auto()
    AGGREGATION = auto()
    ACCESS = auto()
    EDGE = auto()
    DUT = auto()
    TRAFFIC_GEN = auto()
    CONTROLLER = auto()
    UNKNOWN = auto()


class DeviceVendor(Enum):
    """Device vendor enumeration."""
    SONIC = auto()
    CISCO = auto()
    JUNIPER = auto()
    ARISTA = auto()
    NOKIA = auto()
    HUAWEI = auto()
    IXIA = auto()
    SPIRENT = auto()
    KEYSIGHT = auto()
    GENERIC = auto()
    UNKNOWN = auto()


class DevicePlatform(Enum):
    """Device platform/OS enumeration."""
    SONIC = auto()
    IOS = auto()
    IOS_XE = auto()
    IOS_XR = auto()
    NXOS = auto()
    JUNOS = auto()
    EOS = auto()
    SROS = auto()
    VRP = auto()
    LINUX = auto()
    IXNETWORK = auto()
    STC = auto()
    UNKNOWN = auto()


class InterfaceType(Enum):
    """Interface type enumeration."""
    ETHERNET = auto()
    LOOPBACK = auto()
    VLAN = auto()
    PORT_CHANNEL = auto()
    MANAGEMENT = auto()
    SUBINTERFACE = auto()
    TUNNEL = auto()
    VIRTUAL = auto()
    UNKNOWN = auto()


class InterfaceSpeed(Enum):
    """Interface speed enumeration."""
    SPEED_1G = "1G"
    SPEED_10G = "10G"
    SPEED_25G = "25G"
    SPEED_40G = "40G"
    SPEED_50G = "50G"
    SPEED_100G = "100G"
    SPEED_200G = "200G"
    SPEED_400G = "400G"
    SPEED_800G = "800G"
    UNKNOWN = "unknown"


class LinkType(Enum):
    """Link type enumeration."""
    PHYSICAL = auto()
    LOGICAL = auto()
    PORT_CHANNEL = auto()
    VXLAN = auto()
    MPLS = auto()
    GRE = auto()
    UNKNOWN = auto()


class DeviceState(Enum):
    """Device operational state."""
    UNKNOWN = auto()
    DISCOVERED = auto()
    REACHABLE = auto()
    UNREACHABLE = auto()
    CONNECTED = auto()
    CONFIGURED = auto()
    FAILED = auto()
    MAINTENANCE = auto()


class InterfaceState(Enum):
    """Interface operational state."""
    UP = auto()
    DOWN = auto()
    ADMIN_DOWN = auto()
    ERROR = auto()
    UNKNOWN = auto()


@dataclass
class Credentials:
    """Device credentials."""
    username: str
    password: str
    enable_password: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'username': self.username,
            'password': '***HIDDEN***',
            'enable_password': '***HIDDEN***' if self.enable_password else None,
        }


@dataclass
class Interface:
    """Network interface model."""
    name: str
    device_name: str  # Parent device name
    interface_type: InterfaceType = InterfaceType.ETHERNET
    speed: InterfaceSpeed = InterfaceSpeed.UNKNOWN
    description: Optional[str] = None
    mac_address: Optional[str] = None
    ipv4_address: Optional[str] = None
    ipv4_mask: Optional[str] = None
    ipv6_address: Optional[str] = None
    ipv6_prefix: Optional[int] = None
    vlan: Optional[int] = None
    mtu: int = 1500
    admin_state: InterfaceState = InterfaceState.UNKNOWN
    oper_state: InterfaceState = InterfaceState.UNKNOWN
    connected_to: Optional[str] = None  # "device_name:interface_name"
    port_channel: Optional[str] = None  # Parent port-channel if member
    breakout: Optional[str] = None  # Breakout mode (e.g., "4x25G")
    fec: Optional[str] = None  # Forward Error Correction mode
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Get full interface name including device."""
        return f"{self.device_name}:{self.name}"

    @property
    def ipv4_cidr(self) -> Optional[str]:
        """Get IPv4 address in CIDR notation."""
        if self.ipv4_address and self.ipv4_mask:
            # Convert mask to prefix length
            from ipaddress import IPv4Network
            prefix_len = IPv4Network(f"0.0.0.0/{self.ipv4_mask}").prefixlen
            return f"{self.ipv4_address}/{prefix_len}"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'device': self.device_name,
            'type': self.interface_type.name,
            'speed': self.speed.value,
            'description': self.description,
            'mac_address': self.mac_address,
            'ipv4_address': self.ipv4_address,
            'ipv4_mask': self.ipv4_mask,
            'ipv6_address': self.ipv6_address,
            'mtu': self.mtu,
            'admin_state': self.admin_state.name,
            'oper_state': self.oper_state.name,
            'connected_to': self.connected_to,
            'metadata': self.metadata,
        }


@dataclass
class Device:
    """Network device model."""
    name: str
    host: str  # Management IP or hostname
    device_type: DeviceType = DeviceType.SWITCH
    role: DeviceRole = DeviceRole.UNKNOWN
    vendor: DeviceVendor = DeviceVendor.UNKNOWN
    platform: DevicePlatform = DevicePlatform.UNKNOWN
    model: Optional[str] = None
    serial_number: Optional[str] = None
    os_version: Optional[str] = None
    credentials: Optional[Credentials] = None
    mgmt_port: int = 22
    mgmt_interface: Optional[str] = None
    state: DeviceState = DeviceState.UNKNOWN
    interfaces: Dict[str, Interface] = field(default_factory=dict)
    labels: Set[str] = field(default_factory=set)
    groups: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    connection_params: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Connection instance (set by topology manager)
    _connection: Any = field(default=None, repr=False)

    def __post_init__(self):
        """Post initialization processing."""
        # Convert string enums if needed
        if isinstance(self.device_type, str):
            self.device_type = DeviceType[self.device_type.upper()]
        if isinstance(self.role, str):
            self.role = DeviceRole[self.role.upper()]
        if isinstance(self.vendor, str):
            self.vendor = DeviceVendor[self.vendor.upper()]
        if isinstance(self.platform, str):
            self.platform = DevicePlatform[self.platform.upper()]

    @property
    def connection(self):
        """Get active connection."""
        return self._connection

    @connection.setter
    def connection(self, conn):
        """Set active connection."""
        self._connection = conn

    @property
    def is_connected(self) -> bool:
        """Check if device has active connection."""
        return self._connection is not None and self._connection.is_alive()

    def get_interface(self, name: str) -> Optional[Interface]:
        """Get interface by name."""
        return self.interfaces.get(name)

    def add_interface(self, interface: Interface) -> Interface:
        """Add interface to device."""
        interface.device_name = self.name
        self.interfaces[interface.name] = interface
        return interface

    def remove_interface(self, name: str) -> Optional[Interface]:
        """Remove interface from device."""
        return self.interfaces.pop(name, None)

    def get_interfaces_by_type(self, interface_type: InterfaceType) -> List[Interface]:
        """Get all interfaces of a specific type."""
        return [i for i in self.interfaces.values() if i.interface_type == interface_type]

    def get_connected_interfaces(self) -> List[Interface]:
        """Get all interfaces that are connected to other devices."""
        return [i for i in self.interfaces.values() if i.connected_to]

    def add_label(self, label: str):
        """Add label to device."""
        self.labels.add(label)

    def remove_label(self, label: str):
        """Remove label from device."""
        self.labels.discard(label)

    def has_label(self, label: str) -> bool:
        """Check if device has label."""
        return label in self.labels

    def add_to_group(self, group: str):
        """Add device to group."""
        self.groups.add(group)

    def remove_from_group(self, group: str):
        """Remove device from group."""
        self.groups.discard(group)

    def in_group(self, group: str) -> bool:
        """Check if device is in group."""
        return group in self.groups

    def to_dict(self, include_credentials: bool = False) -> Dict[str, Any]:
        """Convert device to dictionary."""
        data = {
            'name': self.name,
            'host': self.host,
            'device_type': self.device_type.name,
            'role': self.role.name,
            'vendor': self.vendor.name,
            'platform': self.platform.name,
            'model': self.model,
            'serial_number': self.serial_number,
            'os_version': self.os_version,
            'mgmt_port': self.mgmt_port,
            'mgmt_interface': self.mgmt_interface,
            'state': self.state.name,
            'interfaces': {k: v.to_dict() for k, v in self.interfaces.items()},
            'labels': list(self.labels),
            'groups': list(self.groups),
            'metadata': self.metadata,
            'connection_params': self.connection_params,
            'is_connected': self.is_connected,
        }
        if include_credentials and self.credentials:
            data['credentials'] = self.credentials.to_dict()
        return data

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Device):
            return self.name == other.name
        return False


@dataclass
class Link:
    """Network link model representing connection between two interfaces."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_device: str = ""
    source_interface: str = ""
    dest_device: str = ""
    dest_interface: str = ""
    link_type: LinkType = LinkType.PHYSICAL
    speed: InterfaceSpeed = InterfaceSpeed.UNKNOWN
    description: Optional[str] = None
    state: InterfaceState = InterfaceState.UNKNOWN
    vlan: Optional[int] = None
    is_lag_member: bool = False
    lag_name: Optional[str] = None
    cost: int = 1  # For path calculation
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.link_type, str):
            self.link_type = LinkType[self.link_type.upper()]
        if isinstance(self.speed, str):
            self.speed = InterfaceSpeed(self.speed)

    @property
    def source(self) -> str:
        """Get source endpoint string."""
        return f"{self.source_device}:{self.source_interface}"

    @property
    def dest(self) -> str:
        """Get destination endpoint string."""
        return f"{self.dest_device}:{self.dest_interface}"

    @property
    def endpoints(self) -> tuple:
        """Get both endpoints as tuple."""
        return (self.source, self.dest)

    def connects(self, device: str) -> bool:
        """Check if link connects to a device."""
        return device in (self.source_device, self.dest_device)

    def get_other_end(self, device: str) -> Optional[str]:
        """Get the device at the other end of the link."""
        if device == self.source_device:
            return self.dest_device
        elif device == self.dest_device:
            return self.source_device
        return None

    def get_peer_interface(self, device: str, interface: str) -> Optional[tuple]:
        """Get peer device and interface for given endpoint."""
        if device == self.source_device and interface == self.source_interface:
            return (self.dest_device, self.dest_interface)
        elif device == self.dest_device and interface == self.dest_interface:
            return (self.source_device, self.source_interface)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'source_device': self.source_device,
            'source_interface': self.source_interface,
            'dest_device': self.dest_device,
            'dest_interface': self.dest_interface,
            'link_type': self.link_type.name,
            'speed': self.speed.value,
            'description': self.description,
            'state': self.state.name,
            'cost': self.cost,
            'metadata': self.metadata,
        }

    def __hash__(self):
        # Links are bidirectional, so hash should be same regardless of direction
        endpoints = tuple(sorted([self.source, self.dest]))
        return hash(endpoints)

    def __eq__(self, other):
        if isinstance(other, Link):
            return set(self.endpoints) == set(other.endpoints)
        return False


@dataclass
class PortChannel:
    """Port channel / LAG model."""
    name: str
    device_name: str
    members: List[str] = field(default_factory=list)  # Interface names
    mode: str = "active"  # active, passive, on
    min_links: int = 1
    description: Optional[str] = None
    state: InterfaceState = InterfaceState.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_member(self, interface: str):
        if interface not in self.members:
            self.members.append(interface)

    def remove_member(self, interface: str):
        if interface in self.members:
            self.members.remove(interface)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'device': self.device_name,
            'members': self.members,
            'mode': self.mode,
            'min_links': self.min_links,
            'description': self.description,
            'state': self.state.name,
        }


@dataclass
class TrafficGenerator:
    """Traffic generator device model."""
    name: str
    host: str  # Chassis IP
    vendor: DeviceVendor = DeviceVendor.UNKNOWN
    model: Optional[str] = None
    ports: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    credentials: Optional[Credentials] = None
    api_port: int = 443
    metadata: Dict[str, Any] = field(default_factory=dict)
    _connection: Any = field(default=None, repr=False)

    def add_port(self, port_id: str, location: str, speed: str,
                 connected_to: Optional[str] = None):
        """Add traffic generator port."""
        self.ports[port_id] = {
            'location': location,
            'speed': speed,
            'connected_to': connected_to,
        }

    def get_ports_connected_to(self, device: str) -> List[str]:
        """Get all ports connected to a specific device."""
        return [
            port_id for port_id, port_info in self.ports.items()
            if port_info.get('connected_to', '').startswith(device + ':')
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'host': self.host,
            'vendor': self.vendor.name,
            'model': self.model,
            'ports': self.ports,
            'api_port': self.api_port,
            'metadata': self.metadata,
        }
