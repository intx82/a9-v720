package main

import (
	"encoding/json"
	"io"
	"net"
	"testing"
	"time"
)

// fakeCam wires a relay Device to an in-test camera TCP connection.
func fakeCam(t *testing.T) (*Device, net.Conn) {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { ln.Close() })
	accepted := make(chan *net.TCPConn, 1)
	go func() {
		c, err := ln.Accept()
		if err != nil {
			accepted <- nil
			return
		}
		accepted <- c.(*net.TCPConn)
	}()
	camSide, err := net.Dial("tcp", ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { camSide.Close() })
	srvSide := <-accepted
	if srvSide == nil {
		t.Fatal("accept failed")
	}
	tcpLn, udpConn := startListeners(t)
	s := NewServer(tcpLn, udpConn, "")
	d := &Device{srv: s, tcp: srvSide, uid: "UID1", camIP: "127.0.0.1", closeCh: make(chan struct{})}
	go d.tcpLoop()
	return d, camSide
}

// readForwardContent reads one relay->cam message and returns its forward content JSON.
func readForwardContent(t *testing.T, cam net.Conn) map[string]any {
	t.Helper()
	cam.SetReadDeadline(time.Now().Add(2 * time.Second))
	hdr := make([]byte, headerLen)
	if _, err := io.ReadFull(cam, hdr); err != nil {
		t.Fatalf("read header: %v", err)
	}
	plen := int(hdr[0]) | int(hdr[1])<<8 | int(hdr[2])<<16 | int(hdr[3])<<24
	body := make([]byte, plen)
	if _, err := io.ReadFull(cam, body); err != nil {
		t.Fatalf("read payload: %v", err)
	}
	m, err := decodeMessage(append(hdr, body...))
	if err != nil {
		t.Fatal(err)
	}
	var j struct {
		Code    int            `json:"code"`
		Content map[string]any `json:"content"`
	}
	if err := json.Unmarshal(m.payload, &j); err != nil {
		t.Fatalf("payload not forward json: %q", m.payload)
	}
	if j.Code != codeCmdForward {
		t.Fatalf("unexpected relay code %d in %q", j.Code, m.payload)
	}
	return j.Content
}

func camForward(cam net.Conn, content map[string]any) {
	cam.Write(jsonMessage(map[string]any{"code": codeCmdForward, "content": content}))
}

func contentCode(c map[string]any) int {
	if f, ok := c["code"].(float64); ok {
		return int(f)
	}
	return -1
}

func TestSpeedGradeLearnedAndEchoed(t *testing.T) {
	d, cam := fakeCam(t)

	camForward(cam, map[string]any{"code": codeFwdBaseInfo, "speedGrade": 1, "instLed": 1})
	if got := contentCode(readForwardContent(t, cam)); got != codeFwdOpenAOpenV {
		t.Fatalf("base info ack handled with code %d, want stream open", got)
	}

	camForward(cam, map[string]any{"code": codeFwdOpenAOpenV})
	c1 := readForwardContent(t, cam)
	if contentCode(c1) != codeSpeedGrade {
		t.Fatalf("after stream start relay sent content %v, want speed grade refresh", c1)
	}
	if g, _ := c1["speedGrade"].(float64); g != 1 {
		t.Fatalf("speed grade echo %v, want 1 (value learned from base info)", c1["speedGrade"])
	}
	d.mu.Lock()
	known, grade := d.gradeKnown, d.speedGrade
	d.mu.Unlock()
	if !known || grade != 1 {
		t.Fatalf("device stored grade %d known=%v, want 1 true", grade, known)
	}
}

func TestSpeedGradeUnknownNoEcho(t *testing.T) {
	d, cam := fakeCam(t)

	camForward(cam, map[string]any{"code": codeFwdBaseInfo, "instLed": 1})
	contentCode(readForwardContent(t, cam)) // drain stream open

	camForward(cam, map[string]any{"code": codeFwdOpenAOpenV})
	cam.SetReadDeadline(time.Now().Add(300 * time.Millisecond))
	buf := make([]byte, 4096)
	if n, err := cam.Read(buf); err == nil {
		m, derr := decodeMessage(buf[:n])
		if derr == nil {
			t.Fatalf("unexpected relay message with unknown grade: %q", m.payload)
		}
		t.Fatalf("unexpected relay bytes with unknown grade: %q", buf[:n])
	}

	camForward(cam, map[string]any{"code": codeSpeedGrade, "speedGrade": 2})
	deadline := time.Now().Add(2 * time.Second)
	for {
		d.mu.Lock()
		known, grade := d.gradeKnown, d.speedGrade
		d.mu.Unlock()
		if known && grade == 2 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("spontaneous 201 push: stored grade %d known=%v, want 2 true", grade, known)
		}
		time.Sleep(10 * time.Millisecond)
	}
}
