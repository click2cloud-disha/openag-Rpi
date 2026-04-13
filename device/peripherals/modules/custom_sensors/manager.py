import time
import RPi.GPIO as GPIO
from grove.adc import ADC

class CustomSensorManager:

    def __init__(self, state):
        self.state = state

        self.adc = ADC()

        GPIO.setmode(GPIO.BCM)
        self.DHT_PIN = 5

    def read_dht11(self):
        # (your existing function here)
        return temp, hum

    def run(self):
        while True:
            try:
                light = self.adc.read(0)
                moisture = self.adc.read(1)

                temp, hum = self.read_dht11()

                if temp is None:
                    time.sleep(5)
                    continue

                # ?? THIS IS THE MOST IMPORTANT PART
                with self.state.lock:
                    if "reported_sensor_stats" not in self.state.environment:
                        self.state.environment["reported_sensor_stats"] = {}

                    self.state.environment["reported_sensor_stats"]["individual"] = {
                        "instantaneous": {
                            "air_temperature_celsius": temp,
                            "air_humidity_percent": hum,
                            "light_intensity": light,
                            "soil_moisture": moisture
                        }
                    }

                print("Updated OpenAg state:", temp, hum)

                time.sleep(5)

            except Exception as e:
                print("Error:", e)
                time.sleep(5)