package main

import (
	"encoding/binary"
	"encoding/json"
	"errors"
)

const headerLen = 20

// protocol commands
const (
	cmdJSON      = 0
	cmdJPEG      = 1
	cmdG711      = 4
	cmdHeartbeat = 100
	cmdRetrans   = 605
)

// json codes
const (
	codeD2SNatRsp      = 12
	codeS2DNatReq      = 11
	codeC2SUdpReq      = 20
	codeS2CUdpRsp      = 21
	codeC2DProbeReq    = 50
	codeD2CProbeRsp    = 51
	codeS2DeviceStatus = 53
	codeRegReq         = 100
	codeRegRsp         = 101
	codeCmdForward     = 301
	codeFwdClose       = 0
	codeFwdBaseInfo    = 4
	codeFwdOpenAOpenV  = 3
	codeSpeedGrade     = 201
	codeRetransmission = 298
)

// msg flags
const (
	flagHead   = 250
	flagBody   = 251
	flagEnd    = 252
	flagFinish = 255
)

var errShortMessage = errors.New("short protocol message")

type message struct {
	payload   []byte
	cmd       uint16
	msgFlag   uint8
	dealFlag  uint8
	forwardID [8]byte
	pkgID     uint32
}

func (m *message) encode() []byte {
	buf := make([]byte, headerLen+len(m.payload))
	binary.LittleEndian.PutUint32(buf[0:4], uint32(len(m.payload)))
	binary.LittleEndian.PutUint16(buf[4:6], m.cmd)
	buf[6] = m.msgFlag
	buf[7] = m.dealFlag
	copy(buf[8:16], m.forwardID[:])
	binary.LittleEndian.PutUint32(buf[16:20], m.pkgID)
	copy(buf[headerLen:], m.payload)
	return buf
}

func decodeMessage(raw []byte) (*message, error) {
	if len(raw) < headerLen {
		return nil, errShortMessage
	}
	m := &message{
		cmd:      binary.LittleEndian.Uint16(raw[4:6]),
		msgFlag:  raw[6],
		dealFlag: raw[7],
		pkgID:    binary.LittleEndian.Uint32(raw[16:20]),
	}
	copy(m.forwardID[:], raw[8:16])
	plen := int(binary.LittleEndian.Uint32(raw[0:4]))
	if plen > len(raw)-headerLen {
		plen = len(raw) - headerLen
	}
	m.payload = raw[headerLen : headerLen+plen]
	return m, nil
}

func jsonMessage(v any) []byte {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	m := &message{payload: b, cmd: cmdJSON}
	copy(m.forwardID[:], "00000000")
	return m.encode()
}

func forwardMessage(content map[string]any) []byte {
	b, err := json.Marshal(map[string]any{
		"code":    codeCmdForward,
		"target":  cliTarget,
		"content": content,
	})
	if err != nil {
		panic(err)
	}
	m := &message{payload: b, cmd: cmdJSON, dealFlag: 1}
	copy(m.forwardID[:], "00000000")
	return m.encode()
}

func heartbeatMessage() []byte {
	m := &message{cmd: cmdHeartbeat}
	copy(m.forwardID[:], "00000000")
	return m.encode()
}
