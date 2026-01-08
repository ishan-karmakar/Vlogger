import logging
from urllib.parse import ParseResult
from vlogger.types import BaseSource, TypeDecoder
import os, io, re
import wpiutil.log

logger = logging.getLogger(__name__)
STRUCT_DTYPE_PREFIX = "struct:"
PROTO_DTYPE_PREFIX = "proto:"
SCHEMA_NT_PREFIX = "NT:/.schema/"
STRUCT_NT_PREFIX = SCHEMA_NT_PREFIX + STRUCT_DTYPE_PREFIX
PROTO_NT_PREFIX = SCHEMA_NT_PREFIX + PROTO_DTYPE_PREFIX

class WPILog(BaseSource):
    SCHEME = "wpilog"

    def __init__(self, ident: ParseResult, regexes: list, **kwargs):
        self.ident = ident
        self.regexes = [re.compile(r) if type(r) == str else r for r in regexes]
        self.field_map = {}
        self.type_decoder = TypeDecoder()
    
    def __enter__(self):
        self.log = wpiutil.log.DataLogReader(self.ident.path.lstrip('/'))
    
    def __exit__(self, exception_type, exception_value, exception_traceback):
        pass
    
    def __iter__(self):
        for record in self.log:
            if record.isStart():
                self._parse_start(record)
            elif record.isFinish():
                self.field_map.pop(record.getFinishEntry(), None)
            else:
                entry_id = record.getEntry()
                if entry_id in self.field_map:
                    data = self._parse_data(record)
                    if self.field_map[entry_id]["public"]:
                        yield {
                            "timestamp": record.getTimestamp(),
                            "data": data,
                            "name": self.field_map[entry_id]["name"]
                        }

    def _parse_data(self, record: wpiutil.log.DataLogRecord):
        match self.field_map[record.getEntry()]["dtype"]:
            case "boolean": return record.getBoolean()
            case "int64": return record.getInteger()
            case "float": return record.getFloat()
            case "double": return record.getDouble()
            case "string": return record.getString()
            case "boolean[]": return record.getBooleanArray()
            case "int64[]": return record.getIntegerArray()
            case "float[]": return record.getFloatArray()
            case "double[]": return record.getDoubleArray()
            case "string[]": return record.getStringArray()
            case _: return self.type_decoder(self.field_map[record.getEntry()], io.BytesIO(record.getRaw()))

    def _parse_start(self, record: wpiutil.log.DataLogRecord):
        data = record.getStartData()
        if data.type == "structschema":
            self.field_map[data.entry] = {
                "name": data.name,
                "dtype": data.type,
                "public": False
            }
        for regex in self.regexes:
            if regex.search(data.name):
                self.field_map.setdefault(data.entry, {
                    "name": data.name,
                    "dtype": data.type,
                    "public": True
                })
                break