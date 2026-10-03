package main

import (
	"encoding/binary"
	"sort"
	"time"
)

// expireWindow is how long an incomplete frame's chunks are kept while
// waiting for retransmissions. The official app waits forever; we cap it
// to bound memory.
var expireWindow = 2 * time.Second

type pkt struct {
	flag    uint8
	data    []byte
	arrived time.Time
}

// window reassembles JPEG frames the way the Naxclow app does
// (NaxclowUdpRetransmissionHandle): packets are collected by pkgID,
// deduplicated, and a frame is complete when its HEAD..END pkgID run is
// contiguous. Incomplete frames are retained until retransmissions fill
// the holes (or expireWindow passes).
type window struct {
	pkts      map[uint32]pkt
	benign    map[uint32]bool // ids consumed by the audio thread (shared sequence)
	delivered uint32          // highest pkgID flushed with a completed frame
}

func newWindow() *window {
	return &window{pkts: map[uint32]pkt{}}
}

// markAudio records that a packet id was delivered on the audio channel
// and returns any frames the marking completed. Audio and video share one
// pkgID sequence (NaxclowProtocol compareTo), so such ids can legitimately
// sit inside a video frame's id run.
func (w *window) markAudio(id uint32) [][]byte {
	if id == 0 {
		return nil
	}
	if w.benign == nil {
		w.benign = map[uint32]bool{}
	}
	if len(w.benign) > 8192 {
		clear(w.benign)
	}
	w.benign[id] = true
	return w.scan(time.Now())
}

// add stores one packet and returns any frames completed by it.
func (w *window) add(id uint32, flag uint8, data []byte, now time.Time) [][]byte {
	if id <= w.delivered || id == 0 {
		return nil
	}
	if _, dup := w.pkts[id]; dup {
		return nil
	}
	w.pkts[id] = pkt{flag: flag, data: data, arrived: now}
	return w.scan(now)
}

// scan delivers every frame whose HEAD..END id run is now contiguous,
// oldest first, and expires chunks that stayed incomplete too long.
func (w *window) scan(now time.Time) [][]byte {
	ids := make([]uint32, 0, len(w.pkts))
	for id := range w.pkts {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(a, b int) bool { return ids[a] < ids[b] })

	var out [][]byte
	// drop packets before the first HEAD (torn frame remnants)
	pos := 0
	for pos < len(ids) && w.pkts[ids[pos]].flag != flagHead && w.pkts[ids[pos]].flag != flagFinish {
		delete(w.pkts, ids[pos])
		pos++
	}
	for pos < len(ids) {
		start := ids[pos]
		p := w.pkts[start]
		if p.flag == flagFinish {
			out = append(out, p.data)
			delete(w.pkts, start)
			w.bump(start)
			pos++
			continue
		}
		if now.Sub(p.arrived) > expireWindow {
			w.dropThrough(ids, pos)
			pos++
			continue
		}
		frame, next, complete := w.collect(start)
		if complete {
			out = append(out, frame)
			for id := start; id <= next; id++ {
				delete(w.pkts, id)
				delete(w.benign, id)
			}
			w.bump(next)
			for pos < len(ids) && ids[pos] <= next {
				pos++
			}
			continue
		}
		pos++
		for pos < len(ids) && w.pkts[ids[pos]].flag != flagHead && w.pkts[ids[pos]].flag != flagFinish {
			pos++
		}
	}
	return out
}

// collect walks the contiguous run starting at a HEAD. Ids that were
// delivered on the audio channel are skipped (benign holes). When complete
// it returns the assembled frame and the END packet's id.
func (w *window) collect(start uint32) ([]byte, uint32, bool) {
	var buf []byte
	for id := start; ; id++ {
		p, ok := w.pkts[id]
		if !ok {
			if w.benign[id] {
				if id == ^uint32(0) {
					return nil, 0, false
				}
				continue
			}
			return nil, 0, false
		}
		if id != start && (p.flag == flagHead || p.flag == flagFinish) {
			return nil, 0, false
		}
		buf = append(buf, p.data...)
		if p.flag == flagEnd {
			sz := 0
			if len(p.data) >= 4 {
				sz = int(binary.LittleEndian.Uint32(p.data[len(p.data)-4:]))
			}
			if len(buf) >= 5 {
				buf = buf[:len(buf)-5]
			}
			if sz > 0 && len(buf) < sz {
				return nil, 0, false
			}
			return buf, id, true
		}
		if id != start && p.flag != flagBody {
			return nil, 0, false
		}
		if id == ^uint32(0) {
			return nil, 0, false
		}
	}
}

// dropThrough expires the incomplete frame beginning at ids[pos]:
// everything up to (but not including) its successor HEAD.
func (w *window) dropThrough(ids []uint32, pos int) {
	next := len(ids)
	for i := pos + 1; i < len(ids); i++ {
		if w.pkts[ids[i]].flag == flagHead || w.pkts[ids[i]].flag == flagFinish {
			next = i
			break
		}
	}
	for _, id := range ids[pos:next] {
		delete(w.pkts, id)
	}
	w.bump(ids[pos])
}

func (w *window) bump(id uint32) {
	if id > w.delivered {
		w.delivered = id
	}
}
