import machine
import time
import os
import ubinascii
import ujson

from copy import deepcopy
from umqtt.robust import MQTTClient

from LED import LED
from Controller import Controller

CONFIG_FILE = "ha_mqtt_json_led.config"
ID = ubinascii.hexlify(machine.unique_id()).decode('ascii')

config = {
    # MQTT config
    'ID': ID,
    'SERVER': "192.168.2.193",
    'CONTROL_TOPIC': "/light/"+ID+"/control",
    'STATE_TOPIC': "/light/"+ID+"/state",
    'CONFIG_TOPIC': "/light/"+ID+"/config",
    'GLOBAL_CONFIG_TOPIC': "/light/config",

    # HW config
    'RED_PIN': 14,
    'GREEN_PIN': 5,
    'BLUE_PIN': 12,
    'PWM_FREQ': 1000
}

old_config = deepcopy(config)

RECONFIG = True

def publish(client, topic, msg):
    if topic != "":
        client.publish(topic, msg)

def connect(id, server, callback, topics):
    c = MQTTClient(id, server)
    c.set_callback(callback)
    c.connect()
    for topic in topics:
        c.subscribe(topic)
    return c

def main_loop():
    global config
    global RECONFIG

    controller = None
    client = None

    if CONFIG_FILE in os.listdir():
        try:
            config.update(ujson.loads(open(CONFIG_FILE).read()))
        except ValueError:
            print("Bad config file -- deleting")
            os.remove(CONFIG_FILE)

    def cb(topic, msg):
        global RECONFIG
        global config
        global old_config

        print("Received:", msg)
        if topic == config['CONTROL_TOPIC'].encode():
            print("Setting target")
            controller.set_target(ujson.loads(msg))
        elif topic == config['CONFIG_TOPIC'].encode() or topic == config['GLOBAL_CONFIG_TOPIC'].encode():
            print("Attempting reconfig")
            try:
                old_config = deepcopy(config)
                config.update(ujson.loads(msg))
                RECONFIG = True
            except ValueError:
                print("Bad config message")

    try:
        while True:
            print("main loop")
            if RECONFIG:
                if client is not None:
                    client.disconnect()
                    client = None
                if controller is not None:
                    controller.kill()
                    controller = None

            if client is None:
                client = connect("mp_mqtt_json_"+config['ID'], config['SERVER'], cb, [config['CONTROL_TOPIC'], config['CONFIG_TOPIC'], config['GLOBAL_CONFIG_TOPIC']])
                controller = Controller(rpin=config['RED_PIN'], gpin=config['GREEN_PIN'], bpin=config['BLUE_PIN'], freq=config['PWM_FREQ'])
                publish(client, config['STATE_TOPIC'], ujson.dumps(controller.get_state()).encode())
                RECONFIG = False
                f = open(CONFIG_FILE, "w")
                f.write(ujson.dumps(config))
                f.close()

            if client.check_msg() or controller.done:
                print("waiting for message")
                client.wait_msg()
            else:
                print("calling update")
                controller.update()

            if controller.done:
                print("Publishing: ")
                print(ujson.dumps(controller.get_state()).encode())
                publish(client, config['STATE_TOPIC'], ujson.dumps(controller.get_state()).encode())
    finally:
        if client is not None:
           client.disconnect()

