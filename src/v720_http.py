
from __future__ import annotations
from datetime import datetime
import email.utils
import random
import json

from queue import Queue, Empty
import socket
from log import log

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import netifaces
from netcl_udp import netcl_udp
from a9_live import PORT, WAV_HDR

TCP_PORT = PORT
HTTP_PORT = 80


class v720_http(log, SimpleHTTPRequestHandler):
    STATIC_DIR = 'static'
    protocol_version = 'HTTP/1.1'
    _dev_lst = {}
    _dev_hnds = {}

    @staticmethod
    def add_dev(dev):
        # if dev.id not in v720_http._dev_lst:
        v720_http._dev_lst[dev.id] = dev

    @staticmethod
    def rm_dev(dev):
        if dev.id in v720_http._dev_lst:
            del v720_http._dev_lst[dev.id]

    @staticmethod
    def serve_forever(_http_port=HTTP_PORT):
        try:
            with ThreadingHTTPServer(("", _http_port), v720_http) as httpd:
                httpd.socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    print('exiting..')
                    exit(0)
        except PermissionError:
            print(f'--- Can\'t open {_http_port} port due to system root permissions or maybe you have already running HTTP server?')
            print(f'--- if not try to use "sudo sysctl -w net.ipv4.ip_unprivileged_port_start={_http_port}"')
            exit(1)

    def __new__(cls, *args, **kwargs) -> v720_http:
        ret = super(v720_http, cls).__new__(cls)
        cls._dev_hnds["live"] = ret.__video_hnd
        cls._dev_hnds["video"] = ret.__video_hnd
        cls._dev_hnds["audio"] = ret.__audio_hnd
        cls._dev_hnds["snapshot"] = ret.__snapshot_hnd
        return ret

    def __init__(self, request, client_address, server) -> None:
        log.__init__(self, 'HTTP')
        try:
            SimpleHTTPRequestHandler.__init__(self, request, client_address, server, directory=v720_http.STATIC_DIR)
        except ConnectionResetError:
            self.err(f'Connection closed by peer @ ({self.client_address[0]})')

    def log_message(self, format: str, *args) -> None:
        self.info(format % args)

    def __dev_list(self):
        self.info(f'GET device list: {self.path}')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Connection', 'close')
        self.end_headers()
        _devs = []
        for _id in v720_http._dev_lst.keys():
            _dev = v720_http._dev_lst[_id]
            _devs.append({
                'host': _dev.host,
                'port': _dev.port,
                'uid': _id
            })
        self.wfile.write(json.dumps(_devs).encode('utf-8'))

    def __video_hnd(self, dev):

        q = Queue(16384) # 15kb * 1024 ~ 15mb per camera
        def _on_video_frame(dev, frame):
            if q.full():
                q.get()
            q.put(frame)

        dev.set_vframe_cb(_on_video_frame)
        try:
            self.warn(f'Live video request @ {dev.id} ({self.client_address[0]})')
            self.send_response(200)
            self.send_header('Connection', 'keep-alive')
            self.send_header('Age', 0)
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary="jpgboundary"')
            self.end_headers()
            dev.cap_live()
            while not self.wfile.closed:
                img = q.get(timeout=5)
                self.wfile.write(b"--jpgboundary\r\n")
                self.send_header('Content-type', 'image/jpeg')
                # self.send_header('Content-length', len(img))
                self.end_headers()
                self.wfile.write(img)
                self.wfile.write(b'\r\n')

        except Empty:
            self.err('Camera request timeout')
            self.send_response(502, f'Camera request timeout {dev.id}@{dev.host}:{dev.port}')
        except BrokenPipeError:
            self.err(f'Connection closed by peer @ {dev.id} ({self.client_address[0]})')
        finally:
            dev.unset_vframe_cb(_on_video_frame)
            dev.cap_stop()

        try:
            self.send_header('Content-length', 0)
            self.send_header('Connection', 'close')
            self.end_headers()
        except BrokenPipeError:
            self.err(f'Connection closed by peer @ {dev.id} ({self.client_address[0]})')

    def __audio_hnd(self, dev):
        q = Queue(16384)  # 15kb * 1024 ~ 15mb per camera

        def _on_audio_frame(dev, frame):
            if q.full():
                q.get()

            q.put(frame)

        dev.set_aframe_cb(_on_audio_frame)
        try:
            self.warn(f'Audio request @ {dev.id} ({self.client_address[0]})')
            self.send_response(200)
            self.send_header('Connection', 'close')
            self.send_header('Age', 0)
            self.send_header('icy-br',64)
            self.send_header('icy-pub',1)
            self.send_header('icy-audio-info','ice-samplerate=8000;ice-bitrate=64;ice-channels=1')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-type', 'audio/wav')
            self.end_headers()
            dev.cap_live()
            self.wfile.write(WAV_HDR)
            while not self.wfile.closed:
                frm = q.get(timeout=5)
                self.wfile.write(frm)

        except Empty:
            self.err('Camera request timeout')
            self.send_response(502, f'Camera request timeout {dev.id}@{dev.host}:{dev.port}')
        except BrokenPipeError:
            self.err(f'Connection closed by peer @ {dev.id} ({self.client_address[0]})')
        finally:
            dev.unset_aframe_cb(_on_audio_frame)
            dev.cap_stop()

        try:
            self.send_header('Content-length', 0)
            self.send_header('Connection', 'close')
            self.end_headers()
        except BrokenPipeError:
            self.err(
                f'Connection closed by peer @ {dev.id} ({self.client_address[0]})')

    def __snapshot_hnd(self, dev):
        self.warn(f'Snapshot request @ {dev.id} ({self.client_address[0]})')
        q = Queue(1)
        def _on_video_frame(dev, frame):
            if q.full():
                q.get()
            q.put(frame)

        dev.set_vframe_cb(_on_video_frame)
        try:
            dev.cap_live()
            img = q.get(timeout=5)
            self.send_response(200)
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Content-length', len(img))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(img)

        except Empty:
            self.err('Camera request timeout')
            self.send_response(502, f'Camera request timeout {dev.id}@{dev.host}:{dev.port}')
        except (BrokenPipeError, ConnectionResetError):
            self.err(f'Connection closed by peer @ {dev.id} ({self.client_address[0]})')
        finally:
            dev.unset_vframe_cb(_on_video_frame)
            dev.cap_stop()

    def do_GET(self):
        if self.path.startswith('/dev/list'):
            self.__dev_list()
        elif not self.path.startswith('/dev') or self.path.startswith('/app'):
            SimpleHTTPRequestHandler.do_GET(self)
        else:
            _path = self.path[1:].split('/')
            if len(_path) == 3 and \
                    _path[0] == 'dev' and \
                    _path[1] in v720_http._dev_lst:
                _cmd = _path[2]

                if _cmd in self._dev_hnds:
                    _dev = v720_http._dev_lst[_path[1]]
                    self._dev_hnds[_cmd](_dev)
            else:
                self.info(f'GET unknown path: {self.path}')
                self.send_error(404, 'Not found')

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
        elif self.path.startswith('/app/api/ApiSysDevices/a9bindingAppDevice'):
            ret = {"code": 200, "message": "OK", "data": None}
        elif self.path.startswith('/app/api/ApiServer/getA9ConfCheck'):
            uid = f'{random.randint(0,99999):05d}'
            p = self.path[len('/app/api/ApiServer/getA9ConfCheck?'):]
            for param in p.split('&'):
                if param.startswith('devicesCode'):
                    uid = param.split('=')[1]

            gws = netifaces.gateways()
            ret = {
                "code": 200,
                "message": "OK",
                "data": {
                    "tcpPort": TCP_PORT,
                    "uid": uid,
                    "isBind": "8",
                    "domain": "v720.naxclow.com",
                    "updateUrl": None,
                    "host": netcl_udp.get_ip(list(gws['default'].values())[0][0] if len(gws['default']) > 0 else '10.42.0.1', 80),
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
            self.err(f'Unknown POST query @ {self.path}')
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(b'Unknown POST request')


if __name__ == '__main__':
    try:
        with ThreadingHTTPServer(("", HTTP_PORT), v720_http) as httpd:
            httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print('exiting..')
                exit(0)
    except PermissionError:
        print(
            f'--- Can\'t open {HTTP_PORT} port due to system root permissions or maybe you have already running HTTP server?')
        print(
            f'--- if not try to use "sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80"')
