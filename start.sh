#!/bin/bash
# Launch the Go relay detached in a screen session (build first:
# go build -buildvcs=false -o catcam .). No root needed (all ports >1024).
# Watch: screen -r catcam   |   Stop: screen -S catcam -X quit
cd "$(dirname "$0")" || exit 1
mkdir -p logs
if pgrep -x catcam >/dev/null; then
	echo "catcam already running (pid $(pgrep -x catcam | tr '\n' ' '))"
	exit 1
fi
screen -L -Logfile "$PWD/logs/server-go.log" -dmS catcam ./catcam "$@"
echo "catcam started in screen session 'catcam' (log: logs/server-go.log)"
