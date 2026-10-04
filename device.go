package main

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"io"
	"log"
	"net"
	"strconv"
	"sync"
	"time"
)

type subscription struct {
	ch chan []byte
}

type Device struct {
	srv     *Server
	tcp     *net.TCPConn
	tcpMu   sync.Mutex
	camIP   string
	camPort int

	uid      string
	dataPort int

	udpMu   sync.Mutex
	dataUDP *net.UDPAddr
	probed  bool

	listenCnt  int
	natRetries int
	streamUp   bool
	// speedGrade mirrors the camera's current quality profile
	// (0=VGA 1=HD 2=FHD), learned from base info / 201 pushes
	gradeKnown bool
	speedGrade int
	mu         sync.Mutex
	videoSubs  map[*subscription]bool
	lastFrame  []byte // most recent complete frame, replayed to new subscribers

	asmMu  sync.Mutex
	win    *window // id-keyed reassembly (app algorithm)
	curRaw []byte  // fallback assembly for senders without pkg ids

	idsMu    sync.Mutex
	pkgIDs   []uint32
	retrMu   sync.Mutex
	retrStop chan struct{}

	closed    bool
	closeCh   chan struct{}
	closeOnce sync.Once
}

func newDevice(s *Server, tcp *net.TCPConn, ip string, port int) *Device {
	return &Device{
		srv:       s,
		tcp:       tcp,
		camIP:     ip,
		camPort:   port,
		dataPort:  randomPort(),
		videoSubs: map[*subscription]bool{},
		closeCh:   make(chan struct{}),
	}
}

func (d *Device) tcpSend(data []byte) {
	d.tcpMu.Lock()
	defer d.tcpMu.Unlock()
	if d.tcp == nil {
		return
	}
	if _, err := d.tcp.Write(data); err != nil {
		log.Printf("%s: tcp send: %v", d.camIP, err)
	}
}

func (d *Device) tcpLoop() {
	r := bufio.NewReader(d.tcp)
	for {
		hdr := make([]byte, headerLen)
		if _, err := io.ReadFull(r, hdr); err != nil {
			log.Printf("%s: tcp closed: %v", d.camIP, err)
			d.disconnect()
			return
		}
		plen := int(binary.LittleEndian.Uint32(hdr[0:4]))
		if plen > 16*1024*1024 {
			log.Printf("%s: broken tcp framing (len=%d), dropping connection", d.camIP, plen)
			d.disconnect()
			return
		}
		body := make([]byte, headerLen+plen)
		copy(body, hdr)
		if plen > 0 {
			if _, err := io.ReadFull(r, body[headerLen:]); err != nil {
				log.Printf("%s: tcp closed: %v", d.camIP, err)
				d.disconnect()
				return
			}
		}
		m, err := decodeMessage(body)
		if err != nil {
			continue
		}
		d.handleTCP(m)
	}
}

func (d *Device) handleTCP(m *message) {
	switch m.cmd {
	case cmdHeartbeat:
		d.tcpSend(heartbeatMessage())

	case cmdJSON:
		var j struct {
			Code    int             `json:"code"`
			UID     string          `json:"uid"`
			Status  int             `json:"status"`
			Content json.RawMessage `json:"content"`
		}
		if err := json.Unmarshal(m.payload, &j); err != nil {
			return
		}
		switch j.Code {
		case codeRegReq:
			d.uid = j.UID
			log.Printf("%s: registered as %s", d.camIP, d.uid)
			d.tcpSend(jsonMessage(map[string]any{"code": codeRegRsp, "status": 200}))
			d.srv.register(d)

		case codeD2SNatRsp:
			log.Printf("%s: nat probe status: %d", d.camIP, j.Status)
			d.maybeRetryNat(j.Status)

		case codeCmdForward:
			if code, ok := forwardContentCode(j.Content); ok {
				d.handleForward(code, j.Content)
			}
		}
	}
}

// forwardContentCode extracts content.code from a forward-response payload.
// The camera sends it as a number or a decimal string.
func forwardContentCode(raw json.RawMessage) (int, bool) {
	var c struct {
		Code any `json:"code"`
	}
	if err := json.Unmarshal(raw, &c); err != nil {
		return 0, false
	}
	switch v := c.Code.(type) {
	case float64:
		return int(v), true
	case string:
		n, err := strconv.Atoi(v)
		return n, err == nil
	}
	return 0, false
}

// forwardContentGrade extracts content.speedGrade, sent by the camera in its
// base info response and in spontaneous code-201 quality-change pushes.
func forwardContentGrade(raw json.RawMessage) (int, bool) {
	var c struct {
		SpeedGrade *int `json:"speedGrade"`
	}
	if err := json.Unmarshal(raw, &c); err != nil || c.SpeedGrade == nil {
		return 0, false
	}
	return *c.SpeedGrade, true
}

func (d *Device) learnGrade(grade int) {
	d.mu.Lock()
	changed := !d.gradeKnown || d.speedGrade != grade
	d.gradeKnown = true
	d.speedGrade = grade
	d.mu.Unlock()
	if changed {
		log.Printf("%s: speed grade is now %d", d.camIP, grade)
	}
}

