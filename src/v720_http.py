
from datetime import datetime
import email.utils
import random
import json
import socket
from log import log

from http.server import BaseHTTPRequestHandler, HTTPServer
from a9_live import PORT

TCP_PORT = PORT
HTTP_PORT = 80

class v720_http(log, BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    @staticmethod
    def serve_forever():
        try:
            with HTTPServer(("", HTTP_PORT), v720_http) as httpd:
                httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    print('exiting..')
                    exit(0)
        except PermissionError:
            print(f'--- Can\'t open {HTTP_PORT} port due to system root permissions or maybe you have already running HTTP server?')
            print(f'--- if not try to use "sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80"')
            exit(1)


    def __init__(self, request, client_address, server) -> None:
        log.__init__(self, 'HTTP')
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)


    def log_message(self, format: str, *args) -> None:
        self.info(format % args)

    def do_POST(self):
        ret = None
        hdr = [
            'HTTP/1.1 200',
            'Server: nginx/1.14.0 (Ubuntu)',
            f'Date: {email.utils.format_datetime(datetime.now())}',
            'Content-Type: application/json',
            'Connection: keep-alive',
        ]
        self.info(f'POST {self.path}')
        if self.path.startswith('/app/api/ApiSysDevicesBatch/registerDevices'):
            ret = {"code": 200, "message": "OK",
                    "data": f"0800c00{random.randint(0,99999):05d}"}
        elif self.path.startswith('/app/api/ApiSysDevicesBatch/confirm'):
            ret = {"code": 200, "message": "OK", "data": None}

        elif self.path.startswith('/app/api/ApiServer/getA9ConfCheck'):
            uid = f'{random.randint(0,99999):05d}'
            p = self.path[len('/app/api/ApiServer/getA9ConfCheck?'):]
            for param in p.split('&'):
                if param.startswith('devicesCode'):
                    uid = param.split('=')[1]

            ret = {
                "code": 200, 
                "message": "OK",
                "data": {
                    "tcpPort": TCP_PORT,
                    "uid": uid,
                    "isBind": "8",
                    "domain": "v720.naxclow.com",
                    "updateUrl": None,
                    "host": "10.42.0.1", 
                    "currTime": f'{int(datetime.timestamp(datetime.now()))}', 
                    "pwd": "deadbeef", 
                    "version": None
                    }
                }
            
        if ret is not None:
            ret = json.dumps(ret)
            hdr.append(f'Content-Length: {len(ret)}')
            hdr.append('\r\n')
            hdr.append(ret)
            resp = '\r\n'.join(hdr)
            self.info(f'sending: {resp}')
            self.wfile.write(resp.encode('utf-8'))
        else:
            self.error(f'Unknown POST query @ {self.path}')


if __name__ == '__main__':
    try:
        with HTTPServer(("", HTTP_PORT), v720_http) as httpd:
            httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print('exiting..')
                exit(0)
    except PermissionError:
        print(f'--- Can\'t open {HTTP_PORT} port due to system root permissions or maybe you have already running HTTP server?')
        print(f'--- if not try to use "sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80"')

