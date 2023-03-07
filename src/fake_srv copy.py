from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import threading
from prot_udp import prot_udp
from prot_json_udp import prot_json_udp
from prot_ap import prot_ap
import cmd_udp
from datetime import datetime
from v720_http import v720_http

HTTP_PORT = 80

FSM_NONE = '-'
FSM_HEARBEAT = 'hearbeat'
FSM_INITIAL = 'initial'
FSM_GET_STATUS = 'get_status'
FSM_SET_NAT = 'set_nat'
FSM_ONLINE = 'online'
FSM_SET_TIMESTAMP = 'timestamp'
FSM_RETRANS = 'retrans'
FSM_BASEINFO = 'baseinfo'
FSM_CAPLIVE = 'caplive'
FSM_POSTCAP = 'postcap'


def fsm_heartbeat(conn: socket, _: bytes):
    print('[TCP] Heartbeat, sending response')
    conn.sendall(prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req())

def fsm_initial(conn: socket, _payload: bytes):
    if _payload is None:
        return

    _pkt = prot_json_udp.resp(_payload)
    print(
        f'[TCP] Found device: {_pkt.json["uid"]} token: {_pkt.json["token"]}')
    FSM['data']['dev_tkn'] = _pkt.json["token"]
    FSM['data']['dev_tg'] = _pkt.json["uid"]
    resp = {'code': cmd_udp.CODE_S2_REGISTER_RSP, 'status': 200}
    print(f'[TCP] Send respone as OK: {resp}')
    conn.sendall(prot_json_udp(json=resp).req())


def fsm_set_nat(conn: socket, _: bytes):
    resp = {
        'code': cmd_udp.CODE_S2D_NAT_REQ,
        'cliTarget': FSM['data']['cli_tg'],
        'cliToken': FSM['data']['cli_tkn'],
        'cliIp': '10.42.0.1',  # it will send there to achive it from `cliNatIp:cliNatPort`
        'cliPort': 53221,
        'cliNatIp': '10.42.0.1',
        'cliNatPort': 41234
    }
    print(f'[TCP] Send status req: {resp}')
    conn.sendall(prot_json_udp(json=resp).req())


def fsm_get_status(conn: socket, to):
    resp = {'code': cmd_udp.CODE_S2_DEVICE_STATUS,
            'status': 1}
    print(f'[TCP] Send status req: {resp}')
    conn.sendall(prot_json_udp(json=resp).req())


def fsm_udp_get_status(conn: socket, to):
    req = {'code': cmd_udp.CODE_S2_DEVICE_STATUS,
           'status': 1}

    print(f'[UDP] Send status req: {req}')
    conn.sendto(prot_json_udp(json=req).req(), to)


def fsm_udp_req(conn: socket, to):
    resp = {'code': cmd_udp.CODE_S2C_UDP_RSP,
            'ip': "10.42.0.1", "port": 53221}
    print(f'[UDP] Send UDP response: {resp}')
    conn.sendto(prot_json_udp(json=resp).req(), to)


def fsm_probe_req(conn: socket, to):
    req = {'code': cmd_udp.CODE_C2D_PROBE_REQ,
           #           'cliToken': FSM['data']['cli_tkn'],
           #           'devTarget': FSM['data']['dev_tg'],
           #           'cliId': FSM['data']['cli_tg'],
           #           'devToken': FSM['data']['dev_tkn']
           }

    print(f'[UDP] Send status req: {req}')
    conn.sendto(prot_json_udp(json=req).req(), to)


def fsm_retrans(conn: socket, _):
    req = {'code': cmd_udp.CODE_CMD_FORWARD,
           'target':  FSM['data']['cli_tg'],
           'content': {
               'code': cmd_udp.CODE_RETRANSMISSION
           }}

    print(f'[TCP] Send retransmission req: {req}')
    conn.sendall(prot_json_udp(json=req).req())


def fsm_caplive(conn: socket, _):
    req = {'code': cmd_udp.CODE_CMD_FORWARD,
           'target': FSM['data']['cli_tg'],
           'content': {
               'code': cmd_udp.CODE_FORWARD_OPEN_A_OPEN_V
           }}

    print(f'[TCP] Send caplive req: {req}')
    conn.sendall(prot_json_udp(json=req).req())

def fsm_postcap(conn: socket, _):
    FSM['data']['connected'] = True

def fsm_baseinfo(conn: socket, _):
    req = {'code': cmd_udp.CODE_CMD_FORWARD,
           'target':  FSM['data']['cli_tg'],
           'content': {
               'unixTimer': int(datetime.timestamp(datetime.now())),
               'code': cmd_udp.CODE_FORWARD_DEV_BASE_INFO
           }}

    print(f'[TCP] Send baseinfo req: {req}')
    conn.sendall(prot_json_udp(json=req).req())


