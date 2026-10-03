package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"
)

const wavHDR = "RIFF\x8a\xdc\x01\x00WAVEfmt \x12\x00\x00\x00\x06\x00\x01\x00@\x1f\x00\x00@\x1f\x00\x00\x01\x00\x08\x00\x00\x00fact\x04\x00\x00\x006\xdc\x01\x00LIST\x1a\x00\x00\x00INFOISFT\x0e\x00\x00\x00Lavf58.45.100\x00data\xff\xff\xff\xff"

var audioSilence = []byte(strings.Repeat("\xd5", 800))

// audioLead is written to every audio consumer immediately after the WAV
// header so downstream ffmpeg gets a packet before the camera's 1-3 s audio
// start-up; without it go2rtc's RTSP ANNOUNCE is late and mix DESCRIBEs
// race to a video-only SDP.
var audioLead = []byte(strings.Repeat("\xd5", 1600))

// audioIdleGrace is how long the audio stream must stay quiet before the
// keepalive starts padding it with silence chunks.
var audioIdleGrace = time.Second

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		if strings.HasPrefix(r.URL.Path, "/dev/") {
			s.postDevCmd(w, r)
			return
		}
		s.postAPI(w, r)
		return
	}
	switch {
	case strings.HasPrefix(r.URL.Path, "/dev/list"):
		lst, _ := json.Marshal(s.deviceList())
		w.Header().Set("Content-Type", "application/json")
		w.Write(lst)
		return
	case strings.HasPrefix(r.URL.Path, "/dev/"):
		parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
		if len(parts) != 3 || parts[0] != "dev" {
			http.NotFound(w, r)
			return
		}
		dev := s.deviceByUID(parts[1])
		if dev == nil {
			http.NotFound(w, r)
			return
		}
		switch parts[2] {
		case "live", "video":
			s.streamVideo(w, r, dev)
		case "audio":
			s.streamAudio(w, r, dev)
		case "snapshot":
			s.snapshot(w, dev)
		default:
			http.NotFound(w, r)
		}
		return
	default:
		http.NotFound(w, r)
	}
}

// streamStats accumulates payload units/bytes for one stream consumer
// between 5-second stat reports.
type streamStats struct {
	units int64
	bytes int64
	from  time.Time
}

func (st *streamStats) add(n int) {
	st.units++
	st.bytes += int64(n)
}

func (s *Server) streamVideo(w http.ResponseWriter, r *http.Request, d *Device) {
	rc := http.NewResponseController(w)
	w.Header().Set("Content-Type", "multipart/x-mixed-replace; boundary=\"jpgboundary\"")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Pragma", "no-cache")
	w.WriteHeader(200)
	rc.Flush()

	sub := d.attachVideo()
	defer d.detach(sub)
	start := time.Now()
	st := streamStats{from: time.Now()}
	tick := time.NewTicker(5 * time.Second)
	defer tick.Stop()
	v, a := d.viewers()
	log.Printf("%s: video viewer connected (%d video, %d audio)", d.uid, v, a)
	defer func() {
		log.Printf("%s: video viewer left after %v: %d frames, %d B", d.uid, time.Since(start).Round(time.Second), st.units, st.bytes)
	}()

	const partHeader = "--jpgboundary\r\nContent-type: image/jpeg\r\n\r\n"
	if _, err := w.Write([]byte(partHeader)); err != nil {
		return
	}
	rc.Flush()
	// keep the stream alive: whenever the camera goes quiet (nightly
	// motion-gating), re-emit the last frame - or a gray placeholder when
	// no frame has ever arrived - so downstream producers never idle out.
	timer := time.NewTimer(1 * time.Second)
	defer timer.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-d.closeCh:
			return
		case frame, ok := <-sub.ch:
			if !ok {
				return
			}
			n, err := w.Write(frame)
			st.add(n)
			if err != nil {
				return
			}
			if _, err := w.Write([]byte("\r\n" + partHeader)); err != nil {
				return
			}
			rc.Flush()
			timer.Reset(100 * time.Millisecond)
		case <-timer.C:
			f := d.latestFrame()
			n, err := w.Write(f)
			st.add(n)
			if err != nil {
				return
			}
			if _, err := w.Write([]byte("\r\n" + partHeader)); err != nil {
				return
			}
			rc.Flush()
			timer.Reset(100 * time.Millisecond)
		case <-tick.C:
			el := time.Since(st.from)
			v, a := d.viewers()
			log.Printf("%s: video viewer stats: %d frames, %.1f fps, %.0f KB/s (%d video, %d audio viewers)",
				d.uid, st.units, float64(st.units)/el.Seconds(), float64(st.bytes)/el.Seconds()/1024, v, a)
			st = streamStats{from: time.Now()}
		}
	}
}

