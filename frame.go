package main

import _ "embed"

//go:embed placeholder.jpg
var placeholderFrame []byte

func (d *Device) latestFrame() []byte {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.lastFrame != nil {
		return d.lastFrame
	}
	return placeholderFrame
}
