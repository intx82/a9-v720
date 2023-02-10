from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import json

PORT=80


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
            resp = 'HTTP/1.1 200\r\nServer: nginx/1.14.0 (Ubuntu)\r\nDate: Fri, 10 Feb 2023 22:29:57 GMT\r\nContent-Type: application/json\r\nContent-Length: 216\r\nConnection: keep-alive\r\n\r\n{"code":200,"message":"操作成功","data":{"tcpPort":29940,"uid":"0800c00128F8","isBind":"8","domain":"v720.naxclow.com","updateUrl":null,"host":"10.42.0.1","currTime":"1676097689","pwd":"91edf41f","version":null}}'
            print(resp)
            self.wfile.write(resp.encode('utf-8'))



def start():
    with HTTPServer(("",PORT), S) as httpd:
        httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        print('running..')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('exiting..')
            exit(0)


if __name__ == '__main__':
    start()
