#!/usr/bin/env bash
set -euo pipefail

### ─── CONFIG ───────────────────────────────────────────────────────────────
ROBOT_IP="192.168.0.4"
INTF="eth0"
REAL_GW="192.168.0.1"
MITM_PORT=8080
CA_PATH="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
SCRIPT_PATH="python/mitm.py"
### ─── END CONFIG ───────────────────────────────────────────────────────────

echo "[*] Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null

echo "[*] Flushing iptables rules..."
iptables -t nat -F
iptables -F

echo "[*] Setting default route → $REAL_GW..."
ip route del default 2>/dev/null || true
ip route add default via "$REAL_GW" dev "$INTF"

echo "[*] Masquerading traffic from $ROBOT_IP..."
iptables -t nat -A POSTROUTING -s "$ROBOT_IP" -o "$INTF" -j MASQUERADE

echo "[*] Redirecting 80/443 from $ROBOT_IP → mitmproxy:$MITM_PORT..."
iptables -t nat -A PREROUTING -s "$ROBOT_IP" -p tcp --dport 80  -j REDIRECT --to-port "$MITM_PORT"
iptables -t nat -A PREROUTING -s "$ROBOT_IP" -p tcp --dport 443 -j REDIRECT --to-port "$MITM_PORT"

export DATA_PATH=/root/360-proxy/data


echo "[*] Launching mitmproxy..."
DATA_PATH=/root/360-proxy/data mitmweb \
     --mode transparent \
     --listen-port "$MITM_PORT" \
     --scripts "$SCRIPT_PATH" \
     --web-host 0.0.0.0 \
     --quiet
