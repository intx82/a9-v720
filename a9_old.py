import socket
import struct
import json
import time
from datetime import datetime

# _wifi_easyjoin: ssid:ap0 bssid:00:00:00:00:00:00 key:1213aCBVDiop@
# _wifi_easyjoin: ssid:NAXCLOW bssid:00:00:00:00:00:00 key:34974033A

import cmd_udp

HOST = "192.168.169.1"
PORT = 6123
DEFAULT_DEVICE_TOKEN = "This is TEST token"

DEFAULT_FORWARD_ID = "00000000"
DEFAULT_DEV_TARGET = "deadbeef"


def reqpp(cmd: int, data: bytearray = []):
#       byteBuf.writeIntLE(naxclowPPProtocol.getDataLen())
#       byteBuf.writeIntLE(naxclowPPProtocol.getCmd())
#       byteBuf.writeIntLE(naxclowPPProtocol.getDataId())
#       byteBuf.writeBytes(naxclowPPProtocol.getReserved())
#       byte[] data = naxclowPPProtocol.getData()
#       if (data != null && data.length != 0) {
#           byteBuf.writeBytes(data)
#       }
    r = bytearray(struct.pack('<LLL8x', len(data), cmd, 0))
    r.extend(data)
    return r


def req(cmd, data = []):
# byteBuf.writeIntLE(naxclowProtocol.getPayloadLen());
# byteBuf.writeShortLE(naxclowProtocol.getCmd());
# byteBuf.writeByte(naxclowProtocol.getMsgFlag());
# byteBuf.writeByte(naxclowProtocol.getDealFlag());
# byteBuf.writeBytes(naxclowProtocol.getForwardId());
# byteBuf.writeIntLE(naxclowProtocol.getPkgId());
# byteBuf.writeBytes(naxclowProtocol.getPayload());
    r = bytearray(struct.pack('<LHBB', len(data), cmd, cmd_udp.DEFAULT_MSG_FLAG,0))
    r.extend(DEFAULT_FORWARD_ID.encode('ascii'))
    r.extend(bytearray([0,0,0,0]))
    r.extend(data)
    return r

def ap_cmd(data): 
    data = {"code":cmd_udp.CODE_AP_COMMAND, "content": data }
    return json_req(data)


def req_connect():
#  public void reqConnect(String str, String str2) {
#         JSONObject jSONObject = new JSONObject();
#         jSONObject.put("code", (Object) Integer.valueOf(NaxclowProtocol.CODE_AP_CONNECT));
#         jSONObject.put(IApp.ConfigProperty.CONFIG_TARGET, (Object) str);
#         jSONObject.put("token", (Object) str2);
#         jSONObject.put("unixTimer", (Object) Long.valueOf((System.currentTimeMillis() / 1000) + ((long) (TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 1000))));
#         sendProtoBeanWithTimeout(jSONObject);
#         NaxclowLog.m3270d("Naxclow", "p2p-udp AP-->" + jSONObject);
#     }
    obj = {
        'code': cmd_udp.CODE_AP_CONNECT,
        'target': DEFAULT_DEV_TARGET,
        'token': DEFAULT_DEVICE_TOKEN,
        'unixTimer': int(datetime.timestamp(datetime.now()))
    }
    return json_req(obj)

def req_baseinfo():
    obj = {
        'code': cmd_udp.CODE_FORWARD_DEV_BASE_INFO,
        'devTarget': DEFAULT_DEV_TARGET,
        'unixTimer': int(datetime.timestamp(datetime.now()))
    }
    return ap_cmd(obj)

def req_filenamelist(date):
    obj = {
        'code': cmd_udp.CODE_SDCARD_REQ_CONFIG,
        'devTarget': DEFAULT_DEV_TARGET,
        'date': date
    }

    return json_req(obj)

def set_playbackfromlive(play = 0): # 3 - stop
    obj = {
        'code': play,
        'devTarget': DEFAULT_DEV_TARGET
    }
    return ap_cmd(obj)

def get_sdcard_status():
    obj = {
        'code': cmd_udp.CODE_FORWARD_DEV_SDCARD_STATUS,
        'devTarget': DEFAULT_DEV_TARGET
    }
    return ap_cmd(obj)

def set_wifi_scan():
    obj = {
        'code': cmd_udp.CODE_FORWARD_DEV_WIFI_SCAN,
        'devTarget': DEFAULT_DEV_TARGET
    }
    return ap_cmd(obj)


def req_sdcard_datelist():
    return json_req({
        'code': cmd_udp.CODE_SDCARD_REQ_DATE_LIST,
        'devTarget': DEFAULT_DEV_TARGET
    })


def req_avi_file_info(date, hours, minute):
    return json_req({
        'code': cmd_udp.CODE_SDCARD_REQ_MEDIA_INFO,
        'devTarget': DEFAULT_DEV_TARGET,
        'date': date,
        'hours': hours,
        'minute': minute,
    })


def req_start_stream(date, hours, minute):
    return json_req({
        'code': cmd_udp.CODE_SDCARD_REQ_START_STREAM,
        'devTarget': DEFAULT_DEV_TARGET,
        'date': date,
        'hours': hours,
        'minute': minute,
    })


def parse_get_filenames(minBin):
    j = 1
    i = 0
    ret = []
    parseLong = minBin
    while (i < 64):
        if (j << i) & parseLong:
            ret.append(i)
        i += 1
        j = 1
    return ret


def ping():
    return req(cmd_udp.P2P_UDP_CMD_HEARTBEAT)

def json_req(data: dict):
    data = json.dumps(data)
    return req(cmd_udp.P2P_UDP_CMD_JSON, data.encode('ascii'))

def jpeg_req():
    return req(cmd_udp.P2P_UDP_CMD_AVI)

def send_bool(sock, data):
    sock.sendall(data)
    return len(sock.recv(1024)) > 0

def send_hex(sock, data):
    sock.sendall(data)
    print(sock.recv(1024).hex())

def send_text(sock, data):
    sock.sendall(data)
    ret = sock.recv(1024)
    sz = struct.unpack('<L', ret[:4])[0]
    print(ret[19:20+sz].decode('ascii'))


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(5)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.connect((HOST, PORT))
    
    print('Connect(P2P_UDP_CMD_LIVE_MOTION):', 'OK' if send_bool(sock, req(cmd_udp.P2P_UDP_CMD_LIVE_MOTION)) else 'Fail')

    send_text(sock, req_connect())
    send_text(sock, req_baseinfo())
    # send_text(sock, set_wifi_scan())
    send_text(sock, get_sdcard_status())
    send_text(sock, req_sdcard_datelist())
    send_text(sock, req_filenamelist(20230124))
    print(sock.recv(1024))
    m = parse_get_filenames(864409584620273472)[0]
    send_text(sock, req_avi_file_info(20230124,2, m))
    
    sock.sendall(req_start_stream(20230124,2, m))
    r = 1
    while(r):
        r = sock.recv(1024)
        print(r.hex())


    # send_text(sock, req_avi_file_info(20230124,2,10))
    # print(sock.recv(1024))

    # for i in range(10):
    #     time.sleep(5)
    #     sock.sendall(ping())
    #     print('Ping: ', 'OK' if sock.recv(1024) else 'Fail')


