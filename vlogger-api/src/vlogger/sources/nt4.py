from vlogger.sources import Source
from vlogger.sources.types import TypeDecoder
import json, logging, re, io, threading, queue
import socket
logger = logging.getLogger(__name__)

STRUCT_PREFIX = "struct:"

class NetworkTables4(Source):
    def __init__(self, hostname, regex_listeners, **kwargs):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Will raise ConnectionRefusedError if can't connect
        # FIXME: Check for signature or equivalent to make sure it is correct live source
        client_socket.connect((hostname, 5810))
        client_socket.close()
        self.hostname = hostname
        self.regex_listeners = regex_listeners.copy()
        self.regex_listeners[f"^{re.escape("NT:/.schema/")}"] = set()
        self.cur_subuid = 0
        self.queue = queue.SimpleQueue()
        self.field_map = {}
        self.type_decoder = TypeDecoder()

    def __iter__(self):
        self.main_thread = threading.Thread(target = self._init_main)
        self.main_thread.daemon = True
        self.main_thread.start()
        return self
    
    def _init_main(self):
        from websockets.sync import client
        with client.connect(f"ws://{self.ip}:5810/nt/vlogger", subprotocols=[client.Subprotocol("v4.1.networktables.first.wpi.edu"), client.Subprotocol("networktables.first.wpi.edu")]) as websocket:
            logger.info("Successfully connected to NT4 server")
            self.websocket = websocket
            websocket.send(json.dumps([
                {
                    "method": "subscribe",
                    "params": {
                        # Not the most efficient but the only way to get all the names
                        "topics": [""],
                        "subuid": 0,
                        "options": {
                            "prefix": True,
                            # We want to get only the announcing of topics, and then we will decide if we want the values
                            # Otherwise getting all value changes of all topics will slow us down a lot
                            "topicsonly": True
                        }
                        # TODO: Do we want only most recent value or all values ever sent
                    }
                },
                {
                    "method": "subscribe",
                    "params": {
                        "topics": ["/.schema/"],
                        "subuid": 1,
                        "options": {
                            "prefix": True,
                            "topicsonly": False
                        }
                    }
                }
            ]))
            self.cur_subuid = 2

            while True:
                msg_raw = websocket.recv()
                if type(msg_raw) == bytes:
                    for msg in self._decode_msgpack(msg_raw):
                        name = self.field_map[msg[0]]["name"]
                        dtype = self.field_map[msg[0]]["dtype"]
                        listeners = self.field_map[msg[0]]["listeners"]
                        regexes = self.field_map[msg[0]]["regex"]
                        if name.startswith("/.schema/struct:"):
                            self.type_decoder.add_struct(name.removeprefix("/.schema/"), msg[3].decode())
                        elif name.startswith("/.schema/proto:"):
                            self.type_decoder.add_proto(msg[3])
                        elif type(msg[3]) == bytes:
                            self.queue.put([regexes, listeners, "NT:" + name, msg[1], self.type_decoder(dtype, io.BytesIO(msg[3]))])
                        else:
                            self.queue.put([regexes, listeners, "NT:" + name, msg[1], msg[3]])
                else:
                    for msg in json.loads(msg_raw):
                        self._handle_command(msg)

    def __next__(self):
        try:
            while True:
                try:
                    return self.queue.get(timeout = 1)
                except queue.Empty:
                    pass
        except KeyboardInterrupt:
            raise StopIteration

    def close(self):
        # Thread is daemon, will auto exit when main program exits
        pass

    def _decode_msgpack(self, msg_raw: bytes):
        from websockets import exceptions
        from msgpack import Unpacker
        decoded = []
        unpacker = Unpacker(io.BytesIO(msg_raw))
        try:
            while True:
                tmp = []
                for i in range(unpacker.read_array_header()):
                    tmp.append(unpacker.unpack())
                decoded.append(tmp)
        except exceptions.OutOfData:
            return decoded
        
    def _handle_command(self, msg):
        if msg["method"] == "announce":
            id = msg["params"]["id"]
            name = msg["params"]["name"]
            sub_fields = []
            for regex, listeners in self.regex_listeners.items():
                if re.search(regex, "NT:" + name):
                    sub_fields.append(name)
                    if id in self.field_map:
                        self.field_map[id]["listeners"] |= listeners
                        self.field_map[id]["regex"].add(regex)
                    else:
                        self.field_map[id] = {
                            "name": name,
                            "dtype": msg["params"]["type"],
                            "listeners": listeners,
                            "regex": { regex }
                        }
            if sub_fields:
                self.websocket.send(json.dumps([{
                    "method": "subscribe",
                    "params": {
                        "topics": sub_fields,
                        "subuid": self.cur_subuid,
                        "options": {
                            "prefix": False,
                            "topicsonly": False
                        }
                    }
                }]))
                self.cur_subuid += 1
        elif msg["method"] == "unannounce":
            self.field_map.pop(msg["params"]["id"], None)
