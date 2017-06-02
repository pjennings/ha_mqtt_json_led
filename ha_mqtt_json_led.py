import machine
import time
import os
import ubinascii
import ujson
import uasyncio as asyncio
import urandom

from copy import deepcopy
from umqtt.simple import MQTTClient
from AsyncMqtt import AsyncMqttClient
from Event import Event

from LED import LED
from Controller import Controller

CONFIG_FILE = "ha_mqtt_json_led.config"

def write_config(config):
    if config['PERSISTENT']:
        with open(CONFIG_FILE, "w") as f:
            f.write(ujson.dumps(config))

async def main_loop():
    file_config = None
    if CONFIG_FILE in os.listdir():
        try:
            file_config = ujson.loads(open(CONFIG_FILE).read())
        except ValueError:
            print("Bad config file -- deleting")
            os.remove(CONFIG_FILE)

    try:
        ID = ubinascii.hexlify(machine.unique_id()).decode('ascii')
    except AttributeError:
        ID = "ha_mqtt_json_led_"+"".join([str(urandom.getrandbits(x)) for x in [3]*8])

    config = {
        # MQTT config
        "CLIENT_ID": "mp_mqtt_json_"+ID,
        "SERVER": "iot.eclipse.org",
        "CONTROL_TOPIC": "/light/"+ID+"/control",
        "STATE_TOPIC": "/light/"+ID+"/state",
        "STATE_REQ_TOPIC": "/light/"+ID+"/get_state",
        "CONFIG_TOPIC": "/light/"+ID+"/config",
        "GLOBAL_CONFIG_TOPIC": "/light/config",
        "PERSISTENT": True,

        # HW config
        "RED_PIN": 14,
        "GREEN_PIN": 5,
        "BLUE_PIN": 12,
        "PWM_FREQ": 1000
    }

    if file_config is not None:
        config.update(file_config)

    write_config(config)

    async def get_state(c, in_event, out_event):
        while True:
            await in_event
            if in_event.value() is None:
                # value will be none if main loop was killed
                break
            else:
                out_event.set(c.get_state())
            in_event.clear()

    client = AsyncMqttClient(config['CLIENT_ID'], config['SERVER'])
    client.connect()
    control_event = client.subscribe(config['CONTROL_TOPIC'])
    config_event = client.subscribe(config['CONFIG_TOPIC'])
    client.subscribe(config['GLOBAL_CONFIG_TOPIC'], event=config_event)
    state_event = client.publish(config['STATE_TOPIC'])
    get_state_event = client.subscribe(config['STATE_REQ_TOPIC'])

    controller = Controller(rpin=config['RED_PIN'], gpin=config['GREEN_PIN'], bpin=config['BLUE_PIN'], freq=config['PWM_FREQ'])

    # Set up async handlers for control/get_state events
    async_loop = asyncio.get_event_loop()
    async_loop.create_task(controller.aloop(control_event, state_event))
    async_loop.create_task(get_state(controller, get_state_event, state_event))

    # In case of reconfig, write the new config and then return, which will allow run_main_loop to rerun this function
    await config_event
    config.update(ujson.loads(config_event.value()))
    write_config(config)

    client.disconnect()
    controller.kill()
    old_config = deepcopy(config)
    get_state_event.set(None)

    async_loop.stop()

def run_main_loop():
    while True:
        async_loop = asyncio.get_event_loop()
        async_loop.run_until_complete(main_loop())

