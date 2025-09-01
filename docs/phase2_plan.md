# Phase 2: Modular Synthesis Engine - Implementation Plan

**Date**: 2025-09-01  
**Status**: Planning Phase  
**Target**: MVP chain: SimpleSine → ADSR → SimpleFilter

## Architecture Overview

```
┌─────────────────────────────────────────┐
│            OSC Control Layer             │
│         /mod/sine/freq 440.0             │
└────────────────────────┬─────────────────┘
                         │
┌────────────────────────▼─────────────────┐
│          Command Protocol v2             │
│    64-byte structured commands           │
└────────────────────────┬─────────────────┘
                         │
┌────────────────────────▼─────────────────┐
│     Worker Process (ModuleHost)          │
│  ┌──────────┐  ┌──────┐  ┌──────────┐  │
│  │SimpleSine├──►│ ADSR ├──►│BiquadFilt│  │
│  └──────────┘  └──────┘  └──────────┘  │
│     Preallocated buffer chain            │
└──────────────────────────────────────────┘
                         │
                    Audio Ring Out

```

## Command Protocol v2 Design Analysis

### Structure (64 bytes per command)
```c
struct CommandV2 {
    uint8_t  op;           // 0=set, 1=gate, 2=patch
    uint8_t  type;         // 0=float, 1=int, 2=bool  
    uint8_t  reserved[14]; // Future expansion
    char     module_id[16];// UTF-8, null-padded
    char     param[16];    // UTF-8, null-padded
    union {
        double   f64;      // Float values
        int64_t  i64;      // Integer values
        uint64_t u64;      // Boolean as 0/1
    } value;               // 8 bytes
};
```

### Advantages
- **Fixed size**: 64 bytes fits existing CommandRing slots perfectly
- **Zero parsing**: Direct struct access, no string parsing in hot path
- **Type safety**: Explicit type field prevents conversion errors
- **Extensible**: 14 reserved bytes for future features
- **Backward compatible**: Can coexist with v1 commands using op field

### Implementation Strategy
```python
# Pack command (control thread)
def pack_command_v2(op, dtype, module_id, param, value):
    cmd = bytearray(64)
    cmd[0] = op
    cmd[1] = dtype
    # bytes 2-15 reserved (zeros)
    cmd[16:32] = module_id.encode('utf-8').ljust(16, b'\0')
    cmd[32:48] = param.encode('utf-8').ljust(16, b'\0')
    struct.pack_into('d' if dtype == 0 else 'q', cmd, 48, value)
    return bytes(cmd)

# Unpack command (worker)
def unpack_command_v2(cmd_bytes):
    op = cmd_bytes[0]
    dtype = cmd_bytes[1]
    module_id = cmd_bytes[16:32].rstrip(b'\0').decode('utf-8')
    param = cmd_bytes[32:48].rstrip(b'\0').decode('utf-8')
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
    """Zero-allocation DSP module interface"""
    
    def __init__(self, sample_rate: int, buffer_size: int):
        """All allocations happen here"""
        self.sr = sample_rate
        self.buffer_size = buffer_size
        self.params = {}  # Parameter storage
        self.param_targets = {}  # For smoothing
        self.param_current = {}  # Current smoothed values
        
    def prepare(self) -> None:
        """Reset state before playback"""
        pass
        
    def set_param(self, param: str, value: float) -> None:
        """Set parameter (boundary-only update)"""
        self.param_targets[param] = value
        
    def process_buffer(self, in_buf: np.ndarray, out_buf: np.ndarray) -> None:
        """Process audio - ZERO ALLOCATIONS ALLOWED"""
        # Apply parameter smoothing
        self._smooth_params()
        # Process audio in-place
        self._process_audio(in_buf, out_buf)
```

