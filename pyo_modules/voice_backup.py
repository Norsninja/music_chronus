"""
Voice module for Music Chronus
Single voice with Sine -> ADSR -> Biquad chain
All frequency/amplitude parameters smoothed with Sig/SigTo
"""

from pyo import *

class Voice:
    """
    Single synthesizer voice with parameter smoothing
    Chain: Sine -> ADSR -> Biquad filter
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
        
        # Frequency control with Port for slide/portamento
        self.freq_raw = Sig(440.0)  # Target frequency
        # Port provides exponential smoothing - perfect for pitch slides
        # Using numeric times as per Senior Dev's correction
        self.freq_port = Port(self.freq_raw, risetime=0.001, falltime=0.001)  # Near-instant by default
        self.freq = self.freq_port  # This is what oscillator will use
        
        # Slide time control (0 = no slide, 0.001-0.5 = slide time)
        self.slide_time = 0.001  # Default to near-instant (no slide)
        
        # Amplitude control with smoothing
        self.amp_sig = Sig(0.3)  # Target amplitude (0-1)
        self.amp = SigTo(self.amp_sig, time=self.smooth_time)  # Smoothed amplitude
        
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
        
        # Oscillator setup with band-limited waveforms
        # Create anti-aliased wave tables
        self.saw_table = SawTable(order=12)  # 12th order for good anti-aliasing
        self.square_table = SquareTable(order=12)
        
        # Start with sawtooth (classic 303)
        self.current_waveform = 0  # 0=saw, 1=square
        
        # Use single Osc that can switch tables (simpler than Selector)
        # Start with saw table
        self.osc = Osc(table=self.saw_table, freq=self.freq, mul=self.adsr)
        
        # Store pre-filter signal for acid input (direct reference)
        # Note: This is the live oscillator output, not a copy
        self.prefilter_signal = self.osc  # Oscillator * ADSR, before filter
        
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
        self.freq_raw.value = freq
    
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
    
    def set_slide_time(self, time):
        """Set portamento/slide time (0.001-0.5 seconds)"""
        time = max(0.001, min(0.5, float(time)))
        self.slide_time = time
        # Update Port times directly with numeric values
        self.freq_port.risetime = time
        self.freq_port.falltime = time
    
    def set_waveform(self, waveform):
        """Set oscillator waveform (0=saw, 1=square)"""
        waveform = int(max(0, min(1, waveform)))
        self.current_waveform = waveform
        # Switch the table in the oscillator
        if waveform == 0:
            self.osc.table = self.saw_table
        else:
            self.osc.table = self.square_table
    
    def get_prefilter_signal(self):
        """Get pre-filter signal (oscillator * ADSR) for acid input"""
        return self.prefilter_signal
    
    def get_status(self):
        """Get current voice status"""
        return {
            'voice_id': self.voice_id,
            'freq': self.freq_raw.value,
            'amp': self.amp_sig.value,
            'filter_freq': self.filter_freq_sig.value,
            'filter_q': self.filter_q_sig.value,
            'reverb_send': self.reverb_send_sig.value,
            'delay_send': self.delay_send_sig.value,
            'slide_time': self.slide_time,
            'waveform': self.current_waveform,
            'adsr': {
                'attack': self.adsr.attack,
                'decay': self.adsr.decay,
                'sustain': self.adsr.sustain,
                'release': self.adsr.release
            }
        }