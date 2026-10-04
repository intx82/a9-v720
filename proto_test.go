package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"testing"
	"time"
)

func TestEncodeDecodeRoundtrip(t *testing.T) {
	payload := bytes.Repeat([]byte{0xAB}, 100)
	m := &message{payload: payload, cmd: cmdJPEG, msgFlag: flagEnd, pkgID: 1234}
	copy(m.forwardID[:], "00000000")
	raw := m.encode()
	if len(raw) != headerLen+100 {
		t.Fatalf("encoded length %d", len(raw))
	}
	got, err := decodeMessage(raw)
	if err != nil {
		t.Fatal(err)
	}
	if got.cmd != cmdJPEG || got.msgFlag != flagEnd || got.pkgID != 1234 {
		t.Fatalf("header mismatch: %+v", got)
	}
	if !bytes.Equal(got.payload, payload) {
		t.Fatal("payload mismatch")
	}
}

func TestDecodeShort(t *testing.T) {
	if _, err := decodeMessage(bytes.Repeat([]byte{0}, 19)); err == nil {
		t.Fatal("expected error for short message")
	}
}

func TestDecodePayloadTruncated(t *testing.T) {
	raw := make([]byte, headerLen+10)
	binary.LittleEndian.PutUint32(raw[0:4], 9999)
	m, err := decodeMessage(raw)
	if err != nil {
		t.Fatal(err)
	}
	if len(m.payload) != 10 {
		t.Fatalf("expected clamped payload, got %d", len(m.payload))
	}
}

func TestJSONMessageFraming(t *testing.T) {
	raw := jsonMessage(map[string]any{"code": 101, "status": 200})
	m, err := decodeMessage(raw)
	if err != nil || m.cmd != cmdJSON {
		t.Fatalf("bad json message: %v %v", m, err)
	}
	plen := binary.LittleEndian.Uint32(raw[0:4])
	if int(plen)+headerLen != len(raw) {
		t.Fatal("json message not self-framing")
	}
}

func newTestDevice() (*Device, *subscription) {
	d := &Device{
		srv:       &Server{},
		videoSubs: map[*subscription]bool{},
		closeCh:   make(chan struct{}),
	}
	s := &subscription{ch: make(chan []byte, 64)}
	d.videoSubs[s] = true
	return d, s
}

func jpegMsg(flag uint8, body []byte) *message {
	return &message{payload: body, cmd: cmdJPEG, msgFlag: flag}
}

func TestReassemblyCompleteFrame(t *testing.T) {
	d, s := newTestDevice()
	jpeg := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{1}, 500)...)
	jpeg = append(jpeg, 0xFF, 0xD9)

	d.reassembleVideo(jpegMsg(flagHead, jpeg[:100]))
	d.reassembleVideo(jpegMsg(flagBody, jpeg[100:300]))
	endBody := append([]byte(nil), jpeg[300:]...)
	trailer := make([]byte, 5)
	binary.LittleEndian.PutUint32(trailer[1:5], uint32(len(jpeg)))
	endBody = append(endBody, trailer...)
	d.reassembleVideo(jpegMsg(flagEnd, endBody))

	select {
	case frame := <-s.ch:
		if !bytes.Equal(frame, jpeg) {
			t.Fatalf("frame mismatch: got %d bytes", len(frame))
		}
	case <-time.After(time.Second):
		t.Fatal("no frame published")
	}
}

func TestReassemblyDropsIncomplete(t *testing.T) {
	d, s := newTestDevice()
	endBody := append([]byte{0x11, 0x22}, 0, 0, 0, 0, 0)
	binary.LittleEndian.PutUint32(endBody[len(endBody)-4:], 10000)
	d.reassembleVideo(jpegMsg(flagEnd, endBody))
	select {
	case f := <-s.ch:
		t.Fatalf("incomplete frame published: %d bytes", len(f))
	default:
	}
}

func TestReassemblyHeadResetsStale(t *testing.T) {
	d, s := newTestDevice()
	// stale body from a lost frame
	d.reassembleVideo(jpegMsg(flagBody, bytes.Repeat([]byte{0xEE}, 50)))
	// new frame starts with HEAD and ends with END
	fresh := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{7}, 58)...)
	fresh = append(fresh, 0xFF, 0xD9)
	d.reassembleVideo(jpegMsg(flagHead, fresh[:20]))
	endBody := append([]byte(nil), fresh[20:]...)
	trailer := make([]byte, 5)
	binary.LittleEndian.PutUint32(trailer[1:5], uint32(len(fresh)))
	endBody = append(endBody, trailer...)
	d.reassembleVideo(jpegMsg(flagEnd, endBody))
	select {
	case frame := <-s.ch:
		if !bytes.Equal(frame, fresh) {
			t.Fatal("HEAD frame polluted by stale data")
		}
	case <-time.After(time.Second):
		t.Fatal("frame after stale data not published")
	}
}

