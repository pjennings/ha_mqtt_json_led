import machine
import time
import os
import ubinascii
import ujson
import uasyncio as asyncio

from copy import deepcopy
from umqtt.robust import MQTTClient
from AsyncMqtt import AsyncMqttClient
from Event import Event

from LED import LED
from Controller import Controller

CONFIG_FILE = "ha_mqtt_json_led.config"

async def main_loop():
    try:
        ID = ubinascii.hexlify(machine.unique_id()).decode('ascii')
    except AttributeError:
        ID = "asdfasdfasdf"

    config = {
        # MQTT config
        "ID": ID,
        "SERVER": "broker.hivemq.com",
        "CONTROL_TOPIC": "/light/"+ID+"/control",
        "STATE_TOPIC": "/light/"+ID+"/state",
        "CONFIG_TOPIC": "/light/"+ID+"/config",
        "GLOBAL_CONFIG_TOPIC": "/light/config",

        # HW config
        "RED_PIN": 14,
        "GREEN_PIN": 5,
        "BLUE_PIN": 12,
        "PWM_FREQ": 1000
    }

    if CONFIG_FILE in os.listdir():
        try:
            config.update(ujson.loads(open(CONFIG_FILE).read()))
        except ValueError:
            print("Bad config file -- deleting")
            os.remove(CONFIG_FILE)

    async def reconfig(event, client, controller, reconfig_done):
        await event
        print("RECONFIG")
        client.disconnect()
        controller.kill()
        old_config = deepcopy(config)
        config.update(ujson.loads(event.value()))
        event.clear()
        print("DONE RECONFIG")
        reconfig_done.set(True)

    client = AsyncMqttClient("mp_mqtt_json_"+config['ID'], config['SERVER'])
    client.connect()
    control_event = client.subscribe(config['CONTROL_TOPIC'])
    config_event = client.subscribe(config['CONFIG_TOPIC'])
    global_config_event = client.subscribe(config['GLOBAL_CONFIG_TOPIC'])
    reconfig_done = Event()

    controller = Controller(rpin=config['RED_PIN'], gpin=config['GREEN_PIN'], bpin=config['BLUE_PIN'], freq=config['PWM_FREQ'])

    async_loop = asyncio.get_event_loop()
    async_loop.create_task(reconfig(config_event, client, controller, reconfig_done))
    async_loop.create_task(reconfig(global_config_event, client, controller, reconfig_done))
    async_loop.create_task(controller.aloop(control_event, client.publish(config['STATE_TOPIC'])))

    await reconfig_done
    print("MAIN LOOP DONE")

def run_main_loop():
    while True:
        async_loop = asyncio.get_event_loop()
        async_loop.run_until_complete(main_loop())

