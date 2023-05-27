#!/usr/bin/env python3

import cv2
import numpy
import io
import cmd_udp
import time
from datetime import datetime
from threading import Timer, Lock
from PIL import Image

from netcl_tcp import netcl_tcp
from v720_ap import v720_ap

HOST = "192.168.169.1"
PORT = 6123
WAV_HDR = b'RIFF\x8a\xdc\x01\x00WAVEfmt \x12\x00\x00\x00\x06\x00\x01\x00@\x1f\x00\x00@\x1f\x00\x00\x01\x00\x08\x00\x00\x00fact\x04\x00\x00\x006\xdc\x01\x00LIST\x1a\x00\x00\x00INFOISFT\x0e\x00\x00\x00Lavf58.45.100\x00data\xff\xff\xff\xff'

frame_time = time.time()
last_img = None
writer_lock = Lock()

def cv2_show_img(frame: bytearray):
    global frame_time, last_img, writer_lock
    t = time.time()
    fps = round(1 / (t - frame_time), 2)
    
    writer_lock.acquire()
    last_img = numpy.array(Image.open(io.BytesIO(frame)))
    cv2.putText(last_img, str(datetime.now()), (5, 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 0), 1, cv2.LINE_AA)
    cv2.putText(last_img, f'FPS: {fps}', (5, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 0), 1, cv2.LINE_AA)
    writer_lock.release()
    cv2.imshow('Frame', last_img)
    cv2.waitKey(1)
    frame_time = t


def show_live(cam: v720_ap, videofile: str = None, audiofile: str = None):
    cv2.startWindowThread()
    cv2.namedWindow('Frame')

    print('Press CTRL-C to exit')
    _video = None
    if videofile is not None:
        _video = cv2.VideoWriter(videofile, cv2.VideoWriter_fourcc(
            'M', 'J', 'P', 'G'), 10, (640, 480))

        def _save_video():
            global writer_lock, last_img
            writer_lock.acquire()
            if last_img is not None:
                _video.write(last_img)
            writer_lock.release()
            
            _v_writer_tmr = Timer(0.1, _save_video)
            _v_writer_tmr.setDaemon(True)
            _v_writer_tmr.start()

        _save_video()

    _audio = None
    if audiofile is not None:
        _audio = open(audiofile, 'wt')
        _audio.write(WAV_HDR)

    try:
        sync = False
        frame = bytearray()

        def on_rcv(cmd, data: bytearray):
            nonlocal sync
            if cmd == cmd_udp.P2P_UDP_CMD_JPEG:
                if not sync:
                    f = data.find(b'\xff\xd8')
                    if f != -1:
                        frame.extend(data[f:])
                        sync = True
                else:  # sync == true
                    f = data.find(b'\xff\xd9')
                    if f != -1:
                        frame.extend(data[:f+2])
                        cv2_show_img(frame)
                        frame.clear()
                        sync = False
                    else:
                        frame.extend(data)
            elif cmd == cmd_udp.P2P_UDP_CMD_G711 and _audio is not None:
                _audio.write(data)
        cam.cap_live(on_rcv)

    except KeyboardInterrupt:
        if _video is not None:
            _video.release()
        if _audio is not None:
            _audio.flush()
            _audio.close()
        return


if __name__ == '__main__':
    with netcl_tcp(HOST, PORT) as sock:
        cam = v720_ap(sock)
        cam.init_live_motion()
        show_live(cam, 'live.avi')
