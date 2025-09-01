# Phase 2: Modular Synthesis Engine - Implementation Specification

**Date**: 2025-09-01  
**Status**: Ready to Implement  
**Reviewed By**: Senior Dev  

## Executive Summary

Build a zero-allocation, failover-safe module chain inside each worker process. MVP delivers: SimpleSine → ADSR → BiquadFilter with OSC control and <10ms failover maintained.

## Locked Design Decisions

1. **Transposed Direct Form II (DF2T)** biquad with RBJ coefficients  
2. **Linear ADSR segments** for MVP (exponential later)  
3. **Sine-only oscillator** initially (saw/square + PolyBLEP later)  
4. **ASCII-only module IDs** ([a-z0-9_]{1,16})  
5. **Boundary-only parameter application** with per-buffer smoothing  
6. **Float64 phase/state**, Float32 output buffers  
7. **Command Protocol v2**: 64-byte fixed struct  

## Command Protocol v2

### Binary Layout (64 bytes)
```c
typedef struct {
    uint8_t  op;              // [0] Operation: 0=set, 1=gate, 2=patch
    uint8_t  type;            // [1] Type: 0=float, 1=int, 2=bool
    uint8_t  reserved[14];    // [2-15] Future expansion
    char     module_id[16];   // [16-31] ASCII only, null-padded
    char     param[16];       // [32-47] ASCII only, null-padded
    union {
        double  f64;          // [48-55] Float values
        int64_t i64;          // [48-55] Integer values
    } value;
} CommandV2;
```

### Python Implementation
```python
import struct

def pack_command_v2(op: int, dtype: int, module_id: str, param: str, value: float) -> bytes:
    """Pack command into 64-byte struct - zero allocations after JIT"""
    cmd = bytearray(64)
    cmd[0] = op
    cmd[1] = dtype
    # Reserved bytes stay zero
    
    # ASCII validation and packing
    if not module_id.replace('_', '').isalnum():
        raise ValueError(f"Invalid module_id: {module_id}")
    cmd[16:32] = module_id.encode('ascii').ljust(16, b'\0')
    cmd[32:48] = param.encode('ascii').ljust(16, b'\0')
    
    # Pack value based on type
    if dtype == 0:  # float
        struct.pack_into('d', cmd, 48, value)
    else:  # int/bool
        struct.pack_into('q', cmd, 48, int(value))
    
    return bytes(cmd)

def unpack_command_v2(cmd_bytes: bytes) -> tuple:
    """Unpack 64-byte command - direct struct access"""
    op = cmd_bytes[0]
    dtype = cmd_bytes[1]
    module_id = cmd_bytes[16:32].rstrip(b'\0').decode('ascii')
    param = cmd_bytes[32:48].rstrip(b'\0').decode('ascii')
    
    if dtype == 0:  # float
        value = struct.unpack_from('d', cmd_bytes, 48)[0]
    else:  # int/bool
        value = struct.unpack_from('q', cmd_bytes, 48)[0]
    
    return op, dtype, module_id, param, value
```

## Module Architecture

### BaseModule Interface
```python
class BaseModule:
    """Base class for all DSP modules - zero allocations in process_buffer"""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        self.sr = sample_rate
        self.buffer_size = buffer_size
        
        # Parameter storage
        self.params = {}          # Current values
        self.param_targets = {}   # Target values (for smoothing)
        self.param_rates = {}     # Smoothing rates per parameter
        
        # Smoothing configuration (samples)
        self.smoothing_times = {
            'amplitude': int(0.005 * sample_rate),  # 5ms
            'frequency': 0,                         # No smoothing by default
            'cutoff': int(0.010 * sample_rate),    # 10ms
            'q': int(0.010 * sample_rate),         # 10ms
        }
        
    def set_param(self, param: str, value: float, immediate: bool = False):
        """Set parameter target (applied at next buffer boundary)"""
        if immediate:
            self.params[param] = value
            self.param_targets[param] = value
        else:
            self.param_targets[param] = value
            
    def prepare(self):
        """Reset module state before playback"""
        pass
        
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray):
        """Process one buffer - MUST BE ALLOCATION-FREE"""
        raise NotImplementedError
        
    def _apply_smoothing(self, param: str):
        """Apply one-pole smoothing to parameter"""
        if param not in self.param_targets:
            return
            
        target = self.param_targets[param]
        current = self.params.get(param, target)
        
        # Calculate smoothing coefficient
        smooth_samples = self.smoothing_times.get(param, 0)
        if smooth_samples > 0:
            alpha = 1.0 / (1.0 + smooth_samples)
            self.params[param] = current + alpha * (target - current)
        else:
            self.params[param] = target
```

