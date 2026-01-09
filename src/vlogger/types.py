from abc import abstractmethod
import re
import logging, struct, io
from urllib.parse import SplitResult
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.message_factory import GetMessageClass
import json
from typing import Any
logger = logging.getLogger(__name__)
PROTO_DTYPE_PREFIX = "proto:"
STRUCT_DTYPE_PREFIX = "struct:"

# Helpful utility class used by sources to decode a stream of bytes into a variety of data types
class TypeDecoder:
    def __init__(self):
        self.struct_map = {}
        self.proto_pool = DescriptorPool()

    def __call__(self, field_info: dict[str, str], data: io.BytesIO) -> Any:
        match field_info["dtype"]:
            case "raw": return data.read()
            case "boolean": return bool.from_bytes(TypeDecoder._attempt_read(data, 1), "little")
            case "int64": return int.from_bytes(TypeDecoder._attempt_read(data, 8), "little")
            case "float": return struct.unpack("<f", TypeDecoder._attempt_read(data, 4))[0]
            case "double": return struct.unpack("<d", TypeDecoder._attempt_read(data, 8))[0]
            case "string": return data.read().decode()
            case "json": return json.load(data)
            case "structschema":
                schema = self({ **field_info, "dtype": "string" }, data)
                dtype = STRUCT_DTYPE_PREFIX + "".join(field_info["name"].split(STRUCT_DTYPE_PREFIX)[1:])
                logger.debug(f"Registered {dtype} in internal struct map")
                fields = [f.split(" ") for f in schema.split(';')]
                for i, field in enumerate(fields):
                    fields[i][0] = "struct:" + field[0] if "struct:" + field[0] in self.struct_map else field[0]

                def __init__(_self, data):
                    for field in fields:
                        _self.__dict__[field[1]] = self({ **field_info, "dtype": field[0] }, data)
                    new_type = type(dtype, (object,), { "__init__": __init__ })
                    self.struct_map[dtype] = new_type
                    return new_type
            case dtype if dtype == PROTO_DTYPE_PREFIX + "FileDescriptorProto":
                desc = self.proto_pool.AddSerializedFile(data.read())
                for k in [*desc.message_types_by_name.keys(), *desc.enum_types_by_name.keys(), *desc.extensions_by_name.keys(), *desc.services_by_name.keys()]:
                    logger.debug("Adding " + k)
                return desc
            case dtype if dtype.startswith(PROTO_DTYPE_PREFIX):
                msg_class = GetMessageClass(self.proto_pool.FindMessageTypeByName(dtype.lstrip(PROTO_DTYPE_PREFIX)))
                return msg_class.FromString(data.read())
            case "string[]":
                arr_len = int.from_bytes(TypeDecoder._attempt_read(data, 4), "little")
                arr = []
                for i in range(arr_len):
                    arr.append(TypeDecoder._attempt_read(data, int.from_bytes(TypeDecoder._attempt_read(data, 4), "little")))
                return arr
            case dtype if dtype.endswith("[]"):
                arr = []
                while True:
                    try:
                        arr.append(self({ **field_info, "dtype": dtype.rstrip("[]") }, data))
                    except EOFError:
                        break
                return arr
            case dtype if dtype in self.struct_map:
                return self.struct_map[dtype](data)
            case _:
                logger.warning(f"Unknown data type {dtype}, treating as raw")
                return self({ **field_info, "dtype": "raw" }, data)

    # Extremely simple helper function to read data and raise EOFError if at end of stream
    @staticmethod
    def _attempt_read(data, size):
        buf = data.read(size)
        if len(buf) != size:
            raise EOFError
        return buf

class BaseSource:
    SCHEME = ""

    @abstractmethod
    def __init__(self, ident: SplitResult, regex: re.Pattern, **kwargs):
        raise NotImplementedError
    
    @abstractmethod
    def __enter__(self):
        raise NotImplementedError
    
    @abstractmethod
    def __exit__(self, exception_type, exception_value, exception_traceback):
        raise NotImplementedError

    @abstractmethod
    def __iter__(self):
        raise NotImplementedError