from vlogger.sources import Source
from vlogger.sources.types import TypeDecoder
import json, logging, re, io, threading, queue
import socket
logger = logging.getLogger(__name__)

STRUCT_DTYPE_PREFIX = "struct:"
PROTO_DTYPE_PREFIX = "proto:"
SCHEMA_NT_PREFIX = "NT:/.schema/"
STRUCT_NT_PREFIX = SCHEMA_NT_PREFIX + STRUCT_DTYPE_PREFIX
PROTO_NT_PREFIX = SCHEMA_NT_PREFIX + PROTO_DTYPE_PREFIX

class NetworkTables4(Source):
    def __init__(self, hostname, regexes, **kwargs):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Will raise ConnectionRefusedError if can't connect
        # FIXME: Check for signature or equivalent to make sure it is correct live source
        client_socket.connect((hostname, 5810))
        client_socket.close()

        self.hostname = hostname
        self.regexes = [re.compile(r) for r in regexes]
        self.internal_regexes = [re.compile("^" + re.escape("NT:/.schema/"))]
        self.cur_subuid = 0
        self.queue = queue.SimpleQueue()
        self.field_map = {}
        self.type_decoder = TypeDecoder()
        # FIXME: Make this thread safe or figure out if it is already
        self.should_close = False

    def __enter__(self):
        self.main_thread = threading.Thread(target = self._init_main)
        self.main_thread.daemon = True
        self.main_thread.start()
        return self

    def _init_main(self):
        from websockets.sync import client
        with client.connect(f"ws://{self.hostname}:5810/nt/vlogger", subprotocols=[client.Subprotocol("v4.1.networktables.first.wpi.edu"), client.Subprotocol("networktables.first.wpi.edu")]) as websocket:
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
                if self.should_close:
                    break
                try:
                    msg_raw = websocket.recv(timeout=1)
                    if type(msg_raw) == bytes:
                        for msg in self._decode_msgpack(msg_raw):
                            name = self.field_map[msg[0]]["name"]
                            dtype = self.field_map[msg[0]]["dtype"]
                            regexes = self.field_map[msg[0]]["regex"]
                            data = msg[3]
                            if type(data) == bytes:
                                data = self.type_decoder({
                                    "name": name,
                                    "dtype": dtype
                                }, io.BytesIO(data))
                            
                            if len(regexes):
                                self.queue.put({
                                    "regexes": regexes,
                                    "name": name,
                                    "timestamp": msg[1],
                                    "data": data
                                })
                    else:
                        for msg in json.loads(msg_raw):
                            self._handle_command(msg)
                except TimeoutError:
                    pass

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
        self.should_close = True
        while self.main_thread.is_alive():
            pass

    def _decode_msgpack(self, msg_raw: bytes):
        from msgpack import Unpacker, exceptions
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
            sub_fields = set()
            normalized_name = "NT:/" + name.removeprefix("/")
            for regex in self.regexes:
                if regex.match(normalized_name):
                    sub_fields.add(name)
                    if id in self.field_map:
                        self.field_map[id]["regex"].add(regex)
                    else:
                        self.field_map[id] = {
                            "name": normalized_name,
                            "dtype": msg["params"]["type"],
                            "regex": { regex }
                        }
            for regex in self.internal_regexes:
                if regex.match(normalized_name):
                    sub_fields.add(name)
                    if not id in self.field_map:
                        self.field_map[id] = {
                            "name": normalized_name,
                            "dtype": msg["params"]["type"],
                            "regex": set()
                        }
            if sub_fields:
                self.websocket.send(json.dumps([{
                    "method": "subscribe",
                    "params": {
                        "topics": list(sub_fields),
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
