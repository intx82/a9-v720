# V720 Fake server

## Preparing setup

You should make an AP and prevent camera access to the internet. I have made it by NetworkManager-GUI, so no details.
Also on my side, NetworkManager working as DHCP server, and in below IP 10.42.0.1 is my laptop and 10.42.0.22 is camera host

Then to be able intercept all cameras requests to the server, needed to install Dnsmasq and override `v720.naxclow.com` and `v720.p2p.naxclow.com` hosts to the local IP (10.42.0.1)
This preparation could be done on a router (ie provide fake DNS records and offer dhcp address). But next one not.

Last but not least, need to install `mosquitto` broker with `mosquitto-utils` to provide an mqtt control pipe. 

After such preparations, camera must be connected to fake-AP, this could be done with `a9-naxclow.py --set-wifi SSID PWD` command. And then you can start `fake_srv.py`


## Camera server registration steps

1. First device goes to register on `bootstrap` server which gives to camera new name and after point on dedicated server with which it will works

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

After that device AP will have name `0800c00128F8`. `操作成功` - translates as 'OK'. This will happens only once, after this step camera will never do this again.


2. Device try to get dedicated server info. So let's route them to our IP (10.42.0.1)

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
3. Device send registration on main server (provided via bootstrap, ie 43.240.74.95:29940)

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
~# python3 naxclow.py 43.240.72.158 29941 57000000000000000000000000000000000000007b22636f6465223a203130302c2022756964223a2022303830306330303132384638222c2022746f6b656e223a2022393165646634316622202c22646f6d61696e223a2022763732302e6e6178636c6f772e636f6d227d
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

4. Camera try to connect to the p2p server

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
5. MQTT operations

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

6. Commands:

MQTT Commands, commands sends always to the same topic: `Naxclow/P2P/Users/Device/sub/0800c00128F8`

To test command, use `mosquitto_pub` and `mosquitto_sub` 

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