### ModuleHost Design
```python
class ModuleHost:
    """Manages module chain in worker process"""
    
    def __init__(self, sample_rate, buffer_size):
        # Pre-allocate ALL buffers
        self.modules = OrderedDict()
        self.chain_buffers = [
            np.zeros(buffer_size, dtype=np.float32) 
            for _ in range(MAX_MODULES + 1)
        ]
        self.buffer_index = 0
        
    def process_chain(self, input_buffer=None):
        """Process entire chain - zero allocations"""
        current = self.chain_buffers[0]
        
        for i, (name, module) in enumerate(self.modules.items()):
            next_buf = self.chain_buffers[(i + 1) % len(self.chain_buffers)]
            module.process_buffer(current, next_buf)
            current = next_buf
            
        return current
```

## Module Specifications

### SimpleSine
- **Parameters**: freq (20-20kHz), wave (sine/saw/square), gain (0-1)
- **State**: phase accumulator (continuous across buffers)
- **Anti-aliasing**: PolyBLEP for saw/square waves
- **Allocation**: Pre-computed phase array, in-place generation

### ADSR Envelope
- **Parameters**: attack (1-5000ms), decay (1-5000ms), sustain (0-1), release (1-5000ms)
- **Trigger**: gate (bool) - note on/off
- **State**: current stage, sample counter, output level
- **Precision**: Sample-accurate transitions

### BiquadFilter
- **Parameters**: mode (LP/HP/BP), cutoff (20-20kHz), Q (0.5-20)
- **Implementation**: Direct Form II (SOS) for stability
- **State**: z1, z2 delay elements per channel
- **Coefficients**: Recalculated only on parameter change

## OSC Namespace Design

### Module Parameters
```
/mod/sine/freq 440.0       # Set oscillator frequency
/mod/sine/wave 1           # 0=sine, 1=saw, 2=square
/mod/adsr/attack 10.0      # Attack time in ms
/mod/filter/cutoff 1000.0  # Filter cutoff in Hz
/mod/filter/q 5.0          # Filter resonance
```

### Gate Control
```
/gate sine on              # Trigger ADSR envelope
/gate sine off             # Release envelope
```

## Test Strategy

### MUS-01: Oscillator Frequency Accuracy
```python
def test_oscillator_accuracy():
    # Generate 1 second of 440Hz
    # FFT and find peak
    # Assert within ±1 cent (±0.254 Hz at 440Hz)
```

### MUS-02: ADSR Timing Accuracy
```python
def test_adsr_timing():
    # Set 100ms attack
    # Gate on, measure rise time
    # Assert within ±1 buffer (5.8ms at 256 samples)
```

### RT: Chain Performance
```python
def test_chain_no_underrun():
    # Run full chain
    # Send 100 OSC messages/sec
    # Assert zero underruns over 60 seconds
```

## Implementation Order

1. **Foundation** (Day 1)
   - [ ] Create module_host.py with ModuleHost class
   - [ ] Create modules/base.py with BaseModule interface
   - [ ] Extend CommandRing with v2 pack/unpack

2. **Core Modules** (Day 2)
   - [ ] Implement SimpleSine with phase accumulator
   - [ ] Implement ADSR with sample-accurate stages
   - [ ] Implement BiquadFilter with SOS coefficients

3. **Integration** (Day 3)
   - [ ] Wire ModuleHost into worker process
   - [ ] Add OSC handlers for /mod/* namespace
   - [ ] Test failover with active module chain

4. **Validation** (Day 4)
   - [ ] Run MUS-01, MUS-02 accuracy tests
   - [ ] Verify RT performance under load
   - [ ] Document quickstart guide

## Success Criteria

- [ ] 440Hz gated tone with envelope and filter
- [ ] Parameter changes via OSC take effect
- [ ] ±1 cent frequency accuracy (MUS-01)
- [ ] ±1 buffer ADSR timing (MUS-02)
- [ ] Zero underruns at 100 msg/sec
- [ ] Failover maintains <10ms during playback

## Quick Start (Post-Implementation)

```bash
# Terminal 1: Start supervisor
source venv/bin/activate
python -m music_chronus.supervisor

# Terminal 2: Send OSC commands
oscsend localhost 5005 /mod/sine/freq f 440.0
oscsend localhost 5005 /mod/adsr/attack f 100.0
oscsend localhost 5005 /gate sine s on
```

---
*Planning document for Phase 2 implementation*  
*Ready for review and discussion*