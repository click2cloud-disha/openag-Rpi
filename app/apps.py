# Import python modules
import os

# Import django modules
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "app"

    def ready(self) -> None:

        import os

        # Prevent multiple starts
        if hasattr(self, "already_started"):
            return
        self.already_started = True

        # Skip device if disabled
        if os.environ.get("NO_DEVICE") == "true":
            print("\n~~~Running app without device~~~\n")
            return

        # ✅ CRITICAL FIX: prevent double execution from Django reloader
        if os.environ.get("RUN_MAIN") != "true":
            return

        from device.coordinator.manager import CoordinatorManager
        import threading

        print("🔥 STARTING COORDINATOR (SAFE SINGLE RUN)")

        self.coordinator = CoordinatorManager()

        # Run coordinator in background thread
        thread = threading.Thread(target=self.coordinator.run, daemon=True)
        thread.start()
