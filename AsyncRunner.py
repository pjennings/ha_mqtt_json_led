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

class AsyncRunner:
    def __init__(self, config=None, config_fn=None):
        self.config = config
        self.config_fn = config_fn

        self.read_config()
        self.write_config()

    def write_config(self):
        if self.config_fn is not None:
            with open(self.config_fn, "w") as f:
                f.write(ujson.dumps(self.config))

    def read_config(self):
        file_config = None
        if self.config_fn in os.listdir():
            try:
                file_config = ujson.loads(open(self.config_fn).read())
                self.config.update(file_config)
                return True
            except ValueError:
                print("Bad config file -- deleting")
                os.remove(self.config_fn)
        return False

    async def main_loop(self):
        config = self.config

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
                        events[name][desc] = client.publish("/"+"/".join([self.config['ID'], name, topic]))
                    for desc,topic in val['config']['mqtt']['subscribe'].items():
                        events[name][desc] = client.subscribe("/"+"/".join([self.config['ID'], name, topic]))
            except ImportError:
                print("WARNING: Could not import {}".format(name))
                modules[name] = None

        self.write_config()

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

    def run(self):
        async_loop = asyncio.get_event_loop()
        while True:
            if not async_loop.run_until_complete(self.main_loop()):
                break

            while(len(async_loop.q) > 0):
                print("run_main_loop: {}".format(len(async_loop.q)))
                time.sleep(1)

CONFIG_FILE = "AsyncRunner.config"
def main():
    try:
        ID = ubinascii.hexlify(machine.unique_id()).decode('ascii')
    except AttributeError:
        ID = "".join([str(urandom.getrandbits(x)) for x in [3]*8])

    config = {
        # General config
        "ID": ID,

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

    runner = AsyncRunner(config, CONFIG_FILE)
    runner.run()
