import machine
import time
import uasyncio as asyncio
import ujson

from copy import deepcopy

from LED import LED

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
    def __init__(self, rpin=14, gpin=5, bpin=12, freq=1000):
        self._rp = LED(rpin, name="R", freq=freq)
        self._gp = LED(gpin, name="G", freq=freq)
        self._bp = LED(bpin, name="B", freq=freq)

        self.done = True
        self.alive = True

        self.cstate = state()
        self.sstate = deepcopy(self.cstate)
        self.tstate = deepcopy(self.cstate)
        self.on_state = deepcopy(self.cstate)
        self.update()

    def get_state(self):
        return self.cstate

    def aloop(self, control_event, status_event=None):
        while self.alive:
            await control_event.__await__()
            try:
                target = ujson.loads(control_event.value())
                self.set_target(target)
            except ValueError:
                print("Bad formatting: {}".format(control_event.value()))
            finally:
                control_event.clear()

            while not self.done:
                await asyncio.sleep(0.1)
                self.update()

            if status_event is not None:
                status_event.set(ujson.dumps(self.cstate))

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

    def update(self):
        if not self.done:
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

    def kill(self):
        self._rp.kill()
        self._gp.kill()
        self._bp.kill()
        self.alive = False

