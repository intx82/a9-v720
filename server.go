package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net"
	"sync"
)

const cliTarget = "00112233445566778899aabbccddeeff"

type Server struct {
	tcpPort  int
	udpConn  *net.UDPConn
	serverIP string

	mu        sync.Mutex
	devsByIP  map[string]*Device
	devsByUID map[string]*Device
}

func NewServer(tcpLn net.Listener, udpConn *net.UDPConn, serverIP string) *Server {
	tcpPort := 0
	if ta, ok := tcpLn.Addr().(*net.TCPAddr); ok {
		tcpPort = ta.Port
	}
	return &Server{
		tcpPort:   tcpPort,
		udpConn:   udpConn,
		serverIP:  serverIP,
		devsByIP:  map[string]*Device{},
		devsByUID: map[string]*Device{},
	}
}

// udpPort reports the UDP port cameras send their data to.
func (s *Server) udpPort() int {
	if s.udpConn == nil {
		return 0
	}
	if ua, ok := s.udpConn.LocalAddr().(*net.UDPAddr); ok {
		return ua.Port
	}
	return 0
}

// ipFor reports the address cameras should reach us on: an explicit
// -server-ip/SERVER_IP override, else the source address routing to the
// camera would use.
func (s *Server) ipFor(remote net.IP) string {
	if s.serverIP != "" {
		return s.serverIP
	}
	return localIPFor(remote)
}

func (s *Server) register(d *Device) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if old, ok := s.devsByIP[d.camIP]; ok && old != d {
		old.teardown()
		delete(s.devsByUID, old.uid)
	}
	s.devsByIP[d.camIP] = d
	if d.uid != "" {
		s.devsByUID[d.uid] = d
	}
}

func (s *Server) unregister(d *Device) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if cur, ok := s.devsByIP[d.camIP]; ok && cur == d {
		delete(s.devsByIP, d.camIP)
	}
	if cur, ok := s.devsByUID[d.uid]; ok && cur == d {
		delete(s.devsByUID, d.uid)
	}
}

func (s *Server) deviceByIP(ip string) *Device {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.devsByIP[ip]
}

func (s *Server) deviceByUID(uid string) *Device {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.devsByUID[uid]
}

func (s *Server) deviceList() []map[string]any {
	s.mu.Lock()
	defer s.mu.Unlock()
	lst := []map[string]any{}
	for _, d := range s.devsByUID {
		lst = append(lst, map[string]any{
			"host": d.camIP,
			"port": d.camPort,
			"uid":  d.uid,
		})
	}
	return lst
}

func (s *Server) ServeTCP(ln net.Listener) {
	for {
		conn, err := ln.Accept()
		if err != nil {
			log.Printf("tcp accept: %v", err)
			return
		}
		tcp := conn.(*net.TCPConn)
		tcp.SetKeepAlive(true)
		tcp.SetKeepAlivePeriod(30e9)
		host, portStr, _ := net.SplitHostPort(conn.RemoteAddr().String())
		port := 0
		fmt.Sscanf(portStr, "%d", &port)
		d := newDevice(s, tcp, host, port)
		log.Printf("camera connected: %s:%d", host, port)
		go d.tcpLoop()
	}
}

// ServeUDP is the single UDP demultiplexer for all cameras.
func (s *Server) ServeUDP() {
	buf := make([]byte, 65536)
	for {
		n, addr, err := s.udpConn.ReadFromUDP(buf)
		if err != nil {
			log.Printf("udp read: %v", err)
			return
		}
		s.handleUDP(addr, append([]byte(nil), buf[:n]...))
	}
}

func (s *Server) handleUDP(addr *net.UDPAddr, raw []byte) {
	m, err := decodeMessage(raw)
	if err != nil {
		return
	}
	ip := addr.IP.String()
	dev := s.deviceByIP(ip)

	switch m.cmd {
	case cmdHeartbeat:
		s.udpSend(addr, heartbeatMessage())

	case cmdJPEG, cmdG711:
		if dev != nil {
			dev.handleData(m)
		}

	case cmdJSON:
		s.handleUDPJSON(addr, dev, m)

	default:
		if dev != nil {
			log.Printf("%s: unknown udp cmd %d", ip, m.cmd)
		}
	}
}

func (s *Server) handleUDPJSON(addr *net.UDPAddr, dev *Device, m *message) {
	var j struct {
		Code      int    `json:"code"`
		DevTarget string `json:"devTarget"`
	}
	if err := json.Unmarshal(m.payload, &j); err != nil {
		return
	}

	switch j.Code {
	case codeC2SUdpReq:
		if dev != nil {
			dev.udpMu.Lock()
			dev.dataUDP = addr
			dev.udpMu.Unlock()
		}
		resp := map[string]any{"code": codeS2CUdpRsp}
		if dev != nil {
			resp["ip"] = s.ipFor(addr.IP)
			resp["port"] = dev.dataPort
		} else {
			resp["ip"] = s.ipFor(addr.IP)
			resp["port"] = addr.Port
		}
		s.udpSend(addr, jsonMessage(resp))
		if dev != nil {
			dev.resetProbing()
		}

	case codeD2CProbeRsp:
		target := dev
		if target == nil {
			target = s.deviceByUID(j.DevTarget)
		}
		if target == nil {
			log.Printf("probe from unknown device %s (%s)", addr.IP, j.DevTarget)
			return
		}
		target.dataChannelProbe(addr)
	}
}

func (s *Server) udpSend(addr *net.UDPAddr, data []byte) {
	if _, err := s.udpConn.WriteToUDP(data, addr); err != nil {
		log.Printf("udp send: %v", err)
	}
}

// retransmitConfirm sends cmd 605 with the accumulated package ids.
func (s *Server) retransmitConfirm(addr *net.UDPAddr, ids []uint32) {
	payload := make([]byte, 4*len(ids))
	for i, id := range ids {
		binary.LittleEndian.PutUint32(payload[i*4:], id)
	}
	m := &message{payload: payload, cmd: cmdRetrans}
	copy(m.forwardID[:], "00000000")
	s.udpSend(addr, m.encode())
}

func localIPFor(remote net.IP) string {
	conn, err := net.Dial("udp", net.JoinHostPort(remote.String(), "9"))
	if err != nil {
		return "10.0.0.1"
	}
	defer conn.Close()
	host, _, _ := net.SplitHostPort(conn.LocalAddr().String())
	return host
}

func randomPort() int {
	return 32768 + rand.Intn(65534-32768+1)
}
