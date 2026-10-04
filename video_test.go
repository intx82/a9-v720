package main

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestIdleStreamServesPlaceholder(t *testing.T) {
	d := &Device{
		srv:       &Server{},
		videoSubs: map[*subscription]bool{},
		closeCh:   make(chan struct{}),
	}
	var s Server
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.streamVideo(w, r, d)
	}))
	defer ts.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, "GET", ts.URL+"/dev/x/video", nil)
	if err != nil {
		t.Fatal(err)
	}
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
	select {
	case buf := <-readDone:
		t.Fatalf("stream ended early: %d bytes", len(buf))
	case <-time.After(4 * time.Second):
	}
	cancel()
	var buf []byte
	select {
	case buf = <-readDone:
	case <-time.After(2 * time.Second):
		t.Fatal("stream did not close after cancel")
	}
	if !bytes.Contains(buf, placeholderFrame) {
		t.Fatalf("no placeholder frame served while idle (%d bytes)", len(buf))
	}
}

func TestStatsFPSCountsFreshFramesOnly(t *testing.T) {
	st := streamStats{units: 33, fresh: 3, bytes: 33000}
	got := st.fps(3 * time.Second)
	if got != 1.0 {
		t.Fatalf("fps=%v, want fresh-rate 1.0 (not writes-rate 11)", got)
	}
}

func TestAudioEndpointRemoved(t *testing.T) {
	srv := &Server{devsByIP: map[string]*Device{}, devsByUID: map[string]*Device{}}
	d := &Device{srv: srv, uid: "AUD", videoSubs: map[*subscription]bool{}, closeCh: make(chan struct{})}
	srv.register(d)
	ts := httptest.NewServer(srv)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/dev/AUD/audio")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("GET /audio status %d, want 404 after audio drop", resp.StatusCode)
	}
}
