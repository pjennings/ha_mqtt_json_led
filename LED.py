import machine                                                                                                                               
                                                                                                                                             
class LED:                                                                                                                                   
    def __init__(self, pin, brightness=0, name="LED", freq=1000):                                                                            
        self._pin = machine.Pin(pin, machine.Pin.OUT)                                                                                        
        self._pwm = machine.PWM(self._pin)                                                                                                   
        self._freq = freq                                                                                                                    
        self.name = name                                                                                                                     
                                                                                                                                             
    def update(self, brightness):                                                                                                            
        duty = int(1023*brightness)                                                                                                          
        print("%s: Setting to %s (%s)" % (self.name, brightness, duty))                                                                                                                                                                                                 
        if brightness <= 0.001:                                                                                                              
            self._pwm.duty(0)                                                                                                                
        elif brightness >= 0.999:                                                                                                            
            self._pwm.duty(1023)                                                                                                             
        else:                                                                                                                                
            self._pwm.duty(duty)                                                                                                             

    def kill(self):
        self._pwm.deinit()

