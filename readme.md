# A9 V720 Naxclow Camera 

<img src="https://raw.githubusercontent.com/intx82/a9-v720/master/img/0.jpg" width=480px/>

**This app has been tested only with camera version 202212011602 and only which use Chinese V720 APP and only in AP mode. See pictures of camera PCB below**

Topic on 'home-assistant' forum: <a href="https://community.home-assistant.io/t/popular-a9-mini-wi-fi-camera-the-ha-challenge">https://community.home-assistant.io/t/popular-a9-mini-wi-fi-camera-the-ha-challenge</a>

## How to use script and short brief

Then, turn on the camera and attach to their Wifi-AP. AP name should(could) starts from prefix `Nax` (as i suppose it means name of manufacturer: Naxclow) For example, i have: `Nax_210000211234`

Camera should give IP in range 192.168.169.100 / 255.255.255.0. After, you can try to connect with this script. 

By default, camera has IP 192.168.169.1 and didn't have any Web-page to configure it. Camera can be configured only via mobile-application.

Also, camera networking could be configured from UART via `ifconfig` and `wifi` commands.

**I would not recommend connecting camera to the internet, due to it downloads from Chinese server update package**

- List of all recorded videos inside camera:
    ```
    python3 src/a9_naxclow.py -f
    ```

    Arg `-f` could be replaced `--filelist`

    Camera filenames have datetime format with full date/hour/minute information. 
    
    For example: `202301312016.avi`. 
    
    But on SD card will be saved in different folders by date, `[date]/[hour]/[minute].avi`. (/20230131/20/16.avi)

- Downloading selected video file:
    
    ```
    python3 src/a9_naxclow.py -d 20230131-20-16 -o out.avi
    ```

    or 

    ```
    python3 src/a9_naxclow.py -d 202301312016 -o out.avi
    ```

    Where syntax are:
        src/a9_naxclow.py -d [date-hour-minute] -o [output-file]

    Arg `-d` could be replaced `--download` and `-o` to `--output`

    Date/Hour/Minute could be taken from first command (ie `-f` )
    if -o arg is not provided, the script will save the file as `out.avi`

    While downloading file from camera, recording is not going.

- Live video stream:
    ```
    python3 src/a9_naxclow.py -l -o live.avi -r -i
    ```

    To write captured stream into file use also arg `-o` as it was in previous example.

    To enable IR view use arg `-i` or `--irled` and to flip camera use arg `-r` or `--flip`

    There are no audio inside live record, but it could be succesfull captured and saved, check show_live() function in a9_live.py file

    Audio stream has g711-alaw wav format
- Connect to the existed WIFI AP:
    ```
    python3 src/a9_naxclow.py --set-wifi SSID PWD
    ```
    Where: 
        
        - SSID - yours WIFI AP ssid (ie name)
        - PWD - password

    for example, connect to `mifi` access point with password `mifimifi`
    
    ```
    python3 src/a9_naxclow.py --set-wifi mifi mifimifi
    ```

    PWD (password) should be at least 8 chars length, but not more 36

- Starting a fake-server
    ```bash
    python3 src/a9_naxclow.py -s
    ```

    **To properly work 'fake server', user must make DNS redirect on own (home) router - domains '*.naxclow.com' ('v720.naxclow.com', 'v720.p2p.naxclow.com', 'p2p.v720.naxclow.com') to own server IP**

    **Also, on the server must be installed any MQTT broker or 'p2p.v720.naxclow.com' should be redirected to any public mqtt broker**

    **details how it's works could be found in <a href="fake_server.md">fake_server.md</a>**

    After this part, fake server bring up the web server and listening for camera incoming messages.

    The list of available cameras will be available at `http://[FAKE_SRV_IP]/dev/list` (now as json array)

    After connection camera, MJPEG video stream available at `http://[FAKE_SRV_IP]/dev/[CAM_ID]/live`, snapshot - `http://[FAKE_SRV_IP]/dev/[CAM_ID]/snapshot`

    > There could be issues with opening tcp 80 port without root restriction, there are two ways to avoid it:
    >    - Run server from root (ie sudo)
    >    - Allow use this port by non-priviledged user `sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80`
    >    - Be sure that you are not running any other HTTP server in the system

    if you are starting fake-server thru nginx proxy, use argument `--proxy-port` to change internal http port of fake server

    To connect camera to the Wi-Fi might be used `--set-wifi` argument. See above

**If you faced any issue, try to add `-v (--verbose)` argument to the tool, it may help, if not, don't hesitate, open a new issue, here, in github with a full logs**

## Original source

Disassmbled original app (V720) sources could be found in orig-app folder. Very very early version of a9 script could be found in a9_old.py

## UART logs

Found some manufacturer passwords inside UART logs

```
com.naxclow.Camera

[WLAN_easyfReadId - 136]-Debue:  SET wifi = (NAXCLOW)  (34974033A) 
_wifi_easyjoin: ssid:NAXCLOW bssid:00:00:00:00:00:00 key:34974033A

_wifi_easyjoin: ssid:[ap0] bssid:00:00:00:00:00:00 key:1213aCBVDiop@  <--- Here ssid from most powerful AP in range

```
Full logs could be found in docs dir. <docs/uart.log>

## Camera photos

IP-camera has been built around BL7252 MCU. MCU SDK could be found at github as bdk_rtt (https://github.com/YangAlex66/bdk_rtt) (original link https://github.com/bekencorp/bdk_rtt seems to be dead now)

<img src="https://raw.githubusercontent.com/intx82/a9-v720/master/img/4.jpg" width=480px/>

All photos in img folder

## Where to buy this camera

On aliexpress, could be found by name `A9 V720 camera` and on 2023-01-31 costs 5.2 euro

