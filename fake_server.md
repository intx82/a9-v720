# V720 Fake server

## Preparing setup

You should make an AP and prevent camera access to the internet. I have made it by NetworkManager-GUI, so no details.
Also on my side, NetworkManager working as DHCP server, and below used IP 10.42.0.1 is my laptop and 10.42.0.22 is camera host

Then to be able intercept all cameras requests to the server, needed to install Dnsmasq and override `v720.naxclow.com` and `v720.p2p.naxclow.com` hosts to the local IP (10.42.0.1)
This preparation could be done on a router (ie provide fake DNS records and offer dhcp address).

Last but not least, need to install `mosquitto` broker with `mosquitto-utils` to provide an mqtt control pipe. 

After such preparations, camera must be connected to fake-AP, this could be done with `a9-naxclow.py --set-wifi SSID PWD` command. And then you can start `fake_srv.py`


## Camera server registration steps

### 1. Bootstrap HTTP operations

First device goes to register on `bootstrap` server which gives to camera new name and after point on dedicated server with which it will works


```log
curl -v -X POST "http://v720.naxclow.com/app/api/ApiSysDevicesBatch/registerDevices?batch=A9_X4_V12&random=DEFGHI&token=547d4ef98b"
*   Trying 120.79.92.139:80...
* Connected to v720.naxclow.com (120.79.92.139) port 80 (#0)
> POST /app/api/ApiSysDevicesBatch/registerDevices?batch=A9_X4_V12&random=DEFGHI&token=547d4ef98b HTTP/1.1
> Host: v720.naxclow.com
> User-Agent: curl/7.74.0
> Accept: */*
> 
* Mark bundle as not supporting multiuse
< HTTP/1.1 200 
< Server: nginx/1.14.0 (Ubuntu)
< Date: Fri, 10 Feb 2023 21:43:40 GMT
< Content-Type: application/json
< Content-Length: 59
< Connection: keep-alive
< Vary: Origin
< Vary: Access-Control-Request-Method
< Vary: Access-Control-Request-Headers
< 
* Connection #0 to host v720.naxclow.com left intact
{"code":200,"message":"操作成功","data":"0800c00128F8"} 
```

 After bootstrap message camera might ask an confirmation from server. 

```Log
 curl -v -X POST 'http://v720.naxclow.com/app/api/ApiSysDevicesBatch/confirm?devicesCode=0800c0020ADC&random=NOPQRS&token=025d085049'
*   Trying 8.218.137.74:80...
* Connected to v720.naxclow.com (8.218.137.74) port 80 (#0)
> POST /app/api/ApiSysDevicesBatch/confirm?devicesCode=0800c0020ADC&random=NOPQRS&token=025d085049 HTTP/1.1
> Host: v720.naxclow.com
> User-Agent: curl/7.74.0
> Accept: */*
>
* Mark bundle as not supporting multiuse
< HTTP/1.1 200
< Server: nginx/1.18.0 (Ubuntu)
< Date: Wed, 01 Mar 2023 12:32:03 GMT
< Content-Type: application/json
< Content-Length: 49
< Connection: keep-alive
< Vary: Origin
< Vary: Access-Control-Request-Method
< Vary: Access-Control-Request-Headers
<
* Connection #0 to host v720.naxclow.com left intact
{"code":200,"message":"操作成功","data":null}
```

After that device AP will have name `0800c00128F8`. `操作成功` - translates as 'OK'. This will happens only once, after this step camera will never do this again.


### 2. Device try to get dedicated server info. 

So let's route them to our IP (10.42.0.1)

