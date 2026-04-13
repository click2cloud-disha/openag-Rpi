# Import standard python modules
import abc
import json
import time
import base64
import json
import time
import paho.mqtt.client as mqtt
import os


# Import python typesself.logger.info("🚀 CameraManager initialized")
from typing import Optional, Tuple, Dict, Any

# Import device utilities
from device.utilities import logger, accessors

# Import manager elements
from device.peripherals.classes.peripheral import manager, modes
from device.peripherals.modules.camera import exceptions, events
from device.peripherals.modules.camera.drivers.base_driver import CameraDriver
from device.recipe import modes as recipe_modes


class CameraManager(manager.PeripheralManager):  # type: ignore
    """Manages a camera peripheral."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiates manager"""
        super().__init__(*args, **kwargs)

        self.usb_mux_comms = self.communication.get("usb_mux_comms", None)
        self.usb_mux_channel = self.communication.get("usb_mux_channel", None)

        self.min_sampling_interval = 2
        self.default_sampling_interval = 5

        self.lighting_control = self.parameters.get("lighting_control", {})
        self.lighting_control_enabled = self.lighting_control.get("enabled", False)

        self.previous_recipe_mode = recipe_modes.NORECIPE

        self.logger.debug("Instantiating")
        self.logger.info("🚀 CameraManager initialized")
        

    @property
    def recipe_mode(self) -> str:
        return self.state.recipe.get("mode", recipe_modes.NORECIPE)

    def initialize_peripheral(self) -> None:
        self.logger.debug("Initializing")
        self.clear_reported_values()
        self.health = 100.0
        # 🔥 MQTT setup (same as send_mqtt.py)
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect("192.168.1.155", 1883, 60)

        self.mqtt_topic = "openag/sensors"
        print("✅ Camera MQTT initialized")

        try:
            num_cameras = self.parameters.get("num_cameras", 1)
            self.min_sampling_interval = 120 * num_cameras

            if self.simulate:
                self.logger.debug("Simulating initialization")
                self._update_complete = True
                self.sampling_interval = 5  # capture every 5 seconds
                self.mode = modes.NORMAL   # ✅ ADD THIS
                self.logger.info("✅ CameraManager initialized and moved to NORMAL")
                return

            # ✅ FIXED DRIVER LOADING (MAIN FIX)
            driver_module_name = self.parameters.get("driver_module")
            driver_class = self.parameters.get("driver_class")

            # fallback from setup JSON
            if not driver_module_name:
                driver_module_name = self.setup_dict.get("parameters", {}).get("driver_module")

            if not driver_class:
                driver_class = self.setup_dict.get("parameters", {}).get("driver_class")

            # final fallback (prevents crash)
            driver_module_name = driver_module_name or "picam_driver"
            driver_class = driver_class or "PiCameraDriver"

            self.logger.debug(f"Driver module: {driver_module_name}")
            self.logger.debug(f"Driver class: {driver_class}")

            driver_module = f"device.peripherals.modules.camera.drivers.{driver_module_name}"

            self.driver = self.get_driver(driver_module, driver_class)(
                name=self.name,
                vendor_id=int(self.properties.get("vendor_id"), 16),
                product_id=int(self.properties.get("product_id"), 16),
                resolution=self.properties.get("resolution"),
                num_cameras=num_cameras,
                usb_mux_comms=self.usb_mux_comms,
                usb_mux_channel=self.usb_mux_channel,
                i2c_lock=self.i2c_lock,
                simulate=self.simulate,
                mux_simulator=self.mux_simulator,

            )

        except exceptions.DriverError:
            self.logger.exception("Unable to initialize")
            self.health = 0.0
            self.mode = modes.ERROR

        except ModuleNotFoundError:
            self.logger.exception("Camera module import failed")
            self.health = 0.0
            self.mode = modes.ERROR

        self.mode = modes.NORMAL
        self.logger.info("✅ CameraManager initialized and moved to NORMAL")

    def update_peripheral(self) -> None:
        print("📸 CAPTURE FUNCTION CALLED")
        """Updates peripheral, captures an image."""
        # Capture image
        self.driver.capture()
        
        import time
        time.sleep(2)
        # Get latest image
        try:
            image_dir = "data/images"

            all_files = os.listdir(image_dir)

            # ✅ filter ONLY real image files
            image_files = [
                f for f in all_files
                if os.path.isfile(os.path.join(image_dir, f)) and f.lower().endswith(".jpg")
            ]

            # ✅ sort latest first
            image_files.sort(reverse=True)

            if not image_files:
                print("No images found")
                return

            image_path = os.path.join(image_dir, image_files[0])
            # 🔥 Encode image
            with open(image_path, "rb") as img:
                encoded = base64.b64encode(img.read()).decode("utf-8")

            # 🔥 SAME STRUCTURE AS send_mqtt.py
            payload = {
                "event": "camera",
                "device": self.name,
                "timestamp": time.time(),
                "image": encoded
            }
            # 🔥 Publish
            self.mqtt_client.publish(self.mqtt_topic, json.dumps(payload))
            print("📤 Image sent via MQTT")
        except Exception as e:
            print("❌ Camera MQTT error:", e)
        try:
            self.set_lighting_conditions()

            if self.simulate:
                self.logger.debug("Simulating capture")
            else:
                self.driver.capture()

                try:
                    files = sorted(os.listdir(self.driver.directory))
                    if files:
                        latest_image = files[-1]
                        image_path = os.path.join(self.driver.directory, latest_image)

                        self.logger.info(f"Uploading image: {image_path}")
                        if (
                            self.coordinator.iot
                            and hasattr(self.coordinator.iot, "pubsub")
                            and getattr(self.coordinator.iot.pubsub, "client", None)
                        ):
                            self.coordinator.iot.pubsub.upload_image(image_path)
                        else:
                            self.logger.warning("⏳ MQTT not ready yet, skipping upload")
                            

                except Exception as e:
                    self.logger.error(f"Image upload failed: {e}")

            self.reset_lighting_conditions()
            self.health = 100.0

        except exceptions.DriverError as e:
            self.logger.debug(f"Unable to update: {e}")
            self.mode = modes.ERROR
            self.health = 0

    def run_normal_mode(self) -> None:
        self.logger.info("Entered NORMAL")

        self._update_complete = True
        self.last_update = time.time()

        while True:
            self.last_update_interval = time.time() - self.last_update

            if self.sampling_interval < self.last_update_interval or self.new_recipe():
                self.last_update = time.time()
                self.update_peripheral()

            if self.new_transition(modes.NORMAL):
                break

            self.check_events()

            if self.new_transition(modes.NORMAL):
                break

            time.sleep(2)

    def new_recipe(self) -> bool:
        if self.recipe_mode != self.previous_recipe_mode:
            self.previous_recipe_mode = self.recipe_mode
            if self.recipe_mode == recipe_modes.NORMAL:
                return True
        return False

    def set_lighting_conditions(self) -> None:
        if not self.lighting_control_enabled:
            return

        recipient_type = self.lighting_control.get("recipient_type")
        recipient_name = self.lighting_control.get("recipient_name")

        manager = None
        if recipient_type == "Peripheral":
            manager = self.coordinator.peripherals.get(recipient_name)
        elif recipient_type == "Controller":
            manager = self.coordinator.controllers.get(recipient_name)

        if manager is None:
            return

    def reset_lighting_conditions(self) -> None:
        if not self.lighting_control_enabled:
            return

        recipient_type = self.lighting_control.get("recipient_type")
        recipient_name = self.lighting_control.get("recipient_name")

        self.coordinator.send_event(
            recipient_type, recipient_name, {"type": "Reset"}
        )

    def create_peripheral_specific_event(
        self, request: Dict[str, Any]
    ) -> Tuple[str, int]:
        if request["type"] == events.CAPTURE:
            return self.capture()
        return "Unknown event request type", 400

    def check_peripheral_specific_events(self, request: Dict[str, Any]) -> None:
        if request["type"] == events.CAPTURE:
            self._capture()

    def capture(self) -> Tuple[str, int]:
        request = {"type": events.CAPTURE}
        self.event_queue.put(request)
        return "Capturing image", 200

    def _capture(self) -> None:
        try:
            self.set_lighting_conditions()

            if not self.simulate:
                self.driver.capture()

            self.reset_lighting_conditions()

        except Exception:
            self.mode = modes.ERROR
            self.logger.exception("Capture failed")

    @staticmethod
    def get_driver(module_name: str, class_name: str) -> abc.ABCMeta:
        module_instance = __import__(module_name, fromlist=[class_name])
        class_instance = getattr(module_instance, class_name)
        return class_instance
