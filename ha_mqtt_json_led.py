import machine
import time
import ubinascii
import ujson

from copy import deepcopy
from umqtt.robust import MQTTClient

from LED import LED
from Controller import Controller

ID = ubinascii.hexlify(machine.unique_id())
SERVER = "192.168.2.193"
CLIENT_ID = "ha_mp_esp_"+ID.decode('ascii')
CONTROL_TOPIC = b"/light/"+ID+"/control"
STATE_TOPIC = b"/light/"+ID+"/state"

def main_loop():
    controller = Controller()

    def cb(topic, msg):
        print("Received:", msg)
        controller.set_target(ujson.loads(msg))

    c = MQTTClient(CLIENT_ID, SERVER)
    c.set_callback(cb)
    c.connect()
    c.subscribe(CONTROL_TOPIC)
    c.publish(STATE_TOPIC, ujson.dumps(controller.get_state()).encode())
    try:
        while True:
            print("main loop")
            if c.check_msg() or controller.done:
                print("waiting for message")
                c.wait_msg()
            else:
                print("calling update")
                controller.update()

            if controller.done:
                print("Publishing: ")
                print(ujson.dumps(controller.get_state()).encode())
                c.publish(STATE_TOPIC, ujson.dumps(controller.get_state()).encode())
    finally:
        c.disconnect()