func TestReassemblySkipsTornFrameAfterLoss(t *testing.T) {
	d, s := newTestDevice()
	d.reassembleVideo(jpegMsg(flagHead, []byte{0xFF, 0xD8, 1, 2}))
	// middle of the frame lost, END arrives claiming a bigger size
	endBody := []byte{9, 9}
	trailer := make([]byte, 5)
	binary.LittleEndian.PutUint32(trailer[1:5], 4096)
	d.reassembleVideo(jpegMsg(flagEnd, append(endBody, trailer...)))
	select {
	case f := <-s.ch:
		t.Fatalf("torn frame published: %d bytes", len(f))
	default:
	}
	// next frame with HEAD must be clean
	fresh := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{5}, 28)...)
	fresh = append(fresh, 0xFF, 0xD9)
	d.reassembleVideo(jpegMsg(flagFinish, fresh))
	select {
	case frame := <-s.ch:
		if !bytes.Equal(frame, fresh) {
			t.Fatal("frame after loss polluted")
		}
	case <-time.After(time.Second):
		t.Fatal("frame after loss not published")
	}
}

func TestForwardMessageEnvelope(t *testing.T) {
	raw := forwardMessage(map[string]any{"code": codeFwdBaseInfo})
	m, err := decodeMessage(raw)
	if err != nil {
		t.Fatal(err)
	}
	if m.cmd != cmdJSON || m.dealFlag != 1 {
		t.Fatalf("envelope wrong: cmd=%d deal=%d", m.cmd, m.dealFlag)
	}
	var j struct {
		Code    int `json:"code"`
		Content struct {
			Code int `json:"code"`
		} `json:"content"`
	}
	if err := json.Unmarshal(m.payload, &j); err != nil {
		t.Fatal(err)
	}
	if j.Code != codeCmdForward || j.Content.Code != codeFwdBaseInfo {
		t.Fatalf("payload wrong: %+v", j)
	}
}

func TestForwardContentCode(t *testing.T) {
	cases := []struct {
		raw  string
		want int
		ok   bool
	}{
		{`{"code":4}`, 4, true},
		{`{"code":"3"}`, 3, true},
		{`{"code":"298"}`, 298, true},
		{`{"udpPlayBack":1,"code":4,"netInfo":"ab cd"}`, 4, true},
		{`{"code":4,"sdMoveMode":1,"name":"cam 01"}`, 4, true},
		{`{"status":200}`, 0, false},
		{``, 0, false},
	}
	for _, c := range cases {
		got, ok := forwardContentCode(json.RawMessage(c.raw))
		if got != c.want || ok != c.ok {
			t.Errorf("forwardContentCode(%s) = %d,%v want %d,%v", c.raw, got, ok, c.want, c.ok)
		}
	}
}

func idMsg(flag uint8, id uint32, body []byte) *message {
	m := jpegMsg(flag, body)
	m.pkgID = id
	return m
}

func endMsg(id uint32, body []byte, sz int) *message {
	trailer := make([]byte, 5)
	binary.LittleEndian.PutUint32(trailer[1:5], uint32(sz))
	return idMsg(flagEnd, id, append(append([]byte(nil), body...), trailer...))
}

func TestReassemblyFillsGapAfterEnd(t *testing.T) {
	d, s := newTestDevice()
	jpeg := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{3}, 398)...)
	jpeg = append(jpeg, 0xFF, 0xD9)
	d.reassembleVideo(idMsg(flagHead, 5, jpeg[:100]))
	d.reassembleVideo(idMsg(flagBody, 6, jpeg[100:200]))
	d.reassembleVideo(idMsg(flagBody, 8, jpeg[300:]))
	d.reassembleVideo(endMsg(9, []byte{}, len(jpeg)))
	select {
	case f := <-s.ch:
		t.Fatalf("gap frame published early: %d bytes", len(f))
	default:
	}
	d.reassembleVideo(idMsg(flagBody, 7, jpeg[200:300]))
	select {
	case frame := <-s.ch:
		if !bytes.Equal(frame, jpeg) {
			t.Fatalf("filled frame mismatch: got %d bytes, want %d", len(frame), len(jpeg))
		}
	case <-time.After(time.Second):
		t.Fatal("gap-filled frame not published")
	}
}

