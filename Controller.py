import machine
import time
import uasyncio as asyncio
import ujson

from copy import deepcopy

from LED import LED

def config():
    c = {
        # MQTT config
        'mqtt': {
            'publish': {
                "STATE": "state",
            },
            'subscribe': {
                "CONTROL": "control",
                "STATE_REQ": "get_state",
                "CONFIG": "config"
            }
        },

        # HW config
        "RED_PIN": 14,
        "GREEN_PIN": 5,
        "BLUE_PIN": 12,
        "PWM_FREQ": 1000,

        # Misc config
        "DEFAULT_STATE": None
    }
    return c

def state(src=None):
    s = {
        'brightness': 255,
        'color': {
            'r': 0,
            'g': 0,
            'b': 0
        },
        'flash': 0,
        'transition': 0,
        'state': "OFF"
    }
    if src is not None:
        s.update(src)
    return s

def state_equal(a, b):
    for k in set(a.keys()).union(set(b.keys())):
        if not k in a and k in b:
            return False
        if not k in ['flash', 'transition']:
            if a[k] != b[k]:
                return False
    return True

class Controller:
    def __init__(self, in_config):
        self._rp = None
        self._gp = None
        self._bp = None
        self.alive = False
        self.done = True
        self.config = config()
        self.config.update(in_config)
        self.reconfig(self.config)

    def get_state(self):
        return ujson.dumps(self.cstate)

    def start(self, events):
        async_loop = asyncio.get_event_loop()
        async_loop.create_task(self.aloop(events['CONTROL'], events['STATE']))
        async_loop.create_task(self.aget_state(events['STATE_REQ'], events['STATE']))

    def aget_state(self, in_event, out_event):
        while self.alive:
            await in_event
            if in_event.value() is None:
                # value will be none if main loop was killed
                break
            else:
                out_event.set(self.get_state())
            in_event.clear()

    def aloop(self, control_event, status_event=None):
        async_loop = asyncio.get_event_loop()
        if self.config['DEFAULT_STATE'] is not None:
            control_event.set(ujson.dumps(self.config['DEFAULT_STATE']))
        while self.alive:
            await control_event.__await__()
            if control_event.value() is None:
                self.alive = False
                break

            try:
                target = ujson.loads(control_event.value())
                self.set_target(target)
            except ValueError:
                print("Bad formatting: {}".format(control_event.value()))
            finally:
                control_event.clear()

            async_loop.call_soon(self.update(status_event))

    def set_target(self, new_state):
        # Special handling for on/off transitions
        # Keep track of what state was before turning off, and restore some/all of it when turning back on
        if self.cstate['state'] == "ON" and 'state' in new_state and new_state['state'] != "ON":
            self.on_state = deepcopy(self.cstate)
        elif self.cstate['state'] != "ON" and 'state' in new_state and new_state['state'] == "ON":
            # If OFF->ON and R=B=G=0, set R=B=G=old RGB
            if not 'color' in new_state or sum(new_state['color'].values()) == 0:
                new_state['color'] = deepcopy(self.on_state['color'])
                if sum(new_state['color'].values()) == 0:
                    # If RGB is still 0 here, set R=G=B=255 here so that OFF->ON toggle actually does something
                    new_state['color'] = {'r': 255, 'g': 255, 'b': 255}
            if not 'brightness' in new_state:
                new_state['brightness'] = self.on_state['brightness']

        self.sstate = self.cstate
        self.cstate = deepcopy(self.sstate)
        self.tstate = deepcopy(self.sstate)
        self.tstate.update(deepcopy(new_state))

        # Translate state=OFF to R=G=B=Brightness=0 so that transitions work like normal
        if self.tstate['state'] != "ON":
            self.tstate['color'] = {'r': 0, 'g': 0, 'b': 0}
            self.tstate['brightness'] = 0

        print("Setting target:", self.tstate)
        self.start = time.ticks_ms()
        self.duration = int(self.tstate['transition'])*1000
        self.done = False
        self.last_update = time.ticks_ms()
        self.update()

    async def update(self, status_event=None):
        print("UPDATE")
        while not self.done:
            try:
                t = time.ticks_diff(self.start, time.ticks_ms())/self.duration
            except ZeroDivisionError:
                t = 1

            # Apparently time.ticks_diff changed direction at some point...
            if t < 0:
                t = -t
            self.cstate['brightness'] = int(self.sstate['brightness']+(self.tstate['brightness']-self.sstate['brightness'])*t)
            self.cstate['color']['r'] = int(self.sstate['color']['r']+(self.tstate['color']['r']-self.sstate['color']['r'])*t)
            self.cstate['color']['g'] = int(self.sstate['color']['g']+(self.tstate['color']['g']-self.sstate['color']['g'])*t)
            self.cstate['color']['b'] = int(self.sstate['color']['b']+(self.tstate['color']['b']-self.sstate['color']['b'])*t)

            b_pct = float(self.cstate['brightness'])/255.0

            self._rp.update(float(self.cstate['color']['r']*b_pct)/255.0)
            self._gp.update(float(self.cstate['color']['g']*b_pct)/255.0)
            self._bp.update(float(self.cstate['color']['b']*b_pct)/255.0)

            if state_equal(self.cstate, self.tstate) or t >= 0.999:
                self.cstate = self.tstate
                self.done = True

                if status_event is not None:
                    status_event.set(self.get_state())

            await asyncio.sleep(0.1)

    def kill(self):
        if self._rp is not None:
            self._rp.kill()
        if self._gp is not None:
            self._gp.kill()
        if self._bp is not None:
            self._bp.kill()
        self.alive = False

    def reconfig(self, new_config):
        self.kill()
        self.config = new_config

        self._rp = LED(self.config['RED_PIN'], name="R", freq=self.config['PWM_FREQ'])
        self._gp = LED(self.config['GREEN_PIN'], name="G", freq=self.config['PWM_FREQ'])
        self._bp = LED(self.config['BLUE_PIN'], name="B", freq=self.config['PWM_FREQ'])

        self.done = True
        self.alive = True

        self.cstate = state()
        self.sstate = deepcopy(self.cstate)
        self.tstate = deepcopy(self.cstate)
        self.on_state = deepcopy(self.cstate)
        self.update()
