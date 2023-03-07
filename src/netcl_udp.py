
from __future__ import annotations
import socket
from netcl import netcl

class netcl_udp(netcl):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port, log_prefix='UDP-CL')

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
        self._socket.bind((netcl_udp.get_ip(self._host, self._port), self._port))
        self.info('[UDP-Client] connection open')

    def close(self) -> None:
        self.info('[UDP-Client] connection closed')
        pass

    def __enter__(self) -> netcl_udp:
        self.open()
        return self

    def __exit__(self, t, v, traceback) -> None:
        self._socket.close()

    def recv(self) -> bytes:
        if self._socket is None:
            return None

        r = self._socket.recvfrom(1024)
        self.dbg(f'[UDP-Client] recv from {r[1]}: {r[0].hex()}')
        return r
    
    def send(self, data: bytes) -> None:
        self.dbg(f'[UDP-Client] sending: {data.hex()}')
        self._socket.sendto(data, (self._host, self._port))

    def request(self, data, err=0) -> bytes:
        if self._socket is None:
            return None

        self.send(data)
        return self.recv()
