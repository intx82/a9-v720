
from __future__ import annotations
import logging
import socket
import time
from queue import Queue
from netsrv import netsrv


class netsrv_udp(netsrv):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(host, port, log_prefix='UDP-SRV')
        self.is_closed = True
        self._forked = False
        self._socket = None
        self._frk_list = []
        self._rcv_data = Queue()
        self._waiter = None

    @staticmethod
    def get_ip(host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, port))
        host = s.getsockname()[0]
        s.close()
        return host

    def open(self) -> None:
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.bind((self._host, self._port))
            self.is_closed = False
            self.info('Waiting for connection')

        rd = self._socket.recvfrom(1024)
        for _fork in self._frk_list:
            if _fork._host == rd[1][0] and _fork._port == rd[1][1]:
                _fork._rcv_data.put(rd)
                return

        self._rcv_data.put(rd)

    def fork(self) -> netsrv_udp:
        if self._forked:
            return None
        
        ret = None
        if not self._rcv_data.empty():
            rd = self._rcv_data.get()
            ret = netsrv_udp(rd[1][0], rd[1][1])
            ret._rcv_data.put(rd)
            ret._socket = self._socket
            ret.is_closed = False
            ret._forked = True
            self._frk_list.append(ret)

        return ret

    def close(self) -> None:
        self.is_closed = True

    def __enter__(self) -> netsrv_udp:
        return self

    def __exit__(self, t, v, traceback) -> None:
        self.close()

    def recv(self) -> tuple:
        if self._forked:
            while self._rcv_data.empty():
                time.sleep(0.01)

            ret = self._rcv_data.get()
            self.dbg(f'Recv: {ret[0].hex() if len(ret[0]) < 64 else f"{ret[0][:64].hex()}..."}')
            return ret[0]
        return None

    def send(self, data: bytes) -> None:
        if self._forked:
            self.dbg(f'Send: {data.hex() if len(data) < 64 else f"{data[:64].hex()}..."}')
            self._socket.sendto(data, (self._host, self._port))

    def request(self, data, err=0) -> bytes:
        self.send(data)
        return self.recv()

    def __str__(self) -> str:
        if self._forked:
            return f'UDP-CON@{self._host}:{self._port}'
        else:
            return f'UDP-SRV@{self._host}:{self._port}'

    def __repr__(self) -> str:
        return self.__str__()




def udp_test():
    import threading

    def udp_hnd(conn : netsrv_udp):
        while True:
            print(conn.recv())
            conn.send(f'[{threading.currentThread().getName()}] OK\r\n'.encode('ascii'))

    with netsrv_udp('', 1234) as _udp:
        try:
            while True:
                _udp.open()
                fork = _udp.fork()
                if fork is not None:
                    udp_cl_th = threading.Thread(target=udp_hnd, args=(fork,), name=f'{fork}')
                    udp_cl_th.setDaemon(True)
                    udp_cl_th.start()
        except KeyboardInterrupt:
            print('...exiting')



if __name__ == '__main__':
    udp_test()
    
    # import os
    # os.popen('sleep 1 && echo "asdfsa" | nc -u localhost 1234')
    # with netsrv_udp('localhost', 1234) as _con:
    #     _con.open()
    #     frk = _con.fork()
    #     if frk is not None:
    #         ret = frk._rcv()
    #         print(ret)
