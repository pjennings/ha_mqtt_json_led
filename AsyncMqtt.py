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

    def subscribe(self, topic, qos=0):
        print("Subscribing to {}".format(topic))
        if not topic in self.events:
            self.events[topic] = []
            MQTTClient.subscribe(self, topic, qos)
        e = Event()
        self.events[topic].append(e)
        return e

    def publish(self, topic):
        my_event = Event()

        async def publish_loop(topic,event):
            while self._alive:
                await event
                MQTTClient.publish(self, topic, event.value())
                event.clear()

        async_loop = asyncio.get_event_loop()
        async_loop.create_task(publish_loop(topic,my_event))
        return my_event
