package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func newAVDevice() *Device {
	return &Device{
		videoSubs: map[*subscription]bool{},
		audioSubs: map[*subscription]bool{},
		closeCh:   make(chan struct{}),
	}
}

func dataMsg(cmd uint16, flag uint8, id uint32, payload []byte) *message {
	return &message{cmd: cmd, msgFlag: flag, pkgID: id, payload: payload}
}

func jpegFrame(fill byte, n int) []byte {
	f := bytes.Repeat([]byte{fill}, n)
	f[0], f[1] = 0xFF, 0xD8
	f[len(f)-2], f[len(f)-1] = 0xFF, 0xD9
	return f
}

// trailer is the 5-byte END packet payload: 1 pad byte + LE frame size.
func trailer(size int) []byte {
	t := make([]byte, 5)
	binary.LittleEndian.PutUint32(t[1:5], uint32(size))
	return t
}

func TestAudioRawForwarding(t *testing.T) {
	d := newAVDevice()
	sub := &subscription{ch: make(chan []byte, 256)}
	d.mu.Lock()
	d.audioSubs[sub] = true
	d.mu.Unlock()

	payload := bytes.Repeat([]byte{0xAA}, 800)
	d.handleData(dataMsg(cmdG711, flagFinish, 1000, payload))
	select {
	case got := <-sub.ch:
		if !bytes.Equal(got, payload) {
			t.Fatalf("got %d audio bytes, want 800 raw (no trailer strip)", len(got))
		}
	case <-time.After(time.Second):
		t.Fatal("no audio delivered")
	}

	d.handleData(dataMsg(cmdG711, flagBody, 1001, []byte("xyz")))
	select {
	case got := <-sub.ch:
		if string(got) != "xyz" {
			t.Fatalf("got %q, want raw xyz", got)
		}
	case <-time.After(time.Second):
		t.Fatal("non-FINISH audio packet not forwarded")
	}
}

func TestAudioNoSilenceWhileFlowing(t *testing.T) {
	old := audioIdleGrace
	audioIdleGrace = 300 * time.Millisecond
	defer func() { audioIdleGrace = old }()

	d := newAVDevice()
	var s Server
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.streamAudio(w, r, d)
	}))
	defer ts.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, ts.URL+"/audio", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	readDone := make(chan []byte, 1)
	go func() {
		buf, _ := io.ReadAll(resp.Body)
		readDone <- buf
	}()

	chunk := bytes.Repeat([]byte{0xAA}, 800)
	deadline := time.Now().Add(6 * time.Second)
	for time.Now().Before(deadline) {
		d.publish(d.audioSubs, chunk)
		time.Sleep(200 * time.Millisecond)
	}
	cancel()
	buf := <-readDone
	if i := bytes.IndexByte(buf[len(wavHDR)+len(audioLead):], 0xD5); i >= 0 {
		t.Fatalf("silence injected at offset %d while real audio was flowing", i)
	}
}

func TestAudioLeadInSilence(t *testing.T) {
	d := newAVDevice()
	var s Server
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.streamAudio(w, r, d)
	}))
	defer ts.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, http.MethodGet, ts.URL+"/audio", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()

	type res struct {
		buf []byte
		err error
	}
	done := make(chan res, 1)
	go func() {
		buf := make([]byte, len(wavHDR)+len(audioLead))
		_, err := io.ReadFull(resp.Body, buf)
		done <- res{buf, err}
	}()
	select {
	case r := <-done:
		if r.err != nil {
			t.Fatalf("lead-in not delivered promptly: %v", r.err)
		}
		if !bytes.Equal(r.buf[:len(wavHDR)], []byte(wavHDR)) {
			t.Fatal("missing WAV header")
		}
		if !bytes.Equal(r.buf[len(wavHDR):], audioLead) {
			t.Fatal("lead-in after header is not A-law silence")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("no lead-in bytes before first camera chunk")
	}
}

func sendVideoFrame(d *Device, start uint32, frame []byte) {
	id := start
	d.handleData(dataMsg(cmdJPEG, flagHead, id, frame[:400]))
	for i := 400; i < len(frame); i += 200 {
		id++
		d.handleData(dataMsg(cmdJPEG, flagBody, id, frame[i:min(i+200, len(frame))]))
	}
	id++
	d.handleData(dataMsg(cmdJPEG, flagEnd, id, trailer(len(frame))))
}

func TestReassemblyResetAcrossSessions(t *testing.T) {
	d := newAVDevice()
	sub := &subscription{ch: make(chan []byte, 64)}
	d.mu.Lock()
	d.videoSubs[sub] = true
	d.mu.Unlock()

	sendVideoFrame(d, 1, jpegFrame(0x11, 4000))
	if d.lastFrame == nil {
		t.Fatal("session 1 frame never assembled")
	}
	d.handleForward(codeFwdClose, nil)
	d.handleForward(codeFwdOpenAOpenV, nil)

	sendVideoFrame(d, 1, jpegFrame(0x22, 4000))
	if d.lastFrame == nil || d.lastFrame[2] != 0x22 {
		t.Fatalf("session 2 frame dropped after id restart (last=%v)", d.lastFrame)
	}
}

func TestAudioIDBenignHole(t *testing.T) {
	w := newWindow()
	frame := jpegFrame(0x33, 4000)
	w.markAudio(2) // packet 2 carried audio on the shared id sequence
	w.add(1, flagHead, frame[:400], time.Now())
	w.add(3, flagBody, frame[400:800], time.Now())
	if got := w.add(4, flagBody, frame[800:], time.Now()); got != nil {
		t.Fatalf("frame completed before END")
	}
	got := w.add(5, flagEnd, trailer(len(frame)), time.Now())
	if len(got) != 1 || !bytes.Equal(got[0], frame) {
		t.Fatalf("frame not assembled across audio-owned hole: %d frames", len(got))
	}
}

func TestGarbageNeverBecomesLastFrame(t *testing.T) {
	d := newAVDevice()
	sub := &subscription{ch: make(chan []byte, 64)}
	d.mu.Lock()
	d.videoSubs[sub] = true
	d.mu.Unlock()

	sendVideoFrame(d, 1, jpegFrame(0x44, 4000))
	if d.lastFrame == nil {
		t.Fatal("good frame not accepted")
	}
	good := d.lastFrame
	select {
	case <-sub.ch:
	default:
		t.Fatal("good frame not published")
	}

	// frame that passes SOI but lost its EOI (truncated garbage)
	trunc := jpegFrame(0x55, 4000)
	trunc[len(trunc)-2] = 0x00
	d.handleData(dataMsg(cmdJPEG, flagHead, 100, trunc[:400]))
	d.handleData(dataMsg(cmdJPEG, flagEnd, 101, trailer(len(trunc))))
	if !bytes.Equal(d.lastFrame, good) {
		t.Fatal("frame without EOI accepted as lastFrame")
	}
	select {
	case f := <-sub.ch:
		t.Fatalf("frame without EOI published (%d bytes)", len(f))
	default:
	}

	// frame shorter than its END-declared size
	short := jpegFrame(0x66, 2000)
	d.handleData(dataMsg(cmdJPEG, flagHead, 200, short[:400]))
	d.handleData(dataMsg(cmdJPEG, flagEnd, 201, trailer(4000)))
	if !bytes.Equal(d.lastFrame, good) {
		t.Fatal("undersized frame accepted as lastFrame")
	}
}
