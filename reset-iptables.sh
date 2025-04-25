#!/bin/bash
echo "[*] Resetting iptables to default..."

# Flush all rules
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -t raw -F
iptables -t security -F

# Delete all user-defined chains
iptables -X
iptables -t nat -X
iptables -t mangle -X
iptables -t raw -X
iptables -t security -X

# Reset default policies to ACCEPT
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

echo "[*] iptables rules have been reset to default."