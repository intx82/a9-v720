from __future__ import annotations
from json import dumps, loads, decoder

from dataclasses import dataclass, asdict, field
from datetime import datetime

import cmd_udp
from prot_udp import prot_udp
from prot_udp import tests as prot_udp_tests


@dataclass
class prot_json_udp(prot_udp):
    DEFAULT_DEV_TARGET = "deadbeef"
    DEFAULT_DEVICE_TOKEN = "This is TEST token"

    # public
    json: dict = field(default_factory=dict)

    def req(self) -> bytes:
        self.cmd = cmd_udp.P2P_UDP_CMD_JSON
        self.payload = dumps(self.json,
                             default=self.__dumps_bytes__).encode('ascii')
        return super().req()

    @staticmethod
    def resp(income: bytes) -> prot_json_udp:
        r = prot_udp.resp(income)
        if r is not None and (r.cmd == cmd_udp.P2P_UDP_CMD_JSON or r.cmd == cmd_udp.P2P_UDP_CMD_DIRECT_MOTION):
            try:
                return prot_json_udp(**asdict(r),
                                     json=loads(r.payload.decode('ascii')))
            except (UnicodeDecodeError, decoder.JSONDecodeError):
                print(f'---Exception with: {r.payload}')

        return None

    def __str__(self) -> str:
        return dumps(self.json, default=self.__dumps_bytes__, indent=4)

    def __repr__(self) -> str:
        return f'JSON: {self.json}'


def tests():
    prot_udp_tests()

    print('----------- ', prot_json_udp.__name__, 'Tests ---------------')
    _json = {
        'code': cmd_udp.CODE_AP_CONNECT,
        'target': prot_json_udp.DEFAULT_DEV_TARGET,
        'token': prot_json_udp.DEFAULT_DEVICE_TOKEN,
        'unixTimer': int(datetime.timestamp(datetime.now()))
    }

    _str = dumps(_json)

    _payload = bytearray([0, 0, 0, 0, cmd_udp.P2P_UDP_CMD_JSON, 0, 0,
                          0, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0, 0, 0, 0])

    _payload[0] = len(_str)
    _payload.extend(_str.encode('ascii'))

    p = prot_json_udp.resp(_payload)
    print('0. ', _payload, '->', p)
    assert(_payload == p.req())
    assert(p.json == _json)
    assert(p.json['code'] == cmd_udp.CODE_AP_CONNECT)
    print('0. PASS')

    _payload[4] = cmd_udp.P2P_UDP_CMD_XML
    p = prot_json_udp.resp(_payload)
    print('1. ', _payload, '->', p)
    assert(p is None)
    print('1. PASS')


if __name__ == '__main__':
    tests()
