from urllib.parse import SplitResult
from vlogger.types import BaseSource, TypeDecoder
import io, re
from wpiutil.log import DataLogRecord, DataLogReader

GETTERS = {
    "boolean": [DataLogRecord.getBoolean, DataLogRecord.getBooleanArray],
    "float": [DataLogRecord.getFloat, DataLogRecord.getFloatArray],
    "double": [DataLogRecord.getDouble, DataLogRecord.getDoubleArray],
    "int64": [DataLogRecord.getInteger, DataLogRecord.getIntegerArray],
    "string": [DataLogRecord.getString, DataLogRecord.getStringArray],
}

class WPILog(BaseSource):
    SCHEME = "wpilog"

    def __init__(self, ident: SplitResult, regex: re.Pattern, **kwargs):
        self.regex = regex
        self.field_map = {}
        self.type_decoder = TypeDecoder()
        self.log = DataLogReader(ident.path.lstrip('/'))
    
    def __enter__(self):
        pass
    
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
                    if self.field_map[entry_id]["getter"]:
                        data = self.field_map[entry_id]["getter"](record)
                    else:
                        data = self.type_decoder(self.field_map[entry_id], io.BytesIO(record.getRaw()))
                    if self.field_map[entry_id]["public"]:
                        yield {
                            "timestamp": record.getTimestamp(),
                            "data": data,
                            "name": self.field_map[entry_id]["name"]
                        }

    def _parse_start(self, record: DataLogRecord):
        data = record.getStartData()
        public: bool | None = None
        if data.type == "structschema":
            public = False
        if self.regex.search(data.name):
            public = True
        if public is not None:
            getter = GETTERS.get(data.type.rstrip("[]"))
            if getter:
                [single, array] = getter
                getter = array if data.type.endswith("[]") else single
            self.field_map.setdefault(data.entry, {
                "name": data.name,
                "dtype": data.type,
                "getter": getter,
                "public": public
            })
    