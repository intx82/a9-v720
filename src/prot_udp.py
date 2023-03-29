from __future__ import annotations
import struct
import json

from dataclasses import dataclass, field
import cmd_udp

# byteBuf.writeIntLE(naxclowProtocol.getPayloadLen());
# byteBuf.writeShortLE(naxclowProtocol.getCmd());
# byteBuf.writeByte(naxclowProtocol.getMsgFlag());
# byteBuf.writeByte(naxclowProtocol.getDealFlag());
# byteBuf.writeBytes(naxclowProtocol.getForwardId());
# byteBuf.writeIntLE(naxclowProtocol.getPkgId());
# byteBuf.writeBytes(naxclowProtocol.getPayload());

@dataclass
class prot_udp:
    # public const
    DEFAULT_FORWARD_ID = b"00000000"
    DEFAULT_PKG_ID = b"\0\0\0\0"

    # private const
    _STRUCT_FMT = '<LHBB8sL'

    # public var
    payload: bytearray = field(default_factory=bytearray)
    cmd: int = cmd_udp.P2P_UDP_CMD_JSON
    msg_flag: int = cmd_udp.DEFAULT_MSG_FLAG

    # private var
    _deal_flag: int = 0
    _forward_id: bytes = DEFAULT_FORWARD_ID
    _pkg_id: int = 0
    _len: int = 0

    def req(self) -> bytes:
        return bytes(struct.pack(f'{self._STRUCT_FMT}{len(self.payload)}s',
                                 len(self.payload),
                                 self.cmd,
                                 self.msg_flag,
                                 self._deal_flag,
                                 self._forward_id,
                                 self._pkg_id,
                                 self.payload
                                 ))

    @staticmethod
    def resp(income: bytes) -> prot_udp:
        if income is None:
            return None

        _len = struct.calcsize(prot_udp._STRUCT_FMT)
        if len(income) < _len:
            return None

        (_len, _cmd, _msg_flag, _deal_flag, _fwd_id, _pkg_id) = struct.unpack(prot_udp._STRUCT_FMT, income[:_len])

        _payload = income[struct.calcsize(prot_udp._STRUCT_FMT):]
        if len(_payload) > _len:
            _payload = _payload[:_len]

        return prot_udp(_payload, _cmd, _msg_flag, _deal_flag, _fwd_id, _pkg_id, _len)

    @staticmethod
    def __dumps_bytes__(o):
        if type(o) is bytes or type(o) is bytearray:
            return o.hex()
        
        if hasattr(o, '__dict__'):
            return o.__dict__

        return f'{type(o)}'

    def __str__(self) -> str:
        return json.dumps(self.__dict__, default=self.__dumps_bytes__, indent=4)

    def __repr__(self) -> str:
        _p =  self.payload.hex() if len(self.payload) <= 32 else f'{self.payload[:32].hex()}...'
        return f'CMD: {self.cmd}, len: {len(self.payload)} ({self._len}), MSG_Flag: {self.msg_flag}, pkg_id: {self._pkg_id}, deal_fl: {self._deal_flag}, fwd-id: {self._forward_id} Payload: {_p}'



def tests():
    print ('----------- ', prot_udp.__name__, 'Tests ---------------')
    # 0. resp return None
    p = prot_udp.resp(bytes([]))
    print('0.', [], ' -> ', p)
    assert(p is None)
    print('0. PASS ')


# 1. resp return prot_udp()
    income = bytes([0, 0, 0, 0, cmd_udp.P2P_UDP_CMD_HEARTBEAT, 0, 12,
                   0, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0, 0, 0, 0])
    p = prot_udp.resp(income)
    print('1. ', income, ' -> ', p)
    assert(p is not None)
    assert(p.req() == income)
    print('1. PASS')

# 2.
    income = bytes([6, 0, 0, 0, cmd_udp.P2P_UDP_CMD_HEARTBEAT, 0, 12, 0, 0x30,
                   0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0x30, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6])
    p = prot_udp.resp(income)
    print('2.', income, ' -> ', p)
    assert(p is not None)
    assert(p.req() == income)
    assert(p.payload == bytes([1, 2, 3, 4, 5, 6]))
    print('2. PASS')

if __name__ == "__main__":
    tests()