
from __future__ import annotations
import socket

import time
import cmd_udp

from prot_udp import prot_udp
from conn import conn

class conn_tcp(conn):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port)

    def open(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(30)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._socket.connect((self._host, self._port))
    
    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> conn_tcp:
        self.open()
        return self

    def __exit__(self, t, v, traceback) -> None:
        self._socket.close()

    def _rcv(self):
        if self._socket is None:
            return None

        data = self._socket.recv(20)
        if len(data) > 0 and len(data) < 20:
            # print('---- need to append data to create a package')
            data = bytearray(data)
            _a = self._socket.recv(20 - len(data))
            if len(_a) == 0:
                return data

            data.extend(_a)

        recv = prot_udp.resp(bytearray(data))
        if recv is not None:
            if recv.cmd == cmd_udp.P2P_UDP_CMD_HEARTBEAT:
                self._socket.sendall(
                    prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req())
                if len(data) > 20:
                    recv = prot_udp.resp(bytearray(data[20:]))
                else:
                    raise IOError('Skip due to heartbig')

            if recv.cmd != cmd_udp.P2P_UDP_CMD_HEARTBEAT:
                data = bytearray(data)
                while recv._len > len(recv.payload):
                    rl = recv._len - len(recv.payload)
                    # print(f'----- Full {recv._len} Need {rl} Got {len(recv.payload)}')
                    rest = self._socket.recv(rl)
                    if len(rest) == 0:
                        break

                    recv.payload.extend(rest)
                return recv.req()

        return data

    def _req(self, data, err=0) -> bytes:
        if self._socket is None:
            return None
        try:
            self._snd(data)
            return self._rcv()
        except (socket.timeout, IOError):
            if err < 5:
                err += 1
                print(f'-- Try again: {err + 1} after {(err * err) * 0.1} sec')
                time.sleep((err * err) * 0.1)
                return self._req(data, err)
            return None

    def _snd(self, data) -> None:
        self._socket.sendall(data)