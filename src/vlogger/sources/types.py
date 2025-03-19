import logging, struct, io
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.message_factory import GetMessageClass
import json
logger = logging.getLogger(__name__)
PROTO_DTYPE_PREFIX = "proto:"
STRUCT_DTYPE_PREFIX = "struct:"

# Helpful utility class used by sources to decode a stream of bytes into a variety of data types
class TypeDecoder:
    def __init__(self):
        self.struct_map = {}
        self.proto_pool = DescriptorPool()

    def __call__(self, field_info: dict, data: io.BytesIO):
        dtype = field_info["dtype"]
        name = field_info["name"]
        if dtype == "raw": return data.read()
        elif dtype == "boolean": return bool.from_bytes(TypeDecoder._attempt_read(data, 1), "little")
        elif dtype == "int64": return int.from_bytes(TypeDecoder._attempt_read(data, 8), "little")
        elif dtype == "float": return struct.unpack("<f", TypeDecoder._attempt_read(data, 4))[0]
        elif dtype == "double": return struct.unpack("<d", TypeDecoder._attempt_read(data, 8))[0]
        elif dtype == "string": return data.read().decode()
        elif dtype == "json": return json.load(data) # BytesIO counts as file I/O object
        elif dtype == "structschema":
            string = self({
                "name": name,
                "dtype": "string"
            }, data)
            dtype = STRUCT_DTYPE_PREFIX + "".join(name.split(STRUCT_DTYPE_PREFIX)[1:])
            logger.debug(f"Registered {dtype} in internal struct map")
            fields = [f.split(" ") for f in string.split(";")]
            for i, field in enumerate(fields):
                fields[i][0] = "struct:" + field[0] if "struct:" + field[0] in self.struct_map else field[0]

            def __init__(_self, data):
                for field in fields:
                    _self.__dict__[field[1]] = self({
                        "name": name,
                        "dtype": field[0]
                    }, data)
            self.struct_map[dtype] = type(dtype, (object,), {
                "__init__": __init__
            })
            return string
        elif dtype == PROTO_DTYPE_PREFIX + "FileDescriptorProto":
            desc = self.proto_pool.AddSerializedFile(data.read())
            for k in desc.message_types_by_name.keys() + desc.enum_types_by_name.keys() + desc.extensions_by_name.keys() + desc.services_by_name.keys():
                logger.debug("Adding " + k)
            return desc
        elif dtype.startswith(PROTO_DTYPE_PREFIX):
            msg_class = GetMessageClass(self.proto_pool.FindMessageTypeByName(dtype[len(PROTO_DTYPE_PREFIX):]))
            return msg_class.FromString(data.read())
        elif dtype == "string[]":
            arr_len = int.from_bytes(TypeDecoder._attempt_read(data, 4), byteorder="little")
            arr = []
            for i in range(arr_len):
                arr.append(TypeDecoder._attempt_read(data, int.from_bytes(TypeDecoder._attempt_read(data, 4), byteorder="little")).decode())
            return arr
        elif dtype.endswith("[]"):
            arr = []
            while True:
                try:
                    arr.append(self({
                        "name": name,
                        "dtype": dtype[:-2]
                    }, data))
                except EOFError:
                    break
            return arr
        elif dtype in self.struct_map:
            return self.struct_map[dtype](data)
        else:
            logger.warning(f"Unkown data type {dtype}, treating as raw")
            return self({
                "name": name,
                "dtype": "raw"
            }, data)

    # Extremely simple helper function to read data and raise EOFError if at end of stream
    @staticmethod
    def _attempt_read(data, size):
        buf = data.read(size)
        if len(buf) != size:
            raise EOFError
        return buf
