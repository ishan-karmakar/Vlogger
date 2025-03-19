import logging
from vlogger.sources import Source
from vlogger.sources.types import TypeDecoder
import os, io, re
logger = logging.getLogger(__name__)
STRUCT_DTYPE_PREFIX = "struct:"
PROTO_DTYPE_PREFIX = "proto:"
SCHEMA_NT_PREFIX = "NT:/.schema/"
STRUCT_NT_PREFIX = SCHEMA_NT_PREFIX + STRUCT_DTYPE_PREFIX
PROTO_NT_PREFIX = SCHEMA_NT_PREFIX + PROTO_DTYPE_PREFIX

class WPILog(Source):
    def __init__(self, file, regexes: list, **kwargs):
        self.file = open(file, "rb")
        if self.file.read(6) != b"WPILOG":
            raise ValueError("WPILog signature not found when parsing file")

        # Map of regexes that are used by the client
        self.regexes = [re.compile(r) for r in regexes]
        # Map of regexes that are used internally, may overlap with self.regexes
        self.internal_regexes = [re.compile("^" + re.escape("NT:/.schema/"))]
        # Map of actual field ids -> listeners + data, will be populated when start records come
        self.field_map = {}
        self.type_decoder = TypeDecoder()

    def __enter__(self):
        # File is already opened in __init__
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.file.close()

    def __iter__(self):
        # _parse_header seeks to start of file every time, no need to do it here
        self._parse_header()
        return self
    
    def __next__(self):
        while True:
            ret = self._parse_record()
            if ret:
                return ret

    def _parse_header(self):
        self.file.seek(6, os.SEEK_SET)
        version = int.from_bytes(self.file.read(2), "little")
        logger.debug(f"File version: {(version >> 8) & 0xFF}.{version & 0xFF}")

        extra_header_len = int.from_bytes(self.file.read(4), "little")
        extra_header = self.file.read(extra_header_len).decode()
        logger.debug(f"Extra header: '{extra_header}'")

    def _parse_record(self):
        bitfield = self.file.read(1)
        if not len(bitfield):
            raise StopIteration
        
        header_bitfield = int.from_bytes(bitfield, "little")
        entry_id_length = (header_bitfield & 0b11) + 1
        payload_size_length = ((header_bitfield >> 2) & 0b11) + 1
        timestamp_length = ((header_bitfield >> 4) & 0b111) + 1

        id = int.from_bytes(self.file.read(entry_id_length), "little")
        payload_size = int.from_bytes(self.file.read(payload_size_length), "little")
        timestamp = int.from_bytes(self.file.read(timestamp_length), "little")

        if id == 0:
            self._parse_control()
        else:
            return self._parse_data(id, payload_size, timestamp)
    
    def _parse_control(self):
        control_type = int.from_bytes(self.file.read(1), "little")
        entry_id = int.from_bytes(self.file.read(4), "little")

        if control_type == 0:
            entry_name_length = int.from_bytes(self.file.read(4), "little")
            entry_name = self.file.read(entry_name_length).decode()
            entry_type_length = int.from_bytes(self.file.read(4), "little")
            entry_type = self.file.read(entry_type_length).decode()
            entry_metadata_length = int.from_bytes(self.file.read(4), "little")
            self.file.seek(entry_metadata_length, os.SEEK_CUR) # We don't care about metadata

            logger.debug(f"Found start record for {entry_name}")
            if entry_name_length == 0:
                raise Exception

            entry_name = entry_name[3:] # Remove NT:
            if not entry_name.startswith("/"):
                entry_name = "/" + entry_name

            entry_name = "NT:" + entry_name

            # Loop through all target fields and test against target regex
            for regex in self.regexes:
                if regex.match(entry_name):
                    if entry_id in self.field_map:
                        self.field_map[entry_id]["regexes"].add(regex)
                    else:
                        self.field_map[entry_id] = {
                            "name": entry_name,
                            "dtype": entry_type,
                            "regexes": { regex}
                        }
            
            for regex in self.internal_regexes:
                if regex.match(entry_name):
                    if not entry_id in self.field_map:
                        self.field_map[entry_id] = {
                            "name": entry_name,
                            "dtype": entry_type,
                            "regexes": set()
                        }
        elif control_type == 1:
            metadata_length = int.from_bytes(self.file.read(4), "little")
            self.file.seek(metadata_length, os.SEEK_CUR)
        elif control_type == 2:
            self.field_map.pop(entry_id, None)

    def _parse_data(self, id, payload_size, timestamp):
        if not id in self.field_map:
            self.file.seek(payload_size, os.SEEK_CUR)
            return

        topic = self.field_map[id]
        payload = self.file.read(payload_size)
        data = self.type_decoder(topic, io.BytesIO(payload))
        if len(topic["regexes"]):
            return {
                "regexes": topic["regexes"],
                "name": topic["name"],
                "timestamp": timestamp,
                "data": data
            }
