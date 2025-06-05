#!/usr/bin/env python3
import argparse
from a9_naxclow import send_ap_wifi_credentials
from netcl_tcp import netcl_tcp
from v720_ap import v720_ap
from v720_sta import start_srv
import cmd_udp


def pair_camera(args):
    send_ap_wifi_credentials(args.ip, args.ssid, args.password, args.wifi_port)


def http_server(args):
    start_srv(args.port)


def capture_frame(args):
    host = args.ip
    port = args.camera_port
    out = args.output
    frame = bytearray()
    sync = False

    def on_rcv(cmd, data):
        nonlocal sync, frame
        if cmd == cmd_udp.P2P_UDP_CMD_JPEG:
            if not sync:
                idx = data.find(b"\xff\xd8")
                if idx != -1:
                    frame.extend(data[idx:])
                    sync = True
            else:
                idx = data.find(b"\xff\xd9")
                if idx != -1:
                    frame.extend(data[:idx+2])
                    raise StopIteration
                else:
                    frame.extend(data)

    try:
        with netcl_tcp(host, port) as sock:
            cam = v720_ap(sock)
            cam.init_live_motion()
            cam.cap_live(on_rcv)
    except StopIteration:
        with open(out, 'wb') as f:
            f.write(frame)
        print(f"Frame saved to {out}")


def main():
    parser = argparse.ArgumentParser(description="Utilities similar to cam-reverse")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("http_server", help="start HTTP server")
    sp.add_argument("--port", type=int, default=80)
    sp.set_defaults(func=http_server)

    sp = sub.add_parser("pair", help="configure camera Wi-Fi")
    sp.add_argument("--ip", default="192.168.169.1")
    sp.add_argument("--ssid", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--wifi-port", type=int, default=8090)
    sp.set_defaults(func=pair_camera)

    sp = sub.add_parser("frame", help="capture single frame")
    sp.add_argument("--ip", default="192.168.169.1")
    sp.add_argument("--camera-port", type=int, default=6123)
    sp.add_argument("--output", required=True)
    sp.set_defaults(func=capture_frame)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
