from __future__ import annotations
from json import dumps, loads

from dataclasses import dataclass, asdict, field
from datetime import datetime

import cmd_udp
from prot_json_udp import prot_json_udp
from prot_json_udp import tests as prot_json_tests




@dataclass
class prot_ap(prot_json_udp):
    # public
    content: dict = field(default_factory=dict)

    def req(self) -> bytes:
        self.json = {
            "code": cmd_udp.CODE_AP_COMMAND,
            "content": self.content
        }
        return super().req()

    @staticmethod
    def resp(income: bytes) -> prot_ap:
        r = prot_json_udp.resp(income)
        if r is not None:
            return prot_ap(**asdict(r), content=r.json['content'])
        return None

    def __str__(self) -> str:
        return dumps(self.content, default=self.__dumps_bytes__, indent=4)

    def __repr__(self) -> str:
        return f'CONTENT: {self.content}'


def tests():
    prot_json_tests()

    print('----------- ', prot_ap.__name__, 'Tests ---------------')
    _json = {
        "code": cmd_udp.CODE_AP_COMMAND,
        "content": {
            'code': cmd_udp.CODE_FORWARD_DEV_WIFI_SCAN,
            'devTarget': prot_ap.DEFAULT_DEV_TARGET
        }
    }

    _str = dumps(_json)

    _payload = bytearray([0, 0, 0, 0, cmd_udp.P2P_UDP_CMD_JSON, 0, 0,
                          0, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0, 0, 0, 0])

    _payload[0] = len(_str)
    _payload.extend(_str.encode('ascii'))

    p = prot_ap(content=_json['content'])
    print('0. ',p,' -> ', p.req())
    assert(_payload == p.req())
    assert(p.content == _json['content'])
    print('0. PASS')


if __name__ == '__main__':
    tests()