func (d *Device) handleForward(code int, content json.RawMessage) {
	switch code {
	case codeFwdBaseInfo:
		log.Printf("%s: base info received, opening stream", d.camIP)
		if grade, ok := forwardContentGrade(content); ok {
			d.learnGrade(grade)
		}
		d.sendForward(map[string]any{"code": codeFwdOpenAOpenV})
		d.startRetransmit()

	case codeSpeedGrade:
		if grade, ok := forwardContentGrade(content); ok {
			d.learnGrade(grade)
		}

	case codeFwdOpenAOpenV:
		log.Printf("%s: video streaming started", d.camIP)
		d.mu.Lock()
		d.streamUp = true
		grade, known := d.speedGrade, d.gradeKnown
		d.mu.Unlock()
		// the reference resets all retransmission/reassembly state when a
		// stream starts (setupRetransmission); pkg ids restart at 0 there
		d.resetReassembly()
		d.startRetransmit()
		if known {
			// echoing the camera's own grade back is the reference client's
			// escape hatch for a garbled stream: it forces a fresh encoder
			// (IDR) without changing the negotiated profile
			log.Printf("%s: refreshing stream via speed grade echo (%d)", d.camIP, grade)
			d.sendForward(map[string]any{"code": codeSpeedGrade, "speedGrade": grade})
		}

	case codeFwdClose:
		log.Printf("%s: video streaming stopped", d.camIP)
		d.stopRetransmit()
		d.resetReassembly()
	}
}

func (d *Device) sendForward(content map[string]any) {
	d.tcpSend(forwardMessage(content))
}

func (d *Device) dataChannelProbe(addr *net.UDPAddr) {
	d.udpMu.Lock()
	first := !d.probed
	d.dataUDP = addr
	d.probed = true
	d.udpMu.Unlock()

	if first {
		log.Printf("%s: device probing data channel, probing back", d.camIP)
		d.srv.udpSend(addr, jsonMessage(map[string]any{"code": codeC2DProbeReq}))
		return
	}
	log.Printf("%s: data channel ready, starting initial sequence", d.camIP)
	d.initialSequence()
}

func (d *Device) resetProbing() {
	d.udpMu.Lock()
	d.probed = false
	d.udpMu.Unlock()
}

func (d *Device) initialSequence() {
	d.tcpSend(jsonMessage(map[string]any{"code": codeS2DeviceStatus, "status": 1}))
	d.sendForward(map[string]any{"code": codeRetransmission})
	d.tcpSend(forwardMessage(map[string]any{
		"unixTimer": time.Now().Unix(),
		"code":      codeFwdBaseInfo,
	}))
}

func (d *Device) handleData(m *message) {
	d.idsMu.Lock()
	d.pkgIDs = append(d.pkgIDs, m.pkgID)
	d.idsMu.Unlock()

	switch m.cmd {
	case cmdJPEG:
		d.reassembleVideo(m)
	case cmdG711:
		// audio payloads are no longer delivered; the camera still spends
		// shared pkgIDs on them, so note the id as a benign reassembly hole
		// for the video window
		d.asmMu.Lock()
		var ready [][]byte
		if d.win != nil {
			ready = d.win.markAudio(m.pkgID)
		}
		d.asmMu.Unlock()
		d.deliver(ready)
	}
}

func (d *Device) reassembleVideo(m *message) {
	d.asmMu.Lock()
	var ready [][]byte
	if m.pkgID == 0 {
		ready = d.rawVideo(m)
	} else {
		if d.win == nil {
			d.win = newWindow()
		}
		ready = d.win.add(m.pkgID, m.msgFlag, m.payload, time.Now())
	}
	d.asmMu.Unlock()
	d.deliver(ready)
	d.startRetransmit()
}

// deliver validates assembled frames and hands them to the video consumers.
func (d *Device) deliver(ready [][]byte) {
	for _, f := range ready {
		if validJPEG(f) {
			d.mu.Lock()
			d.lastFrame = f
			d.mu.Unlock()
			d.publish(d.videoSubs, f)
		} else {
			log.Printf("%s: dropping invalid frame %d bytes", d.camIP, len(f))
		}
	}
}

// rawVideo assembles frames that carry no pkg ids (fallback path).
func (d *Device) rawVideo(m *message) [][]byte {
	switch m.msgFlag {
	case flagHead:
		d.curRaw = append([]byte(nil), m.payload...)
	case flagFinish:
		frame := append([]byte(nil), m.payload...)
		d.curRaw = nil
		return [][]byte{frame}
	case flagBody:
		d.curRaw = append(d.curRaw, m.payload...)
	case flagEnd:
		body := m.payload
		if len(body) >= 5 {
			d.curRaw = append(d.curRaw, body[:len(body)-5]...)
		}
		frame := d.curRaw
		d.curRaw = nil
		sz := 0
		if len(body) >= 5 {
			sz = int(binary.LittleEndian.Uint32(body[len(body)-4:]))
		}
		if len(frame) >= sz {
			return [][]byte{frame}
		}
		log.Printf("%s: dropping incomplete frame %d/%d", d.camIP, len(frame), sz)
	}
	return nil
}

