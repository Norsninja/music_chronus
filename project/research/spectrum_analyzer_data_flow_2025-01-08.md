# Spectrum Analyzer Data Flow Research - 2025-01-08

## Executive Summary
Investigation of complete spectrum analyzer data flow from engine to visualizer display revealed a critical port mismatch causing zero data display. Engine broadcasts to port 5006 while visualizer operates on port 5007 due to port conflicts. Spectrum data generation and processing mechanisms are functional but disconnected due to network routing issues.

## Scope
Complete trace of spectrum analyzer data flow from Pyo Spectrum object creation through OSC broadcast to visualizer display rendering, examining data types, processing stages, and potential failure points.

## Key Findings

### Pattern Analysis
The data flow follows a clear but broken chain: Engine generates spectrum data successfully, processes it into 8-band format, broadcasts to port 5006, but visualizer listens on port 5007 due to port conflicts, resulting in zero display values despite functioning processing logic.

### Implementation Details

#### 1. Engine Side - Data Generation
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 845-851
- Purpose: Initialize spectrum analyzer with Pyo Spectrum object
```python
def setup_monitoring(self):
    """Setup real-time audio and message monitoring"""
    # Audio level monitoring
    self.peak_meter = PeakAmp(self.master)
    
    # Spectrum analyzer for visualization (better for display than FFT)
    self.spectrum_analyzer = Spectrum(self.master, size=2048)
    
    # OSC broadcast client for visualization data
    self.viz_broadcast = udp_client.SimpleUDPClient('127.0.0.1', 5006)
```

**Data Type**: Pyo Spectrum object with 2048-point FFT analysis
**Expected Output**: 512 frequency bins (spectrum_data)

#### 2. Engine Side - Data Processing
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 919-954
- Purpose: Convert spectrum data to 8-band display format
```python
# Get the spectrum magnitude data
spectrum_data = self.spectrum_analyzer.get()

# Handle None during initialization
if spectrum_data is None:
    spectrum_data = [0.0] * 512  # Default FFT size

if spectrum_data and len(spectrum_data) > 0:
    # Group into 8 frequency bands (logarithmic grouping for better display)
    spectrum = []
    # Define band boundaries (rough frequency ranges)
    bands = [
        (0, 4),      # 0-86 Hz (sub-bass)
        (4, 8),      # 86-172 Hz (bass)
        (8, 16),     # 172-344 Hz (low-mid)
        (16, 32),    # 344-689 Hz (mid)
        (32, 64),    # 689-1378 Hz (high-mid)
        (64, 128),   # 1378-2756 Hz (presence)
        (128, 256),  # 2756-5512 Hz (brilliance)
        (256, 512)   # 5512-11025 Hz (air)
    ]
    
    for start, end in bands:
        # Ensure we don't exceed array bounds
        end = min(end, len(spectrum_data))
        if start < len(spectrum_data):
            # RMS of the band
            band_sum = sum(spectrum_data[start:end])
            band_avg = band_sum / (end - start) if end > start else 0
            # Scale for display (adjust multiplier as needed)
            spectrum.append(min(band_avg * 100, 1.0))
        else:
            spectrum.append(0.0)
    
    # Send spectrum data
    self.viz_broadcast.send_message('/viz/spectrum', spectrum[:8])
```

**Data Type**: List of 8 float values (0.0 to 1.0)
**Processing**: Logarithmic frequency band grouping with RMS calculation and scaling factor of 100
**Error Handling**: Fallback to zero array on exceptions (lines 955-957)

#### 3. Engine Side - OSC Broadcast
- File: E:\TidalCyclesChronus\music_chronus\engine_pyo.py
- Lines: 854, 954
- Purpose: Send spectrum data to visualizer via OSC
```python
# OSC broadcast client for visualization data
self.viz_broadcast = udp_client.SimpleUDPClient('127.0.0.1', 5006)

# Send spectrum data
self.viz_broadcast.send_message('/viz/spectrum', spectrum[:8])
```

**Target Port**: 5006
**Message Format**: '/viz/spectrum' with 8 float arguments
**Data Type**: OSC message with float32 arguments

#### 4. Visualizer Side - OSC Reception
- File: E:\TidalCyclesChronus\music_chronus\visualizer.py
- Lines: 41, 107, 114-118
- Purpose: Receive OSC messages from engine
```python
# OSC configuration
self.osc_monitor_port = 5006  # Receive visualization broadcast data

# Specific handlers for visualization data
self.dispatcher.map("/viz/spectrum", self.handle_spectrum_data)

# Monitor existing OSC traffic
server = ThreadingOSCUDPServer(
    (self.osc_ip, self.osc_monitor_port),
    self.dispatcher
)
```

