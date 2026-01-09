from pprint import pprint
import re
from urllib.parse import SplitResult

import requests
from vlogger.types import BaseSource
from urllib.parse import urlunsplit, urlencode

'''
/?action=getversion
/?action=getdevices
/?action=getcommonsignals
PROBABLY NOT USEFUL - /?action=runcaniv&cmd=--version&path=C:%5CUsers%5Cishan%5CAppData%5CLocal%5CPackages%5CCTRElectronics.209251697EEC9_fcacbrk06xgc2%5CLocalCache%5C
/?action=plotpro&model=Talon%20FX%20vers.%20C&id=1&canbus=&signals=0,2028,&resolution=50
/?action=plotpro&model=Talon%20FX%20vers.%20C&id=1&canbus=&signals=0,2128,2129,2085,2130,2028,&resolution=50
/?action=getconfigv2&model=CANCoder%20vers.%20H&id=20&canbus=
/?action=deviceinformation&model=CANCoder%20vers.%20H&id=20&canbus=
/?action=getcontrols&id=20&canbus=&model=CANCoder%20vers.%20H
/?action=getsignals&model=CANCoder%20vers.%20H&id=20&canbus=
'''

MODEL_CLASS_MAPPING = {
    "Talon FX": "TalonFX",
    "CANCoder": "CANcoder"
}

class PhoenixDiagnosticServer(BaseSource):
    SCHEME = "pds"

    def __init__(self, ident: SplitResult, regex: re.Pattern, **kwargs):
        self.netloc = f"{ident.hostname or "localhost"}:{ident.port or 1250}"
        self.regex = regex
        self.session = requests.Session()
        self.device_map: dict[int, dict] = {}
        self.signal_map = {}
        self.resolution = kwargs.get("resolution", 50)

    def __enter__(self):
        return self
    
    def __iter__(self):
        # TODO: Bus util percentage
        yield from self._get_version()
        self._get_common_signals()
        yield from self._get_devices()

        yield { "name": "Server/OneshotDataFinished" }

        streams = { id: self._plot_device(id) for id in self.device_map }

        while True:
            for id, stream in streams.items():
                point = next(stream)
                for code, data in point["Signals"].items():
                    yield {
                        "timestamp": point["Timestamp"],
                        "name": f"ID {id}/{self.signal_map[int(code)]}",
                        "data": data
                    }

    def __exit__(self, exception_type, exception_value, exception_traceback):
        pass

    def _get_version(self):
        version = self._run_query({ "action": "getversion" })
        for k in ["ReleaseInfo", "Version"]:
            yield from self._return_oneshot(f"Server/{k}", version[k])

    def _get_devices(self):
        devices = self._run_query({ "action": "getdevices" })["DeviceArray"]
        for device in devices:
            for k, v in device.items():
                if k == "ID":
                    continue
                yield from self._return_oneshot(f"ID {device["ID"]}/{k}", v)

            class_name = device["Model"].split("vers.")[0].strip()
            class_name = MODEL_CLASS_MAPPING.get(class_name, class_name)
            signals = self._run_query({ "action": "getsignals", "model": device["Model"], "id": device["ID"] })["Signals"]
            signals = { x["Id"]: x["Name"] for x in signals }
            if class_name in MODEL_CLASS_MAPPING:
                signals = self.common_signals[class_name] | signals
            for code, signal in signals.items():
                if self.regex.search(f"ID {device["ID"]}/{signal}"):
                    self.device_map.setdefault(device["ID"], device | { "signals": [] })
                    self.device_map[device["ID"]]["signals"].append(code)
                    self.signal_map[code] = signal
                    break

    def _get_common_signals(self):
        body = self._run_query({ "action": "getcommonsignals" })["Signals"]
        for k, v in body.items():
            body[k] = { x["Id"]: x["Name"] for x in v }
        self.common_signals = body

    def _plot_device(self, id):
        while True:
            response = self._run_query({
                "action": "plotpro",
                "model": self.device_map[id]["Model"],
                "id": id,
                "signals": ",".join(map(str, self.device_map[id]["signals"])),
                "resolution": self.resolution
            })
            for point in response["Points"]:
                yield point

    def _return_oneshot(self, name: str, data):
        if self.regex.search(name):
            yield { "name": name, "data": data }

    def _run_query(self, query: dict):
        return self.session.get(urlunsplit(("http", self.netloc, "", urlencode(query), "")), timeout=10).json()
