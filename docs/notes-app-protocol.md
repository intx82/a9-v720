# Naxclow app protocol findings (anti-garble mechanisms)

Source: `orig-app/com.naxclow.v720_source_from_JADX.zip` (JADX decompile of the
official app) + `resources/assets/apps/__UNI__B0F6577/www/pages/native/live.js`.

## How the official client avoids/fixes garbled video

1. **Never renders incomplete frames.** `NaxclowUdpRetransmissionHandle`
   delivers a run to the decoder only when the packet-id sequence is
   contiguous (`pkgId + i` check); incomplete runs simply never reach the
   codec. Stale runs are dropped when a newer HEAD arrives.
2. **Continuous NACK loop.** Every >=200 ms `sendPakId()` sends a `cmd 605`
   containing the *pending* ids (received-but-not-assembled, `VPakId ∪
   APakId`, sorted). 100 ms deadline per packet, 10 ms scheduler tick. Our
   relay's equivalent (100 ms ticker confirming all received ids,
   `startRetransmit`) is equal-or-better in practice — left unchanged.
   `CODE_RETRANSMISSION` (298) is **never** called by the app — retransmission
   is always active on the device.
3. **The escape hatch: code 201 `{"code":201,"speedGrade":N}`.** The device
   reports its current grade in the base-info response (top-level
   `speedGrade` field, alongside `instLed`, `IrLed`, `mirrorFlip`,
   `udpPlayBack`...) and pushes a standalone code-201 message on change.
   The UI grade popup sends the same JSON (`setDeviceVideoHD` /
   `reqSpeedGrade`). Switching grade restarts the encoder — a fresh IDR
   clears a garbled stream for good. `0=VGA(640x480) 1=HD(720p) 2=FHD`.
4. Every stream open is preceded by base-info; the app then always sends
   `setLiveStreamMode mode:3` (codes: 0=close/close, 1=open-audio-only,
   2=video-only, 3=open both).

## Ported into the relay (2026-10-03)

- `device.go` learns `speedGrade` from the code-4 base-info response and from
  spontaneous 201 pushes (`learnGrade`, guarded by `d.mu`).
- On a stream-open ack (`codeFwdOpenAOpenV`) the relay echoes the camera's
  own current grade back (`{"code":201,"speedGrade":N}`) — same-value echo
  forces the encoder restart/IDR without changing the negotiated profile.
  Skipped when the grade was never learned.
- Tests: `grade_test.go` (learn + echo, unknown-grade silence, spontaneous
  201 learning). Both cams report grade 1; live 2x20 s decode census after
  deploy: zero decode errors, cam170 500 frames/20 s, cam199 RF-limited as
  usual.

## Command map (forward content codes)

0/1/2/3 stream modes, 4 baseinfo, 201 speedGrade, 202 IrLed, 203 sdcard
mode, 204 wifi, 205/206 move alert/grade, 207 format, 208 AP mode, 210
inst-led, 211 wifi scan, 212 motor, 216 flip, 217 speedControl, 218 sdcard
status, 219 RF433, 220 LED_EI, 221 AP pwd, 298 retransmission ctrl, 299
reboot, 301 CMD_FORWARD wrapper. cmd types: 0=JSON 1=JPEG 3=AAC 4=G711
5=RAW 6=PCM 7=AVI 8=XML 100=HB 101/102=ping/pong; flags 0xFA HEAD 0xFB BODY
0xFC END 0xFF FINISH.
