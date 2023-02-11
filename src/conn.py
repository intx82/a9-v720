

from __future__ import annotations


class conn:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def __enter__(self) -> conn:
        return self

    def __exit__(self, t, v, traceback):
        pass

    def _rcv(self) -> bytes:
        return None

    def _req(self, data, err=0) -> bytes:
        return None

    def _snd(self, data) -> None:
        pass