FSM = {
    'states': {
        FSM_NONE: [[None, None, None], None, FSM_NONE],
        FSM_HEARBEAT: [[100, None, None], fsm_heartbeat, FSM_NONE],
        FSM_INITIAL: [[0, 100, None], fsm_initial, FSM_SET_NAT],
        FSM_SET_NAT: [[None, None, None], fsm_set_nat, FSM_NONE],
        FSM_GET_STATUS: [[None, None, None], fsm_get_status, FSM_RETRANS],
        FSM_RETRANS: [[None, None, None], fsm_retrans, FSM_BASEINFO],
        FSM_BASEINFO: [[None, None, None], fsm_baseinfo, FSM_NONE],
        FSM_CAPLIVE: [[0, 301, 4], fsm_caplive, None],
        FSM_CAPLIVE: [[0, 301, 3], fsm_postcap, FSM_NONE],
    },
    'step': FSM_NONE,
    'data': {
        'dev_tkn': None,
        'dev_tg': None,
        'cli_tg': '00112233445566778899aabbccddeeff',
        'cli_tkn': '55ABfb77',
        'connected': False
    }
}


def fsm_udp_timestamp(conn: socket, to):
    req = {'code': cmd_udp.CODE_C2D_TIMESTAMP,
           'timeStamp': f'{int(datetime.timestamp(datetime.now())) * 1000}'}

    print(f'[UDP] Send timestamp req: {req}')
    conn.sendto(prot_json_udp(json=req).req(), to)


def udp_ping(conn: socket, to):
    conn.sendto(prot_udp(cmd=cmd_udp.P2P_UDP_CMD_PING).req(), to)