func validJPEG(f []byte) bool {
	if len(f) < 4 || f[0] != 0xFF || f[1] != 0xD8 {
		return false
	}
	for i := len(f) - 4; i < len(f)-1; i++ {
		if f[i] == 0xFF && f[i+1] == 0xD9 {
			return true
		}
	}
	return false
}

func (d *Device) publish(subs map[*subscription]bool, data []byte) {
	d.mu.Lock()
	defer d.mu.Unlock()
	for s := range subs {
		select {
		case s.ch <- data:
		default:
			select {
			case <-s.ch:
			default:
			}
			select {
			case s.ch <- data:
			default:
			}
		}
	}
}

func (d *Device) attachVideo() *subscription {
	s := &subscription{ch: make(chan []byte, 64)}
	d.mu.Lock()
	d.videoSubs[s] = true
	if d.lastFrame != nil {
		s.ch <- d.lastFrame
	}
	d.mu.Unlock()
	d.capLive()
	return s
}

func (d *Device) detach(s *subscription) {
	d.mu.Lock()
	delete(d.videoSubs, s)
	d.mu.Unlock()
	d.capStop()
}

// viewers reports the number of live video stream consumers.
func (d *Device) viewers() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.videoSubs)
}

func (d *Device) capLive() {
	d.mu.Lock()
	first := d.listenCnt == 0
	d.listenCnt++
	if first {
		d.natRetries = 0
	}
	d.mu.Unlock()
	if first {
		log.Printf("%s: first listener, sending nat probe", d.camIP)
		d.sendNatProbe()
	}
}

func (d *Device) sendNatProbe() {
	d.tcpSend(jsonMessage(map[string]any{
		"code":       codeS2DNatReq,
		"cliTarget":  cliTarget,
		"cliToken":   "deadc0de",
		"cliIp":      "255.255.255.255",
		"cliPort":    0,
		"cliNatIp":   d.srv.ipFor(net.ParseIP(d.camIP)),
		"cliNatPort": d.srv.udpPort(),
	}))
}

// The camera answers the nat probe with status 500 when it is still
// tearing down a previous forward session; retry until it accepts.
func (d *Device) maybeRetryNat(status int) {
	d.mu.Lock()
	if status == 200 {
		d.natRetries = 0
		d.mu.Unlock()
		return
	}
	retry := d.listenCnt > 0 && !d.streamUp && d.natRetries < 10
	if retry {
		d.natRetries++
	}
	d.mu.Unlock()
	if !retry {
		return
	}
	go func() {
		select {
		case <-d.closeCh:
			return
		case <-time.After(time.Second):
		}
		d.mu.Lock()
		live := d.listenCnt > 0 && !d.streamUp
		d.mu.Unlock()
		if live {
			log.Printf("%s: retrying nat probe", d.camIP)
			d.sendNatProbe()
		}
	}()
}

func (d *Device) capStop() {
	d.mu.Lock()
	if d.listenCnt > 0 {
		d.listenCnt--
	}
	last := d.listenCnt == 0
	if last {
		d.streamUp = false
	}
	d.mu.Unlock()
	if !last {
		return
	}
	d.stopRetransmit()
	d.sendForward(map[string]any{"code": codeFwdClose})
}

func (d *Device) resetReassembly() {
	d.asmMu.Lock()
	d.win = nil
	d.curRaw = nil
	d.asmMu.Unlock()
	d.idsMu.Lock()
	d.pkgIDs = nil
	d.idsMu.Unlock()
}

func (d *Device) startRetransmit() {
	d.retrMu.Lock()
	defer d.retrMu.Unlock()
	if d.retrStop != nil {
		return
	}
	d.retrStop = make(chan struct{})
	stop := d.retrStop
	go func() {
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-stop:
				return
			case <-d.closeCh:
				return
			case <-ticker.C:
				d.idsMu.Lock()
				ids := d.pkgIDs
				d.pkgIDs = nil
				d.idsMu.Unlock()
				d.udpMu.Lock()
				addr := d.dataUDP
				d.udpMu.Unlock()
				if addr != nil {
					d.srv.retransmitConfirm(addr, ids)
				}
			}
		}
	}()
}

func (d *Device) stopRetransmit() {
	d.retrMu.Lock()
	defer d.retrMu.Unlock()
	if d.retrStop != nil {
		close(d.retrStop)
		d.retrStop = nil
	}
}

func (d *Device) disconnect() {
	d.closeOnce.Do(func() {
		close(d.closeCh)
	})
	d.srv.unregister(d)
	d.teardown()
}

func (d *Device) teardown() {
	d.stopRetransmit()
	d.tcp.Close()
	d.mu.Lock()
	for s := range d.videoSubs {
		close(s.ch)
		delete(d.videoSubs, s)
	}
	d.mu.Unlock()
}
