#!/bin/bash

echo "Starting..."
mkdir -p /root/logs
PYTHONUNBUFFERED=1 mitmweb \
     --mode transparent \
     --listen-port 8080 \
     --scripts /root/python/mitm.py \
     --web-host 0.0.0.0 \
     --web-port 8081 \
     --no-web-open-browser