import paho.mqtt.client as mqtt
import json
import time
import RPi.GPIO as GPIO
from grove.adc import ADC

# -------- MQTT CONFIG --------
BROKER = "192.168.1.155"
TOPIC = "openag/sensors"

client = mqtt.Client()
client.connect(BROKER, 1883, 60)

adc = ADC()

# -------- DHT SETUP (RAW GPIO VERSION) --------
GPIO.setmode(GPIO.BCM)
DHT_PIN = 5

def read_dht11(pin):
    data = []

    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.02)
    GPIO.output(pin, GPIO.HIGH)
    GPIO.setup(pin, GPIO.IN)

    for i in range(85):
        count = 0
        while GPIO.input(pin) == (i % 2):
            count += 1
            if count > 100:
                break
        data.append(count)

    bits = []
    for i in range(3, len(data), 2):
        bits.append(1 if data[i] > 10 else 0)

    bytes_data = []
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i+8]:
            byte = (byte << 1) | bit
        bytes_data.append(byte)

    if len(bytes_data) >= 5:
        humidity = bytes_data[0]
        temperature = bytes_data[2]
        return temperature, humidity
    else:
        return None, None

# -------- LOOP --------
while True:
    try:
        light = adc.read(0)
        moisture = adc.read(1)

        temp, hum = read_dht11(DHT_PIN)

        if temp is None or hum is None:
            print("DHT read failed")
            time.sleep(5)
            continue

        data = {
            "event": "sensor",
            "air_temperature_celsius": temp,
            "air_humidity_percent": hum,
            "light_intensity": light,
            "soil_moisture": moisture
        }

        client.publish(TOPIC, json.dumps(data))
        print("Sent:", data)

        time.sleep(5)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