### SimpleSine Module
```python
class SimpleSine(BaseModule):
    """Phase accumulator oscillator - sine only for MVP"""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # State (float64 for precision)
        self.phase = 0.0
        self.phase_wrap_counter = 0
        
        # Parameters
        self.params = {
            'freq': 440.0,
            'gain': 1.0
        }
        self.param_targets = self.params.copy()
        
        # Pre-allocate work buffer
        self.phase_array = np.arange(buffer_size, dtype=np.float64)
        
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray):
        """Generate sine wave - zero allocations"""
        # Apply smoothing
        self._apply_smoothing('freq')
        self._apply_smoothing('gain')
        
        freq = self.params['freq']
        gain = self.params['gain']
        
        # Phase increment (radians per sample)
        phase_inc = 2.0 * np.pi * freq / self.sr
        
        # Generate phase values (in-place)
        # phase_array is pre-allocated, just update values
        phase_end = self.phase + phase_inc * self.buffer_size
        
        # Use NumPy's linspace equivalent without allocation
        for i in range(self.buffer_size):
            self.phase_array[i] = self.phase + i * phase_inc
            
        # Generate sine wave directly into output (float32)
        np.sin(self.phase_array, out=out_buf, casting='same_kind')
        out_buf *= gain
        
        # Update phase with wrapping
        self.phase = phase_end % (2.0 * np.pi)
        
        # Periodic precision reset (every ~1000 cycles)
        self.phase_wrap_counter += 1
        if self.phase_wrap_counter > 1000:
            self.phase = self.phase % (2.0 * np.pi)
            self.phase_wrap_counter = 0
```

### ADSR Module
```python
class ADSR(BaseModule):
    """Linear ADSR envelope generator"""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # State
        self.stage = 'idle'  # idle, attack, decay, sustain, release
        self.level = 0.0
        self.gate = False
        
        # Parameters (times in ms)
        self.params = {
            'attack': 10.0,
            'decay': 100.0,
            'sustain': 0.7,
            'release': 200.0
        }
        self.param_targets = self.params.copy()
        
    def set_gate(self, gate: bool):
        """Trigger envelope (applied at next buffer boundary)"""
        self.gate = gate
        if gate and self.stage == 'idle':
            self.stage = 'attack'
        elif not gate and self.stage != 'idle':
            self.stage = 'release'
            
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray):
        """Apply envelope to input - in-place multiplication"""
        # Convert times to samples
        attack_samples = int(self.params['attack'] * 0.001 * self.sr)
        decay_samples = int(self.params['decay'] * 0.001 * self.sr)
        release_samples = int(self.params['release'] * 0.001 * self.sr)
        sustain_level = self.params['sustain']
        
        # Process envelope sample by sample (required for accuracy)
        for i in range(self.buffer_size):
            # State machine
            if self.stage == 'attack':
                self.level += 1.0 / max(1, attack_samples)
                if self.level >= 1.0:
                    self.level = 1.0
                    self.stage = 'decay'
                    
            elif self.stage == 'decay':
                self.level -= (1.0 - sustain_level) / max(1, decay_samples)
                if self.level <= sustain_level:
                    self.level = sustain_level
                    self.stage = 'sustain'
                    
            elif self.stage == 'sustain':
                self.level = sustain_level
                
            elif self.stage == 'release':
                self.level -= self.level / max(1, release_samples)
                if self.level <= 0.0001:
                    self.level = 0.0
                    self.stage = 'idle'
                    
            # Apply envelope (in-place)
            out_buf[i] = in_buf[i] * self.level
```

