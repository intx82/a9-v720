
from __future__ import annotations
import socket
import time
import sys

from netcl import netcl


class netsrv_tcp(netcl):
    def __init__(self, host: str, port: int, log_prefix = 'TCP-SRV') -> None:
        super().__init__(host, port, log_prefix=log_prefix)
        self.is_closed = True
        self._forked = False
        self._frk_conns = []

    def fork(self) -> netsrv_tcp:
        if not self.is_closed:
            ret = netsrv_tcp(self._addr[0], self._addr[1], log_prefix='TCP-CON')
            ret._socket = self._socket
            ret._conn = self._conn
            ret._addr = self._addr
            ret._forked = True
            ret.is_closed = False
            self._frk_conns.append(ret)
            return ret
        return None

    def open(self) -> None:
        if not self._forked:
            if not hasattr(self, '_socket'):
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if sys.platform.startswith('linux'):
                    self._socket.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 30)
                    self._socket.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 4)
                    self._socket.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 15)

                self._socket.bind((self._host, self._port))
                self._socket.listen(10)

            self.info('Waiting for connection')
            (self._conn, self._addr) =  self._socket.accept()
            self.info(f'Connected: {self._addr}')
            self.is_closed = False

    def close(self) -> None:
        self.is_closed = True
        if not self._forked:
            for con in self._frk_conns:
                if not con.is_closed:
                    con.close()
            self._socket.close()
            self.err(f'Connection closed')
        else:
            self._conn.close()
            self.err(f'Connection closed: {self._addr}')

    @property
    def fd(self) -> socket.socket:
        return self._conn

    def __enter__(self) -> netsrv_tcp:
        return self

    def __exit__(self, t, v, traceback) -> None:
        self.close()

    def recv(self):
        if self._forked:
            if self.is_closed:
                return None

            if not hasattr(self, '_socket') or not hasattr(self, '_conn'):
                self.err('Connection closed, open it first')
                return None

            if self._socket is None or self._conn is None:
                return None

            try:
                data = self._conn.recv(1024)
            except (ConnectionResetError, TimeoutError, OSError):
                data = bytearray()

            if len(data) == 0:
                self.err(f'Connection closed by peer (camera @ {self._addr})')
                self.close()

            self.dbg(f'Recv: {data.hex() if len(data) < 64 else f"{data[:64].hex()}..."}')
            return data
        
        self.err('recieving from not forked connection')
        return None

    def request(self, data, _err=0) -> bytes:
        try:
            self._socket.settimeout(2)
            self.send(data)
            ret = self.recv()
            self._socket.settimeout(None)
            return ret
        except (socket.timeout, IOError):
            if _err < 5:
                _err += 1
                self.warn(f'Socket timeout, try again: {_err + 1} after {(_err * _err) * 0.1} sec')
                time.sleep((_err * _err) * 0.1)
                return self.request(data, _err)
            return None

    def send(self, data) -> None:
        if self._forked:
            if not hasattr(self, '_socket') or not hasattr(self, '_conn'):
                self.err('Connection closed, open it first')
                return

            if not self.is_closed:
                self.dbg(f'Send: {data.hex() if len(data) < 64 else f"{data[:64].hex()}..."}')
                try:
                    self._conn.sendall(data)
                except BrokenPipeError:
                    self.err('sending failed, connection closed')
                    self.close()
            else:
                self.err('sending failed, connection closed')
        else:
            self.err('sending from not forked connection')

    def __str__(self) -> str:
        if self._forked:
            return f'TCP-CON@{self._host}:{self._port}'
        else:
            return f'TCP-SRV@{self._host}:{self._port}'

    def __repr__(self) -> str:
        return self.__str__()


def tcp_test():
    import threading

    def tcp_hnd(conn : netsrv_tcp):
        while not conn.is_closed:
            print(conn.recv())
            conn.send(f'[{threading.currentThread().getName()}] OK\r\n'.encode('ascii'))

    with netsrv_tcp('',6123) as _tcp:
        try:
            while True:
                _tcp.open()
                fork = _tcp.fork()
                if fork is not None:
                    tcp_cl_th = threading.Thread(target=tcp_hnd, args=(fork,), name=f'{fork}')
                    tcp_cl_th.setDaemon(True)
                    tcp_cl_th.start()
        except KeyboardInterrupt:
            print('...exiting')


if __name__ == '__main__':
    tcp_test()