# CatCam — AV breakage fix notes (2026-09-30 → 2026-10-01)

## Problem

The `catcam1av`/`catcam2av` combined audio+video streams were produced by two
`ffmpeg` pipe-join producers (`catcamXa` + `catcamXv` merged via a
`ffmpeg -i pipe… -i pipe…` merge source). Symptom: the combined streams broke
(stalled/froze) whenever a camera's cloud session hiccuped, and the go2rtc
probe of a pipe input cannot expose the PCMA leg at all — go2rtc only
publishes medias it can *parse from the source container*, and a raw pipe has
no container. Result: consumers saw video-only or died on EOF.

## Fix (criterion 18): single-exec AV producers

`/usr/src/go2rtc.yaml` now defines each AV stream as **one** exec producer:

```yaml
catcam1av: exec:/usr/src/catcam-av.sh 080c0e053F2F {output}#killsignal=15#killtimeout=5
catcam2av: exec:/usr/src/catcam-av.sh 080c0e054577 {output}#killsignal=15#killtimeout=5
```

`/usr/src/catcam-av.sh` runs a single ffmpeg that:

1. pulls `/dev/<uid>/audio` (→ `pcm_alaw` 8 kHz) and `/dev/<uid>/video`
   (→ re-encoded `h264` 12 fps) from the local relay (`127.0.0.1:8247`), both
   legs with `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5`,
2. muxes them into one RTSP session and **pushes it to go2rtc's `{output}`**,
3. the wrapper retries every 1 s on ffmpeg exit, so a camera-session tear
   (camera drops its cloud connection) heals in ~1 s *inside the producer*,
   transparently replacing the producer without ending go2rtc's consumers.

go2rtc sees a proper RTSP source (two medias: H.264 + PCMA), so both tracks
are published on every consumer protocol. The old
`preload: catcam1a/2a: audio` lines were removed (2026-10-01): the av streams
no longer consume the `catcamXa` legs; a-legs now start on demand only.

## Verification matrix (RTSP, `-c copy`, 10 s captures, 2026-10-01)

| stream  | video         | v-packets | audio        | a-packets | max pts gap | nonmono |
|---------|---------------|-----------|--------------|-----------|-------------|---------|
| catcam1av | h264          | 120       | pcm_alaw 8k  | 111       | ≤ 0.1 s     | 0       |
| catcam2av | h264          | 120       | pcm_alaw 8k  | 111       | ≤ 0.1 s     | 0       |

Both medias present, audio gap-free, monotonic.

## WebRTC evidence (go2rtc webui `stream.html`, https://localhost:1984)

- Baseline `catcam1av` (12 s): `readyState=connected`, 127 video frames,
  ~92 KB audio received, ICE connected. No mosaic artifacts in screenshots
  (`/tmp/webrtc_catcam1av.png`).
- Producer-kill survival: wrapper SIGKILLed mid-stream → `framesReceived`
  continued to climb (10.7→14.9 s) across the respawn on the *same* PeerConnection;
  after `location.reload()` (new session) playback re-established (129 frames).
- `catcam2av`: 133 frames in 12 s.
- Screenshots show no 8×8-block/mosaic corruption (scene is dark pre-dawn).

## Camera tear / reboot evidence

Scenario A — forced session tear
(`sudo ss -K state established dst 10.0.0.199` at t=15 s during a 180 s
`stream.mp4` fetch):

| time (CEST) | event |
|---|---|
| 06:03:13 | ss kills camera's cloud+MQTT sockets |
| 06:03:13 | go2rtc WRN `error=EOF url=exec:…catcam-av.sh…` (producer exit) |
| ~06:03:14 | wrapper retry respawns producer |
| 06:03:22 | relay byte-stream stalls (camera reconnect window) |
| 06:03:23-24 | relay log: camera reconnected, "registered as 080c0e053F2F" |
| 06:03:28 | fetch bytes resume (~170 KB/6 s) |

Result `stream.mp4` consumer: 180 s fetched, 168.5 s duration, 2024 video
packets, 12 fps in *every* 6 s window, max pts gap 0.08 s — seamless across
the tear.

Scenario B — MQTT remote reboot (`code 299`):

```
mosquitto_pub -h 10.0.0.2 -p 1883 -q 1 \
  -t "Naxclow/P2P/Users/Device/sub/080c0e053F2F" \
  -m '{"code":299,"reboot":1}'
```

Camera redials its cloud session 5–19 s later (10–11 s outage, re-registers
same second; relay log "camera connected / registered as / streaming
started"). **Only executes while the camera is idle** — ignored while an
active stream session is held. This restarts the P2P session, not the full
device boot; scenario A (ss-K) is the software-reachable full-tear equivalent
(a physical reboot was not available).

## Cross-consumer semantics after a producer respawn

| consumer | behavior across tear+respawn |
|---|---|
| HTTP `stream.mp4` | survives seamlessly (rebinds; pts continuous) |
| WebRTC | survives on same PeerConnection; new session after reload |
| RTSP client session | **freezes** (bad cseq) — go2rtc-intrinsic; client must reconnect |

## Known quirks (pre-existing, unchanged)

- `stream.wav?src=…` returns a 19-byte header only for these sources — use
  RTSP/`-c copy` captures for audio verification.
- `stream.mp4` negotiates video-only (AAC negotiation quirk); audio
  verification via RTSP/WebRTC.

## 2026-10-03: browser garbling root cause — chroma profile

Camera JPEGs decode to **yuvj422p (4:2:2)**; the go2rtc exec producers fed
that straight into libx264, producing H.264 **High 4:2:2** which browser
WebRTC decoders cannot handle → permanent mosaic/green screens on
stream.html regardless of relay health (ffprobe showed
profile-level-id=7A0016). Fix: `-pix_fmt yuv420p` added to catcam1v/2v
producers and /usr/src/catcam-av.sh; all streams now High/yuvj420p.
Note: ffmpeg null-sink decode checks never caught this — libav decodes
4:2:2 fine; verify H.264 profiles with ffprobe, not just decode censuses.

## 2026-10-03 evening: audio streams dropped (a + av)

AV/a producers never beat plain video in practice (0.5-2 fps rendered vs 5+),
so the audio path is retired end to end:

- go2rtc (backup `.bak-audiodrop`): only `catcam1v`/`catcam2v` exec producers;
  `catcam1a/2a` + `catcam1av/2av` and `/usr/src/catcam-av.sh` removed.
  API list confirms exactly `catcam1v/2v` (+ foreign streams).
- Relay: `/dev/<uid>/audio` returns 404 (falls to default NotFound); WAV
  header/silence/lead-in and audio subscriber plumbing removed. The cmd-G711
  branch still marks its pkgIDs as benign holes in the video window (the
  camera spends shared ids on audio regardless of consumers).
- Stats format: `(... viewers)` single count; frame/fps already fresh-only.

Verified: 13 unit tests + vet clean; live capture cam199 = 300 decoded parts /
12 s, fresh stats 1-3 fps (RF-limited, matches render); catcam1v probe High/yuv420p;
cam170 was idle during deploy (cams stop dialing after >5 min without a server;
wake them via MQTT code 299, see README operational notes).
