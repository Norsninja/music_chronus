#!/bin/bash

echo "==================================="
echo "PulseAudio Setup for WSL2"
echo "==================================="
echo ""
echo "WINDOWS SIDE (do this first):"
echo "1. Download PulseAudio for Windows from:"
echo "   https://www.freedesktop.org/wiki/Software/PulseAudio/Ports/Windows/Support/"
echo ""
echo "2. Extract and edit etc/pulse/default.pa"
echo "   Add this line: load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12"
echo ""
echo "3. Run pulseaudio.exe"
echo ""
echo "WSL2 SIDE (after Windows setup):"
echo ""

# Get WSL2 host IP
export HOST_IP=$(ip route | grep default | awk '{print $3}')
echo "Your Windows host IP is: $HOST_IP"
echo ""

# Set PulseAudio to use Windows host
echo "export PULSE_SERVER=tcp:$HOST_IP" >> ~/.bashrc
export PULSE_SERVER=tcp:$HOST_IP

echo "Testing PulseAudio connection..."
pactl info 2>/dev/null

if [ $? -eq 0 ]; then
    echo "PulseAudio connected successfully!"
else
    echo "PulseAudio connection failed. Make sure:"
    echo "1. PulseAudio is running on Windows"
    echo "2. Windows Firewall allows the connection"
    echo "3. The IP address is correct: $HOST_IP"
fi

echo ""
echo "Once PulseAudio is working, we can use SuperCollider with it!"