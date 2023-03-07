

from __future__ import annotations
from netcl import netcl


class netsrv(netcl):
    def __init__(self, host: str, port: int, log_prefix = '') -> None:
        super().__init__(host, port, log_prefix)

    def fork(self) -> netsrv:
        return self

