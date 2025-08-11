# A9 V720 Naxclow Camera 

![Camera Image](https://raw.githubusercontent.com/intx82/a9-v720/master/img/0.jpg)

**Note:** This application has been tested only with camera version `202212011602` that uses the Chinese V720 app in AP mode. Please refer to the PCB images of the camera provided below for verification.

**Note:** Looks like fake server is not working with FW >= `202411201737`.

Discussion on the Home Assistant forum: [Popular A9 Mini Wi-Fi Camera - The HA Challenge](https://community.home-assistant.io/t/popular-a9-mini-wi-fi-camera-the-ha-challenge/230108)


---

## How to Use the Script

This guide will help you set up and use the A9 V720 Naxclow Camera in two modes:

1. **AP Mode (Access Point Mode):** The camera acts as a Wi-Fi hotspot, and you connect directly to it.
2. **STA Mode (Station Mode):** The camera connects to your existing Wi-Fi network.

---

## Part 1: Configuring and Using the Camera in **AP Mode**

### 1. Connect to the Camera's Wi-Fi Access Point (AP)

- **Power On the Camera:** Turn on your A9 V720 Naxclow camera.
- **Connect to the Camera's Wi-Fi:** On your device, connect to the camera's Wi-Fi AP. The AP name typically starts with the prefix `Nax`, which likely refers to the manufacturer Naxclow. For example, `Nax_210000211234`.

### 2. Verify IP Address

- **IP Range:** The camera should assign an IP address in the range `192.168.169.x` with a subnet mask of `255.255.255.0`.
- **Default IP:** By default, the camera's IP address is `192.168.169.1`.
- **Configuration Interface:** The camera does not have a web interface for configuration; it can only be configured via the mobile application.
- **UART Configuration (Optional):** If you have UART access, you can configure the camera's network settings using the `ifconfig` and `wifi` commands.

> **Warning:** We do not recommend connecting the camera to the internet, as it may download update packages from external servers.

### 3. List Recorded Videos on the Camera

To list all recorded videos stored on the camera, use the following command:

```
python3 src/a9_naxclow.py -f
```

- The `-f` argument can also be written as `--filelist`.
- **File Naming Convention:** Camera filenames are in a datetime format containing full date, hour, and minute information, e.g., `202301312016.avi`.
- **Storage Structure:** On the SD card, videos are saved in different folders by date, formatted as `[date]/[hour]/[minute].avi` (e.g., `/20230131/20/16.avi`).

### 4. Download a Selected Video File

To download a specific video file from the camera, use one of the following commands:

```
python3 src/a9_naxclow.py -d 20230131-20-16 -o out.avi
```

or

```
python3 src/a9_naxclow.py -d 202301312016 -o out.avi
```

- **Syntax Explanation:**

  ```
  python3 src/a9_naxclow.py -d [date-hour-minute] -o [output-file]
  ```

- The `-d` argument can also be written as `--download`, and `-o` as `--output`.
- **Date and Time Format:** The date, hour, and minute can be obtained from the output of the `-f` command.
- **Default Output File:** If the `-o` argument is not provided, the script will save the file as `out.avi`.
- **Recording Note:** While downloading a file from the camera, recording is paused.

### 5. Live Video Streaming

To start a live video stream, use the following command:

```
python3 src/a9_naxclow.py -l -o live.avi -r -i
```

- **Save Stream to File:** Use the `-o` argument to specify an output file to save the captured stream.
- **Enable IR View:** Use `-i` or `--irled` to enable infrared (IR) mode.
- **Flip Camera View:** Use `-r` or `--flip` to flip the camera view.
- **Audio Note:** There is no audio in the live recording by default. However, audio can be captured and saved by modifying the `show_live()` function in the `a9_live.py` file.
- **Audio Format:** The audio stream uses the G.711 A-law WAV format.

---

## Part 2: Configuring and Using the Camera in **STA Mode**

### 1. Connect the Camera to an Existing Wi-Fi Network

To connect the camera to your existing Wi-Fi network, use the following command:

```
python3 src/a9_naxclow.py --set-wifi [SSID] [PWD]
```

- **Parameters:**
  - `SSID`: The name of your Wi-Fi access point.
  - `PWD`: The password for your Wi-Fi network.
- **Example:** To connect to an access point named `mifi` with the password `mifimifi`:

  ```
  python3 src/a9_naxclow.py --set-wifi mifi mifimifi
  ```

- **Password Requirements:** The password should be at least 8 characters long but not exceed 36 characters.

### 2. Starting a Fake Server

To use the camera over your network, you may need to start a fake server. This is because the camera tries to connect to its cloud servers, and by faking these, we can capture the camera's stream locally.

#### Start the Fake Server

Use the following command to start the fake server:

```
python3 src/a9_naxclow.py -s
```

**Important Configuration Steps:**

![Camera Image](https://raw.githubusercontent.com/intx82/a9-v720/master/img/dns.png)

> in my case 192.168.2.3 is a RPi server IP

- **DNS Redirection:** For the fake server to function correctly, you must set up DNS redirection on your home router. Redirect all domains ending with `*.naxclow.com` (e.g., `v720.naxclow.com`, `v720.p2p.naxclow.com`, `p2p.v720.naxclow.com`) to your server's IP address. See [DNS Redirection](#dns-redirection) below for more specific instructions.
- **MQTT Broker:** Ensure that an MQTT broker is installed on your server, or redirect `p2p.v720.naxclow.com` to a public MQTT broker.
- **Further Details:** For more information on how this works, please refer to [fake_server.md](fake_server.md).

**After Configuration:**

- **Web Server Activation:** The fake server will start a web server and listen for incoming messages from the camera.
- **Available Cameras:** Access the list of available cameras at `http://[FAKE_SERVER_IP]/dev/list` (returns a JSON array).
- **Live Stream and Snapshot:**
  - Live MJPEG video stream: `http://[FAKE_SERVER_IP]/dev/[CAM_ID]/live`
  - Snapshot: `http://[FAKE_SERVER_IP]/dev/[CAM_ID]/snapshot`

**Port Configuration Notes:**

- **Port 80 Access Issues:** If you encounter issues opening TCP port 80 without root privileges, consider the following solutions:
  - Run the server as root (e.g., using `sudo`).
  - Allow non-privileged users to use port 80 by executing:

    ```
    sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80
    ```

  - Ensure that no other HTTP server is running on your system.
- **Proxy Configuration:** If you are starting the fake server through an Nginx proxy, use the `--proxy-port` argument to change the internal HTTP port of the fake server.

---

## DNS Redirection

DNS Redirection is necessary for the Fake Server to work, but it can be tricky to setup. The most typical domestic setup includes a router which acts as a DHCP and DNS server. Depending on the router model and firmware, you might be able to add the DNS redirections directly in the router. A more common situation, though, is that the router is very limited in functionality.

In those cases, you will need to use a secondary DNS server with more capabilities. This might be a Rasperry Pi, or another, more configurable router. 

Here follows an example on how to setup such a secondary DNS on a Raspberry Pi, running Ubuntu, at IP address 192.168.1.2 (please substitute with your own address).

The strategy is this: In your main router (which acts as DHCP server), you need to change it to tell all DHCP clients to use your RPi as DNS, so you'll need to change the DNS to 192.168.1.2. Some routers (e.g. running Asus Merlin firmware), can override the DNS server on a per-device basis. If your router can do that, you only need to change the DNS for your A9 cams.

On the RPi, you'll install dnsmasq, and have it send all requests "upstream" to your real DNS (I highly recommend using 1.1.1.1, but you can use the DNS provided by your ISP), except for requests to naxclow.

On the RPi, run:
```
sudo apt install dnsmasq
```

then (as root) create `/etc/dnsmasq.d/a9-camera` with the following contents:
```
server=/naxclow.com/192.168.1.5
address=/naxclow.com/192.168.1.5
``` 
but replace 192.168.1.5 with the IP of the computer that actually runs the fake server.

## Troubleshooting

If you encounter any issues:

- **Verbose Mode:** Add the `-v` or `--verbose` argument to the command for detailed logs.
- **Seeking Help:** If the problem persists, please open a new issue on GitHub with the full logs attached. We are here to help!

---

## Additional Information

### Original Source

- **Disassembled App Sources:** The disassembled sources of the original V720 app can be found in the `orig-app` folder.
- **Early Script Version:** A very early version of the A9 script is available as `a9_old.py`.

### UART Logs

We discovered some manufacturer passwords in the UART logs:

```
com.naxclow.Camera

[WLAN_easyfReadId - 136]-Debug: SET wifi = (NAXCLOW)  (34974033A) 
_wifi_easyjoin: ssid:NAXCLOW bssid:00:00:00:00:00:00 key:34974033A

_wifi_easyjoin: ssid:[ap0] bssid:00:00:00:00:00:00 key:1213aCBVDiop@  <-- Here, the SSID is from the most powerful AP in range
```

- **Full Logs:** The complete logs are available in the `docs` directory at [`docs/uart.log`](docs/uart.log).

### Camera Photos

- **Hardware Details:** The IP camera is built around the BL7252 MCU.
- **SDK Availability:** The MCU SDK is available on GitHub as [bdk_rtt](https://github.com/YangAlex66/bdk_rtt). Please note that the original link (`https://github.com/bekencorp/bdk_rtt`) appears to be inactive.
- **Image Reference:**

  ![Camera PCB](https://raw.githubusercontent.com/intx82/a9-v720/master/img/4.jpg)

- **Additional Photos:** All photos are available in the `img` folder.

### Where to Buy This Camera

- **Purchase Information:** The camera can be found on AliExpress by searching for `A9 V720 camera`.
- **Price Reference:** As of January 31, 2023, the camera was priced at approximately €5.20.

---

We hope this guide helps you in using the A9 V720 Naxclow Camera with our script. If you have any questions or need further assistance, please feel free to reach out.

---
