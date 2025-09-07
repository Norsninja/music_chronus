"""
Voice module for Music Chronus
Single voice with Sine -> ADSR -> Biquad chain
All frequency/amplitude parameters smoothed with Sig/SigTo
SIMPLIFIED VERSION FOR DEBUGGING
"""

from pyo import *

class Voice:
    """
    Single synthesizer voice with parameter smoothing
    Chain: Osc(Sine/Saw) -> ADSR -> Biquad filter
    """
    
    def __init__(self, voice_id, server=None):
        """
        Initialize a voice with smoothed parameters
        
        Args:
            voice_id: Identifier for this voice (e.g., "voice1")
            server: Pyo server instance (uses default if None)
        """
        self.voice_id = voice_id
        self.server = server or Server.get_server()
        
        # Parameter smoothing time (20ms default as per Senior Dev)
        self.smooth_time = 0.02
        
        # Frequency control with smoothing
        self.freq_sig = Sig(440.0)  # Target frequency
        self.freq = SigTo(self.freq_sig, time=self.smooth_time)  # Smoothed frequency
        
        # Amplitude control with smoothing
        self.amp_sig = Sig(0.3)  # Target amplitude (0-1)
        self.amp = SigTo(self.amp_sig, time=self.smooth_time)  # Smoothed amplitude
        
        # Slide/Portamento control (0-1.5 seconds)
        self.slide_time_sig = Sig(0.0)  # 0 = no portamento
        self.slide_time = SigTo(self.slide_time_sig, time=0.005)  # Quick update for slide changes
        
        # Create ported frequency signal for smooth glides
        # Port provides exponential smoothing which sounds more musical than linear
        self.ported_freq = Port(
            self.freq,  # Input from SigTo smoothed freq
            risetime=self.slide_time,  # Time to rise to higher frequency
            falltime=self.slide_time   # Time to fall to lower frequency
        )
        
        # Filter parameters with smoothing
        self.filter_freq_sig = Sig(1000.0)  # Target filter frequency
        self.filter_freq = SigTo(self.filter_freq_sig, time=self.smooth_time)
        
        self.filter_q_sig = Sig(2.0)  # Target filter Q (resonance)
        self.filter_q = SigTo(self.filter_q_sig, time=self.smooth_time)
        
        # ADSR envelope (not smoothed - gates are instantaneous)
        self.adsr = Adsr(
            attack=0.01,   # 10ms default attack
            decay=0.1,     # 100ms default decay  
            sustain=0.7,   # 70% sustain level
            release=0.5,   # 500ms release
            dur=0,         # Infinite duration (gate controlled)
            mul=self.amp   # Modulated by smoothed amplitude
        )
        
        # Make envelope exponential for more natural sound
        self.adsr.setExp(0.75)
        
        # Create waveform tables
        self.sine_table = HarmTable([1], size=8192)  # Pure sine
        self.saw_table = SawTable(order=12, size=8192).normalize()  # Band-limited saw
        self.square_table = SquareTable(order=10, size=8192).normalize()  # Band-limited square
        
        # Create oscillators for each waveform (all running simultaneously)
        # Now using ported_freq for smooth portamento/glide
        self.osc_sine = Osc(
            table=self.sine_table,
            freq=self.ported_freq,  # Use ported frequency for glide
            mul=self.adsr
        )
        
        self.osc_saw = Osc(
            table=self.saw_table,
            freq=self.ported_freq,  # Use ported frequency for glide
            mul=self.adsr
        )
        
        self.osc_square = Osc(
            table=self.square_table,
            freq=self.ported_freq,  # Use ported frequency for glide
            mul=self.adsr
        )
        
        # Waveform selector control (0=sine, 1=saw, 2=square)
        self.waveform_select = Sig(0)
        
        # Selector with equal-power crossfade for click-free switching
        self.osc = Selector(
            [self.osc_sine, self.osc_saw, self.osc_square],
            voice=self.waveform_select
        )
        self.osc.setMode(1)  # Mode 1 = equal-power crossfade
        
        # Store pre-filter signal for acid input
        # This is the oscillator output before filtering
        self.prefilter_signal = self.osc
        
        # Biquad lowpass filter with smoothed parameters
        self.filter = Biquad(
            self.osc,
            freq=self.filter_freq,
            q=self.filter_q,
            type=0  # 0 = lowpass
        )
        
        # Output signal (before sends)
        self.output = self.filter
        
        # Send levels for effects (smoothed)
        self.reverb_send_sig = Sig(0.0)  # 0-1
        self.reverb_send = SigTo(self.reverb_send_sig, time=self.smooth_time)
        
        self.delay_send_sig = Sig(0.0)  # 0-1
        self.delay_send = SigTo(self.delay_send_sig, time=self.smooth_time)
        
    def set_freq(self, freq):
        """Set oscillator frequency (20-5000 Hz)"""
        freq = max(20.0, min(5000.0, float(freq)))
        self.freq_sig.value = freq
    
    def set_amp(self, amp):
        """Set voice amplitude (0-1)"""
        amp = max(0.0, min(1.0, float(amp)))
        self.amp_sig.value = amp
    
    def set_filter_freq(self, freq):
        """Set filter cutoff frequency (50-8000 Hz)"""
        freq = max(50.0, min(8000.0, float(freq)))
        self.filter_freq_sig.value = freq
    
    def set_filter_q(self, q):
        """Set filter Q/resonance (0.5-10)"""
        q = max(0.5, min(10.0, float(q)))
        self.filter_q_sig.value = q
    
    def set_adsr(self, param, value):
        """Set ADSR parameter (attack, decay, sustain, release)"""
        value = float(value)
        
        if param == 'attack':
            value = max(0.001, min(2.0, value))
            self.adsr.attack = value
        elif param == 'decay':
            value = max(0.0, min(2.0, value))
            self.adsr.decay = value
        elif param == 'sustain':
            value = max(0.0, min(1.0, value))
            self.adsr.sustain = value
        elif param == 'release':
            value = max(0.01, min(3.0, value))
            self.adsr.release = value
    
    def set_reverb_send(self, level):
        """Set reverb send level (0-1)"""
        level = max(0.0, min(1.0, float(level)))
        self.reverb_send_sig.value = level
    
    def set_delay_send(self, level):
        """Set delay send level (0-1)"""
        level = max(0.0, min(1.0, float(level)))
        self.delay_send_sig.value = level
    
    def gate(self, state):
        """Trigger or release the envelope"""
        if state > 0:
            self.adsr.play()  # Trigger attack
        else:
            self.adsr.stop()  # Trigger release
    
    def get_dry_signal(self):
        """Get the dry output signal"""
        return self.output
    
    def get_reverb_send(self):
        """Get signal to send to reverb"""
        return self.output * self.reverb_send
    
    def get_delay_send(self):
        """Get signal to send to delay"""
        return self.output * self.delay_send
    
    def get_prefilter_signal(self):
        """Get pre-filter signal (oscillator * ADSR) for acid input"""
        return self.prefilter_signal
    
    # LFO integration methods (Senior Dev fix pattern)
    def apply_filter_lfo(self, lfo_signal):
        """Apply LFO modulation to filter cutoff frequency
        
        Args:
            lfo_signal: PyoObject outputting scaled Hz offset (e.g., ±800Hz)
        """
        # Store reference to prevent GC
        self._filter_lfo = lfo_signal
        
        # Create new total frequency with clamping
        # Use self.filter_freq (the SigTo smoothed base) + LFO
        self._filter_freq_total = Clip(
            self.filter_freq + self._filter_lfo, 
            50, 8000  # Safe frequency range
        )
        
        # Rebind the filter frequency to include LFO
        self.filter.freq = self._filter_freq_total
        
        print(f"[VOICE] {self.voice_id} filter LFO applied")
    
    def apply_amp_lfo(self, lfo_signal):
        """Apply LFO modulation to amplitude (tremolo effect)
        
        Args:
            lfo_signal: PyoObject outputting amplitude multiplier (e.g., 0.2-1.0)
        """
        # Store reference to prevent GC
        self._amp_lfo = lfo_signal
        
        # Create new total amplitude 
        # Use self.amp (the SigTo smoothed base) * LFO
        self._amp_total = self.amp * self._amp_lfo
        
        # Rebind the ADSR multiplier to include tremolo
        self.adsr.mul = self._amp_total
        
        print(f"[VOICE] {self.voice_id} amplitude LFO applied")

    def set_slide_time(self, time):
        """Set portamento/slide time in seconds (0-1.5s)
        
        0: No portamento (instant frequency changes)
        0.05-0.2: Fast slides (good for subtle glides)
        0.2-0.5: Medium slides (classic synth portamento)
        0.5-1.5: Slow slides (dramatic pitch sweeps)
        """
        time = max(0.0, min(1.5, float(time)))
        self.slide_time_sig.value = time
        print(f"[VOICE] {self.voice_id} slide_time set to {time:.3f}s")
    
    def set_waveform(self, waveform):
        """Set oscillator waveform type
        
        Args:
            waveform: 0=sine, 1=saw, 2=square
        """
        waveform = int(waveform)
        if waveform < 0 or waveform > 2:
            print(f"[VOICE] Warning: Invalid waveform {waveform}, using 0 (sine)")
            waveform = 0
        self.waveform_select.value = waveform
    
    def get_status(self):
        """Get current voice status"""
        return {
            'voice_id': self.voice_id,
            'freq': self.freq_sig.value,
            'amp': self.amp_sig.value,
            'filter_freq': self.filter_freq_sig.value,
            'filter_q': self.filter_q_sig.value,
            'reverb_send': self.reverb_send_sig.value,
            'delay_send': self.delay_send_sig.value,
            'adsr': {
                'attack': self.adsr.attack,
                'decay': self.adsr.decay,
                'sustain': self.adsr.sustain,
                'release': self.adsr.release
            },
            'waveform': int(self.waveform_select.value),
            'slide_time': self.slide_time_sig.value
        }
    
    def get_schema(self):
        """Get parameter schema for this voice module"""
        return {
            "name": f"Voice ({self.voice_id})",
            "type": "voice",
            "params": {
                "freq": {"type": "float", "min": 20, "max": 5000, "default": 440.0, "smoothing_ms": 20, "unit": "Hz"},
                "amp": {"type": "float", "min": 0, "max": 1, "default": 0.3, "smoothing_ms": 20},
                "osc/type": {"type": "int", "min": 0, "max": 2, "default": 0, "notes": "0=sine, 1=saw, 2=square"},
                "filter/freq": {"type": "float", "min": 50, "max": 8000, "default": 1000.0, "smoothing_ms": 20, "unit": "Hz"},
                "filter/q": {"type": "float", "min": 0.5, "max": 10, "default": 2.0, "smoothing_ms": 20},
                "adsr/attack": {"type": "float", "min": 0.001, "max": 2, "default": 0.01, "unit": "seconds"},
                "adsr/decay": {"type": "float", "min": 0, "max": 2, "default": 0.1, "unit": "seconds"},
                "adsr/sustain": {"type": "float", "min": 0, "max": 1, "default": 0.7},
                "adsr/release": {"type": "float", "min": 0.01, "max": 3, "default": 0.5, "unit": "seconds"},
                "send/reverb": {"type": "float", "min": 0, "max": 1, "default": 0.0},
                "send/delay": {"type": "float", "min": 0, "max": 1, "default": 0.0},
                "slide_time": {"type": "float", "min": 0, "max": 1.5, "default": 0.0, "smoothing_ms": 5, "unit": "seconds", "notes": "Portamento/glide time"}
            },
            "gates": ["gate"],
            "notes": "Polyphonic voice with Osc(Sine/Saw/Square) -> ADSR -> Biquad filter chain"
        }