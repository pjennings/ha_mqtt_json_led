import uasyncio as asyncio
from umqtt.simple import MQTTClient
from Event import Event

class AsyncMqttClient(MQTTClient):
    TIMEOUT=0.1

    def __init__(self, *args, **kwargs):
        MQTTClient.__init__(self, *args, **kwargs)
        self.events = {}

        self._alive = True

        def cb(topic,msg):
            topic = topic.decode()
            msg = msg.decode()
            print("Received {}={}".format(topic,msg))
            if not topic in self.events:
                raise ValueError("Not subscribed to topic '%s' but received message anyway" % topic)
            for f in self.events[topic]:
                f.set(msg)
        MQTTClient.set_callback(self, cb)
        async_loop = asyncio.get_event_loop()
        async_loop.create_task(self.subscribe_loop())

    def disconnect(self):
        self._alive = False
        MQTTClient.disconnect(self)

    async def subscribe_loop(self):
        while self._alive:
            self.check_msg()
            yield from asyncio.sleep(1)

    def set_callback(self, *args, **kwargs):
        raise ImplementationError("Callbacks are not used for AsyncMqttClient")

    def subscribe(self, topic, qos=0, event=None):
        print("Subscribing to {}".format(topic))
        if not topic in self.events:
            self.events[topic] = []
            MQTTClient.subscribe(self, topic, qos)
        if event is None:
            event = Event()
        self.events[topic].append(event)
        return event

    def publish(self, topic, event=None):
        if event is None:
            event = Event()

        async def publish_loop(topic,p_event):
            while self._alive:
                await p_event
                MQTTClient.publish(self, topic, p_event.value())
                p_event.clear()

        async_loop = asyncio.get_event_loop()
        async_loop.create_task(publish_loop(topic,event))
        return event