func TestReassemblyPendingExpires(t *testing.T) {
	d, s := newTestDevice()
	old := expireWindow
	expireWindow = 10 * time.Millisecond
	defer func() { expireWindow = old }()

	d.reassembleVideo(idMsg(flagHead, 5, []byte{0xFF, 0xD8, 1}))
	// id 6 lost forever; END at 7 closes an incomplete run
	d.reassembleVideo(endMsg(7, []byte{2}, 4096))
	time.Sleep(30 * time.Millisecond)

	fresh := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{9}, 38)...)
	fresh = append(fresh, 0xFF, 0xD9)
	d.reassembleVideo(idMsg(flagHead, 100, fresh[:20]))
	d.reassembleVideo(endMsg(101, fresh[20:], len(fresh)))
	select {
	case f := <-s.ch:
		if !bytes.Equal(f, fresh) {
			t.Fatalf("wrong frame published: %d bytes", len(f))
		}
	case <-time.After(time.Second):
		t.Fatal("frame after expiry not published")
	}
	// late retransmit of the expired frame must not resurrect it
	d.reassembleVideo(idMsg(flagBody, 6, []byte{7, 7}))
	select {
	case f := <-s.ch:
		t.Fatalf("expired frame resurrected: %d bytes", len(f))
	default:
	}
}

func TestReassemblyIgnoresDuplicateChunk(t *testing.T) {
	d, s := newTestDevice()
	jpeg := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{4}, 198)...)
	jpeg = append(jpeg, 0xFF, 0xD9)
	d.reassembleVideo(idMsg(flagHead, 5, jpeg[:100]))
	d.reassembleVideo(idMsg(flagBody, 6, jpeg[100:]))
	d.reassembleVideo(idMsg(flagBody, 6, jpeg[100:]))
	d.reassembleVideo(endMsg(7, []byte{}, len(jpeg)))
	select {
	case frame := <-s.ch:
		if !bytes.Equal(frame, jpeg) {
			t.Fatalf("duplicate inflated frame: got %d want %d", len(frame), len(jpeg))
		}
	case <-time.After(time.Second):
		t.Fatal("frame with duplicate chunk not published")
	}
}

func TestNewAttachReplaysLastFrame(t *testing.T) {
	d, s := newTestDevice()
	jpeg := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{5}, 198)...)
	jpeg = append(jpeg, 0xFF, 0xD9)
	d.reassembleVideo(idMsg(flagHead, 1, jpeg[:100]))
	d.reassembleVideo(endMsg(2, jpeg[100:], len(jpeg)))
	<-s.ch
	d.detach(s)
	s2 := d.attachVideo()
	select {
	case f := <-s2.ch:
		if !bytes.Equal(f, jpeg) {
			t.Fatalf("replayed frame mismatch: %d bytes", len(f))
		}
	default:
		t.Fatal("new attach did not receive cached frame")
	}
}

func mkFrame(fill byte, n int) []byte {
	f := append([]byte{0xFF, 0xD8}, bytes.Repeat([]byte{fill}, n-2)...)
	return append(f, 0xFF, 0xD9)
}

func TestReassemblySurvivesRetransmitStorm(t *testing.T) {
	d, s := newTestDevice()
	a := mkFrame(1, 500)
	b := mkFrame(2, 500)
	send := func(flag uint8, id uint32, data []byte, sz int) {
		if flag == flagEnd {
			d.reassembleVideo(endMsg(id, data, sz))
		} else {
			d.reassembleVideo(idMsg(flag, id, data))
		}
	}
	send(flagHead, 2, a[:100], 0)
	send(flagBody, 3, a[100:200], 0)
	send(flagBody, 4, a[200:300], 0)
	send(flagBody, 5, a[300:400], 0)
	send(flagEnd, 6, a[400:], len(a))

	send(flagHead, 7, b[:100], 0)
	send(flagBody, 8, b[100:200], 0)

	// stale full-frame retransmission of the already-published frame A
	send(flagHead, 2, a[:100], 0)
	send(flagBody, 3, a[100:200], 0)
	send(flagBody, 4, a[200:300], 0)
	send(flagBody, 5, a[300:400], 0)
	send(flagEnd, 6, a[400:], len(a))

	send(flagBody, 9, b[200:300], 0)
	send(flagEnd, 10, b[300:], len(b))

	select {
	case f := <-s.ch:
		if !bytes.Equal(f, a) {
			t.Fatalf("first frame wrong: %d bytes", len(f))
		}
	case <-time.After(time.Second):
		t.Fatal("frame A not published")
	}
	select {
	case f := <-s.ch:
		if !bytes.Equal(f, b) {
			t.Fatalf("frame B corrupted by storm: %d bytes", len(f))
		}
	case <-time.After(time.Second):
		t.Fatal("frame B not published intact")
	}
	select {
	case f := <-s.ch:
		t.Fatalf("stale retransmit produced extra frame: %d bytes", len(f))
	default:
	}
}