class S(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_POST(self):
        print('REQ:', self.path)
        if self.path.startswith('/app/api/ApiSysDevicesBatch/registerDevices'):
            self.close_connection = False
            resp = 'HTTP/1.1 200\r\nServer: nginx/1.14.0 (Ubuntu)\r\nDate: Fri, 10 Feb 2023 21:43:40 GMT\r\nContent-Type: application/json\r\nContent-Length: 59\r\nConnection: keep-alive\r\n\r\n{"code":200,"message":"操作成功","data":"0800c0012345"}'
            print(resp)
            self.wfile.write(resp.encode('utf-8'))
        if self.path.startswith('/app/api/ApiSysDevicesBatch/confirm'):
            self.close_connection = False
            resp = 'HTTP/1.1 200\r\nServer: nginx/1.14.0 (Ubuntu)\r\nDate: Fri, 10 Feb 2023 21:43:40 GMT\r\nContent-Type: application/json\r\nContent-Length: 59\r\nConnection: keep-alive\r\n\r\n{"code":200,"message":"操作成功","data": null}'
            print(resp)
            self.wfile.write(resp.encode('utf-8'))
        elif self.path.startswith('/app/api/ApiServer/getA9ConfCheck'):
            resp = 'HTTP/1.1 200\r\nServer: nginx/1.14.0 (Ubuntu)\r\nDate: Fri, 10 Feb 2023 22:29:57 GMT\r\nContent-Type: application/json\r\nContent-Length: 215\r\nConnection: keep-alive\r\n\r\n{"code":200,"message":"操作成功","data":{"tcpPort":6123,"uid":"0800c00128F8","isBind":"8","domain":"v720.naxclow.com","updateUrl":null,"host":"10.42.0.1","currTime":"1676097689","pwd":"91edf41f","version":null}}'
            print(resp)
            self.wfile.write(resp.encode('utf-8'))


def tcp_thread(arg):
    try:
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _socket.bind(('10.42.0.1', 6123))
        _socket.listen()

        conn, addr = _socket.accept()
        with conn:
            print(f"[TCP] Connected by {addr}")
            conn.settimeout(1.0)
            while True:
                try:
                    _payload = conn.recv(1024)
                    if not _payload or len(_payload) == 0:
                        break
                    _pkt = prot_udp.resp(_payload)

                    if _pkt.cmd is None:
                        continue

                    for state in FSM['states'].items():
                        exp_cmd = state[1][0]
                        cb = state[1][1]
                        next_step = state[1][2]

                        if exp_cmd[0] == _pkt.cmd and cb is not None and callable(cb):
                            if _pkt.cmd == 0:
                                _pkt = prot_json_udp.resp(_payload)
                                print(
                                    f'[TCP] JSON recv: [{len(_payload)}]: {_pkt}')
                                if exp_cmd[1] == _pkt.json['code']:
                                    if _pkt.json['code'] == 301:
                                        _pkt = prot_ap.resp(_payload)
                                        if _pkt.content['code'] == exp_cmd[2]:
                                            cb(conn, _payload)
                                            FSM['step'] = next_step
                                            print('Next step @ rcv:',
                                                  FSM['step'])
                                            break
                                    else:
                                        cb(conn, _payload)
                                        FSM['step'] = next_step
                                        print('Next step @ rcv:', FSM['step'])
                                        break

                            else:
                                print(
                                    f'[TCP] Recv [{len(_payload)}]: {_pkt.cmd}')
                                cb(conn, _payload)
                                FSM['step'] = next_step
                                print('Next step @ rcv:', FSM['step'])
                                break
                except socket.timeout:
                    pass

                while FSM['step'] != FSM_NONE:
                    print('Curr step:', FSM['step'])
                    FSM['states'][FSM['step']][1](conn, None)
                    FSM['step'] = FSM['states'][FSM['step']][2]
                    print('Next step @ fsm1:', FSM['step'])

    except Exception as ex:
        print(ex)
    finally:
        _socket.close()
        exit(1)


def srv_udp_thread(arg):
    global send_online
    _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _socket.bind(('10.42.0.1', 6123))
    rmt = None
    probe = True
    while True:
        try:
            _socket.settimeout(1.0)
            _payload, _to = _socket.recvfrom(1024)
            rmt = _to
            if not _payload or len(_payload) == 0:
                break

            _pkt = prot_udp.resp(_payload)

            if _pkt.cmd is None:
                continue

            if _pkt.cmd == cmd_udp.P2P_UDP_CMD_HEARTBEAT:
                print('[UDP-SRV] Heartbeat, sending response')
                _socket.sendto(
                    prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req(), _to)
            elif _pkt.cmd == cmd_udp.P2P_UDP_CMD_JSON:
                _pkt = prot_json_udp.resp(_payload)
                print(f'[UDP-SRV] JSON recv: [{len(_payload)}]: {_pkt}')
                if _pkt.json['code'] == cmd_udp.CODE_C2S_UDP_REQ:
                    fsm_udp_req(_socket, _to)
                elif _pkt.json['code'] == cmd_udp.CODE_D2C_PROBE_RSP:
                    if probe:
                        fsm_probe_req(_socket, _to)
                        probe = False
                    else:
                        FSM['step'] = FSM_GET_STATUS

        except socket.timeout:
            pass


# def cl_udp_thread(arg):
#     global send_online
#     probe = 2

#     _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#     _socket.bind(('10.42.0.1', 53221))
#     while True:
#         _payload, _to = _socket.recvfrom(1024)
#         if not _payload or len(_payload) == 0:
#             break

#         _pkt = prot_udp.resp(_payload)

#         if _pkt.cmd is None:
#             continue

#         _pkt = prot_udp.resp(_payload)
#         if _pkt.cmd == 0:
#             _pkt = prot_json_udp.resp(_payload)
#             print(f'[UDP-CLI] JSON recv: [{len(_payload)}]: {_pkt}')

#             if _pkt.json['code'] == cmd_udp.CODE_D2C_PROBE_RSP:
#                 print(f'[UDP-CLI] JSON recv: [{len(_payload)}]: {_pkt}')
#                 if probe:
#                     fsm_probe_req(_socket, _to)
#                     probe -= 1
#                 else:
#                     fsm_udp_retrans(_socket, _to)
#                     # fsm_udp_timestamp(_socket, _to)
#                     # _socket.sendto(prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req(), _to)
#                     send_online = True
#                     # FSM['step'] = FSM_GET_STATUS

#         elif _pkt.cmd == cmd_udp.P2P_UDP_CMD_HEARTBEAT:
#             print('[UDP] Heartbeat, sending response')
#             _socket.sendto(
#                 prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req(), _to)
#         else:
#             print(f'[UDP] Recv [{len(_payload)}]: {_pkt.cmd}')


def start():
    tt = threading.Thread(target=tcp_thread, args=(1,))
    tt.setDaemon(True)
    tt.start()
    tu = threading.Thread(target=srv_udp_thread, args=(1,))
    tu.setDaemon(True)
    tu.start()

    # tu2 = threading.Thread(target=cl_udp_thread, args=(1,))
    # tu2.setDaemon(True)
    # tu2.start()

    with HTTPServer(("", HTTP_PORT), S) as httpd:
        httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        print('running..')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('exiting..')
            exit(0)


if __name__ == '__main__':
    start()
