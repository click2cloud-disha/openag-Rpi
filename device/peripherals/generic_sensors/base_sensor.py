class BaseSensor:
    def __init__(self, name, pin=None, bus=None, address=None):
        self.name = name
        self.pin = pin
        self.bus = bus
        self.address = address

    def read(self):
        """
        This method should be implemented by child sensors
        """
        raise NotImplementedError("Sensor must implement read()")

    def format_data(self, data):
        """
        Standard format for telemetry
        """
        return {
            "sensor": self.name,
            "data": data
        }
