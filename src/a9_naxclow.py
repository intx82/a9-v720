#!/usr/bin/env python3

from conn_tcp import conn_tcp
import time
import argparse
from datetime import datetime
from tqdm.auto import tqdm

# _wifi_easyjoin: ssid:ap0 bssid:00:00:00:00:00:00 key:1213aCBVDiop@
# _wifi_easyjoin: ssid:NAXCLOW bssid:00:00:00:00:00:00 key:34974033A

from v720_ap import v720_ap

from a9_live import show_live

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


def download(cam, file, date, hour, min, total_sz = 0):
    _pb = tqdm(range(0, total_sz), unit='B', unit_scale=True, unit_divisor=1024)
    def _on_rcv(id,sz):
        _pb.update(sz)

    ret = cam.get_file(date, hour, min, _on_rcv)
    if ret[1] is not None:
        with open(file, 'wb') as avi:
            avi.write(ret[1])
        return(len(ret[1]), ret[0])
    return(0, ret[0])


def parse_dt(s: str):
    s = s.split('-', 3)
    return (
        int(s[0]),
        int(s[1]) if len(s) > 1 else datetime.now().hour,
        int(s[2]) if len(s) > 2 else datetime.now().minute - 2
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    arg_gr = parser.add_mutually_exclusive_group(required=True)
    arg_gr.add_argument('-d', '--download', type=str,
                        help='Download file with provided datetime. Format: [date]-[hour]-[miute], example: 20230131-22-29')
    arg_gr.add_argument('-f', '--filelist', action="store_true",
                        help='List available files (datetimes)')
    arg_gr.add_argument('-l', '--live', action="store_true",
                        help='Show live stream')
    parser.add_argument('-o', '--output', type=str,
                        help='Output filename', default=None)
    parser.add_argument('-c', '--host', type=str,
                        help='Host and port (192.168.169.1:6123)', default=f"{HOST}:{PORT}")

    args = parser.parse_args()
    host = args.host.split(':', 2)
    port = PORT if len(host) == 1 else int(host[1])

    with conn_tcp(host[0], port) as sock:
        cam = v720_ap(sock)
        cam.init_live_motion()
        if cam.sdcard_status():
            if args.filelist:
                print_filelist(cam)
            elif args.download:
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
                download(cam, args.output, dt[0], dt[1], dt[2], file_info['fileSize'])
            elif args.live:
                show_live(cam, args.output)
        else:
            print('Camera doesn\'t have a SD Card')
