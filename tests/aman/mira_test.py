"""Topology Manager Usage Examples."""

import time

from topology import TopologyManager
from core import MiraLogger, log_execution

# export PYTHONPATH="/Users/amans/Desktop/mira_sdk/src/"

# topo_mgr = TopologyManager("tests/aman/mira_topo.yaml")

log = MiraLogger("MiraTest")
log.add_console_handler(level="DEBUG")

log.info("Starting topology manager")
log.debug("This is a debug message")
log.warning("This is a warning")
log.error("This is an error")
log.critical("This is critical")


log1 = MiraLogger("MiraTest_1")
log1.add_console_handler(level="INFO")

log1.info("Starting topology manager")
log1.debug("This is a debug message")
log1.warning("This is a warning")
log1.error("This is an error")
log1.critical("This is critical")



log1.banner("This is a banner message")

@log_execution("Simulating work")
def simulate_work():
    log.debug("Simulating some work...")
    time.sleep(2)
    log.debug("Work simulation complete.")

simulate_work()