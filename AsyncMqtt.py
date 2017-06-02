import uasyncio as asyncio
from umqtt.simple import MQTTClient
from Event import Event

class AsyncMqttClient(MQTTClient):
    TIMEOUT=0.1

    def __init__(self, *args, **kwargs):
        MQTTClient.__init__(self, *args, **kwargs)
        self.s_events = {}
        self.p_events = {}

        self._alive = True

        def cb(topic,msg):
            if not self._alive:
                return
            topic = topic.decode()
            msg = msg.decode()
            print("Received {}={}".format(topic,msg))
            if not topic in self.s_events:
                raise ValueError("Not subscribed to topic '%s' but received message anyway" % topic)
            for f in self.s_events[topic]:
                f.set(msg)
        MQTTClient.set_callback(self, cb)
        async_loop = asyncio.get_event_loop()
        async_loop.create_task(self.subscribe_loop())

    def disconnect(self):
        self._alive = False
        for topic,events in self.s_events.items():
            for event in events:
                event.set(None)
        for topic,events in self.p_events.items():
            for event in events:
                event.set(None)
        MQTTClient.disconnect(self)

    async def subscribe_loop(self):
        while self._alive:
            self.check_msg()
            yield from asyncio.sleep(1)

    def set_callback(self, *args, **kwargs):
        raise ImplementationError("Callbacks are not used for AsyncMqttClient")

    def subscribe(self, topic, qos=0, event=None):
        print("Subscribing to {}".format(topic))
        if not topic in self.s_events:
            self.s_events[topic] = []
            MQTTClient.subscribe(self, topic, qos)
        if event is None:
            event = Event()
        self.s_events[topic].append(event)
        return event

    def publish(self, topic, qos=0, event=None):
        if event is None:
            event = Event()

        async def publish_loop(topic,p_event):
            while self._alive:
                await p_event
                if self._alive:
                    # Check self._alive again because client disconnect will trigger event in order to break await above
                    MQTTClient.publish(self, topic, p_event.value())
                    p_event.clear()
                else:
                    break

        if not topic in self.p_events:
            self.p_events[topic] = []
        self.p_events[topic].append(event)

        async_loop = asyncio.get_event_loop()
        async_loop.create_task(publish_loop(topic,event))
        return event
