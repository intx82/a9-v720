package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	"os"
)

func main() {
	tcpPort := flag.String("tcp", "0.0.0.0:6123", "device control TCP address")
	udpPort := flag.String("udp", "0.0.0.0:6123", "device data UDP address")
	httpPort := flag.String("http", "0.0.0.0:8247", "HTTP listener address")
	serverIP := flag.String("server-ip", os.Getenv("SERVER_IP"),
		"IP advertised to cameras (default: SERVER_IP env, else route to each camera)")
	flag.Parse()

	udpAddr, err := net.ResolveUDPAddr("udp", *udpPort)
	if err != nil {
		log.Fatalf("resolve udp: %v", err)
	}
	udpConn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		log.Fatalf("listen udp: %v", err)
	}

	tcpLn, err := net.Listen("tcp", *tcpPort)
	if err != nil {
		log.Fatalf("listen tcp: %v", err)
	}

	srv := NewServer(tcpLn, udpConn, *serverIP)

	go srv.ServeUDP()
	go srv.ServeTCP(tcpLn)

	httpSrv := &http.Server{
		Addr:    *httpPort,
		Handler: srv,
	}
	log.Printf("catcam up: tcp=%s udp=%s http=%s", *tcpPort, *udpPort, *httpPort)
	log.Fatal(httpSrv.ListenAndServe())
}
