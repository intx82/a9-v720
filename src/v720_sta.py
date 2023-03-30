import logging
import threading
from datetime import datetime

from log import log

from netsrv import netsrv
from netsrv_tcp import netsrv_tcp
from netsrv_udp import netsrv_udp

import cmd_udp
from prot_udp import prot_udp
from prot_json_udp import prot_json_udp


class v720_sta(log):
    TCP_PORT = 6123
    UDP_PORT = 6123
    CLI_TG = '00112233445566778899aabbccddeeff'
    CLI_TKN = 'deadc0de'

    def __init__(self, tcp_conn: netsrv_tcp, udp_conn: netsrv_udp = None, videoframe_cb: callable = None, audioframe_cb: callable = None, init_done_cb: callable = None, disconnect_cb: callable = None) -> None:
        super().__init__(f'V720-STA@{id(self):x}')
        self._raw_hnd_lst = {
            f'{cmd_udp.P2P_UDP_CMD_JSON}': self.__json_hnd,
            f'{cmd_udp.P2P_UDP_CMD_HEARTBEAT}': self.__heartbeat_hnd,
            f'{cmd_udp.P2P_UDP_CMD_G711}': self.__on_audio_rcv_hnd,
            f'{cmd_udp.P2P_UDP_CMD_JPEG}': self.__on_mjpg_rcv_hnd,
        }

        self._json_hnd_lst = {
            f'{cmd_udp.CODE_2S_REGISTER_REQ}': self.__reg_req_hnd,
            f'{cmd_udp.CODE_D2S_NAT_RSP}': self.__nat_probe_hnd,
            f'{cmd_udp.CODE_C2S_UDP_REQ}': self.__udp_probe_hnd,
            f'{cmd_udp.CODE_D2C_PROBE_RSP}': self.__data_ch_probe_hnd,
            f'{cmd_udp.CODE_CMD_FORWARD}': self.__fwd_resp_hnd,
        }

        self._fwd_hnd_lst = {
            f'{cmd_udp.CODE_FORWARD_DEV_BASE_INFO}': self.__baseinfo_hnd,
            f'{cmd_udp.CODE_FORWARD_OPEN_A_OPEN_V}': self.__on_open_video,
            f'{cmd_udp.CODE_FORWARD_CLOSE_A_CLOSE_V}': self.__on_close_video,
        }

        self._vframe = bytearray()
        self._aframe = bytearray()
        self._frame_lst_mtx = threading.Lock()
        self._frame_lst = []

        self._cb_mtx = threading.Lock()
        self._vframe_cb = []
        if videoframe_cb is not None and callable(videoframe_cb):
            self._vframe_cb.append(videoframe_cb)

        self._aframe_cb = []
        if audioframe_cb is not None and callable(audioframe_cb):
            self._aframe_cb.append(audioframe_cb)

        self._init_done_cb = init_done_cb
        self._disconnect_cb = disconnect_cb

        self._uid = None
        self._data_ch_probed = False

        self._retrans_tmr = None
        self.set_tcp_conn(tcp_conn)
        if udp_conn is not None:
            self.set_udp_conn(udp_conn)
        else:
            self._udp = None

    @property
    def id(self):
        return self._uid

    @property
    def host(self):
        return self._tcp._host

    @property
    def port(self):
        return self._tcp._port

    def set_tcp_conn(self, tcp_conn: netsrv_tcp):
        self._tcp = tcp_conn
        self._tcpth = threading.Thread(
            target=self.__tcp_hnd, name=f'{tcp_conn}')
        self._tcpth.setDaemon(True)
        self._tcpth.start()

    def set_udp_conn(self, udp_conn: netsrv_udp):
        self._udp = udp_conn
        self._udpth = threading.Thread(
            target=self.__udp_hnd, name=f'{udp_conn}')
        self._udpth.setDaemon(True)
        self._udpth.start()

    def set_vframe_cb(self, cb: callable):
        if cb is not None and callable(cb):
            with self._cb_mtx:
                self._vframe_cb.append(cb)

    def unset_vframe_cb(self, cb):
        if cb in self._vframe_cb:
            with self._cb_mtx:
                self._vframe_cb.remove(cb)

    def set_aframe_cb(self, cb: callable):
        if cb is not None and callable(cb):
            with self._cb_mtx:
                self._aframe_cb.append(cb)

    def unset_aframe_cb(self, cb):
        if cb in self._aframe_cb:
            with self._cb_mtx:
                self._aframe_cb.remove(cb)

    def set_init_done_cb(self, cb: callable):
        if cb is not None and callable(cb):
            self._init_done_cb = cb
        else:
            self._init_done_cb = None

    def set_disconnect_cb(self, cb: callable):
        if cb is not None and callable(cb):
            self._disconnect_cb = cb
        else:
            self._disconnect_cb = None

    def __tcp_hnd(self):
        while not self._tcp.is_closed:
            self.__on_tcp_rcv(self._tcp.recv())
        
        if self._udp is not None:
            self._udp.close()

        if self._disconnect_cb is not None and callable(self._disconnect_cb):
            self._disconnect_cb(self)

    def __on_tcp_rcv(self, data: bytes):
        if data is None or len(data) == 0:
            return

        req = prot_udp.resp(data)
        self.dbg(f'Request (TCP): {req.__repr__()}')

        if f'{req.cmd}' in self._raw_hnd_lst:
            self._raw_hnd_lst[f'{req.cmd}'](self._tcp, data)
        else:
            self.warn(f'Unknown request {req}')

    def __udp_hnd(self):
        while not self._udp.is_closed:
            self.__on_udp_rcv(self._udp.recv())

    def __on_udp_rcv(self, data):
        req = prot_udp.resp(data)
        self.dbg(f'Request (UDP): {req.__repr__()}')

        if f'{req.cmd}' in self._raw_hnd_lst:
            self._raw_hnd_lst[f'{req.cmd}'](self._udp, data)
        else:
            self.warn(f'Unknown request {req}')

    def __json_hnd(self, conn: netsrv, payload: bytes):
        pkg = prot_json_udp.resp(payload)
        if f'{pkg.json["code"]}' in self._json_hnd_lst:
            self.dbg(f'Receive JSON: {pkg}')
            self._json_hnd_lst[f'{pkg.json["code"]}'](conn, pkg)
        else:
            self.warn(f'Receive unknown JSON: {pkg}')

    def __fwd_resp_hnd(self, conn: netsrv, pkg: prot_json_udp):
        cmd = pkg.json['content']['code']

        if f'{cmd}' in self._fwd_hnd_lst:
            self._fwd_hnd_lst[f'{cmd}'](conn, pkg)
        else:
            self.warn(f'Receive unknown FWD: {pkg}')

    def __heartbeat_hnd(self, conn: netsrv, payload: bytes):
        self.info('Heartbeat received, sending heartbeat response')
        conn.send(prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req())

    def __reg_req_hnd(self, conn: netsrv_tcp, pkg: prot_json_udp):
        self._uid = pkg.json["uid"]
        self.info(f'Receive registration request (device: {self._uid})')
        resp = prot_json_udp(json={
            'code': cmd_udp.CODE_S2_REGISTER_RSP,
            'status': 200
        })
        self.dbg(f'send registration response: {resp}')
        conn.send(resp.req())
        # self.__send_nat_probe(conn)
        if self._init_done_cb is not None and callable(self._init_done_cb):
            self._init_done_cb(self)

    def __send_nat_probe(self, conn: netsrv_tcp):
        self.info(f'Sending NAT probe request')
        req = prot_json_udp(json={
            'code': cmd_udp.CODE_S2D_NAT_REQ,
            'cliTarget': self.CLI_TG,
            'cliToken': self.CLI_TKN,
            'cliIp': '255.255.255.255',  # make it unaccessible from anywhere
            'cliPort': 0,
            'cliNatIp': '255.255.255.255',
            'cliNatPort': 0
        })
        self.dbg(f'NAT probe request: {req}')
        conn.send(req.req())

    def __udp_probe_hnd(self, conn: netsrv_udp, pkg: prot_json_udp):
        self.info('Found UDP probing, sending response')
        resp = prot_json_udp(json={
            'code': cmd_udp.CODE_S2C_UDP_RSP,
            'ip': '255.255.255.255',  # make it unaccessible from anywhere
            'port': 0
        })
        self.dbg(f'UDP probing response: {resp}')
        conn.send(resp.req())
        self._data_ch_probed = False

    def __nat_probe_hnd(self, conn: netsrv_tcp, pkg: prot_json_udp):
        self.info(f'Receive NAT probation status {pkg}')

    def __data_ch_probe_hnd(self, conn: netsrv_udp, pkg: prot_json_udp):
        if not self._data_ch_probed:
            self.info(f'Device probing data channel, probe again')
            resp = prot_json_udp(json={
                'code': cmd_udp.CODE_C2D_PROBE_REQ,
            })
            self._data_ch_probed = True
            self.dbg(f'Data-channel probing response: {resp}')
            conn.send(resp.req())
        else:
            self.info(f'Device probing done')
            self.__initial_sequence()

    @staticmethod
    def __prep_fwd(content: dict) -> prot_json_udp:
        return prot_json_udp(json={
            'code': cmd_udp.CODE_CMD_FORWARD,
            'target':  v720_sta.CLI_TG,
            'content': content
        })

    def __initial_sequence(self):
        self.info(f'Sending initial sequence')
        resp = prot_json_udp(json={
            'code': cmd_udp.CODE_S2_DEVICE_STATUS,
            'status': 1
        })
        self.dbg(f'Updating device status: {resp}')
        self._tcp.send(resp.req())

        resp = self.__prep_fwd({
            'code': cmd_udp.CODE_RETRANSMISSION
        })
        self.dbg(f'Send forward-retransmission command: {resp}')
        self._tcp.send(resp.req())

        resp = self.__prep_fwd({
            'unixTimer': int(datetime.timestamp(datetime.now())),
            'code': cmd_udp.CODE_FORWARD_DEV_BASE_INFO
        })
        self.dbg(f'Send baseinfo command: {resp}')
        self._tcp.send(resp.req())

    def __baseinfo_hnd(self, conn: netsrv_tcp, pkg: prot_json_udp):
        self.info(f'Found device, starting video-streaming')
        self.__start_live()

    def __start_live(self):
        resp = self.__prep_fwd({
            'code': cmd_udp.CODE_FORWARD_OPEN_A_OPEN_V
        })
        self.dbg(f'Send open_video/open_audio command: {resp}')
        self._tcp.send(resp.req())
        self._first_retrans_send = False
        if self._retrans_tmr:
            self._retrans_tmr.cancel()
            self._retrans_tmr = None

    def cap_live(self):
        self.__send_nat_probe(self._tcp)

    def cap_stop(self):
        with self._cb_mtx:
            if len(self._vframe_cb) > 1:
                self.warn(f'Client still conected')
                return

        resp = self.__prep_fwd({
            'code': cmd_udp.CODE_FORWARD_CLOSE_A_CLOSE_V
        })
        self.dbg(f'Send stop streaming (close_video/close_audio) {resp}')
        self._tcp.send(resp.req())
        self._first_retrans_send = False
        if self._retrans_tmr:
            self._retrans_tmr.cancel()
            self._retrans_tmr = None

    def __on_open_video(self, conn: netsrv_tcp, pkg: prot_json_udp):
        self.warn(f'Starting video streaming')

    def __on_close_video(self, conn: netsrv_tcp, pkg: prot_json_udp):
        self.warn(f'Video streaming has been stopped')
        if self._retrans_tmr:
            self._retrans_tmr.cancel()
            self._first_retrans_send = False

    def __rtr_tmr_hnd(self):
        if self._retrans_tmr:
            self._retrans_tmr.cancel()

        if self._first_retrans_send:
            self._retrans_tmr = threading.Timer(0.1, self.__rtr_tmr_hnd)
            self._retrans_tmr.setDaemon(True)
            self._retrans_tmr.setName(f'retrans-tmr@{self._tcp._host}:{self._tcp._port}')
            self._retrans_tmr.start()
            self.__retransmission_confirm()

    def __retransmission_confirm(self, sent_empty=False):
        pkg = prot_udp(b'', cmd_udp.P2P_UDP_CMD_RETRANSMISSION_CONFIRM)

        if not sent_empty:
            frm_lst = bytearray()
            with self._frame_lst_mtx:
                for fl in self._frame_lst:
                    frm_lst.extend(int.to_bytes(fl, 4, 'little'))
                self._frame_lst.clear()
            pkg.payload = frm_lst

        self.dbg('Send empty P2P_UDP_CMD_RETRANSMISSION_CONFIRM')
        self._udp.send(pkg.req())

    def __on_audio_rcv_hnd(self, conn: netsrv_udp, payload: bytes):
        pkg = prot_udp.resp(payload)
        with self._frame_lst_mtx:
            self._frame_lst.append(pkg._pkg_id)

        if pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_HEAD:
            self._aframe = bytearray()
            self._aframe.extend(pkg.payload)
        elif pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_BODY:
            self._aframe.extend(pkg.payload)
        elif pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_END:
            self._aframe.extend(pkg.payload)
            with self._cb_mtx:
                for cb in self._aframe_cb:
                    cb(self, self._aframe)

        elif pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_FINISH:
            self.dbg('Receive G711 frame')
            with self._cb_mtx:
                for cb in self._aframe_cb:
                    cb(self, self._aframe)

    def __on_mjpg_rcv_hnd(self, conn: netsrv_udp, payload: bytes):
        pkg = prot_udp.resp(payload)
        with self._frame_lst_mtx:
            self._frame_lst.append(pkg._pkg_id)

        if pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_HEAD \
                or pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_FINISH:

            self._vframe = bytearray()
            self._vframe.extend(pkg.payload)
        elif pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_BODY:
            self._vframe.extend(pkg.payload)
        elif pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_END:
            self._vframe.extend(pkg.payload[:-5])
            sz = int.from_bytes(pkg.payload[-4:], byteorder='little')
            self.dbg(f'Receive H264 frame sz: ({sz} <> {len(self._vframe)})')

            with self._cb_mtx:
                for cb in self._vframe_cb:
                    cb(self, self._vframe)

            if not self._first_retrans_send:
                self.__retransmission_confirm(sent_empty=True)
                self._first_retrans_send = True
                self.__rtr_tmr_hnd()

        elif pkg.msg_flag == cmd_udp.PROTOCOL_MSG_FLAG_FINISH:
            self.dbg(f'Receive single H264 frame')
            with self._cb_mtx:
                for cb in self._vframe_cb:
                    cb(self, pkg.payload)


