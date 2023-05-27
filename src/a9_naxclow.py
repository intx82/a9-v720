#!/usr/bin/env python3

from netcl_tcp import netcl_tcp
import time
import argparse
from datetime import datetime
from tqdm.auto import tqdm
from log import log
import logging

from v720_ap import v720_ap
from v720_sta import start_srv

from a9_live import show_live


# _wifi_easyjoin: ssid:ap0 bssid:00:00:00:00:00:00 key:1213aCBVDiop@
# _wifi_easyjoin: ssid:NAXCLOW bssid:00:00:00:00:00:00 key:34974033A


HOST = "192.168.169.1"
PORT = 6123


def print_filelist(cam):
    for date in cam.sdcard_datelist():
        time.sleep(0.5)
        print(f'Files @ {date}:')
        for file in cam.filename_list(date):
            finfo = cam.avi_file_info(date, file[0], file[1])
            if finfo is not None:
                print(
                    f'\t\t-{file[0]:02d}:{file[1]:02d}: Filename: {finfo["fileName"]}, Size: {finfo["fileSize"]}')
            else:
                print(
                    f'\t\t-{file[0]:02d}:{file[1]:02d}: Could not get file info')


def download(cam, file, date, hour, min, total_sz=0):
    _pb = tqdm(range(0, total_sz), unit='B',
               unit_scale=True, unit_divisor=1024)

    def _on_rcv(id, sz):
        _pb.update(sz)

    ret = cam.get_file(date, hour, min, _on_rcv)
    if ret[1] is not None:
        with open(file, 'wb') as avi:
            avi.write(ret[1])
        return(len(ret[1]), ret[0])
    return(0, ret[0])


def parse_dt(s: str):
    if s is None:
        raise AttributeError('Empty date')
    s = s.split('-', 3)
    if len(s) == 0:
        raise AttributeError('Wrong date')

    if len(s) == 1 and len(s[0]) == len("202302101314"):
        return (int(s[0][:8]),
                int(s[0][8:10]),
                int(s[0][10:]))
    else:
        return (
            int(s[0]),
            int(s[1]) if len(s) > 1 else datetime.now().hour,
            int(s[2]) if len(s) > 2 else datetime.now().minute - 2
        )


def parse_dt_test():
    ret = parse_dt('202302101319')
    assert(ret[0] == 20230210)
    assert(ret[1] == 13)
    assert(ret[2] == 19)

    ret = parse_dt('20230210-13-19')
    assert(ret[0] == 20230210)
    assert(ret[1] == 13)
    assert(ret[2] == 19)

    start_srv()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    arg_gr = parser.add_mutually_exclusive_group(required=True)
    arg_gr.add_argument('-d', '--download', type=str, help='Download file with provided datetime. Format: [date]-[hour]-[miute], example: 20230131-22-29')
    arg_gr.add_argument('-f', '--filelist', action="store_true", help='List available files (recorded date\'s and time\'s)')
    arg_gr.add_argument('-l', '--live', action="store_true", help='Show live stream')
    arg_gr.add_argument('-s', '--server', action='store_true', help='Start a fake-server', default=False)
    arg_gr.add_argument('--set-wifi', nargs=2, help='Try to connect to specified AP (--set-wifi AP PWD)')
    parser.add_argument('-o', '--output', type=str, help='Output filename', default=None)
    parser.add_argument('-i', '--irled', action='store_true', help='Enable IR led(lens)', default=False)
    parser.add_argument('-r', '--flip', action='store_true', help='Flip camera', default=False)
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable debug logs', default=False)
    parser.add_argument('--proxy-port', type=int, help='HTTP server port, use for proxying it via NGINX, etc', default=80)
    parser.add_argument('-c', '--host', type=str, help='Host and port (192.168.169.1:6123)', default=f"{HOST}:{PORT}")

    args = parser.parse_args()

    if not args.verbose:
        log.set_log_lvl(logging.WARN)

    if args.server:
        print(f'''-------- A9 V720 fake-server starting. --------
\033[92mDevice list: http://127.0.0.1:{args.proxy_port}/dev/list
Live capture: http://127.0.0.1:{args.proxy_port}/dev/[CAM-ID]/live
Audio capture: http://127.0.0.1:{args.proxy_port}/dev/[CAM-ID]/audio
Snapshot: http://127.0.0.1:{args.proxy_port}/dev/[CAM-ID]/snapshot\033[0m
''')
        start_srv(args.proxy_port)
    else:
        host = args.host.split(':', 2)
        port = PORT if len(host) == 1 else int(host[1])

        with netcl_tcp(host[0], port) as sock:
            cam = v720_ap(sock)
            cam.init_live_motion()

            if args.filelist and cam.sdcard_status():
                print_filelist(cam)
            elif args.download and cam.sdcard_status():
                dt = parse_dt(args.download)
                file_info = cam.avi_file_info(dt[0], dt[1], dt[2])
                if file_info is None or file_info['fileSize'] == -1:
                    print(f'File {dt[0]}-{dt[1]}-{dt[2]} not found')
                    exit(1)

                output = args.output
                if output is None:
                    output = f"{file_info['fileName']}.avi"

                print('Found file @', dt[0], dt[1], dt[2], ':',
                      file_info['fileName'], ' with size:', file_info['fileSize'])
                download(cam, args.output, dt[0],
                         dt[1], dt[2], file_info['fileSize'])
            elif args.live:
                cam.ir_led(args.irled)
                cam.flip(args.flip)
                show_live(cam, args.output)
            # elif args.set_ap_pwd:
            #     print(f'Set AP pwd to: {args.set_ap_pwd}')
            #     if len(args.set_ap_pwd) < 8 or len(args.set_ap_pwd) > 32:
            #         print('AP password couldn\'t be lessa than 8 chars or more than 36')
            #         exit(1)

            #     print(cam.set_ap_pwd(args.set_ap_pwd))
            elif args.set_wifi:
                print(f'Try to connect: SSID: {args.set_wifi[0]}, pwd: {args.set_wifi[1]}')
                if cam.set_wifi(*args.set_wifi) is not None:
                    print('Set successful, rebooting camera')
                    cam.reboot()
                else:
                    print('Camera not respond')

            else:
                print('Camera doesn\'t have a SD Card')
