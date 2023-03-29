
from __future__ import annotations
import socket

import time
import cmd_udp

from prot_udp import prot_udp
from netcl import netcl

class netcl_tcp(netcl):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port, log_prefix='TCP-CL')
        

    def open(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(30)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._socket.connect((self._host, self._port))
        self.info('Connected')
    
    def close(self) -> None:
        self._socket.close()

    def __enter__(self) -> netcl_tcp:
        self.open()
        return self

    def __exit__(self, t, v, traceback) -> None:
        self.info('Connection closed')
        self._socket.close()

    def recv(self):
        if self._socket is None:
            return None

        data = self._socket.recv(20)
        
        if len(data) > 0 and len(data) < 20:
            data = bytearray(data)
            _a = self._socket.recv(20 - len(data))
            if len(_a) == 0:
                self.dbg(f'Recv: {data.hex()}')
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
                    raise IOError('Skip due to heartbeat')

            if recv.cmd != cmd_udp.P2P_UDP_CMD_HEARTBEAT:
                data = bytearray(data)
                while recv._len > len(recv.payload):
                    rl = recv._len - len(recv.payload)
                    self.dbg(f'Full {recv._len} need {rl} Got {len(recv.payload)}, try to receive rest')
                    rest = self._socket.recv(rl)
                    if len(rest) == 0:
                        break

                    recv.payload.extend(rest)

                self.dbg(f'recv prot_udp: {recv}')
                return recv.req()

        self.dbg(f'recv data: {bytearray(data).hex()}')
        return data

    def request(self, data, err=0) -> bytes:
        if self._socket is None:
            return None
        try:
            self.send(data)
            return self.recv()
        except (socket.timeout, IOError):
            if err < 5:
                err += 1
                self.warn(f'Socket timeout, try again: {err + 1} after {(err * err) * 0.1} sec')
                time.sleep((err * err) * 0.1)
                return self.request(data, err)
            return None

    def send(self, data: bytes) -> None:
        self.dbg(f'send: {data.hex()}')
        self._socket.sendall(data)