#!/usr/bin/env bash
set -e

RSU="vanetza-nap-main-rsu-1"
OBU1="vanetza-nap-main-obu1-1"
OBU2="vanetza-nap-main-obu2-1"

DELAY="${1:-50ms}"
JITTER="${2:-0ms}"
LOSS="${3:-0%}"

echo "Applying netem..."
echo "Delay  = $DELAY"
echo "Jitter = $JITTER"
echo "Loss   = $LOSS"

for C in "$RSU" "$OBU1" "$OBU2"; do
  echo "-> $C"
  docker exec "$C" tc qdisc replace dev eth0 root netem delay "$DELAY" "$JITTER" loss "$LOSS"
  docker exec "$C" tc qdisc show dev eth0
done

echo "Done."
