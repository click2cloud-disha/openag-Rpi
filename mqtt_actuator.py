import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import json
import os
import time

# -------- CONFIG --------
BROKER = "192.168.1.155"
CONTROL_TOPIC = "openag/control"
REGISTER_TOPIC = "openag/register"

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# -------- LOAD CONFIG --------
with open("device_config.json") as f:
    config = json.load(f)

actuators = config["actuators"]

# -------- SETUP GPIO FOR RELAYS --------
for key, value in actuators.items():
    if value["type"] == "relay":
        GPIO.setup(value["pin"], GPIO.OUT)
        GPIO.output(value["pin"], GPIO.LOW)  # default OFF

# -------- REGISTER ALL ACTUATORS --------
def register_all(client):
    for key, value in actuators.items():
        register_msg = {
            "event": "register_actuator",
            "actuator": {
                "key": key,
                "type": value["type"]
            }
        }
        client.publish(REGISTER_TOPIC, json.dumps(register_msg))
        print(f"Registered: {key}")

# -------- CAMERA FUNCTION --------
def handle_camera(action):
    if action:
        print("📸 Capturing image...")
        os.makedirs("images", exist_ok=True)

        # 🔥 FIXED COMMAND (NO PREVIEW MODE)
        filename = f"images/image_{int(time.time())}.jpg"

        os.system(f"rpicam-still -n -o {filename}")
        print(f"Saved: {filename}")
    else:
        print("Camera OFF (no action)")

# -------- MQTT CALLBACKS --------
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT")
    client.subscribe(CONTROL_TOPIC)

    register_all(client)


def on_message(client, userdata, msg):
    print("Received:", msg.payload.decode())

    try:
        data = json.loads(msg.payload.decode())

        for key, value in data.items():
            if key in actuators:
                actuator = actuators[key]

                # -------- RELAY DEVICES --------
                if actuator["type"] == "relay":
                    pin = actuator["pin"]

                    if value:
                        GPIO.output(pin, GPIO.HIGH)
                        print(f"{key} ON")
                    else:
                        GPIO.output(pin, GPIO.LOW)
                        print(f"{key} OFF")

                # -------- CAMERA --------
                elif actuator["type"] == "camera":
                    handle_camera(value)

    except Exception as e:
        print("Error:", e)

# -------- MQTT CLIENT --------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_forever()
