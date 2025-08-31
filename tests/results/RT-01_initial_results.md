# RT-01 Test Results - Initial Baseline

## Test Date: 2025-08-30

### Environment
- Platform: WSL2 Ubuntu on Windows
- Python: 3.12
- Audio Bridge: PulseAudio TCP (tcp:172.21.240.1:4713)

### Test 1: PulseAudio Direct (Baseline)

**Result: FAILED** ❌

#### Statistics:
- Mean Latency: 97.17ms
- Median Latency: 95.56ms
- Min Latency: 63.56ms
- Max Latency: 189.93ms
- Success Rate: 0% (target was <50ms)

#### Analysis:
The PulseAudio subprocess approach has unacceptable latency for real-time music:
1. **Process spawn overhead**: Each `paplay` call spawns a new process (~50-100ms)
2. **No buffer control**: Can't optimize buffer sizes
3. **Network overhead**: TCP bridge adds latency
4. **No real-time priority**: Regular process scheduling

#### Conclusion:
This confirms our architectural decision - we MUST use rtmixer with C-level callbacks to achieve <20ms latency.

### Next Steps:
1. Install `portaudio19-dev` package
2. Reinstall sounddevice to link with PortAudio
3. Test rtmixer with proper C callbacks
4. Target: <20ms latency

### Expected Improvements with rtmixer:
- **C-level callbacks**: Bypass Python GIL entirely
- **Lock-free ring buffers**: Zero-copy audio transfer  
- **Real-time thread priority**: OS-level scheduling
- **Direct hardware access**: Through PortAudio
- **Configurable buffers**: Can optimize for latency vs stability

### Command to install missing dependency:
```bash
sudo apt-get install portaudio19-dev
# Then reinstall sounddevice
pip uninstall sounddevice
pip install sounddevice --no-cache-dir
```