### BiquadFilter Module
```python
class BiquadFilter(BaseModule):
    """Transposed Direct Form II biquad - RBJ cookbook coefficients"""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        super().__init__(sample_rate, buffer_size)
        
        # State variables (float64 for stability)
        self.z1 = 0.0
        self.z2 = 0.0
        
        # Coefficients
        self.b0 = 1.0
        self.b1 = 0.0
        self.b2 = 0.0
        self.a1 = 0.0
        self.a2 = 0.0
        
        # Parameters
        self.params = {
            'mode': 0,  # 0=LP, 1=HP, 2=BP
            'cutoff': 1000.0,
            'q': 0.707
        }
        self.param_targets = self.params.copy()
        
    def _update_coefficients(self):
        """Calculate RBJ cookbook coefficients"""
        # Clamp parameters
        cutoff = np.clip(self.params['cutoff'], 1.0, self.sr * 0.49)
        q = max(0.5, self.params['q'])
        
        # Pre-warp
        w0 = 2.0 * np.pi * cutoff / self.sr
        cos_w0 = np.cos(w0)
        sin_w0 = np.sin(w0)
        alpha = sin_w0 / (2.0 * q)
        
        # Low-pass coefficients (RBJ cookbook)
        if self.params['mode'] == 0:  # LP
            b0 = (1 - cos_w0) / 2
            b1 = 1 - cos_w0
            b2 = (1 - cos_w0) / 2
            a0 = 1 + alpha
            a1 = -2 * cos_w0
            a2 = 1 - alpha
            
        # Normalize (a0 = 1)
        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0
        
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray):
        """Filter using Transposed Direct Form II"""
        # Update coefficients if parameters changed
        if (self.params['cutoff'] != self.param_targets['cutoff'] or
            self.params['q'] != self.param_targets['q']):
            self._apply_smoothing('cutoff')
            self._apply_smoothing('q')
            self._update_coefficients()
            
        # Process samples (DF2T structure)
        for i in range(self.buffer_size):
            x = in_buf[i]
            
            # Transposed Direct Form II
            y = self.b0 * x + self.z1
            self.z1 = self.b1 * x - self.a1 * y + self.z2
            self.z2 = self.b2 * x - self.a2 * y
            
            # Denormal prevention
            if abs(self.z1) < 1e-10:
                self.z1 = 0.0
            if abs(self.z2) < 1e-10:
                self.z2 = 0.0
                
            out_buf[i] = y
```

## ModuleHost Integration

```python
class ModuleHost:
    """Manages module chain in worker process"""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        self.sr = sample_rate
        self.buffer_size = buffer_size
        
        # Fixed chain for MVP
        self.modules = OrderedDict([
            ('sine', SimpleSine(sample_rate, buffer_size)),
            ('adsr', ADSR(sample_rate, buffer_size)),
            ('filter', BiquadFilter(sample_rate, buffer_size))
        ])
        
        # Pre-allocate intermediate buffers
        self.buffers = [
            np.zeros(buffer_size, dtype=np.float32)
            for _ in range(len(self.modules) + 1)
        ]
        
    def process_command(self, cmd_bytes: bytes):
        """Apply command at buffer boundary"""
        op, dtype, module_id, param, value = unpack_command_v2(cmd_bytes)
        
        if op == 0:  # Set parameter
            if module_id in self.modules:
                self.modules[module_id].set_param(param, value)
                
        elif op == 1:  # Gate
            if module_id == 'adsr':
                self.modules['adsr'].set_gate(bool(value))
                
    def process_chain(self) -> np.ndarray:
        """Process full chain - returns final buffer"""
        current_buf = self.buffers[0]
        
        for i, (name, module) in enumerate(self.modules.items()):
            next_buf = self.buffers[i + 1]
            module.process_buffer(current_buf, next_buf)
            current_buf = next_buf
            
        return current_buf
```

## OSC Integration

