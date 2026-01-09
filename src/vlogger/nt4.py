from urllib.parse import SplitResult
from vlogger.types import BaseSource, TypeDecoder
import re, io, queue, ntcore

class NetworkTables4(BaseSource):
    SCHEME = "nt4"

    def __init__(self, ident: SplitResult, regex: re.Pattern):
        self.ident = ident
        self.regex = regex
        self.queue = queue.SimpleQueue()
        self.type_decoder = TypeDecoder()
        self.listeners = []

    def __enter__(self):
        ntcore.NetworkTableInstance.getDefault().startClient4("vlogger")
        ntcore.NetworkTableInstance.getDefault().setServer(self.ident.hostname or "localhost", self.ident.port or 0)
        self.listeners.extend([
            ntcore.NetworkTableInstance.getDefault().addListener([""], ntcore.EventFlags.kPublish, self._topic_listener),
            ntcore.NetworkTableInstance.getDefault().addListener(["/.schema/struct:"], ntcore.EventFlags.kValueRemote, self._add_structschema)
        ])
        return self

    def __iter__(self):
        return self

    def __next__(self):
        try:
            while True:
                try:
                    return self.queue.get(timeout = 1)
                except queue.Empty:
                    pass
        except KeyboardInterrupt:
            raise StopIteration

    def __exit__(self, exception_type, exception_value, exception_traceback):
        for listener in self.listeners:
            ntcore.NetworkTableInstance.getDefault().removeListener(listener)
        ntcore.NetworkTableInstance.getDefault().stopClient()

    def _topic_listener(self, event: ntcore.Event):
        if not isinstance(event.data, ntcore.TopicInfo):
            return
        if self.regex.search(event.data.name):
            self.listeners.append(ntcore.NetworkTableInstance.getDefault().addListener(event.data.topic, ntcore.EventFlags.kValueRemote, self._value_listener))
    
    def _value_listener(self, event: ntcore.Event):
        if not isinstance(event.data, ntcore.ValueEventData):
            return
        data = event.data.value.value()
        if event.data.value.type() == ntcore.NetworkTableType.kRaw:
            data = self.type_decoder({
                "name": event.data.topic.getName(),
                "dtype": event.data.topic.getTypeString()
            }, io.BytesIO(event.data.value.value()))
        self.queue.put({
            "name": event.data.topic.getName(),
            "timestamp": event.data.value.time(),
            "data": data
        })

    def _add_structschema(self, event: ntcore.Event):
        if not isinstance(event.data, ntcore.ValueEventData):
            return
        self.type_decoder({
            "name": event.data.topic.getName(),
            "dtype": event.data.topic.getTypeString()
        }, io.BytesIO(event.data.value.value()))