**Expected Port**: 5006
**Actual Port**: 5007 (due to port conflict)
**Handler**: Dedicated function for /viz/spectrum messages

#### 5. Visualizer Side - Data Handling
- File: E:\TidalCyclesChronus\music_chronus\visualizer.py
- Lines: 150-161
- Purpose: Process received spectrum data
```python
def handle_spectrum_data(self, addr: str, *args):
    """Handle spectrum analysis data"""
    # Log to message display FIRST so it appears in OSC panel
    self.handle_osc_message(addr, *args)
    
    # Then process the data
    with self.data_lock:
        if args and len(args) >= 8:
            self.spectrum_data = [float(x) for x in args[:8]]
            # Mark as receiving live data
            self.engine_connected = True
            self.last_status_update = time.time()
```

**Data Storage**: self.spectrum_data (list of 8 floats)
**Thread Safety**: Protected by self.data_lock
**Validation**: Checks for minimum 8 arguments

#### 6. Visualizer Side - Display Rendering
- File: E:\TidalCyclesChronus\music_chronus\visualizer.py
- Lines: 234-264
- Purpose: Render spectrum data as visual bars
```python
def create_spectrum_display(self) -> Panel:
    """Create frequency spectrum display"""
    with self.data_lock:
        # Frequency labels
        freq_labels = ["63", "125", "250", "500", "1k", "2k", "4k", "8k"]
        
        # Create spectrum bars
        lines = []
        max_height = 10
        
        for row in range(max_height, 0, -1):
            line = ""
            for i, value in enumerate(self.spectrum_data):
                bar_height = int(value * max_height)
                if bar_height >= row:
                    line += "██"
                else:
                    line += "  "
                line += " "
            lines.append(Text(line, style="cyan"))
```

**Display Format**: ASCII bars using "██" characters
**Height Calculation**: int(value * 10) for 10-row display
**Data Source**: self.spectrum_data (initialized as [0.0] * 8)

### Code Flow

1. **Engine Initialization**: Spectrum object created with 2048-point FFT
2. **Data Collection**: spectrum_analyzer.get() returns 512 frequency bins or None
3. **Band Processing**: 512 bins grouped into 8 logarithmic frequency bands
4. **Data Scaling**: Each band averaged and scaled by factor of 100, clamped to 1.0
5. **OSC Transmission**: Array sent to port 5006 via '/viz/spectrum' message
6. **Reception Failure**: Visualizer listening on port 5007, misses data
7. **Display Render**: Uses default [0.0] * 8 values, shows no bars

### Related Components

**Network Stack**:
- Engine: SimpleUDPClient targeting 127.0.0.1:5006
- Visualizer: ThreadingOSCUDPServer on 127.0.0.1:5007 (port conflict)

**Data Structures**:
- Pyo Spectrum: C-based FFT analysis with Python interface
- Python lists: Float arrays for band data transport
- Rich Text objects: Terminal display rendering

**Threading**:
- Engine broadcast: Audio callback thread
- Visualizer reception: Dedicated OSC thread
- Display update: Main UI thread with data_lock synchronization

## File Inventory

- E:\TidalCyclesChronus\music_chronus\engine_pyo.py - Spectrum generation and broadcast (lines 845-957)
- E:\TidalCyclesChronus\music_chronus\visualizer.py - Reception and display (lines 41-264)
- E:\TidalCyclesChronus\music_chronus\project\research\visualizer_diagnostic_research_2025-01-08.md - Previous port conflict documentation

## Technical Notes

### Critical Issues Identified

1. **Port Mismatch**: Engine broadcasts to port 5006, visualizer listens on port 5007
2. **Silent Failure**: OSC server exception handling masks port binding failures
3. **No Data Validation**: No logging of received spectrum values for debugging

### Data Type Verification

- **Spectrum.get() Return**: Returns Python list of float values or None
- **Band Processing**: Produces 8 float values between 0.0 and 1.0
- **OSC Transport**: Float32 values via python-osc library
- **Display Conversion**: Integer bar heights via int(value * 10)

### Performance Characteristics

- **Update Rate**: Every audio callback cycle (approximately 170Hz at 256 buffer size)
- **Processing Cost**: 8 band calculations per update with array slicing and summation
- **Network Overhead**: Single UDP packet with 8 float32 values (32 bytes payload)

### Error Handling Analysis

- **Engine Side**: Try/catch sends zeros on spectrum extraction failure
- **Visualizer Side**: Silent port conflict fallback without notification
- **Data Validation**: Proper argument count checking in message handlers

The spectrum analyzer data flow is architecturally sound but operationally broken due to network port mismatch. The engine successfully generates, processes, and transmits spectrum data, but the visualizer never receives it due to listening on the wrong port.