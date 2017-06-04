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
        ID = "".join([str(urandom.getrandbits(x)) for x in [3]*8])

    config = {
        # MQTT config
        "CLIENT_ID": "mp_mqtt_json_"+ID,
        "SERVER": "iot.eclipse.org",
        "CONFIG_TOPIC": "/"+ID+"/config",
        "PERSISTENT": True,

        "modules": {
            "light": {
                "module": "Controller",
                "config": None
            }
        }
    }

    if file_config is not None:
        config.update(file_config)

    # Connect to mqtt
    client = AsyncMqttClient(config['CLIENT_ID'], config['SERVER'])
    client.connect()

    # Import and initialize modules
    modules = {}
    instances = {}
    events = {}
    for name,val in config['modules'].items():
        try:
            exec("import {}".format(val['module']), modules)
            if val['config'] is None:
                val['config'] = modules[val['module']].config()
            print(modules)
            instances[name] = getattr(modules[val['module']], val['module'])(val['config'])
            if 'mqtt' in val['config']:
                events[name] = {}
                for desc,topic in val['config']['mqtt']['publish'].items():
                    events[name][desc] = client.publish("/"+"/".join([ID, name, topic]))
                for desc,topic in val['config']['mqtt']['subscribe'].items():
                    events[name][desc] = client.subscribe("/"+"/".join([ID, name, topic]))
        except ImportError:
            print("WARNING: Could not import {}".format(name))
            modules[name] = None

    write_config(config)

    config_event = client.subscribe(config['CONFIG_TOPIC'])
    #client.subscribe(config['CONFIG_TOPIC'], event=config_event)

    # Start each inst
    for name,inst in instances.items():
        inst.start(events[name])

    # In case of reconfig, write the new config and then return, which will allow run_main_loop to rerun this function
    await config_event

    # Will return false if config_event.value() is empty -- special case to end loop
    result = False
    if config_event.value() != "":
        config.update(ujson.loads(config_event.value()))
        write_config(config)
        result = True

    client.disconnect()
    controller.kill()
    old_config = deepcopy(config)
    get_state_event.set(None)

    while(len(async_loop.q) > 1):
        print("main_loop: {}".format(len(async_loop.q)))
        yield from asyncio.sleep(1)

    return result

def run_main_loop():
    async_loop = asyncio.get_event_loop()
    while True:
        if not async_loop.run_until_complete(main_loop()):
            break

        while(len(async_loop.q) > 0):
            print("run_main_loop: {}".format(len(async_loop.q)))
            time.sleep(1)

