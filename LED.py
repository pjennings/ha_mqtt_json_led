try:
    import machine                                                                                                                               
except ImportError:
    machine = None

class LED:                                                                                                                                   
    def __init__(self, pin, brightness=0, name="LED", freq=1000):
        try:
            self._pin = machine.Pin(pin, machine.Pin.OUT)
            self._pwm = machine.PWM(self._pin) 
        except AttributeError:
            self._pin = None
            self._pwm = None                                                                                                  
        self._freq = freq                                                                                                                    
        self.name = name                                                                                                                     

    def reinit(self):
        try:
            self._pwm = machine.PWM(self._pin) 
        except AttributeError:
            self._pwm = None

    def update(self, brightness):                                                                                                            
        duty = max(min(int(1023*brightness), 1023), 0)
        print("%s: Setting to %s (%s)" % (self.name, brightness, duty))
        if self._pwm is not None:
            if brightness <= 0.001:
                self._pwm.duty(0)
            elif brightness >= 0.999:
                self._pwm.duty(1023)
            else:
                self._pwm.duty(duty)

    def kill(self):
        if self._pwm is not None:
            self._pwm.deinit()

