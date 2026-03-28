#!/usr/bin/env bash
set -e

RSU="vanetza-nap-main-rsu-1"
OBU1="vanetza-nap-main-obu1-1"
OBU2="vanetza-nap-main-obu2-1"

echo "Clearing netem..."

for C in "$RSU" "$OBU1" "$OBU2"; do
  echo "-> $C"
  docker exec "$C" tc qdisc del dev eth0 root 2>/dev/null || true
  docker exec "$C" tc qdisc show dev eth0
done

echo "Done."
