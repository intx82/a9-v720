from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import threading
from prot_udp import prot_udp
from prot_json_udp import prot_json_udp
from prot_ap import prot_ap
import cmd_udp
import time

HTTP_PORT = 80


class S(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_POST(self):
        print('REQ:', self.path)
        if self.path.startswith('/app/api/ApiSysDevicesBatch/registerDevices'):
            self.close_connection = False
            resp = 'HTTP/1.1 200\r\nServer: nginx/1.14.0 (Ubuntu)\r\nDate: Fri, 10 Feb 2023 21:43:40 GMT\r\nContent-Type: application/json\r\nContent-Length: 59\r\nConnection: keep-alive\r\n\r\n{"code":200,"message":"操作成功","data":"0800c00128F8"}'
            print(resp)
            self.wfile.write(resp.encode('utf-8'))
        elif self.path.startswith('/app/api/ApiServer/getA9ConfCheck'):
            resp = 'HTTP/1.1 200\r\nServer: nginx/1.14.0 (Ubuntu)\r\nDate: Fri, 10 Feb 2023 22:29:57 GMT\r\nContent-Type: application/json\r\nContent-Length: 215\r\nConnection: keep-alive\r\n\r\n{"code":200,"message":"操作成功","data":{"tcpPort":6123,"uid":"0800c00128F8","isBind":"8","domain":"v720.naxclow.com","updateUrl":null,"host":"10.42.0.1","currTime":"1676097689","pwd":"91edf41f","version":null}}'
            print(resp)
            self.wfile.write(resp.encode('utf-8'))


def tcp_thread(arg):
    try:
        tkn = None
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _socket.bind(('10.42.0.1', 6123))
        _socket.listen()
        conn, addr = _socket.accept()
        with conn:
            print(f"Connected by {addr}")
            while True:
                _payload = conn.recv(1024)
                if not _payload:
                    continue

                _pkt = prot_udp.resp(_payload)
                print(f'Recv [{len(_payload)}]: {_pkt.cmd}')
                if _pkt.cmd == 0:
                    _pkt = prot_json_udp.resp(_payload)
                    if _pkt.json['code'] == 100:
                        print(f'Found device: {_pkt.json["uid"]} token: {_pkt.json["token"]}')
                        tkn = _pkt.json["token"]
                        resp = {'code': 101, 'status': 200}
                        print(f'Send respone as OK: {resp}')
                        conn.sendall(prot_json_udp(json=resp).req())
                        time.sleep(1)
                        resp = prot_json_udp(json={'code': 52, "status": 1, "token": tkn})
                        # resp._forward_id = bytes.fromhex('0800c00128F8')
                        print(f'Send respone as OK: {resp}')
                        conn.sendall(resp.req())

                if _pkt.cmd == 100:
                    print('Heartbeat, sending response')
                    conn.sendall(
                        prot_udp(cmd=cmd_udp.P2P_UDP_CMD_HEARTBEAT).req())
    except Exception as ex:
        print(ex)
    finally:
        _socket.close()
        exit(1)


def start():
    tt = threading.Thread(target=tcp_thread, args=(1,))
    tt.setDaemon(True)
    tt.start()
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
