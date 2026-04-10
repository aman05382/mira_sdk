"""Example usage of SONiC connections."""

from mira.connections.vendors.sonic.sonic_connection import SONiCConnection
from mira.connections.connection_manager import ConnectionManager
from mira.connections.connection_factory import ConnectionFactory


# Example 1: Basic SONiC connection
def example_basic_sonic():
    """Basic SONiC connection example."""
    
    # Using context manager
    with SONiCConnection(
        host="192.168.1.1",
        username="admin",
        password="YourPaSsWoRd"
    ) as sonic:
        # Execute show commands
        version = sonic.show_version()
        print(f"Version: {version}")
        
        interfaces = sonic.show_interfaces_status()
        print(f"Interfaces:\n{interfaces}")
        
        # Get configuration from CONFIG_DB
        port_config = sonic.get_port_config()
        print(f"Port Config: {port_config}")
        
        # Get runtime state from APPL_DB
        routes = sonic.get_route_table()
        print(f"Routes: {routes}")
        
        # Configure interface
        sonic.set_port_admin_status("Ethernet0", "up")
        sonic.set_port_mtu("Ethernet0", 9100)
        
        # Save configuration
        sonic.save_config()


# Example 2: Using Connection Factory
def example_factory():
    """Connection factory example."""
    
    conn = ConnectionFactory.create_connection(
        device_type="sonic",
        host="192.168.1.1",
        username="admin",
        password="YourPaSsWoRd"
    )
    
    conn.connect()
    
    try:
        output = conn.cli("show version")
        print(output)
    finally:
        conn.disconnect()


# Example 3: Managing multiple devices
def example_multi_device():
    """Multi-device management example."""
    
    manager = ConnectionManager(max_workers=5)
    
    # Add multiple SONiC devices
    devices = [
        {"name": "leaf1", "host": "192.168.1.1"},
        {"name": "leaf2", "host": "192.168.1.2"},
        {"name": "spine1", "host": "192.168.1.10"},
    ]
    
    for device in devices:
        manager.add_connection(
            name=device["name"],
            device_type="sonic",
            host=device["host"],
            username="admin",
            password="YourPaSsWoRd"
        )
    
    # Connect to all devices in parallel
    results = manager.connect_all(parallel=True)
    print(f"Connection results: {results}")
    
    # Execute command on all devices
    outputs = manager.execute_command("show version", parallel=True)
    for name, output in outputs.items():
        print(f"\n=== {name} ===")
        print(output)
    
    # Get status
    status = manager.get_status()
    print(f"Status: {status}")
    
    # Disconnect all
    manager.disconnect_all()


# Example 4: Redis operations
def example_redis_operations():
    """Redis database operations example."""
    
    with SONiCConnection(
        host="192.168.1.1",
        username="admin",
        password="YourPaSsWoRd",
        enable_redis=True
    ) as sonic:
        # CONFIG_DB operations
        # Get all ports
        ports = sonic.config_db_get("PORT")
        print(f"All ports: {ports}")
        
        # Get specific port
        eth0_config = sonic.config_db_get("PORT", "Ethernet0")
        print(f"Ethernet0 config: {eth0_config}")
        
        # Modify port configuration
        sonic.config_db_set("PORT", "Ethernet0", "mtu", "9100")
        sonic.config_db_set("PORT", "Ethernet0", "admin_status", "up")
        
        # VLAN operations
        sonic.create_vlan(100)
        sonic.add_vlan_member(100, "Ethernet0", "untagged")
        
        # BGP operations
        sonic.add_bgp_neighbor("10.0.0.1", 65001, "peer1")
        
        # Get operational state from STATE_DB
        port_state = sonic.get_port_state("Ethernet0")
        print(f"Port state: {port_state}")
        
        # Get counters from COUNTERS_DB
        counters = sonic.get_port_counters("Ethernet0")
        print(f"Port counters: {counters}")


if __name__ == "__main__":
    # Run examples
    example_basic_sonic()
    # example_factory()
    # example_multi_device()
    # example_redis_operations()