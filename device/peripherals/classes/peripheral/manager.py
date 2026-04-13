# Import python modules
import os, time, threading, json

# Import python types
from typing import Dict, Optional, Any, Tuple

# Import device utilities
from device.utilities import logger
from device.utilities.statemachine.manager import StateMachineManager
from device.utilities.communication.i2c.mux_simulator import MuxSimulator
from device.utilities.state.main import State

# Import manager elements
from device.peripherals.classes.peripheral import modes, events


class PeripheralManager(StateMachineManager):

    default_sampling_interval = 2
    min_sampling_interval = 1

    def __init__(
        self,
        name: str,
        state: State,
        config: Dict,
        i2c_lock: threading.RLock,
        simulate: bool = False,
        mux_simulator: MuxSimulator = None,
        coordinator=None
    ) -> None:

        super().__init__()

        self.name = name
        self.state = state
        self.config = config
        self.i2c_lock = i2c_lock
        self.simulate = simulate
        self.mux_simulator = mux_simulator
        self.coordinator = coordinator

        self.logger = logger.Logger(f"Manager({self.name})", "peripherals")

        # DEBUG
        self.logger.debug(f"CONFIG: {self.config}")

        # SAFE PARAM LOAD
        self.parameters = self.config.get("parameters", {}) or {}
        self.variables = self.parameters.get("variables", {}) or {}
        self.communication = self.parameters.get("communication", {}) or {}

        self.logger.debug(f"PARAMETERS: {self.parameters}")

        # I2C SAFE INIT
        self.bus = self.communication.get("bus")
        if self.bus == "default":
            self.bus = os.getenv("DEFAULT_I2C_BUS")
        if self.bus == "none":
            self.bus = None
        if self.bus is not None:
            try:
                self.bus = int(self.bus)
            except:
                self.bus = None

        self.mux = self.communication.get("mux")
        if self.mux == "default":
            self.mux = os.getenv("DEFAULT_MUX_ADDRESS")
        if self.mux == "none":
            self.mux = None
        if self.mux is not None:
            try:
                self.mux = int(self.mux, 16)
            except:
                self.mux = None

        self.channel = self.communication.get("channel")

        self.address = self.communication.get("address")
        if self.address is not None:
            try:
                self.address = int(self.address, 16)
            except:
                self.address = None

        # SETUP LOAD (FIXED)
        self.setup_dict = self.load_setup_dict_from_file()
        self.setup_uuid = self.setup_dict.get("uuid", None)
        self.properties = self.setup_dict.get("properties", {}) or {}

        # STATE MACHINE
        self.mode = modes.INIT

    # ---------------- SAMPLING INTERVAL ---------------- #

    @property
    def sampling_interval(self) -> float:
        """Gets sampling interval from shared state object."""

        peripheral_state = self.state.peripherals.get(self.name, {})
        stored = peripheral_state.get("stored", {})
        stored_sampling_interval = stored.get("sampling_interval", None)

        if stored_sampling_interval is not None:
            return float(stored_sampling_interval)

        return self.default_sampling_interval

    @sampling_interval.setter
    def sampling_interval(self, value: float) -> None:
        """Sets sampling interval in shared state."""
        with self.state.lock:
            if self.name not in self.state.peripherals:
                self.state.peripherals[self.name] = {}

            if "stored" not in self.state.peripherals[self.name]:
                self.state.peripherals[self.name]["stored"] = {}

            self.state.peripherals[self.name]["stored"]["sampling_interval"] = value

    # ---------------- SAFE SETUP LOADER ---------------- #

    def load_setup_dict_from_file(self) -> Dict:
        self.logger.debug("Loading setup file")

        setup = self.parameters.get("setup", {}) or {}
        file_name = setup.get("file_name")

        if not file_name:
            self.logger.error("Missing setup.file_name in config")
            return {}

        file_path = f"device/peripherals/modules/{file_name}.json"

        if not os.path.exists(file_path):
            self.logger.error(f"Setup file not found: {file_path}")
            return {}

        try:
            with open(file_path) as f:
                data = json.load(f)
                self.logger.debug(f"Setup loaded: {data}")
                return data
        except Exception as e:
            self.logger.error(f"Failed to load setup file: {e}")
            return {}

    # ---------------- STATE MACHINE ---------------- #

    def run(self) -> None:
        while True:

            if self.is_shutdown:
                break

            if self.mode == modes.INIT:
                self.run_init_mode()

            elif self.mode == modes.SETUP:
                self.run_setup_mode()

            elif self.mode == modes.NORMAL:
                self.run_normal_mode()

            elif self.mode == modes.RESET:
                self.run_reset_mode()

            elif self.mode == modes.ERROR:
                self.run_error_mode()

            elif self.mode == modes.SHUTDOWN:
                self.run_shutdown_mode()

            else:
                self.logger.critical("Invalid mode")
                self.is_shutdown = True
                break

    def run_init_mode(self):
        self.logger.info("INIT MODE")

        try:
            self.initialize_peripheral()
            self.mode = modes.SETUP
        except Exception as e:
            self.logger.error(f"Init error: {e}")
            self.mode = modes.ERROR

    def run_setup_mode(self):
        self.logger.info("SETUP MODE")

        try:
            self.setup_peripheral()
            self.mode = modes.NORMAL
        except Exception as e:
            self.logger.error(f"Setup error: {e}")
            self.mode = modes.ERROR

    # ✅ FIXED FUNCTION (CRITICAL)
    def run_normal_mode(self):
        self.logger.info("NORMAL MODE")

        self.last_update = time.time()

        while True:

            if self.is_shutdown:
                break

            # ✅ CRITICAL LINE (missing earlier)
            self.last_update_interval = time.time() - self.last_update

            if self.sampling_interval < self.last_update_interval:
                self.last_update = time.time()

                try:
                    self.update_peripheral()
                except Exception as e:
                    self.logger.error(f"Update error: {e}")
                    self.mode = modes.ERROR
                    break

            time.sleep(0.1)

    def run_reset_mode(self):
        self.logger.info("RESET MODE")

        try:
            self.reset_peripheral()
            self.mode = modes.INIT
        except Exception as e:
            self.logger.error(f"Reset error: {e}")
            self.mode = modes.ERROR

    def run_error_mode(self):
        self.logger.error("ERROR MODE")

        try:
            self.clear_reported_values()
        except Exception as e:
            self.logger.error(f"Error clearing values: {e}")

        time.sleep(2)
        self.mode = modes.RESET

    def run_shutdown_mode(self):
        self.logger.info("SHUTDOWN MODE")
        self.is_shutdown = True

    # ---------------- CORE FUNCTIONS ---------------- #

    def initialize_peripheral(self):
        self.logger.debug("Initialize peripheral")

    def setup_peripheral(self):
        self.logger.debug("Setup peripheral")

    def update_peripheral(self):
        self.logger.debug("Update peripheral")

    def reset_peripheral(self):
        self.logger.info("Reset peripheral")
        self.clear_reported_values()

    def shutdown_peripheral(self):
        self.logger.info("Shutdown peripheral")
        self.clear_reported_values()

    def clear_reported_values(self) -> None:
        self.logger.debug("Clearing reported values")

        try:
            with self.state.lock:
                if self.name in self.state.peripherals:
                    if "reported" in self.state.peripherals[self.name]:
                        self.state.peripherals[self.name]["reported"] = {}
        except Exception as e:
            self.logger.error(f"Error clearing reported values: {e}")