# Simple Audio Setup for WSL2 → Windows

## Option 1: WSLg Audio (Easiest - If you have it)

First, check if you already have WSLg (GUI support):

```bash
# In WSL2, check if you have WSLg
ls /mnt/wslg
```

If that directory exists, you might already have audio! Try:
```bash
pactl info
```

## Option 2: PulseAudio Bridge (Most Reliable)

### Step 1: Windows Side Setup

1. **Download PulseAudio for Windows**
   - Go to: https://pgaskin.net/pulseaudio-win32/
   - Download the latest release (pulseaudio-x.x.x-win32.zip)
   - Extract to C:\PulseAudio

2. **Configure PulseAudio**
   - Edit `C:\PulseAudio\etc\pulse\default.pa`
   - Add at the end:
   ```
   load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1;172.16.0.0/12 auth-anonymous=1
   load-module module-esound-protocol-tcp auth-anonymous=1
   ```

3. **Create Start Script**
   - Create `C:\PulseAudio\start-pulseaudio.bat`:
   ```batch
   @echo off
   cd C:\PulseAudio\bin
   pulseaudio.exe --use-pid-file=false --exit-idle-time=-1
   ```
   - Run this batch file (you'll see a terminal window - keep it open)

### Step 2: WSL2 Side Setup

```bash
# Get your Windows host IP (WSL2 assigns this dynamically)
export HOST_IP=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')

# Tell PulseAudio to use Windows server
export PULSE_SERVER=tcp:$HOST_IP

# Make it permanent
echo "export PULSE_SERVER=tcp:\$(cat /etc/resolv.conf | grep nameserver | awk '{print \$2}')" >> ~/.bashrc

# Test it
pactl info
```

If you see server info, IT'S WORKING!

### Step 3: Configure SuperCollider to use PulseAudio

```bash
# Install PulseAudio support in WSL2
sudo apt-get install pulseaudio-utils

# Now SuperCollider will automatically use PulseAudio
```

## Option 3: VcXsrv with Audio (Alternative)

1. Install VcXsrv on Windows (X server with audio)
2. Run XLaunch with "Disable access control" checked
3. In WSL2:
   ```bash
   export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
   export PULSE_SERVER=tcp:$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')
   ```

## Troubleshooting

**Windows Firewall Issues?**
- Windows Defender may block the connection
- Add an inbound rule for port 4713 (PulseAudio default)
- Or temporarily disable firewall to test

**Still No Sound?**
```bash
# Check if PulseAudio sees the Windows server
pactl info

# Test with a simple sound
speaker-test -c 2

# Check SuperCollider can see audio
scsynth -H default
```

## Quick Test

Once set up, test with:
```bash
# Simple beep test
paplay /usr/share/sounds/freedesktop/stereo/bell.oga

# Or generate a test tone
speaker-test -t sine -f 440 -l 1
```

---

## Why This Works

- **PulseAudio** is a sound server that can work over network
- **Windows** becomes the sound server (has the real hardware)  
- **WSL2** becomes a client sending audio data
- It adds ~20-50ms latency (fine for music production)