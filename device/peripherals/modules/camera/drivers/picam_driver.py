import threading
import os
import datetime
import subprocess

from typing import Optional, Dict, Any

from device.peripherals.modules.camera.drivers.base_driver import CameraDriver
from device.utilities.communication.i2c.mux_simulator import MuxSimulator


class PiCameraDriver(CameraDriver):
    def __init__(
        self,
        name: str,
        vendor_id: int,
        product_id: int,
        resolution: str,
        num_cameras: int = 1,
        simulate: bool = False,
        usb_mux_comms: Optional[Dict[str, Any]] = None,
        usb_mux_channel: Optional[int] = None,
        i2c_lock: Optional[threading.RLock] = None,
        mux_simulator: Optional[MuxSimulator] = None
    ) -> None:

        # ✅ Always use libcamera (rpicam) instead of picamera
        self.simulate = simulate

        super().__init__(
            name=name,
            vendor_id=vendor_id,
            product_id=product_id,
            resolution=resolution,
            num_cameras=num_cameras,
            simulate=self.simulate,
            usb_mux_comms=usb_mux_comms,
            usb_mux_channel=usb_mux_channel,
            i2c_lock=i2c_lock,
            mux_simulator=mux_simulator
        )

        self.logger.info("Using rpicam-still (libcamera) for image capture")

    # ✅ FIXED: Properly inside class
    def capture(self, retry: bool = True) -> None:
        super().capture(retry=retry)

        timestring = datetime.datetime.utcnow().strftime("%Y-%m-%d_T%H-%M-%SZ")
        filename = f"{timestring}_{self.name}.jpg"
        full_path = os.path.join(self.directory, filename)

        try:
            # ✅ Capture image using Raspberry Pi libcamera
            subprocess.run(
                ["rpicam-still", "-o", full_path, "-n"],
                check=True
            )

            self.logger.info(f"Image captured: {full_path}")

        except Exception as e:
            self.logger.error(f"Capture failed: {e}")