```python
# In supervisor.py handle_osc_message
def handle_osc_message(self, addr: str, *args):
    """Map OSC to Command Protocol v2"""
    parts = addr.split('/')
    
    if len(parts) >= 4 and parts[1] == 'mod':
        # /mod/<module>/<param> <value>
        module_id = parts[2]
        param = parts[3]
        value = float(args[0])
        
        cmd = pack_command_v2(0, 0, module_id, param, value)
        self.broadcast_command_raw(cmd)
        
    elif len(parts) >= 3 and parts[1] == 'gate':
        # /gate <module> on|off
        module_id = parts[2]
        gate = args[0] == 'on' or args[0] == 1
        
        cmd = pack_command_v2(1, 2, module_id, 'gate', int(gate))
        self.broadcast_command_raw(cmd)
```

## Testing Strategy

### MUS-01: Frequency Accuracy Test
```python
def test_frequency_accuracy():
    """Test oscillator within ±1 cent of target"""
    # Generate 1 second at 440Hz
    module = SimpleSine(44100, 256)
    module.set_param('freq', 440.0, immediate=True)
    
    # Collect samples
    samples = []
    for _ in range(173):  # ~1 second
        out = np.zeros(256, dtype=np.float32)
        module.process_buffer(None, out)
        samples.extend(out)
    
    # FFT with Hann window
    samples = np.array(samples[:44100])
    window = np.hanning(len(samples))
    fft = np.fft.rfft(samples * window)
    freqs = np.fft.rfftfreq(len(samples), 1/44100)
    
    # Find peak with quadratic interpolation
    peak_idx = np.argmax(np.abs(fft))
    
    # Quadratic peak interpolation for sub-bin accuracy
    if 0 < peak_idx < len(fft) - 1:
        y1 = np.abs(fft[peak_idx - 1])
        y2 = np.abs(fft[peak_idx])
        y3 = np.abs(fft[peak_idx + 1])
        
        # Parabolic interpolation
        x0 = (y3 - y1) / (2 * (2 * y2 - y1 - y3))
        peak_freq = freqs[peak_idx] + x0 * (freqs[1] - freqs[0])
    else:
        peak_freq = freqs[peak_idx]
    
    # Check ±1 cent tolerance (±0.254 Hz at 440Hz)
    assert abs(peak_freq - 440.0) <= 0.254
```

### MUS-02: ADSR Timing Test
```python
def test_adsr_timing():
    """Test ADSR attack within ±1 buffer"""
    module = ADSR(44100, 256)
    module.set_param('attack', 100.0, immediate=True)  # 100ms
    
    # Trigger gate
    module.set_gate(True)
    
    # Measure rise time
    samples = []
    for _ in range(20):  # Enough for 100ms
        in_buf = np.ones(256, dtype=np.float32)
        out_buf = np.zeros(256, dtype=np.float32)
        module.process_buffer(in_buf, out_buf)
        samples.extend(out_buf)
    
    # Find 10% and 90% points
    samples = np.array(samples)
    idx_10 = np.where(samples >= 0.1)[0][0]
    idx_90 = np.where(samples >= 0.9)[0][0]
    
    rise_samples = idx_90 - idx_10
    expected_samples = int(0.08 * 44100)  # 80% of 100ms
    
    # ±1 buffer tolerance (256 samples)
    assert abs(rise_samples - expected_samples) <= 256
```

## Performance Validation

- Python per-sample loops OK for 1-2 modules at 256 buffer
- Consider Numba JIT if scaling beyond 3-4 modules
- Profile with cProfile to identify hot spots
- Monitor callback timing in supervisor metrics

## Next Steps

1. Implement BaseModule and test infrastructure
2. Create SimpleSine with MUS-01 test
3. Add ADSR with MUS-02 test  
4. Implement BiquadFilter with coefficient tests
5. Integrate ModuleHost into worker process
6. Add OSC mapping and test with live commands
7. Verify failover with active chain

---
*Implementation specification ready for Phase 2 development*  
*All design decisions locked per Senior Dev review*