# Changelog

## 2026-10-04 — browser chroma fix, fresh-frame stats, audio retirement (f91bd78)

- Forced `-pix_fmt yuv420p` on go2rtc exec producers (catcam1v/catcam2v) so browsers
  get H.264 High/4:2:0 instead of High 4:2:2 mosaic/green output (cams' JPEGs decode
  to yuvj422p); verified with ffprobe profile + pix_fmt.
- Relay stats now count only fresh frames: `streamStats.fresh` incremented solely on
  new-frame delivery (`st.fresh` in http.go); keepalive-replay writes no longer inflate
  fps (log now shows truthful 1.0-2.6 fps on cam199).
- Speed-grade mechanism: relay learns `speedGrade` from code-4 baseinfo and echoes
  `{"code":201,"speedGrade":N}` on stream-open to force a fresh IDR; echo skipped when
  grade unknown (device.go, proto.go, grade_test.go).
- Audio path retired per operator decision (AV/a streams rendered at 0.5-2 fps):
  `/dev/<uid>/audio` returns 404; streamAudio/WAV/silence helpers removed; go2rtc
  trimmed to video-only producers; cmdG711 branch keeps hole-marking so video window
  assembly stays protected.
- docs/notes-app-protocol.md added; docs/notes-av-breakage-fix.md extended with the
  evening block (chroma verification + audio retirement rationale).