def start_srv():
    from v720_http import v720_http

    devices = []
    _mtx = threading.Lock()

    def on_init_done(dev: v720_sta):
        print(f'''-------- Found device {dev.id} --------
\033[92mLive capture: http://127.0.0.1/dev/{dev.id}/live
Snapshot: http://127.0.0.1/dev/{dev.id}/snapshot\033[0m
''')
        v720_http.add_dev(dev)

    def on_disconnect_dev(dev: v720_sta):
        if dev in devices:
            print(f'\033[31m-------- Device {dev.id} has been disconnected --------\033[0m')
            devices.remove(dev)
            v720_http.rm_dev(dev)
        else:
            print('Unknown dev')

    def tcp_thread():
        with netsrv_tcp('', v720_sta.TCP_PORT) as _tcp:
            while True:
                _tcp.open()
                fork = _tcp.fork()
                if fork is not None:
                    with _mtx:
                        dev = v720_sta(fork, init_done_cb=on_init_done, disconnect_cb=on_disconnect_dev)
                        devices.append(dev)

    def udp_thread():
        with netsrv_udp('', v720_sta.UDP_PORT) as _udp:
            while True:
                _udp.open()
                fork = _udp.fork()
                if fork is not None:
                    dev_found = False
                    with _mtx:
                        for dev in devices:
                            if dev.host == fork._host:
                                dev.set_udp_conn(fork)
                                dev_found = True
                                break

                    if not dev_found:
                        fork.info('Device for connection is not found')

    http_th = threading.Thread(target=v720_http.serve_forever, name='HTTP-SRV')
    http_th.setDaemon(True)
    http_th.start()

    tcp_th = threading.Thread(target=tcp_thread, name='TCP-SRV')
    tcp_th.setDaemon(True)
    tcp_th.start()

    udp_th = threading.Thread(target=udp_thread, name='UDP-SRV')
    udp_th.setDaemon(True)
    udp_th.start()

    tcp_th.join()


if __name__ == '__main__':
    start_srv()
