package main

import (
	"encoding/binary"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type confCheck struct {
	Code int `json:"code"`
	Data struct {
		TCPPort int    `json:"tcpPort"`
		Host    string `json:"host"`
	} `json:"data"`
}

func startListeners(t *testing.T) (net.Listener, *net.UDPConn) {
	t.Helper()
	tcpLn, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { tcpLn.Close() })
	udpAddr, err := net.ResolveUDPAddr("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	udpConn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { udpConn.Close() })
	return tcpLn, udpConn
}

func TestDevCmdForward(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
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
	defer camSide.Close()
	srvSide := <-accepted
	if srvSide == nil {
		t.Fatal("accept failed")
	}
	defer srvSide.Close()

	tcpLn, udpConn := startListeners(t)
	s := NewServer(tcpLn, udpConn, "")
	d := &Device{srv: s, tcp: srvSide, uid: "UID1", camIP: "127.0.0.1"}
	s.register(d)

	ts := httptest.NewServer(s)
	defer ts.Close()
	resp, err := http.Post(ts.URL+"/dev/UID1/cmd", "application/json",
		strings.NewReader(`{"code":205,"moveAlert":0}`))
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 || !strings.Contains(string(body), "200") {
		t.Fatalf("cmd endpoint: %d %q", resp.StatusCode, body)
	}

	camSide.SetReadDeadline(time.Now().Add(2 * time.Second))
	raw := make([]byte, 4096)
	n, err := camSide.Read(raw)
	if err != nil {
		t.Fatal(err)
	}
	m, err := decodeMessage(raw[:n])
	if err != nil {
		t.Fatal(err)
	}
	var f struct {
		Code    int            `json:"code"`
		Content map[string]any `json:"content"`
	}
	if err := json.Unmarshal(m.payload, &f); err != nil {
		t.Fatalf("forward payload %q: %v", m.payload, err)
	}
	if f.Content["code"] != float64(205) || f.Content["moveAlert"] != float64(0) {
		t.Fatalf("forwarded content = %v", f.Content)
	}
}

func fetchConfCheck(t *testing.T, srv *Server) (confCheck, []byte) {
	t.Helper()
	ts := httptest.NewServer(srv)
	t.Cleanup(ts.Close)
	resp, err := http.Post(ts.URL+"/app/api/ApiServer/getA9ConfCheck", "text/plain", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	var cc confCheck
	if err := json.Unmarshal(body, &cc); err != nil {
		t.Fatalf("confcheck body is not clean JSON: %v (%q)", err, body)
	}
	return cc, body
}

func TestConfCheckUsesRealTCPPortAndRoutedHost(t *testing.T) {
	tcpLn, udpConn := startListeners(t)
	srv := NewServer(tcpLn, udpConn, "")
	cc, body := fetchConfCheck(t, srv)
	if want := tcpLn.Addr().(*net.TCPAddr).Port; cc.Data.TCPPort != want {
		t.Errorf("tcpPort = %d, want listener port %d", cc.Data.TCPPort, want)
	}
	if cc.Data.Host != "127.0.0.1" {
		t.Errorf("host = %q, want 127.0.0.1 (routed to the camera peer)", cc.Data.Host)
	}
	if n := len(body); n == 0 || body[n-1] == ' ' {
		t.Errorf("confcheck body must not be padded: %q", body[n-2:])
	}
}

func TestConfCheckServerIPOverride(t *testing.T) {
	tcpLn, udpConn := startListeners(t)
	srv := NewServer(tcpLn, udpConn, "203.0.113.9")
	cc, _ := fetchConfCheck(t, srv)
	if cc.Data.Host != "203.0.113.9" {
		t.Errorf("host = %q, want override 203.0.113.9", cc.Data.Host)
	}
}

func TestConfCheckUsesXRealIPBehindProxy(t *testing.T) {
	tcpLn, udpConn := startListeners(t)
	srv := NewServer(tcpLn, udpConn, "")
	ts := httptest.NewServer(srv)
	t.Cleanup(ts.Close)
	req, err := http.NewRequest(http.MethodPost, ts.URL+"/app/api/ApiServer/getA9ConfCheck", nil)
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("X-Real-IP", "10.0.0.170")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	var cc confCheck
	if err := json.Unmarshal(body, &cc); err != nil {
		t.Fatal(err)
	}
	if cc.Data.Host == "127.0.0.1" || cc.Data.Host == "" {
		t.Errorf("host = %q, want address routed to the X-Real-IP peer, not the proxy", cc.Data.Host)
	}
}

func TestNatProbeAdvertisesRealUDPPort(t *testing.T) {
	tcpLn, udpConn := startListeners(t)
	srv := NewServer(tcpLn, udpConn, "")

	cli, err := net.Dial("tcp", tcpLn.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	defer cli.Close()
	accepted, err := tcpLn.Accept()
	if err != nil {
		t.Fatal(err)
	}
	defer accepted.Close()

	d := newDevice(srv, accepted.(*net.TCPConn), "127.0.0.1", 1234)
	d.sendNatProbe()

	cli.SetReadDeadline(time.Now().Add(2 * time.Second))
	hdr := make([]byte, headerLen)
	if _, err := io.ReadFull(cli, hdr); err != nil {
		t.Fatal(err)
	}
	body := make([]byte, headerLen+int(binary.LittleEndian.Uint32(hdr[0:4])))
	copy(body, hdr)
	if _, err := io.ReadFull(cli, body[headerLen:]); err != nil {
		t.Fatal(err)
	}
	m, err := decodeMessage(body)
	if err != nil {
		t.Fatal(err)
	}
	var probe map[string]any
	if err := json.Unmarshal(m.payload, &probe); err != nil {
		t.Fatal(err)
	}
	if want := udpConn.LocalAddr().(*net.UDPAddr).Port; int(probe["cliNatPort"].(float64)) != want {
		t.Errorf("cliNatPort = %v, want udp listener port %d", probe["cliNatPort"], want)
	}
	if probe["cliNatIp"] != "127.0.0.1" {
		t.Errorf("cliNatIp = %v, want 127.0.0.1", probe["cliNatIp"])
	}
}

func TestViewerCounts(t *testing.T) {
	d, _ := newTestDevice()
	if v, a := d.viewers(); v != 1 || a != 0 {
		t.Fatalf("initial viewers = %d,%d, want 1,0", v, a)
	}
	s := d.attachVideo()
	if v, _ := d.viewers(); v != 2 {
		t.Errorf("after attach viewers = %d, want 2", v)
	}
	d.detach(s)
	if v, _ := d.viewers(); v != 1 {
		t.Errorf("after detach viewers = %d, want 1", v)
	}
}