func (s *Server) streamAudio(w http.ResponseWriter, r *http.Request, d *Device) {
	rc := http.NewResponseController(w)
	w.Header().Set("Content-Type", "audio/wav")
	w.Header().Set("Connection", "close")
	w.Header().Set("Pragma", "no-cache")
	w.WriteHeader(200)
	w.Write([]byte(wavHDR))
	w.Write(audioLead)
	rc.Flush()

	sub := d.attachAudio()
	defer d.detach(sub)
	start := time.Now()
	st := streamStats{from: time.Now()}
	tick := time.NewTicker(5 * time.Second)
	defer tick.Stop()
	v, a := d.viewers()
	log.Printf("%s: audio viewer connected (%d video, %d audio)", d.uid, v, a)
	defer func() {
		log.Printf("%s: audio viewer left after %v: %d chunks, %d B", d.uid, time.Since(start).Round(time.Second), st.units, st.bytes)
	}()

	// real chunks flow at ~10/s; only start padding with A-law silence
	// once the camera has been quiet for audioIdleGrace, so a jittery but
	// continuous stream is never interleaved with filler (clicks/stutter).
	last := time.Now()
	timer := time.NewTimer(audioIdleGrace)
	defer timer.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-d.closeCh:
			return
		case frame, ok := <-sub.ch:
			if !ok {
				return
			}
			n, err := w.Write(frame)
			st.add(n)
			if err != nil {
				return
			}
			rc.Flush()
			last = time.Now()
			timer.Reset(audioIdleGrace)
		case <-timer.C:
			if since := time.Since(last); since >= audioIdleGrace {
				// pad at realtime cadence while the camera is quiet
				n, err := w.Write(audioSilence)
				st.add(n)
				if err != nil {
					return
				}
				rc.Flush()
				timer.Reset(100 * time.Millisecond)
			} else {
				timer.Reset(audioIdleGrace - since)
			}
		case <-tick.C:
			el := time.Since(st.from)
			v, a := d.viewers()
			log.Printf("%s: audio viewer stats: %d chunks, %.0f B/s (%d video, %d audio viewers)",
				d.uid, st.units, float64(st.bytes)/el.Seconds(), v, a)
			st = streamStats{from: time.Now()}
		}
	}
}

func (s *Server) snapshot(w http.ResponseWriter, d *Device) {
	sub := d.attachVideo()
	defer d.detach(sub)

	select {
	case <-d.closeCh:
		http.Error(w, "device gone", http.StatusGatewayTimeout)
	case frame, ok := <-sub.ch:
		if !ok {
			http.Error(w, "device gone", http.StatusGatewayTimeout)
			return
		}
		w.Header().Set("Content-Type", "image/jpeg")
		w.Header().Set("Content-Length", strconv.Itoa(len(frame)))
		w.Write(frame)
	case <-time.After(5 * time.Second):
		http.Error(w, "Camera request timeout", http.StatusGatewayTimeout)
	}
}

// postDevCmd injects a raw forward command into a camera's TCP control
// session: POST /dev/<uid>/cmd with body {"code":N, ...}. The camera's
// replies arrive as forward responses on the same session.
func (s *Server) postDevCmd(w http.ResponseWriter, r *http.Request) {
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if len(parts) != 3 || parts[0] != "dev" {
		http.NotFound(w, r)
		return
	}
	dev := s.deviceByUID(parts[1])
	if dev == nil {
		http.NotFound(w, r)
		return
	}
	var content map[string]any
	if err := json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&content); err != nil {
		http.Error(w, "bad json: "+err.Error(), http.StatusBadRequest)
		return
	}
	if _, ok := content["code"]; !ok {
		http.Error(w, "missing code", http.StatusBadRequest)
		return
	}
	log.Printf("%s: forward cmd %v", dev.camIP, content)
	dev.sendForward(content)
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"code":200}`))
}

func (s *Server) postAPI(w http.ResponseWriter, r *http.Request) {
	// Cameras reach this API through the nginx sinkhole on :80, so
	// RemoteAddr is the proxy; X-Real-IP carries the camera's address.
	peerIP, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		peerIP = r.RemoteAddr
	}
	if x := r.Header.Get("X-Real-IP"); x != "" {
		peerIP = x
	}
	w.Header().Set("Content-Type", "application/json")
	var ret any
	switch {
	case strings.HasPrefix(r.URL.Path, "/app/api/ApiAlertRecord/a9SendAlertV3"):
		r.ParseForm()
		log.Printf("alert report from %s (uid %s)", peerIP, r.Form.Get("devicesCode"))
		ret = map[string]any{"code": 200, "message": "OK", "data": nil}
	case strings.HasPrefix(r.URL.Path, "/app/api/ApiSysDevicesBatch/registerDevices"):
		ret = map[string]any{"code": 200, "message": "OK", "data": fmt.Sprintf("0800c00%05d", time.Now().UnixNano()%100000)}
	case strings.HasPrefix(r.URL.Path, "/app/api/ApiSysDevicesBatch/confirm"),
		strings.HasPrefix(r.URL.Path, "/app/api/ApiSysDevices/a9bindingAppDevice"):
		ret = map[string]any{"code": 200, "message": "OK", "data": nil}
	case strings.HasPrefix(r.URL.Path, "/app/api/ApiSysDevices/getDevInfo"):
		ret = map[string]any{"code": 200, "message": "OK", "data": map[string]any{"userInfo_state": 1}}
	case strings.HasPrefix(r.URL.Path, "/app/api/ApiServer/getA9ConfCheck"):
		uid := fmt.Sprintf("%05d", time.Now().UnixNano()%100000)
		for k, vs := range r.URL.Query() {
			if k == "devicesCode" && len(vs) > 0 && vs[0] != "" {
				uid = vs[0]
			}
		}
		ret = map[string]any{"code": 200, "message": "OK", "data": map[string]any{
			"tcpPort":   s.tcpPort,
			"uid":       uid,
			"isBind":    "8",
			"domain":    "v720.naxclow.com",
			"updateUrl": nil,
			"host":      s.ipFor(net.ParseIP(peerIP)),
			"currTime":  fmt.Sprintf("%d", time.Now().Unix()),
			"pwd":       "deadbeef",
			"version":   nil,
		}}
	default:
		io.Copy(io.Discard, r.Body)
		log.Printf("unknown POST %s", r.URL.Path)
		http.NotFound(w, r)
		return
	}
	body, _ := json.Marshal(ret)
	w.Write(body)
}
