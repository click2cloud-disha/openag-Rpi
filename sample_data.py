import json
import time
import random
import socket
import paho.mqtt.client as mqtt

# ?? CONFIG (CHANGE THIS)
BROKER = "192.168.1.121"   # ?? Your VM IP
PORT = 1883
TOPIC = "openag/sensors"

# ?? Device identity (for demo clarity)
DEVICE_ID = socket.gethostname()

# ?? MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("? Connected to MQTT Broker")
    else:
        print("? Connection failed with code", rc)

def on_disconnect(client, userdata, rc):
    print("?? Disconnected from MQTT. Reconnecting...")
    time.sleep(5)
    try:
        client.reconnect()
    except:
        print("Reconnect failed")

# ?? MQTT Client Setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect

client.connect(BROKER, PORT, 60)

# ?? Loop
while True:
    try:
        data = {
            "event": "sensor",
            "device_id": DEVICE_ID,
            "timestamp": int(time.time()),

            # Sample sensor values
            "air_temperature_celsius": round(random.uniform(18, 35), 2),
            "air_humidity_percent": round(random.uniform(30, 90), 2),
            "light_intensity": random.randint(350, 1000),
            "soil_moisture": random.randint(350, 1000)
        }

        client.publish(TOPIC, json.dumps(data))

        print("?? Sent:", data)

        time.sleep(10)

    except Exception as e:
        print("? Error:", e)
        time.sleep(30)