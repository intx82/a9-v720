

from __future__ import annotations
from log import log
import socket


class netcl(log):
    def __init__(self, host: str, port: int, log_prefix = '') -> None:
        self._host = host
        self._port = port
        super().__init__(f'{log_prefix} {self._host}:{self._port}')

    @property
    def fd(self) -> socket.socket:
        return None

    def __enter__(self) -> netcl:
        return self

    def __exit__(self, t, v, traceback):
        pass

    def open(self):
        pass

    def close(self):
        pass

    def recv(self) -> bytes:
        return None

    def request(self, data: bytes, err=0) -> bytes:
        return None

    def send(self, data: bytes) -> None:
        pass
