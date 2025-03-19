import logging, struct, io
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.message_factory import GetMessageClass
import json
logger = logging.getLogger(__name__)

# Helpful utility class used by sources to decode a stream of bytes into a variety of data types
class TypeDecoder:
    def __init__(self):
        self.struct_map = {}
        self.proto_pool = DescriptorPool()
    
    def add_struct(self, dtype: str, data: str):
        logger.debug("Adding " + dtype)
        fields = [f.split(" ") for f in data.split(";")]
        for i, field in enumerate(fields):
            fields[i][0] = "struct:" + field[0] if "struct:" + field[0] in self.struct_map else field[0]

        def __init__(_self, data):
            for field in fields:
                _self.__dict__[field[1]] = self(field[0], data)

        self.struct_map[dtype] = type(dtype, (object,), {
            "__init__": __init__
        })
    
    def add_proto(self, data: str):
        desc = self.proto_pool.AddSerializedFile(data)
        for k in desc.message_types_by_name.keys():
            logger.debug("Adding " + k)

    def __call__(self, dtype: str, data: io.BytesIO):
        if dtype == "raw": return data.read()
        elif dtype == "boolean": return bool.from_bytes(TypeDecoder._attempt_read(data, 1), "little")
        elif dtype == "int64": return int.from_bytes(TypeDecoder._attempt_read(data, 8), "little")
        elif dtype == "float": return struct.unpack("<f", TypeDecoder._attempt_read(data, 4))[0]
        elif dtype == "double": return struct.unpack("<d", TypeDecoder._attempt_read(data, 8))[0]
        elif dtype == "string": return data.read().decode()
        elif dtype == "json": return json.load(data) # BytesIO counts as file I/O object
        elif dtype == "structschema": return self("string", data) # Return raw schema as a string
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
                    arr.append(self(dtype.removesuffix("[]"), data))
                except EOFError:
                    break
            return arr
        elif dtype in self.struct_map:
            return self.struct_map[dtype](data)
        else:
            try:
                msg_class = GetMessageClass(self.proto_pool.FindMessageTypeByName(dtype.removeprefix("proto:")))
                return msg_class.FromString(data.read())
            except KeyError:
                pass

            logger.warning(f"Unkown data type {dtype}, treating as raw")
            return self("raw", io.BytesIO(data.getvalue()))

    # Extremely simple helper function to read data and raise EOFError if at end of stream
    @staticmethod
    def _attempt_read(data, size):
        buf = data.read(size)
        if len(buf) != size:
            raise EOFError
        return buf
