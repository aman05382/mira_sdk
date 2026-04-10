"""Topology Manager Usage Examples."""

from topology import (
    load_topology, DeviceRole, DeviceVendor, Credentials, TopologyManager, DevicePlatform
)

# export PYTHONPATH="/Users/amans/Desktop/mira_sdk/src/"

# ========== Example 1: Load from File ==========


def example_load_topology():
    """Load topology from YAML file."""

    topology = load_topology("tests/aman/topology.yaml")

    print(f"Topology: {topology.name}")
    print(f"Devices: {len(topology)}")
    print(f"Statistics: {topology.get_statistics()}")

    # Get all devices
    for device in topology:
        print(f"  - {device.name} ({device.host}) - {device.role.name}")


# ========== Example 2: Build Programmatically ==========
def example_build_topology():
    """Build topology programmatically."""

    # Create manager with default credentials
    topology = TopologyManager(
        name="test-fabric",
        default_credentials=Credentials(
            username="admin",
            password="YourPaSsWoRd"
        )
    )

    # Add spine switches
    spine1 = topology.add_device(
        name="spine1",
        host="192.168.1.10",
        role=DeviceRole.SPINE,
        vendor=DeviceVendor.SONIC,
        platform=DevicePlatform.SONIC
    )

    spine2 = topology.add_device(
        name="spine2",
        host="192.168.1.11",
        role=DeviceRole.SPINE,
        vendor=DeviceVendor.SONIC,
        platform=DevicePlatform.SONIC
    )

    # Add leaf switches
    leaf1 = topology.add_device(
        name="leaf1",
        host="192.168.1.20",
        role=DeviceRole.LEAF,
        vendor=DeviceVendor.SONIC,
        platform=DevicePlatform.SONIC
    )

    leaf2 = topology.add_device(
        name="leaf2",
        host="192.168.1.21",
        role=DeviceRole.LEAF,
        vendor=DeviceVendor.SONIC,
        platform=DevicePlatform.SONIC
    )

    # Add interfaces
    topology.add_interface("spine1", "Ethernet0", speed="100G")
    topology.add_interface("spine1", "Ethernet4", speed="100G")
    topology.add_interface("leaf1", "Ethernet48", speed="100G")
    topology.add_interface("leaf2", "Ethernet48", speed="100G")

    # Add links
    topology.add_link("spine1", "Ethernet0", "leaf1", "Ethernet48", speed="100G")
    topology.add_link("spine1", "Ethernet4", "leaf2", "Ethernet48", speed="100G")

    # Create groups
    topology.create_group("spines", ["spine1", "spine2"])
    topology.create_group("leaves", ["leaf1", "leaf2"])

    # Save topology
    topology.save_to_file("data/inventory/generated_topology.yaml")

    return topology


# ========== Example 3: Query Topology ==========
def example_query_topology():
    """Query topology for devices and links."""

    topology = load_topology("data/inventory/topology.yaml")

    # Get devices by role
    spines = topology.get_devices_by_role(DeviceRole.SPINE)
    leaves = topology.get_devices_by_role(DeviceRole.LEAF)
    print(f"Spines: {[s.name for s in spines]}")
    print(f"Leaves: {[l.name for l in leaves]}")

    # Get devices by vendor
    sonic_devices = topology.get_devices_by_vendor(DeviceVendor.SONIC)
    print(f"SONiC devices: {[d.name for d in sonic_devices]}")

    # Get devices by group
    rack1_devices = topology.get_devices_by_group("rack1")
    print(f"Rack1 devices: {[d.name for d in rack1_devices]}")

    # Get devices by label
    production_devices = topology.get_devices_by_label("production")
    print(f"Production devices: {[d.name for d in production_devices]}")

    # Get specific device
    leaf1 = topology.get_device("leaf1")
    print(f"\nLeaf1 details:")
    print(f"  Host: {leaf1.host}")
    print(f"  Vendor: {leaf1.vendor.name}")
    print(f"  Interfaces: {list(leaf1.interfaces.keys())}")

    # Get links for a device
    leaf1_links = topology.get_links_for_device("leaf1")
    print(f"\nLeaf1 links:")
    for link in leaf1_links:
        print(f"  {link.source} <-> {link.dest}")

    # Get neighbors
    leaf1_neighbors = topology.get_neighbors("leaf1")
    print(f"\nLeaf1 neighbors: {[n.name for n in leaf1_neighbors]}")

    # Get peer for specific interface
    peer = topology.get_peer("leaf1", "Ethernet48")
    if peer:
        peer_device, peer_interface = peer
        print(f"\nLeaf1:Ethernet48 peer: {peer_device.name}:{peer_interface.name}")

    # Custom filter
    connected_sonic = topology.filter_devices(
        lambda d: d.vendor == DeviceVendor.SONIC and d.role == DeviceRole.LEAF
    )
    print(f"\nSONiC Leaves: {[d.name for d in connected_sonic]}")


