"""Topology management module."""

from .models import (
    Device, Interface, Link, PortChannel, TrafficGenerator, Credentials,
    DeviceType, DeviceRole, DeviceVendor, DevicePlatform,
    InterfaceType, InterfaceSpeed, LinkType, DeviceState, InterfaceState
)
from .manager import TopologyManager, load_topology
from core.exceptions import (
    TopologyError, DeviceNotFoundError, DeviceExistsError,
    LinkNotFoundError, LinkExistsError, InterfaceNotFoundError,
    PathNotFoundError, TopologyLoadError, TopologyValidationError
)

__all__ = [
    # Manager
    'TopologyManager',
    'load_topology',

    # Models
    'Device',
    'Interface',
    'Link',
    'PortChannel',
    'TrafficGenerator',
    'Credentials',

    # Enums
    'DeviceType',
    'DeviceRole',
    'DeviceVendor',
    'DevicePlatform',
    'InterfaceType',
    'InterfaceSpeed',
    'LinkType',
    'DeviceState',
    'InterfaceState',

    # Exceptions
    'TopologyError',
    'DeviceNotFoundError',
    'DeviceExistsError',
    'LinkNotFoundError',
    'LinkExistsError',
    'InterfaceNotFoundError',
    'PathNotFoundError',
    'TopologyLoadError',
    'TopologyValidationError',
]
