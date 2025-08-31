#!/bin/bash

echo "==================================="
echo "Fixing PulseAudio Connection"
echo "==================================="
echo ""

# Get the current Windows host IP
HOST_IP=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')
echo "Windows host IP: $HOST_IP"
echo ""

echo "WINDOWS SIDE - Please check:"
echo "1. Is PulseAudio running? (You should see a terminal window)"
echo ""
echo "2. Check if C:\PulseAudio\etc\pulse\default.pa contains:"
echo "   load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12 auth-anonymous=1"
echo ""
echo "3. Windows Firewall might be blocking. Try:"
echo "   - Temporarily disable Windows Firewall to test"
echo "   - Or add a rule allowing port 4713 from WSL2"
echo ""
echo "4. Make sure you started PulseAudio with the .bat file"
echo ""

echo "WSL2 SIDE - Testing connection:"
export PULSE_SERVER=tcp:$HOST_IP

# Try different connection methods
echo "Trying default port 4713..."
pactl -s tcp:$HOST_IP:4713 info 2>&1 | head -5

echo ""
echo "Alternative: Try the simplified server..."
export PULSE_SERVER=$HOST_IP
pactl info 2>&1 | head -5

echo ""
echo "If still not working, in Windows PulseAudio terminal,"
echo "you should see connection attempts. Check for error messages there."