```log
curl -v -X POST "http://v720.naxclow.com/app/api/ApiServer/getA9ConfCheck?devicesCode=0800c00128F8&random=FGHIJK&token=68778db973"
*   Trying 120.79.224.199:80...
* Connected to v720.naxclow.com (120.79.224.199) port 80 (#0)
> POST /app/api/ApiServer/getA9ConfCheck?devicesCode=0800c00128F8&random=FGHIJK&token=68778db973 HTTP/1.1
> Host: v720.naxclow.com
> User-Agent: curl/7.74.0
> Accept: */*
> 
* Mark bundle as not supporting multiuse
< HTTP/1.1 200 
< Server: nginx/1.14.0 (Ubuntu)
< Date: Fri, 10 Feb 2023 22:41:29 GMT
< Content-Type: application/json
< Content-Length: 219
< Connection: keep-alive
< Vary: Origin
< Vary: Access-Control-Request-Method
< Vary: Access-Control-Request-Headers
< 
* Connection #0 to host v720.naxclow.com left intact
{"code":200,"message":"操作成功","data":{"tcpPort":29940,"uid":"0800c00128F8","isBind":"8","domain":"v720.naxclow.com","updateUrl":null,"host":"43.240.74.95","currTime":"1676097689","pwd":"91edf41f","version":null}}
```
### 3. Initial registration

Device send registration on main server (provided via bootstrap, ie 43.240.74.95:29940)


```hex
0000                     57 00 00 00 00 00 00 00 00 00         W.........
0010   00 00 00 00 00 00 00 00 00 00 7b 22 63 6f 64 65   ..........{"code
0020   22 3a 20 31 30 30 2c 20 22 75 69 64 22 3a 20 22   ": 100, "uid": "
0030   30 38 30 30 63 30 30 31 32 38 46 38 22 2c 20 22   0800c00128F8", "
0040   74 6f 6b 65 6e 22 3a 20 22 39 31 65 64 66 34 31   token": "91edf41
0050   66 22 20 2c 22 64 6f 6d 61 69 6e 22 3a 20 22 76   f" ,"domain": "v
0060   37 32 30 2e 6e 61 78 63 6c 6f 77 2e 63 6f 6d 22   720.naxclow.com"
0070   7d                                                }
```

And respone:

```bash
~# python3 tcp_hex.py 43.240.72.158 29941 57000000000000000000000000000000000000007b22636f6465223a203130302c2022756964223a2022303830306330303132384638222c2022746f6b656e223a2022393165646634316622202c22646f6d61696e223a2022763732302e6e6178636c6f772e636f6d227d
190000000000ff00ffffffffffffffff000000007b22636f6465223a3130312c22737461747573223a3230307d
^CTraceback (most recent call last):
  File "/root/naxclow.py", line 10, in <module>
    print(_socket.recv(4096).hex())
KeyboardInterrupt
```

Response: 
```python
>>> from prot_json_udp import prot_json_udp
>>> from prot_udp import prot_udp
>>> p = prot_udp.resp(b'\x19\x00\x00\x00\x00\x00\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x00{"code":101,"status":200}')
>>> p
CMD: 0, len: 25 (25), MSG_Flag: 255, pkg_id: 0, deal_fl: 0, fwd-id: b'\xff\xff\xff\xff\xff\xff\xff\xff' Payload: 7b22636f6465223a3130312c22737461747573223a3230307d
>>> p = prot_json_udp.resp(b'\x19\x00\x00\x00\x00\x00\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x00{"code":101,"status":200}')
>>> p
JSON: {'code': 101, 'status': 200}
```

### 4. Camera try to connect to the p2p server

P2P server: v720.p2p.naxclow.com. Override it also to 10.42.0.1

P2P server is a mqtt-broker, as usually located on 1883, without any encryption

```Log
MQ Telemetry Transport Protocol, Connect Command
    Header Flags: 0x10, Message Type: Connect Command
    Msg Len: 142
    Protocol Name Length: 4
    Protocol Name: MQTT
    Version: MQTT v3.1.1 (4)
    Connect Flags: 0xce, User Name Flag, Password Flag, QoS Level: At least once delivery (Acknowledged deliver), Will Flag, Clean Session Flag
    Keep Alive: 10
    Client ID Length: 12
    Client ID: 0800c00128F8
    Will Topic Length: 31
    Will Topic: Naxclow/P2P/Users/Device/Status
    Will Message Length: 55
    Will Message: 7b22646576696365223a22303830306330303132384638222c22746f6b656e223a224e41…
    User Name Length: 12
    User Name: 0800c00128F8
    Password Length: 12
    Password: "656f41d93b"
```
### 5. MQTT operations

Camera subscribes to topic `Naxclow/P2P/Users/Device/sub/0800c00128F8` and publish a few messages to `Naxclow/P2P/Users/Device/Status` and `Naxclow/P2P/Users/Device/Info`