# ========== Example 4: Path Finding ==========
def example_path_finding():
    """Find paths between devices."""

    topology = load_topology("data/inventory/topology.yaml")

    # Find shortest path
    path = topology.find_path("leaf1", "leaf2")
    print(f"Shortest path leaf1 -> leaf2: {' -> '.join(path)}")

    # Find all paths
    all_paths = topology.find_all_paths("leaf1", "leaf2")
    print(f"\nAll paths leaf1 -> leaf2:")
    for i, path in enumerate(all_paths, 1):
        print(f"  Path {i}: {' -> '.join(path)}")


# ========== Example 5: Connection Management ==========
def example_connection_management():
    """Connect to devices and execute commands."""

    topology = load_topology("data/inventory/topology.yaml")

    # Connect to single device
    topology.connect_device("leaf1")
    leaf1 = topology.get_device("leaf1")
    print(f"Leaf1 connected: {leaf1.is_connected}")

    # Execute command
    output = topology.execute_on_device("leaf1", "show version")
    print(f"Leaf1 version:\n{output}")

    # Connect to all spines
    spine_results = topology.connect_all(
        filter_func=lambda d: d.role == DeviceRole.SPINE
    )
    print(f"Spine connection results: {spine_results}")

    # Execute on multiple devices
    outputs = topology.execute_on_devices(
        "show interfaces status",
        device_names=["leaf1", "leaf2"]
    )
    for device, output in outputs.items():
        print(f"\n=== {device} ===")
        print(output[:500])  # First 500 chars

    # Using context manager (auto disconnect)
    with load_topology("data/inventory/topology.yaml") as topo:
        topo.connect_all()
        results = topo.execute_on_devices("show version")
    # All devices disconnected automatically


# ========== Example 6: Traffic Generator Integration ==========
def example_traffic_generator():
    """Work with traffic generators."""

    topology = load_topology("data/inventory/topology.yaml")

    # Get traffic generator
    ixia = topology.get_traffic_generator("ixia1")
    print(f"Traffic Generator: {ixia.name}")
    print(f"Host: {ixia.host}")
    print(f"Ports: {ixia.ports}")

    # Get ports connected to a specific device
    leaf1_ports = ixia.get_ports_connected_to("leaf1")
    print(f"Ports connected to leaf1: {leaf1_ports}")

    # Get links from traffic generator
    tgen_links = topology.get_links_for_device("ixia1")
    for link in tgen_links:
        print(f"Traffic link: {link.source} -> {link.dest}")


# ========== Example 7: Validation ==========
def example_validation():
    """Validate topology."""

    topology = load_topology("data/inventory/topology.yaml")

    # Validate topology
    errors = topology.validate()
    if errors:
        print("Topology validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Topology is valid!")

    # Get statistics
    stats = topology.get_statistics()
    print(f"\nTopology Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    # Run examples
    example_load_topology()
    # example_build_topology()
    # example_query_topology()
    # example_path_finding()
    # example_connection_management()
    # example_traffic_generator()
    # example_validation()
