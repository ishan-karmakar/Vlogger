from pprint import pprint
import re
from urllib.parse import SplitResult

import requests
from vlogger.types import BaseSource
from urllib.parse import urlunsplit

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

class PhoenixDiagnosticServer(BaseSource):
    SCHEME = "pds"

    def __init__(self, ident: SplitResult, regexes):
        self.netloc = f"{ident.hostname or "localhost"}:{ident.port or 1250}"
        self.regexes = [re.compile(r) if type(r) == str else r for r in regexes]

    def __enter__(self):
        return self
    
    def __iter__(self):
        # TODO: Bus util percentage
        devices = self._run_query("action=getdevices")["DeviceArray"]
        for device in devices:
            for k, v in device.items():
                if k == "ID":
                    continue
                yield from self._return_oneshot(f"ID {device["ID"]}/{k}", v)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        pass

    def _return_oneshot(self, name: str, data):
        for regex in self.regexes:
            if regex.search(name):
                yield { "name": name, "data": data }
                break

    def _get_devices(self) -> dict[str, int]:
        response = self._run_query("action=getdevices")
        pprint(response)

    def _get_common_signals(self) -> dict[str, int]:
        response = self._run_query("action=getcommonsignals")
        pprint(response["Signals"])

    def _run_query(self, query: str):
        return requests.get(urlunsplit(("http", self.netloc, "", query, ""))).json()