Status message contains:

```Json
{"device":"0800c00128F8","token":"NAXCLOW","status": 1}
```

And Info message is:

```Json
{"apStatus": 0,"devPower": 100,"sdCapacity": 0,"IrLed": 0,"SD_freeDisk": -1,"SD_blockDisk": -1,"cameraState": 0,"sd_State": 0,"sdMoveMode": 0,"sdCardReco": 1,"instLed": 1,"random":"BCDEFG","token":"910d310434","devicesCode":"0800c00128F8","wifiName":"intl-laptop","version":"202212011602"}
```

On poweroff camera will send:
```json
{"device":"0800c00128F8","token":"NAXCLOW","status": 0}
```
Commands:

MQTT Commands, commands sends always to the same topic: `Naxclow/P2P/Users/Device/sub/0800c00128F8`

To test command, use `mosquitto_pub` and `mosquitto_sub`

For example: 
```
mosquitto_pub -t 'Naxclow/P2P/Users/Device/sub/0800c00128F8' -h 10.42.0.1 -m '{ "code": 204, "s": "mifi", "p": "mifimifi"}'
```

and listen answers like:
```
mosquitto_sub -t '#' -h 'v720.p2p.naxclow.com' -v | ts [%.s]
```

| CODE                           | Value                                    | Description                                                                                                          |
| ------------------------------ | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
|                                | { code: 209, sdCardReco: * }             | Stop (0) / Start (1) recording to sdCard. Response with status (`Naxclow/P2P/Users/Device/Status`)                   |
| CODE_FORWARD_DEV_MOVE_MODE     | { code: 203, sdMoveMode: * }             | Stop (0) / Start (1) sdMoveMode (?) (write only on moving?) Response with status (`Naxclow/P2P/Users/Device/Status`) |
| CODE_FORWARD_DEV_SDCARD_FORMAT | { code: 207 }                            | Format SD-Card. Response with new status. Should goes with reboot                                                    |
| CODE_FORWARD_DEV_MOVE_ALERT    | { code: 205, moveAlert: * }              | Disable (0) / Enable (1) move alert. Response with status (but i don't seen an move alert itself)                    |
|                                | { code: 215, pirGrade: * }               | pirGrade (?)                                                                                                         |
| CODE_FORWARD_DEV_MOVE_GRADE    | { code: 206, moveGrade: *}               | Move grade (?)                                                                                                       |
|                                | { code: 213, pirAlert: r }               | PIR alert (?)                                                                                                        |
| CODE_FORWARD_DEV_REBOOT        | { code: 299, reboot: 1 }                 | reboot                                                                                                               |
| CODE_FORWARD_DEV_INST_LED      | { code: 210, instLed: * }                | Turn ON (1)/OFF(0) power led (you can turn off power led, but camera will record)                                    |
| CODE_FORWARD_DEV_IR_LED        | { code: 202, IrLed: * }                  | Turn ON (1)/OFF(0) infrared view                                                                                     |
| CODE_FORWARD_DEV_WIFI_SCAN     | { code: 211 }                            | Scan WIFI. Status will have a new field 'scanWifiBase64'                                                             |
| CODE_FORWARD_DEV_SET_WIFI      | { code: 204}                             | Disconnects from wifi                                                                                                |
| CODE_FORWARD_DEV_SET_WIFI      | { code: 204, "s": SSID, "p": "password"} | Connects to provided AP                                                                                              |
| CODE_FORWARD_DEV_AP_MODE       | { code: 208}                             | Switch to AP mode                                                                                                    |
| CODE_FORWARD_DEV_LED_EI        | { code: 220, ledEI: *, lightGrade: *}    | ledEI control 0/1 (in code ledEI == lightGrade) but not working                                                      |
| CODE_FORWARD_DEV_MOTOR_STATE   | { code: 212, pirSysMode: *}              | ?                                                                                                                    |

### 6. Camera establish a connection via NAT

To establish a connection via NAT, the server sends a message with a `code 11` (CODE_S2D_NAT_REQ). 

```
{'code': 11, 'cliTarget': '00112233445566778899aabbccddeeff', 'cliToken': '55ABfb77', 'cliIp': '10.42.0.1', 'cliPort': 53221, 'cliNatIp': '10.42.0.1', 'cliNatPort': 41234}
```

If put in code 11 message wrong IP, nothing bad happens, but opens a door to make a redirection to a 3-rd host (irl this should be phone with application).

After camera will try to establish connection via UDP with at least one of proposed ports (53221 / 41234), otherwise will try to use the same port/IP as TCP but on UDP. This UDP channel later will be used as data-channel to transmit a MJPG/G711 data.

To establish a UDP connection, the camera sends an `code 20 (CODE_C2S_UDP_REQ)` message and waits back for a message with code 21

```
[UDP-SRV] JSON recv: [32]: {
    "code": 20
}
[UDP] Send UDP response: {'code': 21, 'ip': '10.42.0.1', 'port': 53221}
```
Point which is returned in `code 21 (CODE_S2C_UDP_RSP)` really has no matter

> little remark, in CODE_ names could be found a prefixes like _C2S or _C2D - which means Client2Server or Client2Device and vice-versa 

On the TCP channel sends a result of this operation, answer will contain a message with `code 12 (CODE_D2S_NAT_RSP)`

```json
{
    "code": 12,
    "status": 200,
    "devIp": "10.42.0.1",
    "devPort": 53221,
    "devNatIp": "10.42.0.28",
    "devNatPort": 29291,
    "cliTarget": "00112233445566778899aabbccddeeff",
    "cliToken": "55ABfb77"
}
```

### 7. Switching camera to command mode

After receiving a message with `code 12 (CODE_D2S_NAT_RSP)` camera will sends a message with `code 51 (CODE_C2D_PROBE_RSP)`. By default client might send an CODE_C2D_PROBE_REQ again, answer will be the same (ie `code 51 (CODE_C2D_PROBE_RSP)`)

To switch a camera into command mode need to send:

1. command with `code 50 (CODE_C2D_PROBE_REQ)` 

    ```json
    {"code": 50}
    ```
2. Got an answer with `code 51 (CODE_C2D_PROBE_RSP)`
    
    ```JSON
    {
    "code": 51,
    "devTarget": "0800c0012345",
    "status": 200
    }
    ```

3. Send a command to enable command mode, there will not be answer to this command. `code 53 (CODE_S2_DEVICE_STATUS)`
   ```JSON
   {"code": 53, "status": 1}
   ```

4. Send restransmission command:
   
   ```JSON
   {"code": 301, "target": "00112233445566778899aabbccddeeff", "content": {"code": 298}}
  ```

  Where `code 301 (CODE_CMD_FORWARD)` it's a forward code and used the same as in AP mode. 
  `code 298 (CODE_RETRANSMISSION)` - it's a retransmission command itself

  There is no answer to this command too

5. Request a base-info command. So next steps almost the same as it was in AP mode.

  ```JSON
  {"code": 301, "target": "00112233445566778899aabbccddeeff", "content": {"unixTimer": 1677886134, "code": 4}}
  ```

  `code 4 (CODE_FORWARD_DEV_BASE_INFO)` - baseinfo command. 

  On answer to this comamnd, camera will sends current status:

  ```JSON
  {
    "code": 301,
    "target": "00112233445566778899aabbccddeeff",
    "content": {
        "code": 4,
        "IrLed": 1,
        "devPower": 100,
        "speedGrade": 1,
        "moveAlert": 0,
        "sdMoveMode": 0,
        "wifiName": "intl-laptop",
        "instLed": 1,
        "sdDevStatus": 0,
        "mirrorFlip": 0,
        "version": "202212011602"
    }
  }
  ```

### 8. Starting a streaming
  
Starting the streaming is the same as in AP mode, need to send `code 3` command in forward mode.

```
[TCP] Send caplive req: {'code': 301, 'target': '00112233445566778899aabbccddeeff', 'content': {'code': 3}}
Next step @ rcv: -
[TCP] JSON recv: [103]: {
    "code": 301,
    "target": "00112233445566778899aabbccddeeff",
    "content": {
        "code": 3
    }
}
```


### 9. Frames fragmentation

There are three type of frames - 1 (P2P_UDP_CMD_JPEG) / 4 (P2P_UDP_CMD_G711) / 7 (P2P_UDP_CMD_AVI). Type of frame is set in CMD field of the package. JPEG frame could be fragmented (because one JPG frame have size ~15kb, which is more than MTU). To fragment it, every package includes MSG_FLAG value, where:

    * MSG_FLAG = 250 - Start of JPEG frame
    * MSG_FLAG = 251 - Continuation of JPEG frame
    * MSG_FLAG = 252 - End of JPEG frame

The last 4 bytes of the last JPEG package contains the size of the full frame. 

Audio data is not fragmented and looks more like G711-ALAW audio stream 

Every next sent frame should be repeated with `code 605 (P2P_UDP_CMD_RETRANSMISSION_CONFIRM)` which contains already received package_id's in a list. To achieve 10 fps, this command should be retransmitted every 100ms. 

```log
2023-03-06 20:04:05,450  [  DEBUG] [V720-STA] Request (UDP): CMD: 1, len: 1004 (1004), MSG_Flag: 250, pkg_id: 2802, deal_fl: 0, fwd-id: b'\x00\x00\x00\x00\x00\x00\x00\x00' Payload: ffd8ffe000104a46494600010100028001e00000ffc000110801e00280030121...
2023-03-06 20:04:05,450  [   INFO] [V720-STA] Receive H264 frame
2023-03-06 20:04:05,450  [  DEBUG] [UDP-SRV 10.42.0.28:43258] Recv: ec0300000100fb000000000000000000f30a0000d00491befea071db352834015faf34bc8e940075381cfa521eb400bebed4649e307340083d3341e940054673...
2023-03-06 20:04:05,450  [  DEBUG] [V720-STA] Request (UDP): CMD: 1, len: 1004 (1004), MSG_Flag: 251, pkg_id: 2803, deal_fl: 0, fwd-id: b'\x00\x00\x00\x00\x00\x00\x00\x00' Payload: d00491befea071db352834015faf34bc8e940075381cfa521eb400bebed4649e...
... package body
2023-03-06 20:04:05,475  [  DEBUG] [UDP-SRV 10.42.0.28:43258] Recv: ec0300000100fb0000000000000000000a0b0000d28003ed49d7af3ed400873c00093e829fe59cf4c8fa500382ede314a00cf3c500293cd213c500682e1506d1...
2023-03-06 20:04:05,475  [  DEBUG] [V720-STA] Request (UDP): CMD: 1, len: 1004 (1004), MSG_Flag: 251, pkg_id: 2826, deal_fl: 0, fwd-id: b'\x00\x00\x00\x00\x00\x00\x00\x00' Payload: d28003ed49d7af3ed400873c00093e829fe59cf4c8fa500382ede314a00cf3c5...
2023-03-06 20:04:05,475  [   INFO] [V720-STA] Receive H264 frame
2023-03-06 20:04:05,475  [  DEBUG] [UDP-SRV 10.42.0.28:43258] Recv: a80200000100fc0000000000000000000b0b0000e30bc0a004c53b193c0a00090a0e693ef0c8ce2801728b81c963da9a72fd4e1470157b50028c018029a58034...
2023-03-06 20:04:05,475  [  DEBUG] [V720-STA] Request (UDP): CMD: 1, len: 680 (680), MSG_Flag: 252, pkg_id: 2827, deal_fl: 0, fwd-id: b'\x00\x00\x00\x00\x00\x00\x00\x00' Payload: e30bc0a004c53b193c0a00090a0e693ef0c8ce2801728b81c963da9a72fd4e14...
2023-03-06 20:04:05,475  [   INFO] [V720-STA] Receive H264 frame
2023-03-06 20:04:05,475  [   INFO] [V720-STA] Receive H264 frame sz: (25775 <> 25776)
2023-03-06 20:04:05,517  [  DEBUG] [V720-STA] Send empty P2P_UDP_CMD_RETRANSMISSION_CONFIRM
2023-03-06 20:04:05,517  [  DEBUG] [UDP-SRV 10.42.0.28:43258] Send: 680000005d020000303030303030303000000000f20a0000f30a0000f40a0000f50a0000f60a0000f70a0000f80a0000f90a0000fa0a0000fb0a0000fc0a0000...
```
