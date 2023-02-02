
from __future__ import annotations
import socket
from conn import conn

class conn_udp(conn):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port)

    @staticmethod
    def get_ip(host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, port))
        host = s.getsockname()[0]
        s.close()
        return host
       
    def open(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((conn_udp.get_ip(self._host, self._port), self._port))

    def close(self) -> None:
        pass

    def __enter__(self) -> conn_udp:
        self.open()
        return self

    def __exit__(self, t, v, traceback) -> None:
        self._socket.close()

    def _rcv(self) -> bytes:
        if self._socket is None:
            return None

        return self._socket.recvfrom(1024)
        
    def _req(self, data, err=0) -> bytes:
        if self._socket is None:
            return None

        self._socket.sendto(data, (self._host, self._port))
        return self._rcv()
