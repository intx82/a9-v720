# catcam (Go)

Go relay for the Naxclow/V720 cameras - drop-in replacement for the upstream
intx82/a9-v720 Python fake-server (kept only in git history). Serves MJPEG + WAV
streams from the cameras' P2P data channel.

## Build & run

    go vet -buildvcs=false ./... && go test -buildvcs=false ./... && go build -buildvcs=false -o catcam .
    ./start.sh                            # or: ./catcam
    # flags: -tcp :6123 -udp :6123 -http :8247 -server-ip <ip>
    # -server-ip (or SERVER_IP env) overrides the IP advertised to cameras;
    # default is the source address routing to each camera

Run in background (as on DyOne - no root needed, all ports >1024):

    ./start.sh             # detached screen session 'catcam' -> logs/server-go.log
    screen -r catcam         # watch live; screen -S catcam -X quit to stop

`-buildvcs=false` is required (repo `.git` is root-owned; go build otherwise fails with exit 128).

## Endpoints (port 8247)

Cameras reach this via nginx sinkhole `v720(.p2p).naxclow.com:80 -> proxy_pass
127.0.0.1:8247` (sets `X-Real-IP`, which the relay trusts to identify each camera).

    /dev/list                    JSON device list
    /dev/<uid>/video             multipart MJPEG (boundary jpgboundary)
    /dev/<uid>/audio             WAV pcm_alaw 8 kHz mono (continuous; 1600 B lead-in,
                                 silence padding only after 1 s of camera silence)
    /dev/<uid>/snapshot          one JPEG

## Cameras & downstream

| camera | UID          | go2rtc stream (see caveat)        |
|--------|--------------|-----------------------------------|
| cam170 | 080c0e054577 | catcam2v / catcam2a / catcam2av |
| cam199 | 080c0e053F2F | catcam1v / catcam1a / catcam1av |

**Caveat:** `/usr/src/go2rtc.yaml` uses exec producers (`ffmpeg -i http://127.0.0.1:8247/dev/<uid>/...`)
and its catcam1*/catcam2* names are INVERTED relative to the LAN IP order above — verify before
editing. The `*av` streams are native video+audio mixes; `preload:` keeps their audio legs hot so
RTSP DESCRIBEs never race to a video-only SDP. go2rtc API :1984 (HTTPS), RTSP :8554; it runs
in a ROOT screen session (`sudo screen -S go2rtc ...` from /usr/src) - `screen -S go2rtc`
without sudo won't find it.

## Operational notes

- While anyone is watching, the log prints "viewer connected/left" lines plus per-consumer
  stats every 5 s (frames/fps/KB/s video, chunks and B/s audio, current viewer totals).
- Cams hold a persistent TCP connection to :6123 and redial within ~90 s of a server restart.
  If they've been server-less >5 min they stop dialing: wake them via MQTT
  `Naxclow/P2P/Users/Device/sub/<UID>` payload `{"code":299,"reboot":1}` (broker 10.0.0.2:1883);
  re-registration in ~2 min.
- Quick close->reopen makes the camera answer the NAT probe with status 500; the relay retries
  once per second (max 10) - a stalled audio/video consumer after a restart usually means this
  retry path is missing in an older binary.
- Baseline/A-B measurements: re-measure with
  `ffmpeg -i <mjpeg-url> -t 30 -f null -` (drop the `-r 10` cap to see the raw rate).
