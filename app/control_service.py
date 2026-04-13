import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

import paho.mqtt.client as mqtt
import json
from app.models import RecipeModel

BROKER = "192.168.1.155"

client = mqtt.Client()

def get_active_recipe():
    try:
        recipe = RecipeModel.objects.latest("id")
        return json.loads(recipe.json)
    except:
        return None

def get_desired_values(recipe):
    env = list(recipe["environments"].values())[0]
    return env

def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())

    sensor_temp = data.get("air_temperature_celsius")

    recipe = get_active_recipe()
    if not recipe:
        print("No recipe found")
        return

    desired = get_desired_values(recipe)
    desired_temp = desired.get("air_temperature_celsius")

    if sensor_temp > desired_temp:
        command = {"fan": True}
    else:
        command = {"fan": False}

    print("Decision:", command)

    client.publish("openag/control", json.dumps(command))

client.connect(BROKER, 1883, 60)
client.subscribe("openag/sensors")
client.on_message = on_message

print("Control service running...")
client.loop_forever()