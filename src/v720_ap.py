
from socket import socket, timeout
from datetime import datetime

import time
import cmd_udp
from prot_json_udp import prot_json_udp
from prot_xml_udp import prot_xml_udp
from prot_ap import prot_ap
from prot_udp import prot_udp


class v720_ap:
    def __init__(self, socket: socket) -> None:
        self._socket = socket
        self.dev_id = None
        self.forward_id = None

        ret = self._req(prot_udp(cmd=cmd_udp.P2P_UDP_CMD_LIVE_MOTION).req())
        if len(ret) == 0:
            raise IOError('Could not connect to the A9 camera')

        self.connect()
        print('Found A9 camera, FW version:',
              self.baseinfo().content['version'])

    def _rcv(self):
        data = self._socket.recv(1024)
        if len(data) > 0 and len(data) < 20:
            # print('---- need to append data to create a package')
            data = bytearray(data)
            _a = self._socket.recv(1024)
            if len(_a) == 0:
                return data

            data.extend(_a)

        recv = prot_udp.resp(bytearray(data))
        if recv is not None:
            if recv.cmd == cmd_udp.P2P_UDP_CMD_HEARTBEAT:
                # print(f'---- found heartbeat, sending response')
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
#                    print(f'----- Full {recv._len} Need {rl} Got {len(recv.payload)}')
                    rest = self._socket.recv(rl)
                    if len(rest) == 0:
                        break

                    recv.payload.extend(rest)
                return recv.req()

        return data

    def _req(self, data, err=0) -> bytes:
        try:
            self._socket.sendall(data)
            return self._rcv()
        except (timeout, IOError):
            if err < 5:
                err += 1
                print(f'-- Try again: {err + 1} after {(err * err) * 0.1} sec')
                time.sleep((err * err) * 0.1)
                return self._req(data, err)
            return None

    def _json_req(self, prot: dict) -> prot_json_udp:
        r = prot_json_udp.resp(self._req(prot_json_udp(json=prot).req()))
        if r is not None:
            if 'devId' in r.json:
                self.dev_id = r.json['devId']
            if 'forwardId' in r.json:
                self.forward_id = r.json['forwardId']

        return r

    def _ap_req(self, prot: dict):
        return prot_ap.resp(self._req(prot_ap(content=prot).req()))

    def connect(self) -> prot_json_udp:
        return self._json_req({
            'code': cmd_udp.CODE_AP_CONNECT,
            'target': prot_json_udp.DEFAULT_DEV_TARGET,
            'token': prot_json_udp.DEFAULT_DEVICE_TOKEN,
            'unixTimer': int(datetime.timestamp(datetime.now()))
        })

    def baseinfo(self) -> prot_ap:
        return self._ap_req({
            'code': cmd_udp.CODE_FORWARD_DEV_BASE_INFO,
            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET,
            'unixTimer': int(datetime.timestamp(datetime.now()))
        })

    def ping(self) -> bool:
        self._socket.sendall(prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req())
        return len(self._socket.recv(1024)) > 0

    def sdcard_status(self) -> bool:
        r = self._ap_req({
            'code': cmd_udp.CODE_FORWARD_DEV_SDCARD_STATUS,
            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET
        })
        return r.content['sdDevStatus'] > 0 if r is not None else None

    def wifi_scan(self):
        return self._ap_req({
            'code': cmd_udp.CODE_FORWARD_DEV_WIFI_SCAN,
            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET
        })

    def sdcard_datelist(self) -> list:
        r = self._json_req({
            'code': cmd_udp.CODE_SDCARD_REQ_DATE_LIST,
            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET
        })

        if r is not None and 'dates' in r.json:
            return r.json['dates']
        return None

    @staticmethod
    def _parse_get_filenames(minBin):
        j = 1
        i = 0
        ret = []
        parseLong = minBin
        while (i < 64):
            if (j << i) & parseLong:
                ret.append(i)
            i += 1
            j = 1
        return ret

    def filename_list(self, date) -> tuple:
        ret = []
        r = self._json_req({
            'code': cmd_udp.CODE_SDCARD_REQ_CONFIG,
            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET,
            'date': date
        })

        if r is not None and 'status' in r.json and r.json['status'] == 200:
            xml = prot_xml_udp.resp(self._socket.recv(1024))

            if xml is not None and "video" in xml.xml and "catalogue" in xml.xml['video']:
                cat = xml.xml['video']['catalogue']
                if 'option' not in cat:
                    return []

                if int(cat['@hNumb']) > 1:  # as array
                    _hlist = cat['option']
                    for _hour in _hlist:
                        for _minute in v720_ap._parse_get_filenames(int(_hour['@minBin'])):
                            ret.append((int(_hour['@hours']), int(_minute)))

                elif int(cat['@hNumb']) == 1:  # as dict
                    _hour = cat['option']
                    for _minute in v720_ap._parse_get_filenames(int(_hour['@minBin'])):
                        ret.append((int(_hour['@hours']), int(_minute)))
        return tuple(ret)

    def avi_file_info(self, date: int, hours: int, minute: int) -> prot_json_udp:
        r = self._json_req({'code': cmd_udp.CODE_SDCARD_REQ_MEDIA_INFO,
                            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET,
                            'date': date,
                            'hours': hours,
                            'minute': minute
                            })
        return r.json if r is not None else None

    def start_stream(self, date: int, hours: int, minute: int, on_pkg_recv: callable = None) -> prot_json_udp:
        r = self._json_req({
            'code': cmd_udp.CODE_SDCARD_REQ_START_STREAM,
            'devTarget': prot_json_udp.DEFAULT_DEV_TARGET,
            'date': date,
            'hours': hours,
            'minute': minute,
        })
        if r is not None and 'status' in r.json and r.json['status'] == 200:
            ret = bytearray()
            heartbeat_cnt = 0
            while True:
                try:
                    _bf = self._rcv()
                    if _bf is not None and len(_bf) > 0:
                        pkg = prot_udp.resp(_bf)
                        if pkg is not None:
                            if on_pkg_recv is not None and callable(on_pkg_recv):
                                on_pkg_recv(pkg._pkg_id, pkg._len)

                            heartbeat_cnt = 0
                            ret.extend(pkg.payload)
                    else:
                        # print('--- bf is none')
                        break
                except timeout as ex:
                    # print('--- timeout: ', ex)
                    break
                except IOError:
                    # print('--- skip heartbit ')
                    heartbeat_cnt += 1
                    if heartbeat_cnt > 1:
                        break
            return (r.json, ret)

        return (r.json, None) if r is not None else None
